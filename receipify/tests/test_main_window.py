from datetime import date, timedelta
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog, QLabel, QMessageBox

import main_window
import receipt_dialog
from browse import DEFAULT_FILTERS
from database import DEFAULT_SETTINGS
from receipt_dialog import ReceiptDialog
from settings import SettingsPage


# ---- the receipt form

def test_form_rejects_bad_input_then_saves_with_a_copy_of_the_image(image_dir, tmp_path):
    source = tmp_path / "photo.png"
    QPixmap(40, 30).save(str(source))
    dialog = ReceiptDialog(warranty_days=730, return_days=14)
    assert dialog.fields["warranty_days"].text() == "730"  # the defaults from Settings
    dialog.new_image = str(source)
    dialog.update_image()
    assert dialog.image_name.full_text == "photo.png"
    assert not dialog.preview.pixmap().isNull()

    dialog.show()
    QTest.keyClick(dialog.fields["price"], Qt.Key.Key_Return)  # Enter presses Save
    assert dialog.isVisible()
    assert "Product name cannot be empty." in dialog.error_label.text()
    assert not image_dir.exists()  # nothing is copied until the form is valid

    for key, value in (("product", "Mouse"), ("merchant", "Shop"), ("price", "12.34"), ("purchase_date", "2026-01-01")):
        dialog.fields[key].setText(value)
    QTest.keyClick(dialog.fields["price"], Qt.Key.Key_Return)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert (dialog.values["price_cents"], dialog.values["category"]) == (1234, "Uncategorised")
    assert Path(dialog.values["image_path"]).parent == image_dir.resolve()
    assert source.exists()  # the user's original is untouched


def test_edit_form_is_filled_in_and_can_remove_the_image(make_receipt):
    dialog = ReceiptDialog(make_receipt(image_path="/receipts/mouse.png"))
    assert dialog.windowTitle() == "Edit Receipt"
    assert (dialog.fields["product"].text(), dialog.fields["price"].text()) == ("Wireless Mouse", "24.99")
    assert not dialog.remove_button.isHidden()
    dialog.remove_image()
    assert dialog.remove_button.isHidden()
    assert dialog.image_name.full_text == "No image attached"
    dialog.save()
    assert dialog.values["image_path"] is None


@pytest.mark.parametrize("save", [False, True])
def test_scanned_details_fill_only_empty_fields_and_phone_photos_are_deleted(monkeypatch, image_dir, save):
    class AcceptedScan(QDialog):  # stands in for ScanDialog, as if the user chose "Use photo and details"
        def __init__(self, folder, image_path, parent):
            super().__init__(parent)
            self.image_path = str(Path(folder) / "phone.jpg")
            QPixmap(40, 30).save(self.image_path)
            self.values = {"merchant": "TECH STORE", "product": "Mouse", "price": "24.99", "purchase_date": "2026-01-15"}

        def start(self):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(receipt_dialog, "ScanDialog", AcceptedScan)
    dialog = ReceiptDialog(warranty_days=730, return_days=14)
    dialog.fields["product"].setText("My chosen product")
    dialog.scan()
    assert dialog.fields["merchant"].text() == "TECH STORE"
    assert dialog.fields["product"].text() == "My chosen product"  # typed text is kept
    assert dialog.fields["warranty_days"].text() == "730"
    phone_photo = Path(dialog.new_image)
    if save:
        dialog.save()
        assert Path(dialog.values["image_path"]).parent == image_dir.resolve()
    else:
        dialog.reject()
    assert not phone_photo.exists()


# ---- the Receipts tab

def products(window):
    return [card.receipt.product for card in window.cards]


def test_add_edit_and_delete_keep_the_search_and_remove_replaced_images(db, add_receipt, image_dir, monkeypatch):
    image_dir.mkdir()
    old_image = image_dir / "old.png"
    old_image.write_bytes(b"image")
    add_receipt(product="Wireless Mouse", image_path=str(old_image))
    add_receipt(product="Blender")
    window = main_window.MainWindow(db, 1, "alice")
    window.search_bar.setText("mouse")
    assert products(window) == ["Wireless Mouse"]

    class SavedForm:  # stands in for ReceiptDialog, as if the user pressed Save
        def __init__(self, receipt=None, warranty_days=0, return_days=0, parent=None):
            self.values = {"product": "Ergonomic Mouse", "merchant": "Tech Store", "category": "Electronics",
                           "price_cents": 3599, "purchase_date": "2026-08-15", "warranty_days": 365,
                           "return_days": 30, "image_path": None}

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window, "ReceiptDialog", SavedForm)
    window.edit_receipt(window.cards[0].receipt)
    assert products(window) == ["Ergonomic Mouse"]
    assert not old_image.exists()  # the replaced copy is deleted

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    window.delete_receipt(window.cards[0].receipt)
    assert products(window) == ["Ergonomic Mouse"]
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.delete_receipt(window.cards[0].receipt)
    assert products(window) == []
    assert window.search_bar.text() == "mouse"

    window.add_receipt()
    assert products(window) == ["Ergonomic Mouse"]
    assert [r.product for r in db.receipts(1)] == ["Ergonomic Mouse", "Blender"]
    window.close()


def test_empty_list_explains_why_and_offers_to_clear_filters(db, add_receipt):
    window = main_window.MainWindow(db, 1, "alice")
    window.show()
    assert window.empty_state.isVisible()
    assert window.empty_label.text().startswith("No receipts yet")
    assert not window.clear_filters_button.isVisible()  # nothing to clear on a new account

    add_receipt()
    window.filters = {**DEFAULT_FILTERS, "warranty_status": "Expired"}
    window.show_receipts()
    assert window.filter_button.text() == "Filters (1)"
    assert window.empty_label.text() == "No receipts match the current search and filters."
    assert window.clear_filters_button.isVisible()

    window.clear_filters_button.click()
    assert window.filter_button.text() == "Filters"
    assert products(window) == ["Wireless Mouse"]
    assert not window.empty_state.isVisible()
    window.close()


def test_receipt_card_shows_expiry_and_its_buttons_work(make_receipt):
    today = date.today()
    receipt = make_receipt(purchase_date=(today - timedelta(days=10)).isoformat(), warranty_days=365,
                           return_days=14, image_path="/missing.png")
    edited, deleted, viewed = [], [], []
    card = main_window.ReceiptCard(receipt, DEFAULT_SETTINGS, edited.append, deleted.append, viewed.append)
    texts = [label.text() for label in card.findChildren(QLabel)]
    assert f"Warranty: Active · {today + timedelta(days=355)} · 355 days remaining" in texts
    assert f"Return: Expiring soon · {today + timedelta(days=4)} · 4 days remaining" in texts
    assert card.image_label.text() == "Image\nunavailable"

    card.edit_button.click()
    card.delete_button.click()
    card.show()
    card.image_label.setFocus()
    QTest.keyClick(card.image_label, Qt.Key.Key_Space)  # the thumbnail opens from the keyboard too
    assert edited == deleted == viewed == [receipt]


def test_settings_page_saves_valid_values_and_explains_invalid_ones(db):
    saved = []
    page = SettingsPage(db, 1, on_saved=lambda: saved.append(True))
    assert page.fields["default_warranty_days"].text() == "365"
    page.fields["default_warranty_days"].setText("soon")
    page.fields["return_warning_threshold"].setText("-1")
    page.save()
    assert page.message.text() == ("Error: Default warranty days must be an integer.\n"
                                   "Return warning threshold must be greater than or equal to 0.")
    assert db.get_settings(1) == DEFAULT_SETTINGS
    assert saved == []

    page.fields["default_warranty_days"].setText("730")
    page.fields["return_warning_threshold"].setText("10")
    page.save()
    assert page.message.text() == "Settings saved."
    assert db.get_settings(1)["default_warranty_days"] == 730
    assert saved == [True]


def test_tabs_show_the_latest_data_when_opened(db, add_receipt):
    window = main_window.MainWindow(db, 1, "alice")
    add_receipt(price_cents=1000)
    window.tabs.setCurrentWidget(window.dashboard)
    assert window.dashboard.total_label.text() == "EUR 10.00"
    window.tabs.setCurrentWidget(window.export_page)
    assert window.export_page.receipt_list.count() == 1
    window.settings_page.fields["default_warranty_days"].setText("typed but not saved")
    window.tabs.setCurrentWidget(window.settings_page)
    assert window.settings_page.fields["default_warranty_days"].text() == "365"
    window.close()
