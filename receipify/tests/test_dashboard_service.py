from datetime import date, timedelta

from app.models.receipt import Receipt
from app.services.dashboard_service import build_dashboard_summary


def receipt(purchased="2026-01-01", cents=100, category="Tools", **periods):
    return Receipt(1, 1, "Tool", "Shop", category, cents, purchased,
                   periods.get("warranty_days", 0), periods.get("return_days", 0), None, purchased)


def test_all_time_summary_and_year_month_totals_agree():
    summary = build_dashboard_summary([
        receipt("2025-12-31", 999),
        receipt("2026-01-01", 1234),
        receipt("2026-01-31", 200),
        receipt("2026-12-31", 500, category="Home"),
        receipt("2027-01-01", 999),
    ])
    assert list(summary.monthly_spending) == [2025, 2026, 2027]
    assert summary.monthly_spending[2026] == [1434] + [0] * 10 + [500]
    assert summary.total_spending_cents == 3932
    assert list(summary.category_spending.items()) == [("Tools", 3432), ("Home", 500)]
    assert sum(map(sum, summary.monthly_spending.values())) == sum(summary.category_spending.values()) == summary.total_spending_cents


def test_empty_summary():
    summary = build_dashboard_summary([])
    assert summary.total_spending_cents == 0
    assert summary.monthly_spending == summary.category_spending == {}
    assert summary.active_warranties == summary.expired_warranties == 0
    assert summary.deadlines == []


def test_deadline_review_excludes_expired_and_keeps_today_and_day_30():
    today = date(2026, 9, 10)
    purchased = (today - timedelta(days=100)).isoformat()
    receipts = [receipt(purchased, warranty_days=days) for days in [131, 130, 99, 100, 105]]
    receipts.append(receipt(purchased, return_days=102))
    summary = build_dashboard_summary(receipts, today=today)
    assert summary.active_warranties == 4
    assert summary.expired_warranties == 1
    assert [(item.period_name, item.days_remaining) for item in summary.deadlines] == [
        ("Warranty", 0), ("Return", 2), ("Warranty", 5), ("Warranty", 30),
    ]


def test_invalid_dates_keep_all_time_amounts_but_cannot_be_charted():
    summary = build_dashboard_summary([
        receipt("invalid", warranty_days=10), receipt("2026-02-29"),
        receipt("2026-02-28", warranty_days=10**12),
    ])
    assert summary.total_spending_cents == 300
    assert summary.category_spending == {"Tools": 300}
    assert sum(summary.monthly_spending[2026]) == 100
    assert summary.deadlines == []
