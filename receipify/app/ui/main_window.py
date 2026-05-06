from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.data.data_manager import DataManager
from app.services.validation_service import validate_receipt_input
from app.ui.receipt_card import ReceiptCard


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.user_id = 1
        self.data_manager = DataManager()
        self.receipt_cards = []

        self.setWindowTitle("Receipify")
        self.resize(980, 700)
        self.setMinimumSize(760, 520)
        self.build_ui()
        self.load_receipts()

    def build_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("appRoot")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(36, 30, 36, 30)
        main_layout.setSpacing(18)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        main_layout.addLayout(header_layout)

        heading = QLabel("My Receipts")
        heading.setObjectName("pageHeading")
        header_layout.addWidget(heading, stretch=1)

        add_button = QPushButton("Add Receipt")
        add_button.setObjectName("primaryButton")
        add_button.setMinimumHeight(42)
        add_button.clicked.connect(self.open_add_receipt_dialog)
        header_layout.addWidget(add_button)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("searchBar")
        self.search_bar.setPlaceholderText("Search by product or store...")
        self.search_bar.setMinimumHeight(44)
        self.search_bar.textChanged.connect(self.filter_receipts)
        main_layout.addWidget(self.search_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("receiptScrollArea")
        main_layout.addWidget(self.scroll_area, stretch=1)

        self.gallery_widget = QWidget()
        self.gallery_widget.setObjectName("galleryWidget")
        self.gallery_layout = QVBoxLayout(self.gallery_widget)
        self.gallery_layout.setContentsMargins(2, 2, 10, 2)
        self.gallery_layout.setSpacing(14)
        self.scroll_area.setWidget(self.gallery_widget)

        self.empty_label = QLabel("No receipts found.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setObjectName("emptyLabel")

        self.setStyleSheet(self.app_stylesheet())

    def app_stylesheet(self):
        return """
            QWidget#appRoot {
                background-color: #f3f4f6;
                color: #111827;
                font-family: Arial;
                font-size: 14px;
            }

            QLabel#pageHeading {
                color: #111827;
                font-size: 30px;
                font-weight: 700;
                letter-spacing: 0px;
            }

            QLineEdit#searchBar {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 14px;
                color: #111827;
                font-size: 15px;
                padding: 10px 16px;
            }

            QLineEdit#searchBar:focus {
                border: 1px solid #2563eb;
            }

            QLineEdit, QSpinBox, QDateEdit {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #111827;
                padding: 8px 10px;
            }

            QPushButton {
                background-color: #2563eb;
                border: none;
                border-radius: 10px;
                color: #ffffff;
                font-weight: 700;
                padding: 10px 16px;
            }

            QPushButton:hover {
                background-color: #1d4ed8;
            }

            QPushButton:pressed {
                background-color: #1e40af;
            }

            QPushButton#primaryButton {
                min-width: 124px;
            }

            QScrollArea#receiptScrollArea {
                background-color: transparent;
                border: none;
            }

            QWidget#galleryWidget {
                background-color: transparent;
            }

            QFrame#receiptCard {
                background-color: #ffffff;
                border: 1px solid #e1e5ec;
                border-radius: 14px;
            }

            QLabel#cardTitle {
                color: #111827;
                font-size: 20px;
                font-weight: 700;
                letter-spacing: 0px;
            }

            QLabel#cardSubtitle {
                color: #6b7280;
                font-size: 13px;
            }

            QLabel#cardPrice {
                color: #111827;
                font-size: 18px;
                font-weight: 700;
            }

            QLabel#detailLabel {
                color: #6b7280;
                font-size: 12px;
                font-weight: 700;
            }

            QLabel#detailValue {
                color: #1f2937;
                font-size: 14px;
            }

            QLabel#statusBadge {
                border-radius: 10px;
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                padding: 4px 10px;
            }

            QLabel#statusBadge[statusColor="green"] {
                background-color: #2e7d32;
            }

            QLabel#statusBadge[statusColor="orange"] {
                background-color: #ef6c00;
            }

            QLabel#statusBadge[statusColor="red"] {
                background-color: #c62828;
            }

            QLabel#statusBadge[statusColor="grey"] {
                background-color: #6b7280;
            }

            QLabel#emptyLabel {
                color: #6b7280;
                font-size: 16px;
                padding: 80px 20px;
            }
        """

    def load_receipts(self):
        receipts = self.data_manager.get_all_receipts(self.user_id)
        self.display_receipts(receipts)

    def filter_receipts(self, _text=None):
        query = self.search_bar.text().strip()

        if query:
            receipts = self.data_manager.search_receipts(self.user_id, query)
        else:
            receipts = self.data_manager.get_all_receipts(self.user_id)

        self.display_receipts(receipts)

    def display_receipts(self, receipts):
        self.clear_gallery()

        if not receipts:
            self.gallery_layout.addWidget(self.empty_label)
            self.gallery_layout.addStretch(1)
            return

        for receipt in receipts:
            card = ReceiptCard(receipt)
            self.gallery_layout.addWidget(card)
            self.receipt_cards.append(card)

        self.gallery_layout.addStretch(1)

    def clear_gallery(self):
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        self.receipt_cards = []

    def open_add_receipt_dialog(self):
        dialog = AddReceiptDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.cleaned_values
            self.data_manager.add_receipt(user_id=self.user_id, **values)
            self.search_bar.clear()
            self.load_receipts()


class AddReceiptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cleaned_values = {}
        self.setWindowTitle("Add Receipt")
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)
        layout.addLayout(form)

        self.product_name_input = QLineEdit()
        self.merchant_name_input = QLineEdit()
        self.category_name_input = QLineEdit()
        self.category_name_input.setText("Uncategorised")
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("0.00")

        self.purchase_date_input = QDateEdit()
        self.purchase_date_input.setCalendarPopup(True)
        self.purchase_date_input.setDisplayFormat("yyyy-MM-dd")
        self.purchase_date_input.setDate(QDate.currentDate())

        self.warranty_days_input = QSpinBox()
        self.warranty_days_input.setRange(0, 10000)
        self.return_days_input = QSpinBox()
        self.return_days_input.setRange(0, 10000)

        form.addRow("Product name", self.product_name_input)
        form.addRow("Merchant name", self.merchant_name_input)
        form.addRow("Category", self.category_name_input)
        form.addRow("Price in euros", self.price_input)
        form.addRow("Purchase date", self.purchase_date_input)
        form.addRow("Warranty days", self.warranty_days_input)
        form.addRow("Return days", self.return_days_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate_and_accept(self):
        is_valid, errors, cleaned_values = validate_receipt_input(
            product_name=self.product_name_input.text(),
            merchant_name=self.merchant_name_input.text(),
            category_name=self.category_name_input.text(),
            price=self.price_input.text(),
            purchase_date=self.purchase_date_input.date().toString("yyyy-MM-dd"),
            warranty_days=self.warranty_days_input.value(),
            return_days=self.return_days_input.value(),
            image_path=None,
        )

        if not is_valid:
            QMessageBox.warning(self, "Invalid receipt", "\n".join(errors))
            return

        self.cleaned_values = cleaned_values
        self.accept()
