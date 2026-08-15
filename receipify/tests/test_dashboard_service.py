from datetime import date, timedelta

from app.models.receipt import Receipt
from app.services.dashboard_service import build_dashboard_summary


def make_receipt(receipt_id, product_name, category_name, price_cents, purchase_date, **periods):
    return Receipt(
        receipt_id=receipt_id,
        user_id=1,
        product_name=product_name,
        merchant_name="Store",
        category_name=category_name,
        price_cents=price_cents,
        purchase_date=purchase_date.isoformat(),
        warranty_days=periods.get("warranty_days", 0),
        return_days=periods.get("return_days", 0),
        image_path=None,
        created_at="2026-08-15 10:00:00",
    )


def test_dashboard_summary_calculates_totals_categories_and_expiry_lists():
    today = date.today()
    receipts = [
        make_receipt(
            1,
            "Laptop",
            "Electronics",
            120000,
            today - timedelta(days=5),
            warranty_days=20,
        ),
        make_receipt(
            2,
            "Blender",
            "Home",
            5000,
            today - timedelta(days=10),
            warranty_days=5,
        ),
        make_receipt(
            3,
            "Shoes",
            "Clothing",
            7000,
            today - timedelta(days=3),
            return_days=5,
        ),
        make_receipt(
            4,
            "Groceries",
            "Groceries",
            2000,
            today - timedelta(days=10),
            return_days=3,
        ),
    ]

    summary = build_dashboard_summary(receipts, recent_limit=2)

    assert summary.total_receipt_count == 4
    assert summary.total_spending_cents == 134000
    assert [receipt.product_name for receipt in summary.recent_receipts] == [
        "Shoes",
        "Laptop",
    ]
    assert dict(summary.category_spending) == {
        "Electronics": 120000,
        "Clothing": 7000,
        "Home": 5000,
        "Groceries": 2000,
    }
    assert [(item.receipt.product_name, item.period_name) for item in summary.expiring_soon] == [
        ("Shoes", "Return"),
        ("Laptop", "Warranty"),
    ]
    assert {(item.receipt.product_name, item.period_name) for item in summary.expired} == {
        ("Blender", "Warranty"),
        ("Groceries", "Return"),
    }


def test_dashboard_summary_handles_no_receipts():
    summary = build_dashboard_summary([])

    assert summary.total_receipt_count == 0
    assert summary.total_spending_cents == 0
    assert summary.recent_receipts == []
    assert summary.expiring_soon == []
    assert summary.expired == []
    assert summary.category_spending == []


def test_dashboard_summary_uses_configured_warning_thresholds():
    today = date.today()
    receipt = make_receipt(
        1,
        "Laptop",
        "Electronics",
        120000,
        today - timedelta(days=5),
        warranty_days=15,
    )

    summary = build_dashboard_summary(
        [receipt],
        warranty_warning_threshold=5,
    )

    assert summary.expiring_soon == []
