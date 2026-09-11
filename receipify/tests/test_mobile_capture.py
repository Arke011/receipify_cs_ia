import http.client
import io
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty

import pytest
from PIL import Image
from PyQt6.QtWidgets import QDialog, QLabel

from app.services.mobile_capture_service import MobileCaptureSession
from app.ui import scan_dialog
from app.ui.receipt_dialog import AddReceiptDialog
from app.ui.main_window import MainWindow
from app.data.data_manager import DataManager


@pytest.fixture
def session(tmp_path):
    session = MobileCaptureSession("127.0.0.1", tmp_path)
    yield session
    session.stop()


def photo():
    data = io.BytesIO()
    Image.new("RGB", (120, 240), "white").save(data, format="PNG")
    return data.getvalue()


def request(session, method="GET", body=None, path=None, headers=None):
    connection = http.client.HTTPConnection(session.authority, timeout=3)
    connection.request(method, path or "/" + session.token, body=body, headers=headers or {})
    response = connection.getresponse()
    result = response.status, response.read(), dict(response.getheaders())
    connection.close()
    return result


def upload(session, data=None, **kwargs):
    return request(session, "POST", photo() if data is None else data,
                   headers={"Content-Type": "application/octet-stream"}, **kwargs)


def test_pairing_page_then_one_upload_only(session):
    status, body, headers = request(session)
    assert status == 200
    assert b'capture="environment"' in body
    assert headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert upload(session)[0] == 200
    path = Path(session.received.get(timeout=2))
    assert path.parent == session.directory
    with Image.open(path) as image:
        assert image.format == "JPEG"
        assert image.size == (120, 240)
    assert upload(session)[0] == 409
    assert b"Photo received" in request(session)[1]
    assert len(list(session.directory.iterdir())) == 1


def test_wrong_token_wrong_host_and_other_origin_are_rejected(session):
    assert request(session, path="/wrong-token")[0] == 404
    assert request(session, path="/../../README.md")[0] == 404
    assert request(session, headers={"Host": "evil.example"})[0] == 404
    assert request(session, "POST", photo(), headers={"Origin": "https://evil.example", "Content-Type": "application/octet-stream"})[0] == 403
    assert not list(session.directory.iterdir())


def test_invalid_file_can_be_retried_and_oversize_is_rejected(session):
    assert upload(session, b"not an image")[0] == 422
    assert request(session, "POST", b"", headers={"Content-Length": "999999999", "Content-Type": "application/octet-stream"})[0] == 413
    assert request(session, "POST", photo(), headers={"Content-Type": "text/plain"})[0] == 415
    assert not list(session.directory.iterdir())
    assert upload(session)[0] == 200


def test_expired_connection_and_other_sessions_do_not_accept_upload(session, tmp_path):
    other = MobileCaptureSession("127.0.0.1", tmp_path)
    try:
        assert request(other, path="/" + session.token)[0] == 404
        session.deadline = time.monotonic() - 1
        assert upload(session)[0] == 410
        assert request(session)[0] == 410
    finally:
        other.stop()
    assert not list(tmp_path.iterdir())


def test_concurrent_uploads_save_only_one_image(session):
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: upload(session)[0], range(2)))
    assert sorted(statuses) == [200, 409]
    assert len(list(session.directory.iterdir())) == 1


def test_stop_closes_listener_and_incomplete_upload(session):
    connection = socket.create_connection(session.server.server_address)
    connection.sendall((f"POST /{session.token} HTTP/1.1\r\nHost: {session.authority}\r\nContent-Type: application/octet-stream\r\nContent-Length: 100\r\n\r\npartial").encode())
    time.sleep(0.05)
    session.stop()
    assert not session.thread.is_alive()
    with pytest.raises(OSError):
        socket.create_connection(session.server.server_address, timeout=0.2)
    connection.close()
    with pytest.raises(Empty):
        session.received.get_nowait()
    assert not list(session.directory.iterdir())


def test_qr_dialog_receives_photo_and_closes_server(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(scan_dialog, "local_addresses", lambda: [("Test network", "127.0.0.1")])
    dialog = scan_dialog.ScanDialog(tmp_path)
    dialog.show()
    dialog.start_phone()
    session = dialog.session
    assert not dialog.qr_label.pixmap().isNull()
    assert all("127.0.0.1" not in label.text() for label in dialog.findChildren(QLabel))
    received = []
    monkeypatch.setattr(dialog, "start_ocr", received.append)
    assert upload(session)[0] == 200
    dialog.check_upload()
    assert len(received) == 1
    assert Path(received[0]).exists()
    dialog.reject()
    assert session.closed
    assert not dialog.timer.isActive()


def test_closing_main_window_cancels_capture_and_removes_temp(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(scan_dialog, "local_addresses", lambda: [("Test network", "127.0.0.1")])
    window = MainWindow(DataManager(tmp_path / "test.db"))
    parent = AddReceiptDialog(parent=window)
    from tempfile import TemporaryDirectory
    parent.scan_directory = TemporaryDirectory(prefix="receipify-capture-test-")
    directory = Path(parent.scan_directory.name)
    dialog = scan_dialog.ScanDialog(directory, parent=parent)
    window.show()
    parent.show()
    dialog.show()
    dialog.start_phone()
    session = dialog.session
    assert upload(session)[0] == 200
    session.received.get(timeout=2)
    window.close()
    assert session.closed
    assert not directory.exists()
    assert dialog.result() == QDialog.DialogCode.Rejected
