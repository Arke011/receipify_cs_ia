import pytest

from app.services.validation_service import validate_receipt_input


def test_validate_receipt_input_returns_cleaned_values():
    is_valid, errors, values = validate_receipt_input(
        product_name="  Wireless Mouse ",
        merchant_name="  Tech Store ",
        category_name="  ",
        price="24,995",
        purchase_date="2026-08-15",
        warranty_days="365",
        return_days="30",
        image_path="receipt.png",
    )

    assert is_valid is True
    assert errors == []
    assert values == {
        "product_name": "Wireless Mouse",
        "merchant_name": "Tech Store",
        "category_name": "Uncategorised",
        "price_cents": 2500,
        "purchase_date": "2026-08-15",
        "warranty_days": 365,
        "return_days": 30,
        "image_path": "receipt.png",
    }


@pytest.mark.parametrize(
    ("price", "expected_error"),
    [
        ("abc", "Price must be numeric."),
        ("NaN", "Price must be numeric."),
        ("-1", "Price must be greater than or equal to 0."),
    ],
)
def test_validate_receipt_input_rejects_invalid_prices(price, expected_error):
    is_valid, errors, values = validate_receipt_input(
        product_name="Mouse",
        merchant_name="Store",
        price=price,
        purchase_date="2026-08-15",
        warranty_days="0",
        return_days="0",
    )

    assert is_valid is False
    assert expected_error in errors
    assert values == {}


def test_validate_receipt_input_collects_field_errors():
    is_valid, errors, values = validate_receipt_input(
        product_name=" ",
        merchant_name=" ",
        price="1",
        purchase_date="15-08-2026",
        warranty_days="-1",
        return_days="one",
    )

    assert is_valid is False
    assert errors == [
        "Product name cannot be empty.",
        "Merchant name cannot be empty.",
        "Purchase date must be a valid date in YYYY-MM-DD format.",
        "Warranty days must be greater than or equal to 0.",
        "Return days must be an integer.",
    ]
    assert values == {}
