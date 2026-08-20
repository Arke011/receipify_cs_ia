from datetime import date, timedelta

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QProgressBar

from app.data.data_manager import DataManager
from app.ui.dashboard_page import (
    CATEGORY_BAR_FILL_COLOUR,
    CATEGORY_BAR_HEIGHT,
    CATEGORY_BAR_SCALE,
    CategoryBar,
    DashboardPage,
    format_currency,
)
from app.ui.main_window import MainWindow
from app.ui.trend_chart import SpendingTrendDialog


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


def render_bar(share_percent, width=400):
    """A category bar drawn to an image, so its shape can be inspected."""
    from PyQt6.QtGui import QImage

    bar = CategoryBar()
    bar.setRange(0, CATEGORY_BAR_SCALE)
    bar.setValue(round(share_percent * CATEGORY_BAR_SCALE / 100))
    bar.setTextVisible(False)
    bar.setFixedSize(width, CATEGORY_BAR_HEIGHT)

    image = QImage(bar.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    bar.render(image)
    return image


def looks_filled(image, x, y, tolerance=24):
    """Whether a pixel carries the fill colour, allowing for antialiasing.

    The edges of the fill are blended into whatever sits behind them, and the
    two ends do not sit on the same backdrop: the left one overlaps the rounded
    end of the track itself. Comparing exact colours would therefore call two
    identical shapes different.
    """
    from PyQt6.QtGui import QColor

    pixel = image.pixelColor(x, y)
    fill = QColor(CATEGORY_BAR_FILL_COLOUR)

    return all(
        abs(getattr(pixel, channel)() - getattr(fill, channel)()) <= tolerance
        for channel in ("red", "green", "blue")
    )


def end_profile(image, x):
    """Which pixels down one column of the bar are filled."""
    return [looks_filled(image, x, y) for y in range(CATEGORY_BAR_HEIGHT)]


# A fill at least as wide as the bar is tall carries a full round end of its
# own; a narrower one is cut back by the round end of the track instead.
FULL_END_SHARE = 100 * CATEGORY_BAR_HEIGHT / 400


@pytest.mark.parametrize("share_percent", [3, 4, 4.5, 8, 40, 100])
def test_category_bars_keep_both_ends_round_at_any_share(qapp, share_percent):
    """Qt drew a small fill as a rectangle, or rounded one end and squared the other."""
    assert share_percent >= FULL_END_SHARE
    image = render_bar(share_percent)
    fill_width = round(400 * share_percent / 100)

    left = end_profile(image, 0)
    right = end_profile(image, fill_width - 1)

    # The two ends of the fill are cut to the same shape as each other...
    assert left == right
    # ... and that shape is a round one: the corners are cut away, the middle
    # of the column is not.
    assert left[0] is False
    assert left[-1] is False
    assert left[CATEGORY_BAR_HEIGHT // 2] is True


@pytest.mark.parametrize("share_percent", [0.05, 0.1, 0.3, 0.8, 1, 2, 3, 25, 100])
def test_a_fill_never_reaches_outside_the_track(qapp, share_percent):
    """A tiny share used to stand a full-height line against the track's curve.

    The track narrows to nothing at its rounded end, so a fill drawn to the
    full height of the bar hung outside the shape it was supposed to be sitting
    in. Every pixel the fill covers now has to be one the full bar covers too.
    """
    image = render_bar(share_percent)
    track = render_bar(100)

    outside = [
        (x, y)
        for x in range(400)
        for y in range(CATEGORY_BAR_HEIGHT)
        if looks_filled(image, x, y) and not looks_filled(track, x, y)
    ]

    assert outside == []


def test_a_category_bar_fills_only_as_far_as_its_share(qapp):
    image = render_bar(25)
    middle = CATEGORY_BAR_HEIGHT // 2

    assert looks_filled(image, 98, middle)
    # The fill stops at a quarter of the bar rather than being widened to look
    # better, so a small share still reads as a small share.
    assert not looks_filled(image, 104, middle)


def test_a_category_bar_with_nothing_in_it_draws_no_fill(qapp):
    image = render_bar(0)

    assert not any(
        looks_filled(image, x, CATEGORY_BAR_HEIGHT // 2) for x in range(400)
    )


def test_a_bar_with_no_range_is_treated_as_empty(qapp):
    """A category total of zero would otherwise divide by zero mid-paint."""
    bar = CategoryBar()
    bar.setRange(0, 0)

    assert bar.filled_fraction() == 0.0


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


def test_the_chart_plots_one_point_per_month_including_empty_ones(qapp, tmp_path):
    page = build_page(
        tmp_path,
        [
            receipt_values("Mouse", 2499, "2026-08-15"),
            receipt_values("Cable", 1000, "2026-08-02"),
            receipt_values("Blender", 8000, "2026-06-30"),
        ],
    )

    line = page.trend_chart.figure.axes[0].lines[0]

    # July holds no receipts, so it is plotted as zero instead of joining June
    # straight onto August as though the two were neighbouring months.
    assert page.trend_chart.months == ["2026-06", "2026-07", "2026-08"]
    assert list(line.get_ydata()) == [80.0, 0.0, 34.99]


def test_the_chart_panel_states_the_span_it_covers(qapp, tmp_path):
    page = build_page(
        tmp_path,
        [
            receipt_values("Blender", 8000, "2026-06-30"),
            receipt_values("Mouse", 2499, "2026-08-15"),
        ],
    )

    assert page.trend_range_label.text() == "Jun 2026 - Aug 2026"
    assert page.enlarge_button.isEnabled()


def test_the_enlarge_button_is_dead_until_there_is_something_to_show(qapp, tmp_path):
    page = build_page(tmp_path)

    assert page.enlarge_button.isEnabled() is False


def test_enlarging_opens_the_chart_over_the_same_months(qapp, tmp_path, monkeypatch):
    page = build_page(
        tmp_path,
        [
            receipt_values("Blender", 8000, "2026-06-30"),
            receipt_values("Mouse", 2499, "2026-08-15"),
        ],
    )
    opened = []
    # exec() would block on a modal window, so the dialog is only shown.
    monkeypatch.setattr(SpendingTrendDialog, "exec", lambda dialog: opened.append(dialog))

    page.enlarge_button.click()

    assert len(opened) == 1
    assert opened[0].chart.months == ["2026-06", "2026-07", "2026-08"]
    assert opened[0].chart.detailed is True


def test_the_dashboard_updates_when_receipts_change(monkeypatch, qapp, tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")
    window = MainWindow(data_manager=data_manager, user_id=1)

    assert window.dashboard_page.total_spending_value.text() == "EUR 0.00"

    data_manager.add_receipt(user_id=1, **receipt_values("Mouse", 2499, "2026-08-15"))
    window.receipts_changed.emit()

    assert window.dashboard_page.total_spending_value.text() == "EUR 24.99"
    assert window.export_page.receipt_list.count() == 1
    window.close()
