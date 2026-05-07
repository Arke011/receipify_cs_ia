from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.data.data_manager import DataManager
from app.ui.receipt_dialog import AddReceiptDialog
from app.ui.receipt_card import ReceiptCard
from app.ui.styles import app_stylesheet


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.user_id = 1
        self.data_manager = DataManager()
        self.receipt_cards = []

        self.setWindowTitle("Receipify")
        self.resize(1040, 760)
        self.setMinimumSize(820, 560)
        self.build_ui()
        self.load_receipts()

    def build_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("appRoot")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(44, 36, 44, 36)
        main_layout.setSpacing(20)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)
        main_layout.addLayout(header_layout)

        title_area = QVBoxLayout()
        title_area.setSpacing(4)
        header_layout.addLayout(title_area, stretch=1)

        heading = QLabel("My Receipts")
        heading.setObjectName("pageTitle")
        title_area.addWidget(heading)

        subtitle = QLabel("Track purchases, warranties, and return periods.")
        subtitle.setObjectName("pageSubtitle")
        title_area.addWidget(subtitle)

        add_button = QPushButton("+ Add Receipt")
        add_button.setObjectName("primaryButton")
        add_button.setMinimumHeight(46)
        add_button.clicked.connect(self.open_add_receipt_dialog)
        header_layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignTop)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("searchBar")
        self.search_bar.setPlaceholderText("Search by product or store...")
        self.search_bar.setMinimumHeight(48)
        self.search_bar.textChanged.connect(self.filter_receipts)
        main_layout.addWidget(self.search_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("receiptScrollArea")
        main_layout.addWidget(self.scroll_area, stretch=1)

        self.gallery_widget = QWidget()
        self.gallery_widget.setObjectName("galleryWidget")
        self.gallery_layout = QVBoxLayout(self.gallery_widget)
        self.gallery_layout.setContentsMargins(2, 4, 10, 4)
        self.gallery_layout.setSpacing(16)
        self.scroll_area.setWidget(self.gallery_widget)

        self.empty_label = QLabel(
            "No receipts yet. Add your first receipt to begin tracking warranties and returns."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setObjectName("emptyLabel")

        self.setStyleSheet(app_stylesheet())

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
