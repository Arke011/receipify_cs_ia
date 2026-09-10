"""Phone capture and local OCR, with review before returning to the receipt form."""

import io
import ipaddress
import time
from pathlib import Path
from queue import Empty
from uuid import uuid4
from threading import Event

import qrcode
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QAbstractSocket, QNetworkInterface
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout,
)

from app.services.mobile_capture_service import MobileCaptureSession
from app.services.ocr_service import MAX_IMAGE_BYTES, ScanError, normalize_upload, scan_image
from app.ui.formatting import format_currency


class ScanSignals(QObject):
    completed = pyqtSignal(object, object, str)


class ScanJob(QRunnable):
    def __init__(self, image_data):
        super().__init__()
        self.image_data = image_data
        self.cancelled = Event()
        self.signals = ScanSignals()

    def run(self):
        try:
            result, error = scan_image(self.image_data, self.cancelled), ""
        except Exception as exception:
            result, error = None, str(exception) or "The photo could not be scanned. Try another image."
        if not self.cancelled.is_set():
            self.signals.completed.emit(self, result, error)


def local_addresses():
    addresses = []
    for interface in QNetworkInterface.allInterfaces():
        flags = interface.flags()
        if not flags & QNetworkInterface.InterfaceFlag.IsUp or flags & QNetworkInterface.InterfaceFlag.IsLoopBack:
            continue
        for entry in interface.addressEntries():
            if entry.ip().protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
                continue
            address = entry.ip().toString()
            ip = ipaddress.ip_address(address)
            if ip.is_private and not ip.is_loopback and not ip.is_link_local:
                addresses.append((f"{interface.humanReadableName()} — {address}", address))
    return addresses


class ScanDialog(QDialog):
    def __init__(self, directory, image_path=None, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.image_path = image_path
        self.result_data = None
        self.values = {}
        self.session = None
        self.job = None
        self.setWindowTitle("Scan receipt")
        self.setMinimumWidth(440)
        self.resize(520, 400)
        layout = QVBoxLayout(self)
        sources = QHBoxLayout()
        self.phone_button = QPushButton("Use phone")
        self.phone_button.clicked.connect(self.start_phone)
        self.file_button = QPushButton("Choose image")
        self.file_button.clicked.connect(self.choose_image)
        self.attached_button = QPushButton("Scan attached image")
        self.attached_button.setEnabled(bool(image_path))
        self.attached_button.clicked.connect(lambda: self.start_ocr(self.image_path))
        for button in (self.phone_button, self.file_button, self.attached_button):
            button.setAutoDefault(False)
            sources.addWidget(button)
        layout.addLayout(sources)
        self.phone_group = QGroupBox("Capture with your phone")
        phone_layout = QVBoxLayout(self.phone_group)
        self.addresses = QComboBox()
        self.addresses.setAccessibleName("Computer network address")
        for label, address in local_addresses():
            self.addresses.addItem(label, address)
        self.addresses.currentIndexChanged.connect(self.start_phone)
        phone_layout.addWidget(self.addresses)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phone_layout.addWidget(self.qr_label)
        self.link_label = QLabel()
        self.link_label.setTextFormat(Qt.TextFormat.PlainText)
        self.link_label.setWordWrap(True)
        self.link_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        phone_layout.addWidget(self.link_label)
        help_label = QLabel("Scan this QR with your phone's camera. Use the same trusted Wi-Fi. "
                            "This local transfer is unencrypted. If it will not connect, check Windows Firewall "
                            "and avoid guest Wi-Fi, or choose an image instead.")
        help_label.setWordWrap(True)
        phone_layout.addWidget(help_label)
        self.expiry_label = QLabel()
        phone_layout.addWidget(self.expiry_label)
        layout.addWidget(self.phone_group)
        self.phone_group.hide()
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setAccessibleName("Reading receipt")
        self.progress.hide()
        layout.addWidget(self.progress)
        self.review_group = QGroupBox("Detected details")
        form = QFormLayout(self.review_group)
        self.merchant = QLabel()
        self.merchant.setTextFormat(Qt.TextFormat.PlainText)
        self.merchant.setWordWrap(True)
        self.purchase_date = QComboBox()
        self.purchase_date.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.purchase_date.setMinimumContentsLength(22)
        form.addRow("Store / merchant", self.merchant)
        form.addRow("Purchase date", self.purchase_date)
        self.purchase = QComboBox()
        self.purchase.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.purchase.setMinimumContentsLength(22)
        form.addRow("Product / price", self.purchase)
        self.raw_text = QPlainTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setMaximumHeight(130)
        self.raw_text.setAccessibleName("Recognized receipt text")
        form.addRow("Recognized text", self.raw_text)
        layout.addWidget(self.review_group)
        self.review_group.hide()
        note = QLabel("You can correct the details in the receipt form. Existing typed values are kept. "
                      "Category and warranty/return defaults are unchanged.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.use_button = self.buttons.addButton("Use photo and details", QDialogButtonBox.ButtonRole.AcceptRole)
        self.use_button.setDefault(True)
        self.use_button.setEnabled(False)
        self.buttons.accepted.connect(self.use_result)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.check_upload)

    def start(self):
        if self.image_path:
            self.start_ocr(self.image_path)
        else:
            self.start_phone()

    def stop_session(self):
        self.timer.stop()
        if self.session:
            self.session.stop()
            self.session = None

    def start_phone(self, _index=None):
        self.stop_session()
        self.cancel_job()
        self.review_group.hide()
        self.phone_group.show()
        self.qr_label.clear()
        self.link_label.clear()
        self.expiry_label.clear()
        self.use_button.setEnabled(False)
        if self.addresses.currentData() is None:
            self.status.setText("No local Wi-Fi/Ethernet address was found. Connect to a network, reopen Scan, or choose an image.")
            return
        try:
            self.session = MobileCaptureSession(self.addresses.currentData(), self.directory)
            self.destroyed.connect(self.session.stop)
            buffer = io.BytesIO()
            qr = qrcode.QRCode(box_size=4, border=4)
            qr.add_data(self.session.url)
            qr.make(fit=True)
            qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())
            self.qr_label.setPixmap(pixmap)
            self.link_label.setText(self.session.url)
            self.status.setText("Waiting for a photo…")
            self.timer.start()
        except OSError as error:
            self.stop_session()
            self.status.setText(f"Could not start phone capture: {error}. Choose an image instead.")
        self.adjustSize()

    def check_upload(self):
        if not self.session:
            return
        try:
            path = self.session.received.get_nowait()
        except Empty:
            if self.session.expired:
                self.stop_session()
                self.qr_label.clear()
                self.link_label.clear()
                self.status.setText("Connection expired. Press Use phone to generate a new QR code.")
                self.expiry_label.clear()
            else:
                seconds = max(0, int(self.session.deadline - time.monotonic()))
                self.expiry_label.setText(f"Connection expires in {seconds // 60}:{seconds % 60:02d}")
        else:
            self.start_ocr(path)

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose receipt image", "", "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.heic *.heif)")
        if path:
            self.start_ocr(self.as_stored_image(path))

    def as_stored_image(self, path):
        """Convert an iPhone HEIC to JPEG, so the saved receipt image also displays."""
        if Path(path).suffix.lower() not in (".heic", ".heif"):
            return path
        try:
            data = Path(path).read_bytes()
            converted = Path(self.directory) / f"chosen-{uuid4().hex}.jpg"
            converted.write_bytes(normalize_upload(data))
            return str(converted)
        except (OSError, ScanError) as error:
            self.status.setText(str(error))
            return path

    def cancel_job(self):
        if self.job:
            self.job.cancelled.set()
            self.job.signals.completed.disconnect(self.show_result)
            self.job = None
        self.progress.hide()

    def start_ocr(self, path):
        if not path:
            return
        self.stop_session()
        self.cancel_job()
        self.image_path = str(Path(path).resolve())
        self.result_data = None
        self.phone_group.hide()
        self.review_group.hide()
        self.use_button.setEnabled(False)
        self.attached_button.setEnabled(True)
        self.status.setText("Reading the photo on this computer…")
        self.progress.show()
        # Snapshot the bounded input before starting the worker, so cancelling
        # the form can delete its temporary photo even on Windows. All decoding
        # and OCR run in the worker, which never holds that file open.
        try:
            with open(self.image_path, "rb") as source:
                image_data = source.read(MAX_IMAGE_BYTES + 1)
            if len(image_data) > MAX_IMAGE_BYTES:
                raise ScanError("Choose a photo smaller than 15 MB.")
        except (OSError, ScanError) as error:
            self.progress.hide()
            self.status.setText(str(error))
            return
        self.job = ScanJob(image_data)
        self.destroyed.connect(self.job.cancelled.set)
        self.job.signals.completed.connect(self.show_result)
        QThreadPool.globalInstance().start(self.job)
        self.adjustSize()

    @pyqtSlot(object, object, str)
    def show_result(self, job, result, error):
        if job is not self.job:
            return
        self.job = None
        self.progress.hide()
        self.result_data = result
        self.use_button.setEnabled(True)
        self.use_button.setText("Use photo and details" if result else "Use photo only")
        if error:
            self.status.setText(error)
        else:
            self.merchant.setText(result.merchant or "Not detected")
            self.purchase_date.clear()
            self.purchase_date.addItem("Enter date manually", None)
            for candidate in result.dates:
                self.purchase_date.addItem(candidate, candidate)
            if result.purchase_date:
                self.purchase_date.setCurrentIndex(1)
            self.purchase.clear()
            self.purchase.addItem("Enter product and price manually", None)
            # One product whose printed price differs from the receipt total means
            # OCR split an amount. Offer the name against the total, which several
            # lines of the receipt agree on, before the doubtful line price.
            if len(result.items) == 1 and result.total_cents is not None and result.items[0][1] != result.total_cents:
                name = result.items[0][0]
                self.purchase.addItem(f"{name} — {format_currency(result.total_cents)} (receipt total)", (name, result.total_cents))
            for name, cents in result.items:
                self.purchase.addItem(f"{name} — {format_currency(cents)}", (name, cents))
            if result.total_cents is not None:
                self.purchase.addItem(f"Receipt total — {format_currency(result.total_cents)} (enter product name)", ("", result.total_cents))
            self.raw_text.setPlainText(result.text)
            self.review_group.show()
            self.status.setText("\n".join(result.notes) if result.text.strip() else "No text was detected. Try a clearer photo, or use this image and enter details manually.")
        self.adjustSize()

    def use_result(self):
        if not self.use_button.isEnabled() or not self.image_path:
            return
        self.values = {}
        if self.result_data:
            self.values = {"merchant_name": self.result_data.merchant,
                           "purchase_date": self.purchase_date.currentData() or ""}
            selected = self.purchase.currentData()
            if selected:
                name, cents = selected
                self.values.update(product_name=name, price=f"{cents / 100:.2f}")
        self.accept()

    def done(self, result):
        self.stop_session()
        self.cancel_job()
        super().done(result)
