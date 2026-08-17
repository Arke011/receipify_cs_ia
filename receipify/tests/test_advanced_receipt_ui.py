from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QMessageBox

from app.data.data_manager import DataManager
from app.models.receipt import Receipt
from app.services import image_service
from app.services.receipt_browsing_service import default_filters
from app.ui import main_window
from app.ui.filter_dialog import FilterDialog
from app.ui.receipt_dialog import AddReceiptDialog
from app.ui.receipt_image_viewer import ReceiptImageViewer


def add_receipt(data_manager, **overrides):
    values = {
        "product_name": "Wireless Mouse",
        "merchant_name": "Tech Store",
        "category_name": "Electronics",
        "price_cents": 2499,
        "purchase_date": "2026-08-15",
        "warranty_days": 365,
        "return_days": 30,
        "image_path": None,
        "user_id": 1,
    }
    values.update(overrides)
    return data_manager.add_receipt(**values)


def make_receipt(image_path):
    return Receipt(
        receipt_id=1,
        user_id=1,
        product_name="Mouse",
        merchant_name="Tech Store",
        category_name="Electronics",
        price_cents=1000,
        purchase_date="2026-08-15",
        warranty_days=0,
        return_days=0,
        image_path=str(image_path),
        created_at="2026-08-15 10:00:00",
    )


def test_edit_and_delete_keep_the_current_browse_state(monkeypatch, qapp, tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    add_receipt(data_manager)
    window = main_window.MainWindow(data_manager=data_manager)
    window.search_bar.setText("mouse")
    window.filters.update(
        {
            "merchant": "Tech Store",
            "category": "Electronics",
            "sort_by": "Price (lowest)",
        }
    )
    window.update_filter_button()
    window.filter_receipts()
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
            "image_path": None,
        }

        def __init__(self, receipt, parent):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window, "AddReceiptDialog", AcceptedEditDialog)
    window.open_edit_receipt_dialog(receipt)
    assert window.search_bar.text() == "mouse"
    assert window.filters["merchant"] == "Tech Store"
    assert window.filters["category"] == "Electronics"
    assert window.filters["sort_by"] == "Price (lowest)"

    monkeypatch.setattr(main_window.QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.confirm_delete_receipt(window.receipt_cards[0].receipt)
    assert window.search_bar.text() == "mouse"
    assert window.filters["merchant"] == "Tech Store"
    assert window.filters["category"] == "Electronics"
    assert window.receipt_cards == []
    window.close()


def test_filter_button_reports_how_many_filters_are_active(qapp, tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    add_receipt(data_manager)
    window = main_window.MainWindow(data_manager=data_manager)

    assert window.filter_button.text() == "Filters"

    window.filters.update({"merchant": "Tech Store", "warranty_status": "Active"})
    window.update_filter_button()

    assert window.filter_button.text() == "Filters (2)"

    window.clear_all_filters()

    assert window.filter_button.text() == "Filters"
    assert window.filters == default_filters()
    window.close()


def test_applying_the_filter_dialog_updates_the_gallery(monkeypatch, qapp, tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    add_receipt(data_manager)
    add_receipt(data_manager, product_name="Blender", merchant_name="HomeGoods")
    window = main_window.MainWindow(data_manager=data_manager)

    assert len(window.receipt_cards) == 2

    class ApplyingFilterDialog:
        def __init__(self, filters, merchants, categories, parent):
            # The dialog is offered exactly the merchants that are in use.
            assert merchants == ["HomeGoods", "Tech Store"]
            self.values = {**filters, "merchant": "HomeGoods"}

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window, "FilterDialog", ApplyingFilterDialog)
    window.open_filter_dialog()

    assert [card.receipt.product_name for card in window.receipt_cards] == ["Blender"]
    assert window.filter_button.text() == "Filters (1)"
    window.close()


def test_a_cancelled_filter_dialog_changes_nothing(monkeypatch, qapp, tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    add_receipt(data_manager)
    window = main_window.MainWindow(data_manager=data_manager)

    class CancelledFilterDialog:
        values = {**default_filters(), "merchant": "Nowhere"}

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window, "FilterDialog", CancelledFilterDialog)
    window.open_filter_dialog()

    assert window.filters == default_filters()
    assert len(window.receipt_cards) == 1
    window.close()


def test_the_filter_dialog_round_trips_its_values(qapp):
    filters = {**default_filters(), "merchant": "Tech Store", "sort_by": "Price (lowest)"}
    dialog = FilterDialog(filters, merchants=["Tech Store"], categories=["Electronics"])

    assert dialog.merchant_filter.currentText() == "Tech Store"
    assert dialog.sort_filter.currentText() == "Price (lowest)"

    dialog.category_filter.setCurrentText("Electronics")
    dialog.purchase_date_from.setText(" 2026-01-01 ")
    dialog.apply_and_accept()

    assert dialog.values["merchant"] == "Tech Store"
    assert dialog.values["category"] == "Electronics"
    assert dialog.values["purchase_date_from"] == "2026-01-01"

    dialog.clear_all()

    assert dialog.collect_values() == default_filters()


def test_a_filtered_empty_gallery_offers_a_way_back(qapp, tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    add_receipt(data_manager)
    window = main_window.MainWindow(data_manager=data_manager)

    window.search_bar.setText("nothing matches this")

    assert window.receipt_cards == []
    assert window.clear_filters_button.isHidden() is False

    window.clear_filters_button.click()

    assert window.search_bar.text() == ""
    assert len(window.receipt_cards) == 1
    window.close()


def test_image_viewer_scales_valid_images_and_handles_missing_ones(qapp, tmp_path):
    image_path = tmp_path / "receipt.png"
    pixmap = QPixmap(1000, 200)
    pixmap.fill()
    assert pixmap.save(str(image_path))

    viewer = ReceiptImageViewer(image_path)
    viewer.show()
    qapp.processEvents()
    displayed = viewer.image_label.pixmap()
    assert displayed is not None and not displayed.isNull()
    assert abs((displayed.width() / displayed.height()) - 5) < 0.02
    viewer.close()

    missing_viewer = ReceiptImageViewer(tmp_path / "missing.png")
    assert "unavailable" in missing_viewer.image_label.text().casefold()


def test_edit_dialog_explicitly_removes_the_existing_image(qapp, tmp_path):
    receipt = make_receipt(tmp_path / "receipt.png")
    dialog = AddReceiptDialog(receipt=receipt)

    dialog.remove_image()
    dialog.validate_and_accept()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.cleaned_values["image_path"] is None
    assert dialog.image_removed is True


def test_managed_image_removal_never_deletes_external_source(monkeypatch, tmp_path):
    managed_directory = tmp_path / "managed"
    managed_directory.mkdir()
    managed_copy = managed_directory / "copy.png"
    managed_copy.write_bytes(b"copy")
    external_source = tmp_path / "source.png"
    external_source.write_bytes(b"source")
    monkeypatch.setattr(image_service, "MANAGED_IMAGE_DIRECTORY", managed_directory)

    assert image_service.remove_managed_receipt_image(managed_copy) is True
    assert not managed_copy.exists()
    assert image_service.remove_managed_receipt_image(external_source) is False
    assert external_source.exists()


def test_failed_update_delete_and_image_removal_are_shown(monkeypatch, qapp, tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    add_receipt(data_manager, image_path="data/receipt_images/old.png")
    window = main_window.MainWindow(data_manager=data_manager)
    receipt = window.receipt_cards[0].receipt
    messages = []
    monkeypatch.setattr(main_window.QMessageBox, "critical", lambda *args: messages.append(args[1]))

    class AcceptedEditDialog:
        cleaned_values = {
            "product_name": "Mouse",
            "merchant_name": "Tech Store",
            "category_name": "Electronics",
            "price_cents": 2499,
            "purchase_date": "2026-08-15",
            "warranty_days": 365,
            "return_days": 30,
            "image_path": None,
        }

        def __init__(self, receipt, parent):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window, "AddReceiptDialog", AcceptedEditDialog)
    monkeypatch.setattr(data_manager, "update_receipt", lambda **kwargs: False)
    window.open_edit_receipt_dialog(receipt)
    assert messages == ["Unable to update receipt"]

    monkeypatch.setattr(main_window.QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(data_manager, "delete_receipt", lambda *args, **kwargs: False)
    window.confirm_delete_receipt(receipt)
    assert messages[-1] == "Unable to delete receipt"

    monkeypatch.setattr(data_manager, "delete_receipt", lambda *args, **kwargs: True)
    warnings = []
    monkeypatch.setattr(main_window.QMessageBox, "warning", lambda *args: warnings.append(args[1]))
    monkeypatch.setattr(main_window, "remove_managed_receipt_image", lambda path: (_ for _ in ()).throw(OSError("locked")))
    window.confirm_delete_receipt(receipt)
    assert warnings == ["Image removal failed"]
    window.close()
