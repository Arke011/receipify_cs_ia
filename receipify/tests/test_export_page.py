import csv

from PyQt6.QtCore import Qt

from app.data.data_manager import DataManager
from app.ui import export_page as export_page_module
from app.ui.export_page import ExportPage


def build_page(tmp_path, qapp):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    for product_name, price_cents in [("Mouse", 2499), ("Keyboard", 5000), ("Cable", 999)]:
        data_manager.add_receipt(
            product_name=product_name,
            merchant_name="Tech Store",
            category_name="Electronics",
            price_cents=price_cents,
            purchase_date="2026-08-15",
            warranty_days=365,
            return_days=30,
            user_id=1,
        )

    return ExportPage(data_manager, user_id=1)


def test_every_receipt_starts_selected(tmp_path, qapp):
    page = build_page(tmp_path, qapp)

    assert page.receipt_list.count() == 3
    assert len(page.selected_receipt_ids()) == 3
    assert page.selection_label.text() == "3 of 3 selected"


def test_select_none_clears_the_selection_and_blocks_exporting(tmp_path, qapp):
    page = build_page(tmp_path, qapp)

    page.set_all_checked(False)

    assert page.selected_receipt_ids() == []
    assert page.selection_label.text() == "0 of 3 selected"
    assert page.csv_button.isEnabled() is False
    assert page.json_button.isEnabled() is False

    page.set_all_checked(True)

    assert len(page.selected_receipt_ids()) == 3
    assert page.csv_button.isEnabled() is True


def test_only_ticked_receipts_are_written(monkeypatch, tmp_path, qapp):
    page = build_page(tmp_path, qapp)
    output_path = tmp_path / "chosen.csv"

    # Keep only the middle receipt ticked.
    for row in (0, 2):
        page.receipt_list.item(row).setCheckState(Qt.CheckState.Unchecked)

    monkeypatch.setattr(
        export_page_module.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(output_path), "")),
    )
    monkeypatch.setattr(
        export_page_module.QMessageBox,
        "information",
        staticmethod(lambda *args, **kwargs: None),
    )

    page.export_receipts("csv")

    with output_path.open(newline="", encoding="utf-8") as exported_file:
        rows = list(csv.DictReader(exported_file))

    assert [row["product_name"] for row in rows] == ["Keyboard"]


def test_an_empty_account_cannot_export(tmp_path, qapp):
    data_manager = DataManager(tmp_path / "empty.db")
    page = ExportPage(data_manager, user_id=1)

    assert page.receipt_list.count() == 0
    assert page.selection_label.text() == "No receipts to export yet."
    assert page.csv_button.isEnabled() is False


def test_refresh_keeps_choices_and_picks_up_new_receipts(tmp_path, qapp):
    page = build_page(tmp_path, qapp)
    page.receipt_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    unticked_id = page.receipt_list.item(0).data(Qt.ItemDataRole.UserRole)

    page.data_manager.add_receipt(
        product_name="Monitor",
        merchant_name="Tech Store",
        category_name="Electronics",
        price_cents=19900,
        purchase_date="2026-08-16",
        warranty_days=365,
        return_days=30,
        user_id=1,
    )
    page.refresh()

    assert page.receipt_list.count() == 4
    assert unticked_id not in page.selected_receipt_ids()
    assert page.selection_label.text() == "3 of 4 selected"
