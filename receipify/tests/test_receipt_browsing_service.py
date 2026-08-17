import pytest

from app.data.data_manager import DataManager
from app.services.receipt_browsing_service import browse_receipts, sort_receipts


@pytest.fixture
def data_manager(tmp_path):
    return DataManager(tmp_path / "receipify-test.db")


def add_receipt(data_manager, **overrides):
    values = {
        "product_name": "Laptop",
        "merchant_name": "Tech Store",
        "category_name": "Electronics",
        "price_cents": 10000,
        "purchase_date": "2026-08-02",
        "warranty_days": 0,
        "return_days": 0,
        "image_path": None,
        "user_id": 1,
    }
    values.update(overrides)
    return data_manager.add_receipt(**values)


def test_combined_search_filters_and_sorting(data_manager):
    add_receipt(data_manager)
    add_receipt(
        data_manager,
        product_name="Laptop Stand",
        price_cents=6000,
        purchase_date="2026-08-03",
    )
    add_receipt(
        data_manager,
        product_name="Laptop Sleeve",
        merchant_name="Office Shop",
        category_name="Office",
        price_cents=4000,
        purchase_date="2026-08-03",
    )

    results = browse_receipts(
        data_manager.get_all_receipts(1),
        query="laptop",
        merchant="Tech Store",
        category="Electronics",
        warranty_status="Not tracked",
        return_status="Not tracked",
        purchase_date_from="2026-08-01",
        purchase_date_to="2026-08-04",
        sort_by="Price (lowest)",
    )

    assert [receipt.product_name for receipt in results] == ["Laptop Stand", "Laptop"]


def test_sort_options_cover_date_price_name_and_recent_addition(data_manager):
    old_id = add_receipt(data_manager, product_name="Zulu", price_cents=300, purchase_date="2026-01-01")
    new_id = add_receipt(data_manager, product_name="Alpha", price_cents=100, purchase_date="2026-02-01")
    middle_id = add_receipt(data_manager, product_name="Mouse", price_cents=200, purchase_date="2026-01-15")
    receipts = data_manager.get_all_receipts(1)

    assert [receipt.receipt_id for receipt in sort_receipts(receipts, "Purchase date (newest)")] == [new_id, middle_id, old_id]
    assert [receipt.receipt_id for receipt in sort_receipts(receipts, "Purchase date (oldest)")] == [old_id, middle_id, new_id]
    assert [receipt.receipt_id for receipt in sort_receipts(receipts, "Price (highest)")] == [old_id, middle_id, new_id]
    assert [receipt.receipt_id for receipt in sort_receipts(receipts, "Price (lowest)")] == [new_id, middle_id, old_id]
    assert [receipt.product_name for receipt in sort_receipts(receipts, "Product name (A-Z)")] == ["Alpha", "Mouse", "Zulu"]
    assert [receipt.product_name for receipt in sort_receipts(receipts, "Product name (Z-A)")] == ["Zulu", "Mouse", "Alpha"]
    assert [receipt.receipt_id for receipt in sort_receipts(receipts, "Recently added")] == [middle_id, new_id, old_id]


def test_browse_data_and_filter_choices_are_scoped_to_the_user(data_manager):
    alice_id = data_manager.create_user("alice", "secure-password")
    bob_id = data_manager.create_user("bob", "secure-password")
    add_receipt(data_manager, product_name="Alice Laptop", merchant_name="Alice Shop", user_id=alice_id)
    add_receipt(data_manager, product_name="Bob Laptop", merchant_name="Bob Shop", user_id=bob_id)

    alice_results = browse_receipts(data_manager.get_all_receipts(alice_id), query="laptop")

    assert [receipt.product_name for receipt in alice_results] == ["Alice Laptop"]
    assert data_manager.get_receipt_filter_options(alice_id) == {
        "merchants": ["Alice Shop"],
        "categories": ["Electronics"],
    }
