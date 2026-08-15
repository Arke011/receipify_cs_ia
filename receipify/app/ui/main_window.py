from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.data.data_manager import DataManager
from app.ui.dashboard_page import DashboardPage
from app.ui.export_page import ExportPage
from app.ui.receipt_dialog import AddReceiptDialog
from app.ui.receipt_card import ReceiptCard
from app.ui.settings_page import SettingsPage
from app.ui.styles import app_stylesheet


class MainWindow(QMainWindow):
    logged_out = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, data_manager=None, user_id=1, username=None):
        super().__init__()
        self.user_id = user_id
        self.username = username
        self.data_manager = data_manager or DataManager()
        self.receipt_cards = []

        self.setWindowTitle(f"Receipify - {username}" if username else "Receipify")
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

        self.build_navigation(main_layout)

        self.page_stack = QStackedWidget()
        main_layout.addWidget(self.page_stack, stretch=1)

        self.dashboard_page = DashboardPage(self.data_manager, self.user_id)
        self.export_page = ExportPage(self.data_manager, self.user_id)
        self.settings_page = SettingsPage(
            self.data_manager,
            self.user_id,
            on_settings_saved=self.refresh_settings_dependent_views,
        )
        self.pages = {
            "Receipts": self.build_receipts_page(),
            "Dashboard": self.dashboard_page,
            "Export": self.export_page,
            "Settings": self.settings_page,
            "OCR Import": self.build_placeholder_page(
                "OCR Import",
                "OCR receipt importing is planned for a future update. No OCR processing is available yet.",
            ),
        }
        for page in self.pages.values():
            self.page_stack.addWidget(page)

        self.show_page("Receipts")
        self.setStyleSheet(app_stylesheet())

    def build_navigation(self, main_layout):
        navigation_layout = QHBoxLayout()
        navigation_layout.setSpacing(8)
        main_layout.addLayout(navigation_layout)

        brand = QLabel("Receipify")
        brand.setObjectName("appBrand")
        navigation_layout.addWidget(brand)
        navigation_layout.addStretch(1)

        self.navigation_buttons = {}
        for page_name in ("Receipts", "Dashboard", "Export", "Settings", "OCR Import"):
            button = QPushButton(page_name)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, name=page_name: self.show_page(name)
            )
            navigation_layout.addWidget(button)
            self.navigation_buttons[page_name] = button

        self.logout_button = QPushButton("Log out")
        self.logout_button.setObjectName("navButton")
        self.logout_button.clicked.connect(self.logged_out.emit)
        navigation_layout.addWidget(self.logout_button)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def build_receipts_page(self):
        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(0, 0, 0, 0)
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

        return page

    def build_placeholder_page(self, title_text, message):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel(title_text)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(message)
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addStretch(1)
        return page

    def show_page(self, page_name):
        self.page_stack.setCurrentWidget(self.pages[page_name])
        if page_name == "Dashboard":
            self.dashboard_page.refresh()
        elif page_name == "Settings":
            self.settings_page.load_settings()
        for name, button in self.navigation_buttons.items():
            button.setChecked(name == page_name)

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

        settings = self.data_manager.get_settings(self.user_id)
        for receipt in receipts:
            card = ReceiptCard(
                receipt,
                on_edit=self.open_edit_receipt_dialog,
                on_delete=self.confirm_delete_receipt,
                warranty_warning_threshold=settings["warranty_warning_threshold"],
                return_warning_threshold=settings["return_warning_threshold"],
            )
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
        settings = self.data_manager.get_settings(self.user_id)
        dialog = AddReceiptDialog(
            default_warranty_days=settings["default_warranty_days"],
            default_return_days=settings["default_return_days"],
            parent=self,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.cleaned_values
            self.data_manager.add_receipt(user_id=self.user_id, **values)
            self.search_bar.clear()
            self.load_receipts()

    def open_edit_receipt_dialog(self, receipt):
        dialog = AddReceiptDialog(receipt=receipt, parent=self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.data_manager.update_receipt(
                receipt_id=receipt.receipt_id,
                user_id=self.user_id,
                **dialog.cleaned_values,
            )
            self.filter_receipts()

    def confirm_delete_receipt(self, receipt):
        confirmation = QMessageBox.question(
            self,
            "Delete receipt",
            f"Delete '{receipt.product_name}'? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirmation == QMessageBox.StandardButton.Yes:
            self.data_manager.delete_receipt(receipt.receipt_id, user_id=self.user_id)
            self.filter_receipts()

    def refresh_settings_dependent_views(self):
        self.filter_receipts()
        self.dashboard_page.refresh()
