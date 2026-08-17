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

    assert [bar.value() for bar in bars] == [75, 25]

    amounts = [
        label.text()
        for label in page.category_layout.parentWidget().findChildren(QLabel)
        if label.objectName() == "categoryAmount"
    ]
    assert amounts == ["75%  ·  EUR 75.00", "25%  ·  EUR 25.00"]


def test_deadline_rows_are_badged_by_status(qapp, tmp_path):
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

    assert [badge.text() for badge in badges] == ["Expired", "Expiring soon"]
    assert [badge.property("statusColor") for badge in badges] == ["red", "orange"]


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

    # The chart still draws: it carries the same message rather than empty axes.
    chart_texts = [text.get_text() for text in page.trend_chart.figure.axes[0].texts]
    assert chart_texts == ["No Spending Data Available"]


def test_the_chart_plots_one_point_per_month(qapp, tmp_path):
    page = build_page(
        tmp_path,
        [
            receipt_values("Mouse", 2499, "2026-08-15"),
            receipt_values("Cable", 1000, "2026-08-02"),
            receipt_values("Blender", 8000, "2026-06-30"),
        ],
    )

    line = page.trend_chart.figure.axes[0].lines[0]

    assert list(line.get_ydata()) == [80.0, 34.99]
    assert [str(label) for label in line.get_xdata()] == ["2026-06", "2026-08"]


def test_the_dashboard_updates_when_receipts_change(monkeypatch, qapp, tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    window = MainWindow(data_manager=data_manager, user_id=1)

    assert window.dashboard_page.total_spending_value.text() == "EUR 0.00"

    data_manager.add_receipt(user_id=1, **receipt_values("Mouse", 2499, "2026-08-15"))
    window.receipts_changed.emit()

    assert window.dashboard_page.total_spending_value.text() == "EUR 24.99"
    assert window.export_page.receipt_list.count() == 1
    window.close()
