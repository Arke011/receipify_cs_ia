"""The main window: the Receipts tab (a searchable list of receipt cards) plus the other tabs."""

import sqlite3
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QStyle, QTabWidget, QVBoxLayout, QWidget,
)

from browse import DEFAULT_FILTERS, FilterDialog, count_active, filter_receipts
from dashboard import DashboardPage
from export import ExportPage
from images import delete_image
from receipt import days_until, format_euros
from receipt_dialog import ReceiptDialog
from settings import SettingsPage

STATUS_ICONS = {
    "active": QStyle.StandardPixmap.SP_DialogApplyButton,
    "expiring soon": QStyle.StandardPixmap.SP_MessageBoxWarning,
    "expired": QStyle.StandardPixmap.SP_DialogCancelButton,
}  # anything else ("no ... period") gets the information icon


class MainWindow(QMainWindow):
    logged_out = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, db, user_id, username):
        super().__init__()
        self.db = db
        self.user_id = user_id
        self.filters = dict(DEFAULT_FILTERS)
        self.cards = []
        self.setWindowTitle(f"Receipify - {username}")
        self.resize(1040, 760)
        self.setMinimumSize(820, 560)

        self.receipts_page = self.build_receipts_page()
        self.dashboard = DashboardPage(db, user_id)
        self.export_page = ExportPage(db, user_id)
        self.settings_page = SettingsPage(db, user_id, on_saved=self.show_receipts)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.receipts_page, "Receipts")
        self.tabs.addTab(self.dashboard, "Dashboard")
        self.tabs.addTab(self.export_page, "Export")
        self.tabs.addTab(self.settings_page, "Settings")
        self.tabs.currentChanged.connect(self.refresh_tab)

        self.logout_button = QPushButton("Log out")
        self.logout_button.clicked.connect(self.logged_out.emit)
        # The button has a row of its own: in the tab bar's corner it was clipped.
        header = QHBoxLayout()
        header.setContentsMargins(0, 6, 8, 6)
        header.addStretch()
        header.addWidget(self.logout_button)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)
        self.show_receipts()

    def build_receipts_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search product, store, category, or price")
        self.search_bar.setAccessibleName("Search receipts")
        self.search_bar.textChanged.connect(self.show_receipts)
        controls.addWidget(self.search_bar, stretch=1)
        self.filter_button = QPushButton("Filters")
        self.filter_button.clicked.connect(self.edit_filters)
        controls.addWidget(self.filter_button)
        add_button = QPushButton("Add receipt")
        add_button.clicked.connect(self.add_receipt)
        controls.addWidget(add_button)
        layout.addLayout(controls)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area, stretch=1)
        gallery = QWidget()
        self.gallery = QVBoxLayout(gallery)
        scroll_area.setWidget(gallery)

        # Shown in place of the cards when there is nothing to list.
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        self.empty_label = QLabel()
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        empty_layout.addWidget(self.empty_label)
        self.clear_filters_button = QPushButton("Clear search and filters")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        empty_layout.addWidget(self.clear_filters_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.gallery.addWidget(self.empty_state)
        self.gallery.addStretch(1)  # cards are inserted above this, so they sit at the top
        return page

    def refresh_tab(self):
        """Reload a tab when it is opened, so it always shows the latest receipts and settings."""
        page = self.tabs.currentWidget()
        if page is not self.receipts_page:
            page.refresh()

    def show_receipts(self):
        """Rebuild the receipt cards from the database, applying the search text and filters."""
        settings = self.db.get_settings(self.user_id)
        receipts = filter_receipts(self.db.receipts(self.user_id), self.search_bar.text(), self.filters, settings)
        for card in self.cards:
            card.hide()  # hidden at once; Qt deletes it when it is idle
            card.deleteLater()
        self.cards = []
        for receipt in receipts:
            card = ReceiptCard(receipt, settings, self.edit_receipt, self.delete_receipt, self.view_image)
            self.gallery.insertWidget(self.gallery.count() - 1, card)
            self.cards.append(card)

        active_filters = count_active(self.filters)
        self.filter_button.setText(f"Filters ({active_filters})" if active_filters else "Filters")
        filtered = bool(self.search_bar.text().strip() or active_filters)
        if filtered:
            self.empty_label.setText("No receipts match the current search and filters.")
        else:
            self.empty_label.setText("No receipts yet. Add your first receipt to begin tracking warranties and returns.")
        self.clear_filters_button.setVisible(filtered)  # an empty account has no filters to clear
        self.empty_state.setVisible(not receipts)

    def edit_filters(self):
        dialog = FilterDialog(self.filters, self.db.receipts(self.user_id), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.filters = dialog.values
            self.show_receipts()

    def clear_filters(self):
        self.filters = dict(DEFAULT_FILTERS)
        self.search_bar.clear()
        self.show_receipts()

    def add_receipt(self):
        settings = self.db.get_settings(self.user_id)
        dialog = ReceiptDialog(warranty_days=settings["default_warranty_days"],
                               return_days=settings["default_return_days"], parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.db.add_receipt(self.user_id, **dialog.values)
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Unable to add receipt", str(error))
            return
        self.show_receipts()

    def edit_receipt(self, receipt):
        dialog = ReceiptDialog(receipt, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.db.update_receipt(self.user_id, receipt.id, **dialog.values)
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Unable to update receipt", str(error))
            return
        if dialog.values["image_path"] != receipt.image_path:
            self.delete_old_image(receipt.image_path)
        self.show_receipts()

    def delete_receipt(self, receipt):
        answer = QMessageBox.question(
            self, "Delete receipt", f"Delete '{receipt.product}'? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_receipt(self.user_id, receipt.id)
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Unable to delete receipt", str(error))
            return
        self.delete_old_image(receipt.image_path)
        self.show_receipts()

    def delete_old_image(self, path):
        try:
            delete_image(path)
        except OSError as error:
            QMessageBox.warning(self, "Image removal failed",
                                f"The receipt was saved, but its old managed image could not be removed: {error}")

    def view_image(self, receipt):
        if receipt.image_path:
            ImageViewer(receipt.image_path, parent=self).exec()

    def closeEvent(self, event):
        for dialog in self.findChildren(QDialog):
            dialog.reject()  # close any dialog still open
        self.closed.emit()
        super().closeEvent(event)


class Thumbnail(QLabel):
    """A receipt photo preview that can be opened with a click, Enter or Space."""
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


def days_text(days_left):
    if days_left < 0:
        return f"Expired {abs(days_left)} days ago"
    if days_left == 0:
        return "Expires today"
    return f"{days_left} days remaining"


class ReceiptCard(QFrame):
    def __init__(self, receipt, settings, on_edit, on_delete, on_view_image):
        super().__init__()
        self.receipt = receipt
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)

        self.image_label = Thumbnail()
        self.image_label.setFixedSize(80, 72)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.image_label.setAccessibleName("View receipt image")
        self.image_label.setToolTip("View receipt image")
        self.image_label.clicked.connect(lambda: on_view_image(receipt))
        pixmap = QPixmap(receipt.image_path) if receipt.image_path else None
        if pixmap is None:
            self.image_label.setText("No image")
        elif pixmap.isNull():
            self.image_label.setText("Image\nunavailable")
        else:
            self.image_label.setPixmap(pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(self.image_label)

        details = QVBoxLayout()
        title = QHBoxLayout()
        name = QLabel(receipt.product)
        name.setTextFormat(Qt.TextFormat.PlainText)
        name.setWordWrap(True)
        font = name.font()
        font.setBold(True)
        name.setFont(font)
        title.addWidget(name, stretch=1)
        title.addWidget(QLabel(format_euros(receipt.price_cents)))
        details.addLayout(title)
        meta = QLabel(f"{receipt.merchant} · {receipt.category} · Purchased {receipt.purchase_date}")
        meta.setTextFormat(Qt.TextFormat.PlainText)
        meta.setWordWrap(True)
        details.addWidget(meta)
        for period, expiry, status in (
            ("Warranty", receipt.warranty_expiry(), receipt.warranty_status(settings["warranty_warning_threshold"])),
            ("Return", receipt.return_expiry(), receipt.return_status(settings["return_warning_threshold"])),
        ):
            row = QHBoxLayout()
            icon = QLabel()
            icon_type = STATUS_ICONS.get(status, QStyle.StandardPixmap.SP_MessageBoxInformation)
            icon.setPixmap(self.style().standardIcon(icon_type).pixmap(16, 16))
            row.addWidget(icon)
            text = f"{period}: {status.capitalize()}"
            if expiry:
                text += f" · {expiry} · {days_text(days_until(expiry))}"
            info = QLabel(text)
            info.setWordWrap(True)
            row.addWidget(info, stretch=1)
            details.addLayout(row)
        layout.addLayout(details, stretch=1)

        actions = QVBoxLayout()
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(lambda: on_edit(receipt))
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(lambda: on_delete(receipt))
        actions.addWidget(self.edit_button)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        layout.addLayout(actions)


class ImageViewer(QDialog):
    """Shows a receipt's image as large as the window allows."""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.pixmap = QPixmap()
        self.setWindowTitle("Receipt image")
        self.resize(840, 620)
        self.setMinimumSize(420, 320)
        layout = QVBoxLayout(self)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        layout.addWidget(self.image_label, stretch=1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not Path(image_path).is_file():
            self.image_label.setText("This receipt image is unavailable.")
            return
        self.pixmap = QPixmap(str(image_path))
        if self.pixmap.isNull():
            self.image_label.setText("This receipt image could not be read.")
            return
        self.fit_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.pixmap.isNull():
            self.fit_image()

    def fit_image(self):
        self.image_label.setPixmap(self.pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
