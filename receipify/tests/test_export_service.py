import csv
import json

import pytest

from app.data.data_manager import DataManager
from app.services.export_service import EXPORT_FIELDS, export_user_receipts


@pytest.fixture
def data_manager(tmp_path):
    manager = DataManager(tmp_path / "receipify-test.db")
    with manager.connect() as connection:
        connection.execute(
            "INSERT INTO users (user_id, username, password_hash) VALUES (?, ?, ?)",
            (2, "other_user", "not_used_yet"),
        )
    return manager


def add_receipt(data_manager, product_name, user_id=1):
    return data_manager.add_receipt(
        product_name=product_name,
        merchant_name="Tech Store",
        category_name="Electronics",
        price_cents=2499,
        purchase_date="2026-08-15",
        warranty_days=0,
        return_days=0,
        image_path="data/receipt_images/mouse.png",
        user_id=user_id,
    )


def test_export_user_receipts_to_csv_uses_only_the_requested_user(data_manager, tmp_path):
    add_receipt(data_manager, "Wireless Mouse", user_id=1)
    add_receipt(data_manager, "Other User Item", user_id=2)
    output_directory = tmp_path / "exports"
    output_directory.mkdir()
    output_path = output_directory / "receipts.csv"

    exported_count = export_user_receipts(data_manager, 1, output_path, "csv")

    with output_path.open(newline="", encoding="utf-8") as output_file:
        rows = list(csv.DictReader(output_file))

    assert exported_count == 1
    assert rows[0]["product_name"] == "Wireless Mouse"
    assert rows[0]["merchant"] == "Tech Store"
    assert rows[0]["price"] == "24.99"
    assert rows[0]["warranty_status"] == "no warranty period"
    assert rows[0]["image_path"] == "data/receipt_images/mouse.png"
    assert tuple(rows[0]) == EXPORT_FIELDS


def test_export_user_receipts_to_json_includes_requested_fields(data_manager, tmp_path):
    add_receipt(data_manager, "Wireless Mouse")
    output_directory = tmp_path / "exports"
    output_directory.mkdir()
    output_path = output_directory / "receipts.json"

    exported_count = export_user_receipts(data_manager, 1, output_path, "json")

    records = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported_count == 1
    assert records == [
        {
            "product_name": "Wireless Mouse",
            "merchant": "Tech Store",
            "category": "Electronics",
            "price": "24.99",
            "purchase_date": "2026-08-15",
            "warranty_days": 0,
            "return_days": 0,
            "warranty_expiry_date": None,
            "return_expiry_date": None,
            "warranty_status": "no warranty period",
            "return_status": "no return period",
            "image_path": "data/receipt_images/mouse.png",
            "created_at": records[0]["created_at"],
        }
    ]


def test_export_user_receipts_rejects_unknown_formats(data_manager, tmp_path):
    with pytest.raises(ValueError, match="Unsupported export format"):
        export_user_receipts(data_manager, 1, tmp_path / "receipts.xml", "xml")
