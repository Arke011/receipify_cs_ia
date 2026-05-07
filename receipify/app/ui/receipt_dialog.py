from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.validation_service import validate_receipt_input
from app.ui.styles import app_stylesheet


class AddReceiptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cleaned_values = {}
        self.setWindowTitle("New Receipt")
        self.setMinimumWidth(760)
        self.build_ui()
        self.setStyleSheet(app_stylesheet())

    def build_ui(self):
        root = QWidget()
        root.setObjectName("dialogRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(18)

        title = QLabel("New Receipt")
        title.setObjectName("dialogTitle")
        root_layout.addWidget(title)

        subtitle = QLabel("Enter purchase details to track warranty and return periods.")
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

        left_column.addWidget(self.create_field("Product name", self.product_name_input))
        left_column.addWidget(self.create_field("Store / merchant", self.merchant_name_input))
        left_column.addWidget(self.create_field("Category", self.category_name_input))
        left_column.addStretch(1)

        right_column.addWidget(self.create_field("Price", self.price_input))
        right_column.addWidget(self.create_field("Purchase date", self.purchase_date_input))
        right_column.addWidget(self.create_field("Warranty days", self.warranty_days_input))
        right_column.addWidget(self.create_field("Return days", self.return_days_input))
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

        save_button = QPushButton("Save Receipt")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.validate_and_accept)
        button_row.addWidget(save_button)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root)

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

    def validate_and_accept(self):
        is_valid, errors, cleaned_values = validate_receipt_input(
            product_name=self.product_name_input.text(),
            merchant_name=self.merchant_name_input.text(),
            category_name=self.category_name_input.text(),
            price=self.price_input.text(),
            purchase_date=self.purchase_date_input.text(),
            warranty_days=self.warranty_days_input.text(),
            return_days=self.return_days_input.text(),
            image_path=None,
        )

        if not is_valid:
            self.error_label.setText("\n".join(errors))
            self.error_label.show()
            return

        self.cleaned_values = cleaned_values
        self.accept()
