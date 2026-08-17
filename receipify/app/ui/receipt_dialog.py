from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.image_service import copy_receipt_image
from app.services.validation_service import validate_receipt_input
from app.ui.styles import app_stylesheet


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

        left_column.addWidget(self.create_field("Product name", self.product_name_input))
        left_column.addWidget(self.create_field("Store / merchant", self.merchant_name_input))
        left_column.addWidget(self.create_field("Category", self.category_name_input))
        left_column.addStretch(1)

        right_column.addWidget(self.create_field("Price", self.price_input))
        right_column.addWidget(self.create_field("Purchase date", self.purchase_date_input))
        right_column.addWidget(self.create_field("Warranty days", self.warranty_days_input))
        right_column.addWidget(self.create_field("Return days", self.return_days_input))
        right_column.addWidget(self.create_field("Receipt image", self.image_selector))
        right_column.addStretch(1)

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
        self.update_image_display()

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
        selector = QWidget()
        layout = QHBoxLayout(selector)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.image_path_input = self.create_input("No image selected")
        self.image_path_input.setReadOnly(True)
        layout.addWidget(self.image_path_input, stretch=1)

        browse_button = QPushButton("Browse")
        browse_button.setObjectName("secondaryButton")
        browse_button.clicked.connect(self.choose_image)
        layout.addWidget(browse_button)

        self.remove_image_button = QPushButton("Remove")
        self.remove_image_button.setObjectName("dangerButton")
        self.remove_image_button.clicked.connect(self.remove_image)
        self.remove_image_button.setEnabled(bool(self.image_path))
        layout.addWidget(self.remove_image_button)
        return selector

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
        self.remove_image_button.setEnabled(False)
        self.update_image_display()

    def update_image_display(self):
        displayed_path = self.selected_image_path or self.image_path
        self.image_path_input.setText(Path(displayed_path).name if displayed_path else "")
        self.remove_image_button.setEnabled(bool(displayed_path))

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
