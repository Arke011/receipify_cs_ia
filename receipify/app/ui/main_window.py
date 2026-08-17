from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
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
from app.services.image_service import remove_managed_receipt_image
from app.services.receipt_browsing_service import (
    ALL_OPTION,
    SORT_OPTIONS,
    STATUS_OPTIONS,
    browse_receipts,
)
from app.ui.dashboard_page import DashboardPage
from app.ui.export_page import ExportPage
from app.ui.receipt_dialog import AddReceiptDialog
from app.ui.receipt_card import ReceiptCard
from app.ui.settings_page import SettingsPage
from app.ui.styles import app_stylesheet
from app.ui.receipt_image_viewer import ReceiptImageViewer


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

        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(8)
        main_layout.addLayout(filters_layout)

        self.merchant_filter = self.create_filter_combo("Merchant")
        self.category_filter = self.create_filter_combo("Category")
        self.warranty_filter = self.create_filter_combo("Warranty")
        self.return_filter = self.create_filter_combo("Return")
        self.sort_filter = self.create_filter_combo("Sort")
        self.warranty_filter.addItems(STATUS_OPTIONS[1:])
        self.return_filter.addItems(STATUS_OPTIONS[1:])
        self.sort_filter.clear()
        self.sort_filter.addItems(SORT_OPTIONS)
        for filter_widget in (
            self.merchant_filter,
            self.category_filter,
            self.warranty_filter,
            self.return_filter,
            self.sort_filter,
        ):
            filter_widget.currentTextChanged.connect(self.filter_receipts)
            filters_layout.addWidget(filter_widget)

        self.purchase_date_from = QLineEdit()
        self.purchase_date_from.setObjectName("formInput")
        self.purchase_date_from.setPlaceholderText("From YYYY-MM-DD")
        self.purchase_date_from.setMinimumHeight(38)
        self.purchase_date_from.textChanged.connect(self.filter_receipts)
        filters_layout.addWidget(self.purchase_date_from)

        self.purchase_date_to = QLineEdit()
        self.purchase_date_to.setObjectName("formInput")
        self.purchase_date_to.setPlaceholderText("To YYYY-MM-DD")
        self.purchase_date_to.setMinimumHeight(38)
        self.purchase_date_to.textChanged.connect(self.filter_receipts)
        filters_layout.addWidget(self.purchase_date_to)

        self.clear_filters_button = QPushButton("Clear filters")
        self.clear_filters_button.setObjectName("secondaryButton")
        self.clear_filters_button.clicked.connect(self.clear_all_filters)
        filters_layout.addWidget(self.clear_filters_button)

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

    def create_filter_combo(self, accessible_name):
        combo = QComboBox()
        combo.setObjectName("filterCombo")
        combo.setAccessibleName(accessible_name)
        combo.setMinimumHeight(38)
        combo.addItem(ALL_OPTION)
        return combo

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
        self.refresh_filter_options()
        self.filter_receipts()

    def filter_receipts(self, _text=None):
        settings = self.data_manager.get_settings(self.user_id)
        receipts = browse_receipts(
            self.data_manager.get_all_receipts(self.user_id),
            query=self.search_bar.text(),
            merchant=self.merchant_filter.currentText(),
            category=self.category_filter.currentText(),
            warranty_status=self.warranty_filter.currentText(),
            return_status=self.return_filter.currentText(),
            purchase_date_from=self.purchase_date_from.text(),
            purchase_date_to=self.purchase_date_to.text(),
            sort_by=self.sort_filter.currentText(),
            warranty_warning_threshold=settings["warranty_warning_threshold"],
            return_warning_threshold=settings["return_warning_threshold"],
        )
        self.display_receipts(receipts)

    def refresh_filter_options(self):
        options = self.data_manager.get_receipt_filter_options(self.user_id)
        self.set_filter_options(self.merchant_filter, options["merchants"])
        self.set_filter_options(self.category_filter, options["categories"])

    @staticmethod
    def set_filter_options(combo, values):
        current_value = combo.currentText()
        choices = [ALL_OPTION, *values]
        # Preserve a selected value after an edit even if no remaining receipt
        # contains it; the gallery should then correctly show zero matches.
        if current_value and current_value not in choices:
            choices.append(current_value)
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(choices)
        combo.setCurrentText(current_value if current_value in choices else ALL_OPTION)
        combo.blockSignals(False)

    def clear_all_filters(self):
        for filter_widget in (
            self.merchant_filter,
            self.category_filter,
            self.warranty_filter,
            self.return_filter,
        ):
            filter_widget.setCurrentText(ALL_OPTION)
        self.sort_filter.setCurrentText(SORT_OPTIONS[0])
        self.purchase_date_from.clear()
        self.purchase_date_to.clear()
        self.search_bar.clear()
        self.filter_receipts()

    def has_active_browse_filters(self):
        return any(
            (
                self.search_bar.text().strip(),
                self.merchant_filter.currentText() != ALL_OPTION,
                self.category_filter.currentText() != ALL_OPTION,
                self.warranty_filter.currentText() != ALL_OPTION,
                self.return_filter.currentText() != ALL_OPTION,
                self.purchase_date_from.text().strip(),
                self.purchase_date_to.text().strip(),
                self.sort_filter.currentText() != SORT_OPTIONS[0],
            )
        )

    def display_receipts(self, receipts):
        self.clear_gallery()

        if not receipts:
            if self.has_active_browse_filters():
                self.empty_label.setText(
                    "No receipts match the current search and filters. Try clearing them."
                )
            else:
                self.empty_label.setText(
                    "No receipts yet. Add your first receipt to begin tracking warranties and returns."
                )
            self.gallery_layout.addWidget(self.empty_label)
            self.gallery_layout.addStretch(1)
            return

        settings = self.data_manager.get_settings(self.user_id)
        for receipt in receipts:
            card = ReceiptCard(
                receipt,
                on_edit=self.open_edit_receipt_dialog,
                on_delete=self.confirm_delete_receipt,
                on_view_image=self.open_receipt_image_viewer,
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

        if dialog.exec() != QDialog.DialogCode.Accepted:
            # Nothing was saved, so a copy the dialog made must not be left behind.
            self.discard_new_image_copy(dialog.cleaned_values.get("image_path"), None)
            return

        values = dialog.cleaned_values
        try:
            self.data_manager.add_receipt(user_id=self.user_id, **values)
        except Exception as error:
            self.discard_new_image_copy(values.get("image_path"), None)
            QMessageBox.critical(self, "Unable to add receipt", str(error))
            return
        self.load_receipts()

    def open_edit_receipt_dialog(self, receipt):
        dialog = AddReceiptDialog(receipt=receipt, parent=self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                updated = self.data_manager.update_receipt(
                    receipt_id=receipt.receipt_id,
                    user_id=self.user_id,
                    **dialog.cleaned_values,
                )
            except Exception as error:
                self.discard_new_image_copy(dialog.cleaned_values.get("image_path"), receipt.image_path)
                QMessageBox.critical(self, "Unable to update receipt", str(error))
                return
            if not updated:
                self.discard_new_image_copy(dialog.cleaned_values.get("image_path"), receipt.image_path)
                QMessageBox.critical(
                    self,
                    "Unable to update receipt",
                    "This receipt could not be updated. It may no longer belong to this account.",
                )
                return
            self.remove_replaced_image(receipt.image_path, dialog.cleaned_values.get("image_path"))
            self.refresh_filter_options()
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
            try:
                deleted = self.data_manager.delete_receipt(receipt.receipt_id, user_id=self.user_id)
            except Exception as error:
                QMessageBox.critical(self, "Unable to delete receipt", str(error))
                return
            if not deleted:
                QMessageBox.critical(
                    self,
                    "Unable to delete receipt",
                    "This receipt could not be deleted. It may no longer belong to this account.",
                )
                return
            self.remove_replaced_image(receipt.image_path, None)
            self.refresh_filter_options()
            self.filter_receipts()

    def open_receipt_image_viewer(self, receipt):
        ReceiptImageViewer(receipt.image_path, parent=self).exec()

    def remove_replaced_image(self, old_path, new_path):
        if not old_path or old_path == new_path:
            return
        try:
            remove_managed_receipt_image(old_path)
        except OSError as error:
            QMessageBox.warning(
                self,
                "Image removal failed",
                f"The receipt was saved, but its old managed image could not be removed: {error}",
            )

    def discard_new_image_copy(self, new_path, old_path):
        if new_path and new_path != old_path:
            try:
                remove_managed_receipt_image(new_path)
            except OSError:
                # The update error is the actionable failure; a later edit can
                # replace this unused copy safely.
                pass

    def refresh_settings_dependent_views(self):
        self.filter_receipts()
        self.dashboard_page.refresh()
