"""The form for adding a new receipt or editing an existing one."""

from pathlib import Path
from tempfile import TemporaryDirectory

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontMetrics, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QVBoxLayout,
)

from images import copy_image
from receipt import validate_receipt
from scan_dialog import ScanDialog

# Field key (as used by validate_receipt and the scan dialog) -> label, example text.
FIELDS = {
    "product": ("Product name", "Wireless Mouse"),
    "merchant": ("Store / merchant", "Tech Store"),
    "category": ("Category", "Electronics"),
    "price": ("Price (EUR)", "24.99"),
    "purchase_date": ("Purchase date", "YYYY-MM-DD"),
    "warranty_days": ("Warranty days", "365"),
    "return_days": ("Return days", "30"),
}


class ElidedLabel(QLabel):
    """A label that shortens long text with '…' instead of widening the dialog."""

    def __init__(self, elide_mode=Qt.TextElideMode.ElideRight):
        super().__init__()
        self.elide_mode = elide_mode
        self.full_text = ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text):
        self.full_text = text
        self.fit_text()

    def fit_text(self):
        metrics = QFontMetrics(self.font())
        super().setText(metrics.elidedText(self.full_text, self.elide_mode, max(self.width(), 0)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_text()


def short_folder(path, keep=2):
    """The last folders of a path, e.g. '.../scans/2026', so a long path stays on one line."""
    folders = path.parts[:-1]
    if len(folders) <= keep:
        return str(path.parent)
    return str(Path("...", *folders[-keep:]))


class ReceiptDialog(QDialog):
    def __init__(self, receipt=None, warranty_days=0, return_days=0, parent=None):
        super().__init__(parent)
        self.receipt = receipt
        self.values = {}  # the validated receipt, ready to save, once the dialog is accepted
        self.image_path = receipt.image_path if receipt else None  # the image already saved with the receipt
        self.new_image = None  # an image chosen or scanned in this dialog; copied when saved
        self.scan_folder = None  # temporary folder for phone photos, deleted when the dialog closes
        self.setWindowTitle("Edit Receipt" if receipt else "New Receipt")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.fields = {}
        for key, (label, example) in FIELDS.items():
            self.fields[key] = QLineEdit()
            self.fields[key].setPlaceholderText(example)
            form.addRow(label, self.fields[key])
        layout.addLayout(form)
        layout.addWidget(self.build_image_row())

        if receipt:
            for key, value in (("product", receipt.product), ("merchant", receipt.merchant),
                               ("category", receipt.category), ("price", f"{receipt.price_cents / 100:.2f}"),
                               ("purchase_date", receipt.purchase_date), ("warranty_days", receipt.warranty_days),
                               ("return_days", receipt.return_days)):
                self.fields[key].setText(str(value))
        else:
            self.fields["warranty_days"].setText(str(warranty_days))
            self.fields["return_days"].setText(str(return_days))
        self.update_image()

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Save).setDefault(True)
        layout.addWidget(buttons)

    def build_image_row(self):
        self.image_row = QFrame()
        row = QHBoxLayout(self.image_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.preview = QLabel()
        self.preview.setFixedSize(64, 48)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.preview)
        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        self.image_name = ElidedLabel()
        self.image_folder = ElidedLabel(Qt.TextElideMode.ElideLeft)
        text_column.addWidget(self.image_name)
        text_column.addWidget(self.image_folder)
        row.addLayout(text_column, stretch=1)
        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan)
        self.choose_button = QPushButton("Choose file")
        self.choose_button.clicked.connect(self.choose_image)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_image)
        for button in (self.scan_button, self.choose_button, self.remove_button):
            button.setAutoDefault(False)  # so Enter always means Save
            row.addWidget(button)
        return self.image_row

    def scan(self):
        if self.scan_folder is None:
            self.scan_folder = TemporaryDirectory(prefix="receipify-capture-")
        dialog = ScanDialog(self.scan_folder.name, self.new_image or self.image_path, parent=self)
        QTimer.singleShot(0, dialog.start)  # start once the dialog is on screen
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Scanning the image that is already saved needs no new copy.
            is_saved_image = self.image_path and Path(dialog.image_path) == Path(self.image_path).resolve()
            self.new_image = None if is_saved_image else dialog.image_path
            self.update_image()
            # Scanned details only fill empty fields; anything typed is kept.
            for key, value in dialog.values.items():
                if value and not self.fields[key].text().strip():
                    self.fields[key].setText(value)
        dialog.deleteLater()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose receipt image", "",
                                              "Image files (*.bmp *.gif *.jpeg *.jpg *.png *.webp)")
        if path:
            self.new_image = path
            self.update_image()

    def remove_image(self):
        """Detach the image; the saved copy is deleted once the receipt is saved."""
        self.new_image = None
        self.image_path = None
        self.update_image()

    def update_image(self):
        path = self.new_image or self.image_path
        self.remove_button.setVisible(bool(path))
        if not path:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("None")
            self.image_name.setText("No image attached")
            self.image_folder.setText("PNG, JPG, BMP, GIF, or WEBP")
            self.image_row.setToolTip("")
            return
        path = Path(path)
        self.image_name.setText(path.name)
        self.image_folder.setText(short_folder(path))
        self.image_row.setToolTip(str(path))  # the full path is always one hover away
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("No\npreview")
        else:
            self.preview.setText("")
            self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation))

    def save(self):
        errors, values = validate_receipt(**{key: field.text() for key, field in self.fields.items()})
        if errors:
            self.show_error("\n".join(errors))
            return
        values["image_path"] = self.image_path
        if self.new_image:
            try:
                values["image_path"] = copy_image(self.new_image)
            except (OSError, ValueError) as error:
                self.show_error(f"Unable to attach image: {error}")
                return
        self.values = values
        self.accept()

    def show_error(self, message):
        self.error_label.setText(message)
        self.error_label.show()

    def done(self, result):
        for scan in self.findChildren(QDialog):
            scan.reject()  # stops a phone upload that is still waiting
        if self.scan_folder is not None:
            self.scan_folder.cleanup()  # deletes phone photos that were not saved
            self.scan_folder = None
        super().done(result)
