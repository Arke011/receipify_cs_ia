from pathlib import Path
from tempfile import TemporaryDirectory

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontMetrics, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app.services.image_service import copy_receipt_image, resolve_image_path
from app.services.validation_service import validate_receipt_input
from app.ui.scan_dialog import ScanDialog


class ElidedLabel(QLabel):
    """A label that shortens long text to fit instead of stretching its row.

    A plain QLabel asks for the width of its whole text, which pushed the image
    buttons off the edge of the dialog whenever a file name was long.
    """

    def __init__(self, elide_mode=Qt.TextElideMode.ElideRight, parent=None):
        super().__init__(parent)
        self.elide_mode = elide_mode
        self.full_text = ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text):
        self.full_text = text
        self.refresh_elided_text()

    def refresh_elided_text(self):
        metrics = QFontMetrics(self.font())
        super().setText(
            metrics.elidedText(self.full_text, self.elide_mode, max(self.width(), 0))
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_elided_text()


class AddReceiptDialog(QDialog):
    def __init__(
        self,
        receipt=None,
        default_warranty_days=0,
        default_return_days=0,
        parent=None,
    ):
        super().__init__(parent)
        self.receipt = receipt
        self.cleaned_values = {}
        self.is_editing = receipt is not None
        self.image_path = receipt.image_path if receipt else None
        self.selected_image_path = None
        self.image_removed = False
        self.default_warranty_days = default_warranty_days
        self.default_return_days = default_return_days
        self.scan_directory = None
        self.setWindowTitle("Edit Receipt" if self.is_editing else "New Receipt")
        self.setMinimumWidth(480)
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        for attribute, label, placeholder in (
            ("product_name_input", "Product name", "Wireless Mouse"),
            ("merchant_name_input", "Store / merchant", "Tech Store"),
            ("category_name_input", "Category", "Electronics"),
            ("price_input", "Price (EUR)", "24.99"),
            ("purchase_date_input", "Purchase date", "YYYY-MM-DD"),
            ("warranty_days_input", "Warranty days", "365"),
            ("return_days_input", "Return days", "30"),
        ):
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            setattr(self, attribute, field)
            form.addRow(label, field)
        self.image_selector = self.create_image_selector()
        layout.addWidget(self.image_selector)
        self.populate_receipt_values()
        self.update_image_display()
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setDefault(True)
        layout.addWidget(self.buttons)

    def populate_receipt_values(self):
        if self.receipt is None:
            self.warranty_days_input.setText(str(self.default_warranty_days))
            self.return_days_input.setText(str(self.default_return_days))
            return

        self.product_name_input.setText(self.receipt.product_name)
        self.merchant_name_input.setText(self.receipt.merchant_name)
        self.category_name_input.setText(self.receipt.category_name)
        self.price_input.setText(f"{self.receipt.price_euros():.2f}")
        self.purchase_date_input.setText(self.receipt.purchase_date)
        self.warranty_days_input.setText(str(self.receipt.warranty_days))
        self.return_days_input.setText(str(self.receipt.return_days))

    def create_image_selector(self):
        selector = QFrame()
        layout = QHBoxLayout(selector)
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_preview = QLabel()
        self.image_preview.setFixedSize(64, 48)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_preview)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        layout.addLayout(text_column, stretch=1)

        self.image_name_label = ElidedLabel()
        text_column.addWidget(self.image_name_label)

        self.image_hint_label = ElidedLabel(Qt.TextElideMode.ElideLeft)
        text_column.addWidget(self.image_hint_label)

        self.scan_image_button = QPushButton("Scan")
        self.scan_image_button.clicked.connect(self.scan_with_ocr)
        layout.addWidget(self.scan_image_button)

        self.choose_image_button = QPushButton("Choose file")
        self.choose_image_button.clicked.connect(self.choose_image)
        layout.addWidget(self.choose_image_button)

        self.remove_image_button = QPushButton("Remove")
        self.remove_image_button.clicked.connect(self.remove_image)
        layout.addWidget(self.remove_image_button)
        for button in (self.scan_image_button, self.choose_image_button, self.remove_image_button):
            button.setAutoDefault(False)
        return selector

    def scan_with_ocr(self):
        if self.scan_directory is None:
            self.scan_directory = TemporaryDirectory(prefix="receipify-capture-")
        path = self.selected_image_path or (resolve_image_path(self.image_path) if self.image_path else None)
        dialog = ScanDialog(self.scan_directory.name, image_path=path, parent=self)
        QTimer.singleShot(0, dialog.start)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            existing = resolve_image_path(self.image_path).resolve() if self.image_path else None
            self.selected_image_path = dialog.image_path if Path(dialog.image_path) != existing else None
            self.image_removed = False
            self.update_image_display()
            for name, value in dialog.values.items():
                field = getattr(self, name + "_input")
                if value and not field.text().strip():
                    field.setText(value)
        dialog.deleteLater()

    def done(self, result):
        for scan in self.findChildren(QDialog):
            scan.reject()
        if self.scan_directory is not None:
            self.scan_directory.cleanup()
            self.scan_directory = None
        super().done(result)

    def choose_image(self):
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose receipt image",
            "",
            "Image files (*.bmp *.gif *.jpeg *.jpg *.png *.webp)",
        )

        if selected_path:
            self.selected_image_path = selected_path
            self.image_removed = False
            self.update_image_display()

    def remove_image(self):
        """Mark the current attachment for removal when this edit is saved."""
        self.selected_image_path = None
        self.image_path = None
        self.image_removed = True
        self.update_image_display()

    def update_image_display(self):
        displayed_path = self.selected_image_path or self.image_path
        self.remove_image_button.setVisible(bool(displayed_path))

        if not displayed_path:
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText("None")
            self.image_name_label.setText("No image attached")
            self.image_hint_label.setText("PNG, JPG, BMP, GIF, or WEBP")
            self.image_selector.setToolTip("")
            return

        # A stored path is relative to the application, a freshly chosen one is
        # the file the user picked, so only the stored kind needs resolving.
        full_path = (
            Path(self.selected_image_path)
            if self.selected_image_path
            else resolve_image_path(self.image_path)
        )
        self.image_name_label.setText(full_path.name)
        self.image_hint_label.setText(self.shorten_path(full_path))
        # The full path is always one hover away, however long it is.
        self.image_selector.setToolTip(str(full_path))
        self.set_preview_pixmap(full_path)

    def set_preview_pixmap(self, image_path):
        pixmap = QPixmap(str(image_path)) if image_path.is_file() else QPixmap()

        if pixmap.isNull():
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText("No\npreview")
            return

        self.image_preview.setText("")
        self.image_preview.setPixmap(
            pixmap.scaled(
                self.image_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    @staticmethod
    def shorten_path(image_path, keep_parts=2):
        """Show the last folders of a path, so a long one stays one readable line."""
        parts = image_path.parts[:-1]
        if len(parts) <= keep_parts:
            return str(image_path.parent)

        return str(Path("...", *parts[-keep_parts:]))

    def validate_and_accept(self):
        is_valid, errors, cleaned_values = validate_receipt_input(
            product_name=self.product_name_input.text(),
            merchant_name=self.merchant_name_input.text(),
            category_name=self.category_name_input.text(),
            price=self.price_input.text(),
            purchase_date=self.purchase_date_input.text(),
            warranty_days=self.warranty_days_input.text(),
            return_days=self.return_days_input.text(),
            image_path=self.image_path,
        )

        if not is_valid:
            self.error_label.setText("\n".join(errors))
            self.error_label.show()
            return

        if self.selected_image_path:
            try:
                cleaned_values["image_path"] = copy_receipt_image(
                    self.selected_image_path
                )
            except (FileNotFoundError, OSError, ValueError) as error:
                self.error_label.setText(f"Unable to attach image: {error}")
                self.error_label.show()
                return

        self.cleaned_values = cleaned_values
        self.accept()
