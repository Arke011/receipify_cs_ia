from datetime import date, timedelta

import pytest

from receipt import format_euros, validate_receipt


def form(**changes):
    """The receipt form's text, valid unless changed."""
    values = {"product": "Mouse", "merchant": "Store", "category": "", "price": "1",
              "purchase_date": "2026-08-15", "warranty_days": "0", "return_days": "0"}
    values.update(changes)
    return values


def test_valid_form_is_cleaned_ready_to_store():
    errors, values = validate_receipt(**form(product="  Wireless Mouse ", merchant=" Tech Store ", price="24,995",
                                             purchase_date="2026-8-5", warranty_days="365", return_days="30"))
    assert errors == []
    assert values == {
        "product": "Wireless Mouse",
        "merchant": "Tech Store",
        "category": "Uncategorised",
        "price_cents": 2500,  # decimal comma accepted, half a cent rounded up
        "purchase_date": "2026-08-05",
        "warranty_days": 365,
        "return_days": 30,
    }


@pytest.mark.parametrize(("changes", "message"), [
    ({"price": "abc"}, "Price must be numeric."),
    ({"price": "NaN"}, "Price must be numeric."),
    ({"price": "0"}, "Price must be greater than 0."),
    ({"price": "1e400"}, "Price is too large."),
    ({"purchase_date": (date.today() + timedelta(days=1)).isoformat()}, "Purchase date cannot be in the future."),
    ({"warranty_days": "36501"}, "Warranty days must be 36500 or fewer."),
])
def test_invalid_values_are_rejected(changes, message):
    assert validate_receipt(**form(**changes)) == ([message], {})


def test_every_problem_is_reported_at_once():
    errors, _ = validate_receipt(**form(product=" ", merchant="", purchase_date="15-08-2026",
                                        warranty_days="-1", return_days="one"))
    assert errors == [
        "Product name cannot be empty.",
        "Merchant name cannot be empty.",
        "Purchase date must be a valid date in YYYY-MM-DD format.",
        "Warranty days must be greater than or equal to 0.",
        "Return days must be an integer.",
    ]


@pytest.mark.parametrize(("warranty_days", "status"), [
    (0, "no warranty period"),
    (5, "expired"),  # ended 5 days ago
    (10, "expiring soon"),  # ends today
    (40, "expiring soon"),  # 30 days left: the last day of the warning period
    (41, "active"),
])
def test_warranty_status_depends_on_days_left(make_receipt, warranty_days, status):
    purchased = (date.today() - timedelta(days=10)).isoformat()
    receipt = make_receipt(purchase_date=purchased, warranty_days=warranty_days)
    assert receipt.warranty_status(30) == status


@pytest.mark.parametrize("changes", [
    {"purchase_date": "15/08/2026"},
    {"purchase_date": "2026-02-30"},
    {"warranty_days": 3652060},  # past the year 9999
    {"warranty_days": 10**12},
])
def test_unusable_stored_data_counts_as_no_period(make_receipt, changes):
    receipt = make_receipt(**changes)
    assert receipt.warranty_expiry() is None
    assert receipt.warranty_status(30) == "no warranty period"


def test_money_is_shown_with_thousands_separators():
    assert format_euros(124550) == "EUR 1,245.50"
    assert format_euros(99) == "EUR 0.99"
