import pytest

from app.data.data_manager import DataManager


@pytest.fixture
def data_manager(tmp_path):
    return DataManager(tmp_path / "receipify-test.db")


def add_sample_receipt(data_manager, **overrides):
    values = {
        "product_name": "Wireless Mouse",
        "merchant_name": "Tech Store",
        "category_name": "Electronics",
        "price_cents": 2499,
        "purchase_date": "2026-08-15",
        "warranty_days": 365,
        "return_days": 30,
        "image_path": None,
    }
    values.update(overrides)
    return data_manager.add_receipt(**values)


def test_add_and_search_receipts(data_manager):
    mouse_id = add_sample_receipt(data_manager)
    keyboard_id = add_sample_receipt(
        data_manager,
        product_name="Keyboard",
        merchant_name="Office Shop",
        category_name="Office",
        purchase_date="2026-08-16",
    )

    receipts = data_manager.get_all_receipts()
    assert [receipt.receipt_id for receipt in receipts] == [keyboard_id, mouse_id]
    assert receipts[1].merchant_name == "Tech Store"
    assert [receipt.product_name for receipt in data_manager.search_receipts(1, "tech")] == [
        "Wireless Mouse"
    ]
    assert [receipt.product_name for receipt in data_manager.search_receipts(1, "office")] == [
        "Keyboard"
    ]


def test_search_treats_like_wildcards_as_literal_characters(data_manager):
    add_sample_receipt(data_manager)
    add_sample_receipt(data_manager, product_name="Keyboard", merchant_name="Office Shop")
    add_sample_receipt(data_manager, product_name="100% Cotton Towel")
    add_sample_receipt(data_manager, product_name="Snap_On Wrench")

    assert [receipt.product_name for receipt in data_manager.search_receipts(1, "%")] == [
        "100% Cotton Towel"
    ]
    assert [receipt.product_name for receipt in data_manager.search_receipts(1, "_")] == [
        "Snap_On Wrench"
    ]
    assert data_manager.search_receipts(1, "%%%") == []
    assert [
        receipt.product_name for receipt in data_manager.search_receipts(1, "100%")
    ] == ["100% Cotton Towel"]


def test_search_treats_the_escape_character_as_literal(data_manager):
    add_sample_receipt(data_manager, product_name="Back\\Slash Tool")
    add_sample_receipt(data_manager, product_name="Plain Tool")

    assert [
        receipt.product_name for receipt in data_manager.search_receipts(1, "\\")
    ] == ["Back\\Slash Tool"]


def test_update_receipt_replaces_receipt_details(data_manager):
    receipt_id = add_sample_receipt(data_manager)

    updated = data_manager.update_receipt(
        receipt_id=receipt_id,
        product_name="Ergonomic Mouse",
        merchant_name="New Tech Store",
        category_name="Accessories",
        price_cents=3599,
        purchase_date="2026-08-20",
        warranty_days=730,
        return_days=14,
        image_path="images/mouse.png",
    )

    receipt = data_manager.get_all_receipts()[0]
    assert updated is True
    assert receipt.product_name == "Ergonomic Mouse"
    assert receipt.merchant_name == "New Tech Store"
    assert receipt.category_name == "Accessories"
    assert receipt.price_cents == 3599
    assert receipt.purchase_date == "2026-08-20"
    assert receipt.warranty_days == 730
    assert receipt.return_days == 14
    assert receipt.image_path == "images/mouse.png"


def test_delete_receipt_respects_user_ownership(data_manager):
    receipt_id = add_sample_receipt(data_manager)

    assert data_manager.delete_receipt(receipt_id, user_id=2) is False
    assert data_manager.delete_receipt(receipt_id) is True
    assert data_manager.get_all_receipts() == []
