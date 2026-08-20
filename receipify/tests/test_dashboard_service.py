from datetime import date, timedelta

import pytest

from app.data.data_manager import DataManager
from app.models.receipt import Receipt
from app.services.dashboard_service import (
    DashboardService,
    build_dashboard_summary,
    fill_month_gaps,
)


@pytest.fixture
def service(tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    return DashboardService(data_manager)


def store_receipt(service, product_name, price_cents, purchase_date, **overrides):
    values = {
        "product_name": product_name,
        "merchant_name": "Tech Store",
        "category_name": "Electronics",
        "price_cents": price_cents,
        "purchase_date": purchase_date,
        "warranty_days": 0,
        "return_days": 0,
        "user_id": 1,
    }
    values.update(overrides)
    return service.data_manager.add_receipt(**values)


def test_total_spending_covers_only_the_requested_user(service):
    alice_id = service.data_manager.register_user("alice", "password123")
    bob_id = service.data_manager.register_user("bob", "password123")
    store_receipt(service, "Mouse", 2499, "2026-08-15", user_id=alice_id)
    store_receipt(service, "Keyboard", 5000, "2026-08-16", user_id=alice_id)
    store_receipt(service, "Someone else's", 9900, "2026-08-16", user_id=bob_id)

    assert service.get_total_spending(alice_id) == 7499
    assert service.get_total_spending(bob_id) == 9900


def test_active_and_expired_counts_ignore_receipts_without_a_warranty(service):
    today = date.today()
    store_receipt(
        service, "Live", 1000, (today - timedelta(days=10)).isoformat(), warranty_days=365
    )
    store_receipt(
        service, "Lapsed", 1000, (today - timedelta(days=400)).isoformat(), warranty_days=30
    )
    store_receipt(service, "No warranty", 1000, today.isoformat(), warranty_days=0)

    assert service.get_active_and_expired_counts(1) == {"active": 1, "expired": 1}


def test_category_spending_totals_by_category_largest_first(service):
    store_receipt(service, "Mouse", 2499, "2026-08-15", category_name="Electronics")
    store_receipt(service, "Cable", 999, "2026-08-15", category_name="Electronics")
    store_receipt(service, "Blender", 8000, "2026-08-15", category_name="Kitchen")

    assert service.get_category_spending(1) == {"Kitchen": 8000, "Electronics": 3498}


def test_monthly_spending_is_grouped_and_ordered_by_month(service):
    store_receipt(service, "Mouse", 2499, "2026-08-15")
    store_receipt(service, "Cable", 1000, "2026-08-02")
    store_receipt(service, "Blender", 8000, "2026-06-30")

    assert service.get_monthly_spending(1) == {"2026-06": 8000, "2026-08": 3499}


def test_the_monthly_timeline_carries_the_months_in_between(service):
    store_receipt(service, "Mouse", 2499, "2026-08-15")
    store_receipt(service, "Blender", 8000, "2026-05-30")

    # June and July hold no receipts, but they are still months the user lived
    # through, so the timeline reports them as spending nothing.
    assert service.get_monthly_timeline(1) == {
        "2026-05": 8000,
        "2026-06": 0,
        "2026-07": 0,
        "2026-08": 2499,
    }


def test_the_timeline_does_not_reach_beyond_the_recorded_months(service):
    store_receipt(service, "Mouse", 2499, "2026-08-15")

    # One month of receipts is one month of history: months before the first
    # receipt are months that were never recorded, not months of no spending.
    assert service.get_monthly_timeline(1) == {"2026-08": 2499}


def test_the_timeline_of_an_empty_account_is_empty(service):
    assert service.get_monthly_timeline(1) == {}


def test_filling_month_gaps_crosses_the_turn_of_the_year():
    assert fill_month_gaps({"2025-11": 500, "2026-02": 300}) == {
        "2025-11": 500,
        "2025-12": 0,
        "2026-01": 0,
        "2026-02": 300,
    }


def test_filling_month_gaps_leaves_an_unreadable_key_alone():
    """A month that cannot be parsed must not turn the loop into a long one."""
    assert fill_month_gaps({"whenever": 100}) == {"whenever": 100}


def test_upcoming_deadlines_are_within_the_window_and_soonest_first(service):
    today = date.today()
    store_receipt(
        service, "Soon", 1000, (today - timedelta(days=25)).isoformat(), warranty_days=30
    )
    store_receipt(
        service, "Overdue", 1000, (today - timedelta(days=40)).isoformat(), return_days=30
    )
    store_receipt(
        service, "Far off", 1000, today.isoformat(), warranty_days=365
    )

    deadlines = service.get_upcoming_deadlines(1, days=30)

    assert [(item.receipt.product_name, item.period_name) for item in deadlines] == [
        ("Overdue", "Return"),
        ("Soon", "Warranty"),
    ]
    assert deadlines[0].days_remaining == -10
    assert deadlines[1].days_remaining == 5


def test_every_metric_handles_an_empty_account(service):
    assert service.get_total_spending(1) == 0
    assert service.get_active_and_expired_counts(1) == {"active": 0, "expired": 0}
    assert service.get_category_spending(1) == {}
    assert service.get_monthly_spending(1) == {}
    assert service.get_monthly_timeline(1) == {}
    assert service.get_upcoming_deadlines(1) == []


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
