import pytest

from app.models.receipt import Receipt
from app.services.dashboard_service import build_dashboard_summary


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
        "image_path": None,
        "created_at": "2026-08-15 10:00:00",
    }
    values.update(overrides)
    return Receipt(**values)


@pytest.mark.parametrize(
    "stored_date",
    ["", "15/08/2026", "2026-13-45", "not-a-date", "2026-02-30"],
)
def test_malformed_stored_purchase_dates_render_as_untracked(stored_date):
    """A corrupt date already in the database must not crash the gallery."""
    receipt = make_receipt(purchase_date=stored_date)

    assert receipt.warranty_expiry_date() is None
    assert receipt.return_expiry_date() is None
    assert receipt.days_until_warranty_expiry() is None
    assert receipt.days_until_return_expiry() is None
    assert receipt.warranty_status()["color"] == "grey"
    assert receipt.return_status()["color"] == "grey"


@pytest.mark.parametrize("period_days", [99999999, 3652060, 10**12])
def test_out_of_range_period_days_render_as_untracked(period_days):
    """Day counts beyond date.max must not raise OverflowError while rendering."""
    receipt = make_receipt(warranty_days=period_days, return_days=period_days)

    assert receipt.warranty_expiry_date() is None
    assert receipt.return_expiry_date() is None
    assert receipt.warranty_status()["label"] == "no warranty period"
    assert receipt.return_status()["label"] == "no return period"


def test_dashboard_survives_receipts_with_unusable_dates():
    receipts = [
        make_receipt(receipt_id=1, warranty_days=99999999),
        make_receipt(receipt_id=2, purchase_date="15/08/2026"),
        make_receipt(receipt_id=3, product_name="Valid", warranty_days=10),
    ]

    summary = build_dashboard_summary(receipts)

    assert summary.total_receipt_count == 3
    assert [item.receipt.product_name for item in summary.expiring_soon] == ["Valid"]
