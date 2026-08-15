from PyQt6.QtWidgets import QDialog, QMessageBox

from app.data.data_manager import DataManager
from app.models.receipt import Receipt
from app.ui import main_window
from app.ui.receipt_card import ReceiptCard
from app.ui.receipt_dialog import AddReceiptDialog


def make_receipt(**overrides):
    values = {
        "receipt_id": 1,
        "user_id": 1,
        "product_name": "Wireless Mouse",
        "merchant_name": "Tech Store",
        "category_name": "Electronics",
        "price_cents": 2499,
        "purchase_date": "2026-08-15",
        "warranty_days": 365,
        "return_days": 30,
        "image_path": "receipts/mouse.png",
        "created_at": "2026-08-15 10:00:00",
    }
    values.update(overrides)
    return Receipt(**values)


def add_receipt(data_manager):
    return data_manager.add_receipt(
        product_name="Wireless Mouse",
        merchant_name="Tech Store",
        category_name="Electronics",
        price_cents=2499,
        purchase_date="2026-08-15",
        warranty_days=365,
        return_days=30,
        image_path="receipts/mouse.png",
    )


def test_edit_dialog_prefills_and_preserves_image_path(qapp):
    receipt = make_receipt()
    dialog = AddReceiptDialog(receipt=receipt)

    assert dialog.windowTitle() == "Edit Receipt"
    assert dialog.product_name_input.text() == "Wireless Mouse"
    assert dialog.price_input.text() == "24.99"

    dialog.product_name_input.setText("Ergonomic Mouse")
    dialog.validate_and_accept()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.cleaned_values["product_name"] == "Ergonomic Mouse"
    assert dialog.cleaned_values["image_path"] == "receipts/mouse.png"


def test_add_dialog_uses_configured_period_defaults(qapp):
    dialog = AddReceiptDialog(default_warranty_days=730, default_return_days=14)

    assert dialog.warranty_days_input.text() == "730"
    assert dialog.return_days_input.text() == "14"


def test_receipt_card_actions_call_their_callbacks(qapp):
    receipt = make_receipt()
    edited = []
    deleted = []
    card = ReceiptCard(receipt, on_edit=edited.append, on_delete=deleted.append)

    card.edit_button.click()
    card.delete_button.click()

    assert edited == [receipt]
    assert deleted == [receipt]


def test_receipt_card_handles_a_missing_image(qapp):
    card = ReceiptCard(make_receipt(image_path="missing-image.png"))

    assert card.image_label.text() == "Image\nunavailable"


def test_edit_and_delete_refresh_the_current_search(monkeypatch, qapp, tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    receipt_id = add_receipt(data_manager)
    window = main_window.MainWindow(data_manager=data_manager)
    window.search_bar.setText("mouse")
    receipt = window.receipt_cards[0].receipt

    class AcceptedEditDialog:
        cleaned_values = {
            "product_name": "Ergonomic Mouse",
            "merchant_name": "Tech Store",
            "category_name": "Electronics",
            "price_cents": 3599,
            "purchase_date": "2026-08-15",
            "warranty_days": 365,
            "return_days": 30,
            "image_path": "receipts/mouse.png",
        }

        def __init__(self, receipt, parent):
            assert receipt.receipt_id == receipt_id
            assert parent is window

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window, "AddReceiptDialog", AcceptedEditDialog)
    window.open_edit_receipt_dialog(receipt)

    assert window.search_bar.text() == "mouse"
    assert [card.receipt.product_name for card in window.receipt_cards] == [
        "Ergonomic Mouse"
    ]

    monkeypatch.setattr(
        main_window.QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.No,
    )
    window.confirm_delete_receipt(window.receipt_cards[0].receipt)

    assert [card.receipt.product_name for card in window.receipt_cards] == [
        "Ergonomic Mouse"
    ]

    monkeypatch.setattr(
        main_window.QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    window.confirm_delete_receipt(window.receipt_cards[0].receipt)

    assert window.search_bar.text() == "mouse"
    assert window.receipt_cards == []
    assert data_manager.get_all_receipts() == []
    window.close()
