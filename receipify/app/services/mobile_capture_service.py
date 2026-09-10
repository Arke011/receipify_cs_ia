"""A temporary, token-scoped upload endpoint for a trusted local network.

No file browsing, database access, remote execution, or public hosting. The
listener is bound to the chosen interface and lives only for the scan dialog.
"""

import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import SimpleQueue
from uuid import uuid4

from app.services.ocr_service import MAX_IMAGE_BYTES, ScanError, normalize_upload

SESSION_SECONDS = 5 * 60


class CaptureServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, address, handler):
        self.slots = threading.BoundedSemaphore(4)
        self.connections = set()
        self.connection_lock = threading.Lock()
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        request.settimeout(8)
        with self.connection_lock:
            self.connections.add(request)
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.connection_lock:
                self.connections.discard(request)
            self.slots.release()

    def close_connections(self):
        with self.connection_lock:
            for connection in self.connections:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def handle_error(self, request, client_address):
        # Disconnections are expected when a phone leaves or a scan is cancelled.
        pass


class MobileCaptureSession:
    def __init__(self, address, directory, lifetime=SESSION_SECONDS):
        self.directory = Path(directory)
        self.token = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(18)
        self.deadline = time.monotonic() + lifetime
        self.received = SimpleQueue()
        self.lock = threading.Lock()
        self.closed = False
        self.uploaded = False
        self.receiving = False
        self.page = Path(__file__).with_name("mobile_capture.html").read_text(encoding="utf-8").replace("__NONCE__", self.nonce).encode()
        self.server = CaptureServer((address, 0), self.handler_class())
        self.authority = f"{address}:{self.server.server_port}"
        self.url = f"http://{self.authority}/{self.token}"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        self.thread.start()

    @property
    def expired(self):
        return time.monotonic() >= self.deadline

    def stop(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
        self.server.shutdown()
        self.server.close_connections()
        self.server.server_close()
        self.thread.join(timeout=1)

    def handler_class(self):
        session = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Do not log pairing tokens or receipt details.

            def reply(self, code, text, content_type="text/plain; charset=utf-8"):
                body = text.encode() if isinstance(text, str) else text
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", f"default-src 'none'; script-src 'nonce-{session.nonce}'; style-src 'nonce-{session.nonce}'; img-src blob:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

            def authorized(self):
                if self.headers.get("Host") != session.authority or not secrets.compare_digest(self.path, "/" + session.token):
                    self.reply(404, "Connection not found. Scan the QR code shown in Receipify.")
                    return False
                if self.headers.get("Origin") not in (None, "http://" + session.authority):
                    self.reply(403, "This upload must come from the paired receipt page.")
                    return False
                if session.closed or session.expired:
                    self.reply(410, "Connection expired. Generate a new QR code in Receipify.")
                    return False
                return True

            def do_GET(self):
                if self.authorized():
                    if session.uploaded:
                        self.reply(200, "Photo received. Continue on the computer; you can close this page.")
                    else:
                        self.reply(200, session.page, "text/html; charset=utf-8")

            def do_POST(self):
                if not self.authorized():
                    return
                try:
                    lengths = self.headers.get_all("Content-Length", [])
                    length = int(lengths[0]) if len(lengths) == 1 else 0
                except ValueError:
                    length = 0
                if self.headers.get("Transfer-Encoding") or not 0 < length <= MAX_IMAGE_BYTES:
                    self.reply(413, "Choose a photo smaller than 15 MB.")
                    return
                if self.headers.get("Content-Type") != "application/octet-stream":
                    self.reply(415, "Choose a photo using this page's photo controls.")
                    return
                with session.lock:
                    unavailable = session.uploaded or session.receiving or session.closed
                    if not unavailable:
                        session.receiving = True
                if unavailable:
                    self.reply(409, "A photo is already being received or has arrived. Check Receipify.")
                    return
                try:
                    data = self.rfile.read(length)
                    if len(data) != length:
                        raise ScanError("Upload was incomplete. Please try again.")
                    normalized = normalize_upload(data)
                    with session.lock:
                        if session.closed or session.expired:
                            self.reply(410, "Connection expired. Generate a new QR code in Receipify.")
                            return
                        destination = session.directory / f"phone-{uuid4().hex}.jpg"
                        destination.write_bytes(normalized)
                        session.uploaded = True
                    try:
                        self.reply(200, "Photo received. Review the detected details on the computer. You can close this page.")
                    finally:
                        session.received.put(str(destination))
                except ScanError as error:
                    self.reply(422, str(error))
                except (OSError, ValueError):
                    self.reply(400, "The photo could not be received. Please try again.")
                finally:
                    with session.lock:
                        session.receiving = False

        return Handler
