"""The Scan dialog: get a photo (from the phone or a file), read it with OCR, and let the user pick the details."""

import io
import ipaddress
import time
from pathlib import Path
from queue import Empty
from threading import Event
from uuid import uuid4

import qrcode
from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QAbstractSocket, QNetworkInterface
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout,
)

from ocr import MAX_IMAGE_BYTES, ScanError, clean_photo, scan_image
from phone_upload import PhoneUpload
from receipt import format_euros


class ScanSignals(QObject):
    finished = pyqtSignal(object, object, str)  # job, ScanResult (or None), error message


class ScanJob(QRunnable):
    """Runs OCR on a background thread, so the dialog stays responsive while Tesseract works."""

    def __init__(self, image_data):
        super().__init__()
        self.image_data = image_data
        self.cancelled = Event()
        self.signals = ScanSignals()

    def run(self):
        try:
            result, error = scan_image(self.image_data, self.cancelled), ""
        except Exception as exception:  # any failure is reported in the dialog, never raised on the worker thread
            result, error = None, str(exception) or "The photo could not be scanned. Try another image."
        if not self.cancelled.is_set():
            self.signals.finished.emit(self, result, error)


def local_ip():
    """This computer's private IPv4 address on Wi-Fi or Ethernet, or None if it is not on a network."""
    for interface in QNetworkInterface.allInterfaces():
        flags = interface.flags()
        if not flags & QNetworkInterface.InterfaceFlag.IsUp or flags & QNetworkInterface.InterfaceFlag.IsLoopBack:
            continue
        for entry in interface.addressEntries():
            if entry.ip().protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
                continue
            address = ipaddress.ip_address(entry.ip().toString())
            if address.is_private and not address.is_loopback and not address.is_link_local:
                return str(address)
    return None


def qr_pixmap(text):
    buffer = io.BytesIO()
    qr = qrcode.QRCode(box_size=4, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue())
    return pixmap


def combo_box():
    combo = QComboBox()
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(22)
    return combo


class ScanDialog(QDialog):
    def __init__(self, folder, image_path=None, parent=None):
        super().__init__(parent)
        self.folder = folder  # temporary folder for phone photos, owned by the receipt form
        self.image_path = image_path
        self.scan_result = None
        self.values = {}  # the chosen details, read by the receipt form after "Use photo and details"
        self.upload = None
        self.job = None
        self.setWindowTitle("Scan receipt")
        self.setMinimumWidth(440)
        self.resize(520, 400)
        layout = QVBoxLayout(self)

        sources = QHBoxLayout()
        self.regenerate_button = QPushButton("Regenerate QR code")
        self.regenerate_button.clicked.connect(self.start_phone)
        self.file_button = QPushButton("Choose image")
        self.file_button.clicked.connect(self.choose_image)
        self.attached_button = QPushButton("Scan attached image")
        self.attached_button.setEnabled(bool(image_path))
        self.attached_button.clicked.connect(lambda: self.start_ocr(self.image_path))
        for button in (self.regenerate_button, self.file_button, self.attached_button):
            button.setAutoDefault(False)
            sources.addWidget(button)
        layout.addLayout(sources)

        self.phone_group = QGroupBox()
        phone_layout = QVBoxLayout(self.phone_group)
        help_label = QLabel("Please scan this QR code. Make sure to use the same trusted Wi-Fi on both "
                            "of your devices. The local transfer is unencrypted.")
        help_label.setWordWrap(True)
        phone_layout.addWidget(help_label)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setContentsMargins(0, 8, 0, 8)
        phone_layout.addWidget(self.qr_label)
        self.expiry_label = QLabel()
        self.expiry_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phone_layout.addWidget(self.expiry_label)
        self.phone_group.hide()
        layout.addWidget(self.phone_group)

        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # a busy indicator: OCR gives no percentage
        self.progress.setAccessibleName("Reading receipt")
        self.progress.hide()
        layout.addWidget(self.progress)

        self.review_group = QGroupBox("Detected details")
        form = QFormLayout(self.review_group)
        self.merchant = QLabel()
        self.merchant.setTextFormat(Qt.TextFormat.PlainText)
        self.merchant.setWordWrap(True)
        self.purchase_date = combo_box()
        self.purchase = combo_box()
        self.raw_text = QPlainTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setMaximumHeight(130)
        self.raw_text.setAccessibleName("Recognized receipt text")
        form.addRow("Store / merchant", self.merchant)
        form.addRow("Purchase date", self.purchase_date)
        form.addRow("Product / price", self.purchase)
        form.addRow("Recognized text", self.raw_text)
        self.review_group.hide()
        layout.addWidget(self.review_group)
        note = QLabel("You can correct the details after scanning")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.use_button = self.buttons.addButton("Use photo and details", QDialogButtonBox.ButtonRole.AcceptRole)
        self.use_button.setDefault(True)
        self.use_button.setEnabled(False)
        self.buttons.accepted.connect(self.use_result)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        # Checks five times a second whether the phone has sent a photo.
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.check_upload)

    def start(self):
        if self.image_path:
            self.start_ocr(self.image_path)
        else:
            self.start_phone()

    # ---- phone photo

    def start_phone(self):
        self.stop_upload()
        self.cancel_job()
        self.review_group.hide()
        self.phone_group.show()
        self.qr_label.clear()
        self.expiry_label.clear()
        self.use_button.setEnabled(False)
        address = local_ip()
        if address is None:
            self.status.setText("No local Wi-Fi/Ethernet address was found. Connect to a network, reopen Scan, "
                                "or choose an image.")
            return
        try:
            self.upload = PhoneUpload(address, self.folder)
        except OSError as error:
            self.status.setText(f"Could not start phone capture: {error}. Choose an image instead.")
        else:
            self.qr_label.setPixmap(qr_pixmap(self.upload.url))
            self.status.setText("Waiting for a photo…")
            self.timer.start()
        self.adjustSize()

    def check_upload(self):
        try:
            path = self.upload.received.get_nowait()
        except Empty:
            if self.upload.expired:
                self.stop_upload()
                self.qr_label.clear()
                self.expiry_label.clear()
                self.status.setText("Connection expired. Press Regenerate QR code to get a new one.")
            else:
                seconds = max(0, int(self.upload.deadline - time.monotonic()))
                self.expiry_label.setText(f"Connection expires in {seconds // 60}:{seconds % 60:02d}")
        else:
            self.start_ocr(path)

    def stop_upload(self):
        self.timer.stop()
        if self.upload:
            self.upload.stop()
            self.upload = None

    # ---- photo from a file

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose receipt image", "",
                                              "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif *.heic *.heif)")
        if path:
            self.start_ocr(self.heic_to_jpeg(path))

    def heic_to_jpeg(self, path):
        """Convert an iPhone HEIC photo to JPEG, so the saved receipt image can be displayed."""
        if Path(path).suffix.lower() not in (".heic", ".heif"):
            return path
        try:
            converted = Path(self.folder) / f"chosen-{uuid4().hex}.jpg"
            converted.write_bytes(clean_photo(Path(path).read_bytes()))
            return str(converted)
        except (OSError, ScanError) as error:
            self.status.setText(str(error))
            return path

    # ---- OCR

    def start_ocr(self, path):
        if not path:
            return
        self.stop_upload()
        self.cancel_job()
        self.image_path = str(Path(path).resolve())
        self.scan_result = None
        self.phone_group.hide()
        self.review_group.hide()
        self.use_button.setEnabled(False)
        self.attached_button.setEnabled(True)
        self.status.setText("Reading the photo on this computer…")
        self.progress.show()
        # The photo is read into memory here, so the worker never holds the file
        # open and cancelling can delete a temporary photo even on Windows.
        try:
            with open(self.image_path, "rb") as file:
                image_data = file.read(MAX_IMAGE_BYTES + 1)
            if len(image_data) > MAX_IMAGE_BYTES:
                raise ScanError("Choose a photo smaller than 15 MB.")
        except (OSError, ScanError) as error:
            self.progress.hide()
            self.status.setText(str(error))
            return
        self.job = ScanJob(image_data)
        self.job.signals.finished.connect(self.show_result)
        QThreadPool.globalInstance().start(self.job)
        self.adjustSize()

    def cancel_job(self):
        if self.job:
            self.job.cancelled.set()
            self.job.signals.finished.disconnect(self.show_result)
            self.job = None
        self.progress.hide()

    @pyqtSlot(object, object, str)
    def show_result(self, job, result, error):
        if job is not self.job:
            return  # a result from a scan that has since been replaced
        self.job = None
        self.progress.hide()
        self.scan_result = result
        self.use_button.setEnabled(True)
        self.use_button.setText("Use photo and details" if result else "Use photo only")
        if error:
            self.status.setText(error)
            self.adjustSize()
            return

        self.merchant.setText(result.merchant or "Not detected")
        self.purchase_date.clear()
        self.purchase_date.addItem("Enter date manually", None)
        for candidate in result.dates:
            self.purchase_date.addItem(candidate, candidate)
        if result.purchase_date:
            self.purchase_date.setCurrentIndex(1)

        # Nothing is pre-selected: the user must choose a product/price or the total.
        self.purchase.clear()
        self.purchase.addItem("Enter product and price manually", None)
        total = result.total_cents
        # One product whose price differs from the receipt total usually means OCR
        # split an amount, so the total (which several lines agree on) is offered first.
        if len(result.items) == 1 and total is not None and result.items[0][1] != total:
            name = result.items[0][0]
            self.purchase.addItem(f"{name} — {format_euros(total)} (receipt total)", (name, total))
        for name, cents in result.items:
            self.purchase.addItem(f"{name} — {format_euros(cents)}", (name, cents))
        if total is not None:
            self.purchase.addItem(f"Receipt total — {format_euros(total)} (enter product name)", ("", total))

        self.raw_text.setPlainText(result.text)
        self.review_group.show()
        if result.text.strip():
            self.status.setText("\n".join(result.notes))
        else:
            self.status.setText("No text was detected. Try a clearer photo, or use this image and enter details manually.")
        self.adjustSize()

    def use_result(self):
        if not self.use_button.isEnabled() or not self.image_path:
            return
        self.values = {}
        if self.scan_result:
            self.values = {"merchant": self.scan_result.merchant, "purchase_date": self.purchase_date.currentData() or ""}
            if self.purchase.currentData():
                name, cents = self.purchase.currentData()
                self.values.update(product=name, price=f"{cents / 100:.2f}")
        self.accept()

    def done(self, result):
        self.stop_upload()
        self.cancel_job()
        super().done(result)
