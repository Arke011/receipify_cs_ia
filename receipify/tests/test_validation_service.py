from datetime import date, timedelta

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
        ("-1", "Price must be greater than 0."),
        ("0", "Price must be greater than 0."),
        ("0.00", "Price must be greater than 0."),
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


def test_validate_receipt_input_accepts_the_smallest_payable_price():
    is_valid, errors, values = validate_receipt_input(
        product_name="Mouse",
        merchant_name="Store",
        price="0.01",
        purchase_date="2026-08-15",
        warranty_days="0",
        return_days="0",
    )

    assert is_valid is True
    assert errors == []
    assert values["price_cents"] == 1


@pytest.mark.parametrize("days_ahead", [1, 30, 3650])
def test_validate_receipt_input_rejects_future_purchase_dates(days_ahead):
    future_date = date.today() + timedelta(days=days_ahead)

    is_valid, errors, values = validate_receipt_input(
        product_name="Mouse",
        merchant_name="Store",
        price="1",
        purchase_date=future_date.isoformat(),
        warranty_days="0",
        return_days="0",
    )

    assert is_valid is False
    assert errors == ["Purchase date cannot be in the future."]
    assert values == {}


@pytest.mark.parametrize("days_ago", [0, 1, 3650])
def test_validate_receipt_input_accepts_today_and_past_purchase_dates(days_ago):
    purchase_date = date.today() - timedelta(days=days_ago)

    is_valid, errors, values = validate_receipt_input(
        product_name="Mouse",
        merchant_name="Store",
        price="1",
        purchase_date=purchase_date.isoformat(),
        warranty_days="0",
        return_days="0",
    )

    assert is_valid is True
    assert errors == []
    assert values["purchase_date"] == purchase_date.isoformat()


@pytest.mark.parametrize("price", ["1e400", "1E400", "9" * 400, "1e1000"])
def test_validate_receipt_input_rejects_prices_too_large_to_convert(price):
    """Decimal.quantize raises InvalidOperation on huge values; it must not escape."""
    is_valid, errors, values = validate_receipt_input(
        product_name="Mouse",
        merchant_name="Store",
        price=price,
        purchase_date="2026-08-15",
        warranty_days="0",
        return_days="0",
    )

    assert is_valid is False
    assert errors == ["Price is too large."]
    assert values == {}


@pytest.mark.parametrize(
    ("field", "label"),
    [("warranty_days", "Warranty days"), ("return_days", "Return days")],
)
@pytest.mark.parametrize("value", ["99999999", "3652060", str(10**12)])
def test_validate_receipt_input_rejects_period_days_beyond_the_supported_range(
    field, label, value
):
    """Values that overflow date arithmetic must be rejected at the input boundary."""
    periods = {"warranty_days": "0", "return_days": "0"}
    periods[field] = value

    is_valid, errors, values = validate_receipt_input(
        product_name="Mouse",
        merchant_name="Store",
        price="1",
        purchase_date="2026-08-15",
        **periods,
    )

    assert is_valid is False
    assert errors == [f"{label} must be 36500 or fewer."]
    assert values == {}


@pytest.mark.parametrize(
    ("field", "label"),
    [("warranty_days", "Warranty days"), ("return_days", "Return days")],
)
def test_validate_receipt_input_accepts_the_maximum_supported_period(field, label):
    periods = {"warranty_days": "0", "return_days": "0"}
    periods[field] = "36500"

    is_valid, errors, values = validate_receipt_input(
        product_name="Mouse",
        merchant_name="Store",
        price="1",
        purchase_date="2026-08-15",
        **periods,
    )

    assert is_valid is True
    assert errors == []
    assert values[field] == 36500


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
