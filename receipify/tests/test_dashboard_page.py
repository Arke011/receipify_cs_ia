from datetime import date, timedelta

from PyQt6.QtWidgets import QLabel, QProgressBar

from app.data.data_manager import DataManager
from app.ui.dashboard_page import DashboardPage, format_currency
from app.ui.main_window import MainWindow


def build_page(tmp_path, receipts=()):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    for values in receipts:
        data_manager.add_receipt(user_id=1, **values)

    return DashboardPage(data_manager, user_id=1)


def receipt_values(product_name, price_cents, purchase_date, **overrides):
    values = {
        "product_name": product_name,
        "merchant_name": "Tech Store",
        "category_name": "Electronics",
        "price_cents": price_cents,
        "purchase_date": purchase_date,
        "warranty_days": 0,
        "return_days": 0,
    }
    values.update(overrides)
    return values


def category_amounts(page):
    return [
        label.text()
        for label in page.category_layout.parentWidget().findChildren(QLabel)
        if label.objectName() == "categoryAmount"
    ]


def widgets_in(layout, widget_type):
    return [
        layout.itemAt(index).widget()
        for index in range(layout.count())
        if isinstance(layout.itemAt(index).widget(), widget_type)
    ]


def test_currency_is_formatted_with_thousands_separators():
    assert format_currency(124550) == "EUR 1,245.50"
    assert format_currency(0) == "EUR 0.00"
    assert format_currency(99) == "EUR 0.99"


def test_stat_cards_show_spending_and_warranty_counts(qapp, tmp_path):
    today = date.today()
    page = build_page(
        tmp_path,
        [
            receipt_values(
                "Laptop", 120000, (today - timedelta(days=10)).isoformat(), warranty_days=365
            ),
            receipt_values(
                "Blender", 4550, (today - timedelta(days=400)).isoformat(), warranty_days=30
            ),
        ],
    )

    assert page.total_spending_value.text() == "EUR 1,245.50"
    assert page.active_warranties_value.text() == "1"
    assert page.expired_records_value.text() == "1"


def test_category_bars_show_each_share_of_the_total(qapp, tmp_path):
    page = build_page(
        tmp_path,
        [
            receipt_values("Blender", 7500, "2026-08-15", category_name="Kitchen"),
            receipt_values("Mouse", 2500, "2026-08-15", category_name="Electronics"),
        ],
    )

    bars = page.category_layout.parentWidget().findChildren(QProgressBar)

    # Bars are filled in tenths of a percent so they match the printed share.
    assert [(bar.value(), bar.maximum()) for bar in bars] == [(750, 1000), (250, 1000)]

    assert category_amounts(page) == ["75.0%  ·  EUR 75.00", "25.0%  ·  EUR 25.00"]


def test_category_shares_keep_a_decimal_place(qapp, tmp_path):
    """Whole percentages rounded three near-equal categories to 33/33/33."""
    page = build_page(
        tmp_path,
        [
            receipt_values("Blender", 5000, "2026-08-15", category_name="Kitchen"),
            receipt_values("Mouse", 3000, "2026-08-15", category_name="Electronics"),
            receipt_values("Socks", 1000, "2026-08-15", category_name="Clothing"),
        ],
    )

    assert category_amounts(page) == [
        "55.6%  ·  EUR 50.00",
        "33.3%  ·  EUR 30.00",
        "11.1%  ·  EUR 10.00",
    ]

    bars = page.category_layout.parentWidget().findChildren(QProgressBar)
    assert [bar.value() for bar in bars] == [556, 333, 111]


def test_deadline_rows_are_badged_and_exclude_expired_items(qapp, tmp_path):
    today = date.today()
    page = build_page(
        tmp_path,
        [
            receipt_values(
                "Shoes", 8999, (today - timedelta(days=27)).isoformat(), return_days=30
            ),
            receipt_values(
                "Cable", 999, (today - timedelta(days=60)).isoformat(), warranty_days=30
            ),
        ],
    )

    badges = [
        label
        for label in page.deadline_layout.parentWidget().findChildren(QLabel)
        if label.objectName() == "statusBadge"
    ]

    assert [badge.text() for badge in badges] == ["Expiring soon"]
    assert [badge.property("statusColor") for badge in badges] == ["orange"]


def test_an_empty_account_shows_placeholders_instead_of_broken_charts(qapp, tmp_path):
    page = build_page(tmp_path)

    assert page.total_spending_value.text() == "EUR 0.00"
    assert page.active_warranties_value.text() == "0"

    placeholders = [
        label.text()
        for label in page.findChildren(QLabel)
        if label.objectName() == "dashboardEmpty"
    ]
    assert "No Spending Data Available" in placeholders
    assert "Nothing is expiring in the next 30 days." in placeholders

    # Empty accounts retain a useful chart placeholder.
    chart_texts = [text.get_text() for text in page.trend_chart.figure.axes[0].texts]
    assert chart_texts == ["No Spending Data Available"]


def test_chart_selector_changes_only_chart_and_does_not_reload_receipts(qapp, tmp_path, monkeypatch):
    from unittest.mock import Mock

    page = build_page(tmp_path, [
        receipt_values("Mouse", 1234, "2026-01-15"),
        receipt_values("Cable", 200, "2026-12-31"),
        receipt_values("Blender", 5000, "2024-06-15", category_name="Kitchen"),
    ])
    manager = page.data_manager
    read = Mock(wraps=manager.get_all_receipts)
    monkeypatch.setattr(manager, "get_all_receipts", read)
    page.refresh()
    assert read.call_count == 1
    assert page.trend_chart.labels == ["2024", "2025", "2026"]
    assert page.trend_chart.cents == [5000, 0, 1434]
    assert page.total_spending_value.text() == "EUR 64.34"
    before = category_amounts(page)
    page.year_selector.setCurrentIndex(page.year_selector.findData(2026))
    assert page.trend_chart.cents == [1234] + [0] * 10 + [200]
    assert page.trend_chart.labels == ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    assert read.call_count == 1
    assert page.total_spending_value.text() == "EUR 64.34"
    assert category_amounts(page) == before
    page.year_selector.setCurrentIndex(0)
    assert page.trend_chart.cents == [5000, 0, 1434]


def test_chart_selection_survives_crud_and_missing_year_returns_to_all(qapp, tmp_path):
    manager = DataManager(tmp_path / "test.db")
    values = receipt_values("Mouse", 1000, "2026-01-01")
    receipt_id = manager.add_receipt(**values)
    window = MainWindow(data_manager=manager, user_id=1)
    page = window.dashboard_page
    page.year_selector.setCurrentIndex(page.year_selector.findData(2026))
    another_id = manager.add_receipt(**receipt_values("Cable", 500, "2026-01-02"))
    window.receipts_changed.emit()
    assert page.trend_chart.cents[0] == 1500
    assert page.year_selector.currentData() == 2026
    manager.update_receipt(receipt_id, "Mouse", "Tech Store", "Electronics", 2000, "2026-02-01", 0, 0)
    window.receipts_changed.emit()
    assert page.trend_chart.cents[:2] == [500, 2000]
    assert page.total_spending_value.text() == "EUR 25.00"
    manager.delete_receipt(receipt_id)
    manager.delete_receipt(another_id)
    window.receipts_changed.emit()
    assert page.year_selector.currentData() is None
    assert page.trend_chart.cents == []
    assert window.export_page.receipt_list.count() == 0
    window.close()


def test_chart_and_category_data_are_scoped_to_signed_in_user(qapp, tmp_path):
    manager = DataManager(tmp_path / "test.db")
    other = manager.create_user("other", "password123")
    manager.add_receipt(user_id=other, **receipt_values("Private", 5000, "2020-01-01"))
    page = DashboardPage(manager, 1)
    assert page.total_spending_value.text() == "EUR 0.00"
    assert page.year_selector.count() == 1
    assert category_amounts(page) == []


def test_refresh_hides_old_category_and_deadline_rows_before_deferred_deletion(qapp, tmp_path):
    today = date.today()
    page = build_page(tmp_path, [receipt_values(
        "Mouse", 1000, (today - timedelta(days=5)).isoformat(), return_days=10,
    )])
    page.show()
    qapp.processEvents()
    old_category = page.category_layout.itemAt(0).widget()
    old_deadline = page.deadline_layout.itemAt(0).widget()
    page.refresh()
    # The event loop has not deleted these yet: they must not remain painted.
    assert old_category.isHidden()
    assert old_deadline.isHidden()
    qapp.processEvents()
    assert not page.category_layout.itemAt(0).widget().isHidden()
    page.close()
