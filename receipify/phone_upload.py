"""A temporary web page the phone uses to send one receipt photo over the local network.

The page lives at a secret random address, accepts a single photo, expires
after five minutes and is shut down when the scan dialog closes. It never
gives access to the database or to any other file.
"""

import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import SimpleQueue
from uuid import uuid4

from ocr import MAX_IMAGE_BYTES, ScanError, clean_photo

LIFETIME_SECONDS = 5 * 60
PAGE = (Path(__file__).parent / "phone_upload.html").read_bytes()
HEADERS = {
    "Cache-Control": "no-store",  # the phone's browser must not keep the page with its secret address
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                               "img-src blob:; connect-src 'self'; frame-ancestors 'none'",
}


class PhoneUpload:
    def __init__(self, address, folder, lifetime=LIFETIME_SECONDS):
        self.folder = Path(folder)
        self.token = secrets.token_urlsafe(32)  # the secret part of the address in the QR code
        self.deadline = time.monotonic() + lifetime
        self.received = SimpleQueue()  # the saved photo's path, collected by the scan dialog
        self.lock = threading.Lock()
        self.closed = False
        self.receiving = False
        self.uploaded = False
        self.server = UploadServer((address, 0), UploadHandler)  # port 0: any free port
        self.server.upload = self
        self.url = f"http://{address}:{self.server.server_port}/{self.token}"
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
        self.server.server_close()
        self.thread.join(timeout=1)


class UploadServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # a phone leaving mid-upload is normal, not worth a printed traceback


class UploadHandler(BaseHTTPRequestHandler):
    timeout = 8  # seconds a silent connection may stay open

    def log_message(self, *args):
        pass  # never print the secret address

    def reply(self, code, body, content_type="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in HEADERS.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def check_access(self):
        upload = self.server.upload
        # compare_digest takes the same time however much of the token is right.
        if not secrets.compare_digest(self.path, "/" + upload.token):
            self.reply(404, "Connection not found. Scan the QR code shown in Receipify.")
            return False
        if upload.closed or upload.expired:
            self.reply(410, "Connection expired. Generate a new QR code in Receipify.")
            return False
        return True

    def do_GET(self):
        if not self.check_access():
            return
        if self.server.upload.uploaded:
            self.reply(200, "Photo received. Continue on the computer; you can close this page.")
        else:
            self.reply(200, PAGE, "text/html; charset=utf-8")

    def do_POST(self):
        upload = self.server.upload
        if not self.check_access():
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_IMAGE_BYTES:
            self.reply(413, "Choose a photo smaller than 15 MB.")
            return

        # Only one photo per connection: refuse while another is arriving or after one arrived.
        with upload.lock:
            busy = upload.receiving or upload.uploaded or upload.closed
            if not busy:
                upload.receiving = True
        if busy:
            self.reply(409, "A photo is already being received or has arrived. Check Receipify.")
            return

        try:
            data = self.rfile.read(length)
            if len(data) < length:
                raise ScanError("Upload was incomplete. Please try again.")
            photo = clean_photo(data)
            with upload.lock:
                if upload.closed or upload.expired:
                    self.reply(410, "Connection expired. Generate a new QR code in Receipify.")
                    return
                path = upload.folder / f"phone-{uuid4().hex}.jpg"
                path.write_bytes(photo)
                upload.uploaded = True
            upload.received.put(str(path))  # before replying, so the photo arrives even if the phone disconnects
            self.reply(200, "Photo received. Review the detected details on the computer. You can close this page.")
        except ScanError as error:
            self.reply(422, str(error))
        except (OSError, ValueError):
            self.reply(400, "The photo could not be received. Please try again.")
        finally:
            with upload.lock:
                upload.receiving = False
