from datetime import date, timedelta

from PyQt6.QtWidgets import QLabel

from dashboard import DashboardPage, summarize


def test_totals_by_month_and_category_agree(make_receipt):
    summary = summarize([
        make_receipt(purchase_date="2025-12-31", price_cents=999),
        make_receipt(purchase_date="2026-01-01", price_cents=1234),
        make_receipt(purchase_date="2026-01-31", price_cents=200),
        make_receipt(purchase_date="2026-12-31", price_cents=500, category="Home"),
    ])
    assert summary.total_cents == 2933
    assert summary.by_month == {2025: [0] * 11 + [999], 2026: [1434] + [0] * 10 + [500]}
    assert list(summary.by_category.items()) == [("Electronics", 2433), ("Home", 500)]  # largest first


def test_deadlines_run_from_today_to_30_days_ahead(make_receipt):
    today = date(2026, 9, 10)
    purchased = (today - timedelta(days=100)).isoformat()
    receipts = [make_receipt(purchase_date=purchased, warranty_days=days, return_days=0)
                for days in (131, 130, 99, 100, 105)]  # 31, 30, -1, 0 and 5 days left
    receipts.append(make_receipt(purchase_date=purchased, warranty_days=0, return_days=102))
    summary = summarize(receipts, today)
    assert (summary.active_warranties, summary.expired_warranties) == (4, 1)
    assert [(d.period, d.days_left) for d in summary.deadlines] == [
        ("Warranty", 0), ("Return", 2), ("Warranty", 5), ("Warranty", 30),
    ]


def test_unusable_dates_count_in_totals_but_not_on_the_chart(make_receipt):
    summary = summarize([
        make_receipt(purchase_date="invalid", price_cents=100),
        make_receipt(purchase_date="2026-02-28", price_cents=100, warranty_days=10**12),
    ])
    assert summary.total_cents == 200
    assert sum(summary.by_month[2026]) == 100
    assert summary.deadlines == []


def test_page_shows_totals_categories_and_a_chart_for_the_chosen_year(db, add_receipt):
    untracked = {"warranty_days": 0, "return_days": 0}
    add_receipt(price_cents=1234, purchase_date="2026-01-15", **untracked)
    add_receipt(price_cents=200, purchase_date="2026-03-31", **untracked)
    add_receipt(price_cents=5000, purchase_date="2024-06-15", category="Kitchen", **untracked)
    page = DashboardPage(db, 1)
    assert page.total_label.text() == "EUR 64.34"
    assert [label.text() for label in page.findChildren(QLabel) if "%" in label.text()] == [
        "77.7%  ·  EUR 50.00", "22.3%  ·  EUR 14.34"]
    assert (page.chart.labels, page.chart.cents) == (["2024", "2025", "2026"], [5000, 0, 1434])  # 2025 shown as 0

    page.year_selector.setCurrentIndex(page.year_selector.findData(2026))
    assert page.chart.labels[:3] == ["Jan", "Feb", "Mar"]
    assert page.chart.cents == [1234, 0, 200] + [0] * 9
    page.refresh()
    assert page.year_selector.currentData() == 2026  # the chosen year survives a refresh


def test_page_lists_only_deadlines_still_ahead(db, add_receipt):
    today = date.today()
    add_receipt(product="Shoes", purchase_date=(today - timedelta(days=27)).isoformat(), warranty_days=0, return_days=30)
    add_receipt(product="Cable", purchase_date=(today - timedelta(days=60)).isoformat(), warranty_days=30, return_days=0)
    page = DashboardPage(db, 1)
    texts = [label.text() for label in page.findChildren(QLabel)]
    assert "Shoes" in texts
    assert "Cable" not in texts  # already expired
    assert texts.count("Expiring soon") == 1
    assert (page.active_label.text(), page.expired_label.text()) == ("0", "1")
