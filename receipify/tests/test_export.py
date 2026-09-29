import csv
import json

from PyQt6.QtCore import Qt

import export
from database import DEFAULT_SETTINGS


def test_csv_has_a_column_for_every_field(db, add_receipt, tmp_path):
    add_receipt(warranty_days=0, return_days=0, image_path="/images/mouse.png")
    path = tmp_path / "receipts.csv"
    export.write_export(db.receipts(1), path, "csv", DEFAULT_SETTINGS)
    with path.open(newline="", encoding="utf-8") as file:
        [row] = list(csv.DictReader(file))
    assert tuple(row) == export.FIELDS
    assert (row["product_name"], row["merchant"], row["price"], row["warranty_status"], row["image_path"]) == (
        "Wireless Mouse", "Tech Store", "24.99", "no warranty period", "/images/mouse.png")


def test_json_keeps_non_english_text_and_expiry_dates(db, add_receipt, tmp_path):
    add_receipt(product="Ąžuolinis stalas", purchase_date="2026-08-15", warranty_days=365, return_days=0)
    path = tmp_path / "receipts.json"
    export.write_export(db.receipts(1), path, "json", DEFAULT_SETTINGS)
    assert "Ąžuolinis stalas" in path.read_text(encoding="utf-8")
    [record] = json.loads(path.read_text(encoding="utf-8"))
    assert record["warranty_expiry_date"] == "2027-08-15"
    assert record["return_status"] == "no return period"


def test_export_page_writes_only_ticked_receipts(db, add_receipt, tmp_path, monkeypatch):
    page = export.ExportPage(db, 1)
    assert page.selection_label.text() == "No receipts to export yet."
    assert not page.select_all_button.isEnabled()

    for product in ("Mouse", "Keyboard", "Cable"):
        add_receipt(product=product)
    page.refresh()
    assert page.selection_label.text() == "3 of 3 selected"
    page.tick_all(False)
    assert not page.csv_button.isEnabled()
    page.receipt_list.item(1).setCheckState(Qt.CheckState.Checked)  # Keyboard
    add_receipt(product="Monitor")
    page.refresh()  # a new receipt starts ticked; unticked ones stay unticked
    assert page.selection_label.text() == "2 of 4 selected"

    path = tmp_path / "chosen"  # no extension: ".csv" is added
    monkeypatch.setattr(export.QFileDialog, "getSaveFileName", lambda *args: (str(path), ""))
    monkeypatch.setattr(export.QMessageBox, "information", lambda *args: None)
    page.export("csv")
    with path.with_suffix(".csv").open(newline="", encoding="utf-8") as file:
        assert [row["product_name"] for row in csv.DictReader(file)] == ["Monitor", "Keyboard"]
