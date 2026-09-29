import http.client
import io
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PIL import Image
from PyQt6.QtWidgets import QDialog

import scan_dialog
from main_window import MainWindow
from phone_upload import PhoneUpload
from receipt_dialog import ReceiptDialog


@pytest.fixture
def upload(tmp_path):
    upload = PhoneUpload("127.0.0.1", tmp_path)
    yield upload
    upload.stop()


def photo():
    data = io.BytesIO()
    Image.new("RGB", (120, 240), "white").save(data, format="PNG")
    return data.getvalue()


def request(upload, method="GET", body=None, path=None):
    """Send one request as the phone's browser would; returns (status, body, headers)."""
    connection = http.client.HTTPConnection(*upload.server.server_address, timeout=3)
    connection.request(method, path or "/" + upload.token, body=body)
    response = connection.getresponse()
    result = response.status, response.read(), dict(response.getheaders())
    connection.close()
    return result


def test_the_phone_page_accepts_exactly_one_photo(upload):
    status, body, headers = request(upload)
    assert status == 200
    assert b'capture="environment"' in body  # opens the phone's camera
    assert headers["Cache-Control"] == "no-store"
    assert request(upload, "POST", photo())[0] == 200
    saved = Path(upload.received.get(timeout=2))
    with Image.open(saved) as image:
        assert image.format == "JPEG"
    assert request(upload, "POST", photo())[0] == 409
    assert b"Photo received" in request(upload)[1]
    assert list(upload.folder.iterdir()) == [saved]


def test_wrong_address_bad_photo_and_expiry_are_refused(upload):
    assert request(upload, path="/wrong-token")[0] == 404
    assert request(upload, path="/../../README.md")[0] == 404
    assert request(upload, "POST", b"not an image")[0] == 422
    upload.deadline = time.monotonic() - 1
    assert request(upload, "POST", photo())[0] == 410
    assert request(upload)[0] == 410
    assert not list(upload.folder.iterdir())


def test_simultaneous_uploads_save_one_photo(upload):
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(lambda _: request(upload, "POST", photo())[0], range(2)))
    assert statuses == [200, 409]
    assert len(list(upload.folder.iterdir())) == 1


def test_stopping_closes_the_server(upload):
    upload.stop()
    assert not upload.thread.is_alive()
    with pytest.raises(OSError):
        socket.create_connection(upload.server.server_address, timeout=0.2)


def test_scan_dialog_shows_a_qr_code_and_receives_the_photo(monkeypatch, tmp_path):
    monkeypatch.setattr(scan_dialog, "local_ip", lambda: "127.0.0.1")
    dialog = scan_dialog.ScanDialog(tmp_path)
    dialog.start_phone()
    upload = dialog.upload
    assert not dialog.qr_label.pixmap().isNull()
    started = []
    monkeypatch.setattr(dialog, "start_ocr", started.append)
    assert request(upload, "POST", photo())[0] == 200
    dialog.check_upload()
    assert Path(started[0]).exists()
    dialog.reject()
    assert upload.closed
    assert not dialog.timer.isActive()


def test_closing_the_main_window_stops_capture_and_deletes_temporary_photos(db, monkeypatch):
    monkeypatch.setattr(scan_dialog, "local_ip", lambda: "127.0.0.1")
    window = MainWindow(db, 1, "alice")
    form = ReceiptDialog(parent=window)
    form.scan_folder = TemporaryDirectory(prefix="receipify-test-")
    folder = Path(form.scan_folder.name)
    dialog = scan_dialog.ScanDialog(folder, parent=form)
    window.show()
    form.show()
    dialog.show()
    dialog.start_phone()
    upload = dialog.upload
    assert request(upload, "POST", photo())[0] == 200
    upload.received.get(timeout=2)
    window.close()
    assert upload.closed
    assert not folder.exists()
    assert dialog.result() == QDialog.DialogCode.Rejected
