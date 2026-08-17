from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.image_service import copy_receipt_image, resolve_image_path
from app.services.validation_service import validate_receipt_input
from app.ui.styles import app_stylesheet


class ElidedLabel(QLabel):
    """A label that shortens long text to fit instead of stretching its row.

    A plain QLabel asks for the width of its whole text, which pushed the image
    buttons off the edge of the dialog whenever a file name was long.
    """

    def __init__(self, elide_mode=Qt.TextElideMode.ElideRight, parent=None):
        super().__init__(parent)
        self.elide_mode = elide_mode
        self.full_text = ""
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
        self.setWindowTitle("Edit Receipt" if self.is_editing else "New Receipt")
        self.setMinimumWidth(760)
        self.build_ui()
        self.setStyleSheet(app_stylesheet())

    def build_ui(self):
        root = QWidget()
        root.setObjectName("dialogRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(18)

        title = QLabel("Edit Receipt" if self.is_editing else "New Receipt")
        title.setObjectName("dialogTitle")
        root_layout.addWidget(title)

        subtitle = QLabel(
            "Update purchase details to keep warranty and return periods accurate."
            if self.is_editing
            else "Enter purchase details to track warranty and return periods."
        )
        subtitle.setObjectName("dialogSubtitle")
        root_layout.addWidget(subtitle)

        form_container = QFrame()
        form_container.setObjectName("formContainer")
        form_layout = QHBoxLayout(form_container)
        form_layout.setContentsMargins(22, 22, 22, 22)
        form_layout.setSpacing(18)
        root_layout.addWidget(form_container)

        left_column = QVBoxLayout()
        left_column.setSpacing(14)
        right_column = QVBoxLayout()
        right_column.setSpacing(14)
        form_layout.addLayout(left_column, stretch=1)
        form_layout.addLayout(right_column, stretch=1)

        self.product_name_input = self.create_input("e.g. Wireless Mouse")
        self.merchant_name_input = self.create_input("e.g. Tech Store")
        self.category_name_input = self.create_input("e.g. Electronics")
        self.price_input = self.create_input("e.g. 24.99")
        self.purchase_date_input = self.create_input("YYYY-MM-DD")
        self.warranty_days_input = self.create_input("e.g. 365")
        self.return_days_input = self.create_input("e.g. 30")
        self.image_selector = self.create_image_selector()
        self.populate_receipt_values()
        self.update_image_display()

        left_column.addWidget(self.create_field("Product name", self.product_name_input))
        left_column.addWidget(self.create_field("Store / merchant", self.merchant_name_input))
        left_column.addWidget(self.create_field("Category", self.category_name_input))
        left_column.addStretch(1)

        right_column.addWidget(self.create_field("Price", self.price_input))
        right_column.addWidget(self.create_field("Purchase date", self.purchase_date_input))
        right_column.addWidget(self.create_field("Warranty days", self.warranty_days_input))
        right_column.addWidget(self.create_field("Return days", self.return_days_input))
        right_column.addStretch(1)

        # The image row spans the full width, which leaves room for a preview
        # and a readable file name instead of a cramped path box.
        root_layout.addWidget(self.create_field("Receipt image", self.image_selector))

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root_layout.addWidget(self.error_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        root_layout.addLayout(button_row)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)

        save_button = QPushButton("Save Changes" if self.is_editing else "Save Receipt")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.validate_and_accept)
        button_row.addWidget(save_button)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root)

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

    def create_field(self, label_text, input_widget):
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(input_widget)

        return field

    def create_input(self, placeholder):
        input_widget = QLineEdit()
        input_widget.setObjectName("formInput")
        input_widget.setPlaceholderText(placeholder)
        input_widget.setMinimumHeight(42)
        return input_widget

    def create_image_selector(self):
        selector = QFrame()
        selector.setObjectName("imageSelector")
        layout = QHBoxLayout(selector)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        self.image_preview = QLabel()
        self.image_preview.setObjectName("imagePreview")
        self.image_preview.setFixedSize(64, 48)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_preview)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        layout.addLayout(text_column, stretch=1)

        self.image_name_label = ElidedLabel()
        self.image_name_label.setObjectName("imageName")
        text_column.addWidget(self.image_name_label)

        self.image_hint_label = ElidedLabel(Qt.TextElideMode.ElideLeft)
        self.image_hint_label.setObjectName("imageHint")
        text_column.addWidget(self.image_hint_label)

        self.scan_image_button = QPushButton("Scan with OCR")
        self.scan_image_button.setObjectName("secondaryButton")
        self.scan_image_button.clicked.connect(self.scan_with_ocr)
        layout.addWidget(self.scan_image_button)

        self.choose_image_button = QPushButton("Choose file")
        self.choose_image_button.setObjectName("secondaryButton")
        self.choose_image_button.clicked.connect(self.choose_image)
        layout.addWidget(self.choose_image_button)

        self.remove_image_button = QPushButton("Remove")
        self.remove_image_button.setObjectName("dangerButton")
        self.remove_image_button.clicked.connect(self.remove_image)
        layout.addWidget(self.remove_image_button)
        return selector

    def scan_with_ocr(self):
        """Entry point for reading a receipt's details from a photo.

        The scanning itself is not built yet, so this explains the state of it
        rather than pretending to work.
        """
        QMessageBox.information(
            self,
            "Scan with OCR",
            "Reading receipt details from a photo is not available yet.\n\n"
            "Attach the receipt image with 'Choose file' and type the details "
            "in for now.",
        )

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
