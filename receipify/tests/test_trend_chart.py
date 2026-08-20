import pytest

from app.ui.trend_chart import (
    MonthlyTrendChart,
    SpendingTrendDialog,
    available_ranges,
    format_month,
    format_month_range,
    take_recent_months,
)


def months(count, start_year=2025, start_month=1, amount=1000):
    """A run of consecutive months, e.g. 14 months from 2025-01."""
    timeline = {}
    year, month = start_year, start_month
    for index in range(count):
        timeline[f"{year}-{month:02d}"] = amount + index
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return timeline


def test_months_are_labelled_readably():
    assert format_month("2026-08") == "Aug 26"
    assert format_month("2026-08", short=False) == "Aug 2026"
    # A key that is not a month is shown as it is rather than crashing the draw.
    assert format_month("nonsense") == "nonsense"


def test_a_span_reads_from_its_first_month_to_its_last():
    assert format_month_range(["2025-11", "2025-12", "2026-01"]) == "Nov 2025 - Jan 2026"
    assert format_month_range(["2026-01"]) == "Jan 2026"
    assert format_month_range([]) == ""


def test_a_range_keeps_the_most_recent_months():
    timeline = months(5, start_month=1)

    assert list(take_recent_months(timeline, 2)) == ["2025-04", "2025-05"]
    assert list(take_recent_months(timeline, None)) == list(timeline)
    # Asking for more months than exist is not an error, it is everything.
    assert list(take_recent_months(timeline, 50)) == list(timeline)


def test_only_ranges_that_hide_something_are_offered():
    assert available_ranges(3) == [("All recorded months", None)]
    assert available_ranges(14) == [
        ("Last 6 months", 6),
        ("Last 12 months", 12),
        ("All recorded months", None),
    ]


def test_the_chart_plots_every_month_it_is_given(qapp):
    chart = MonthlyTrendChart()

    chart.plot({"2026-06": 8000, "2026-07": 0, "2026-08": 3499})

    line = chart.figure.axes[0].lines[0]
    assert list(line.get_ydata()) == [80.0, 0.0, 34.99]
    assert chart.months == ["2026-06", "2026-07", "2026-08"]


def test_an_empty_chart_carries_a_message_instead_of_bare_axes(qapp):
    chart = MonthlyTrendChart()

    chart.plot({})

    assert [text.get_text() for text in chart.figure.axes[0].texts] == [
        "No Spending Data Available"
    ]
    assert chart.months == []


@pytest.mark.parametrize("month_count", [2, 12, 40])
def test_x_labels_are_thinned_out_rather_than_left_to_collide(qapp, month_count):
    chart = MonthlyTrendChart()
    chart.resize(420, 260)

    chart.plot(months(month_count))

    labels = chart.figure.axes[0].get_xticklabels()
    # Whatever the history, the labels stay within the room the canvas has.
    assert len(labels) <= max(chart.width() // 58, 1)
    # The newest month is the one a reader looks for, so it is always labelled.
    assert labels[-1].get_text() == format_month(chart.months[-1])


def test_a_wider_chart_labels_more_of_the_months(qapp):
    narrow = MonthlyTrendChart()
    narrow.resize(360, 260)
    narrow.plot(months(24))

    wide = MonthlyTrendChart()
    wide.resize(1400, 260)
    wide.plot(months(24))

    assert len(wide.figure.axes[0].get_xticklabels()) > len(
        narrow.figure.axes[0].get_xticklabels()
    )


def test_double_clicking_the_small_chart_asks_for_the_enlarged_one(qapp):
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtGui import QMouseEvent

    chart = MonthlyTrendChart()
    requests = []
    chart.enlarge_requested.connect(lambda: requests.append(True))

    chart.mouseDoubleClickEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPoint(10, 10).toPointF(),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert requests == [True]


def test_the_enlarged_chart_shows_the_whole_history_by_default(qapp):
    dialog = SpendingTrendDialog(months(18))

    assert dialog.chart.months == list(months(18))
    assert dialog.range_label.text() == "Jan 2025 - Jun 2026"
    dialog.close()


def test_choosing_a_shorter_range_redraws_the_enlarged_chart(qapp):
    dialog = SpendingTrendDialog(months(18))

    dialog.range_selector.setCurrentIndex(0)

    assert dialog.range_selector.currentData() == 6
    assert dialog.chart.months == list(months(18))[-6:]
    assert dialog.range_label.text() == "Jan 2026 - Jun 2026"
    dialog.close()


def test_the_range_selector_is_hidden_when_there_is_only_one_range(qapp):
    dialog = SpendingTrendDialog(months(4))
    dialog.show()

    assert dialog.range_selector.isVisible() is False
    dialog.close()


def test_the_enlarged_chart_summarises_the_range_on_show(qapp):
    dialog = SpendingTrendDialog({"2026-06": 8000, "2026-07": 0, "2026-08": 4000})

    summary = dialog.summary_label.text()

    assert "3 months" in summary
    assert "Total EUR 120.00" in summary
    assert "Average EUR 40.00 a month" in summary
    assert "Highest Jun 2026 (EUR 80.00)" in summary
    dialog.close()


def test_an_empty_history_leaves_the_enlarged_chart_saying_so(qapp):
    dialog = SpendingTrendDialog({})

    assert dialog.range_label.text() == "Nothing has been recorded yet."
    assert dialog.summary_label.text() == ""
    dialog.close()


def test_full_screen_is_a_toggle_that_names_its_own_way_back(qapp):
    dialog = SpendingTrendDialog(months(6))
    dialog.show()

    dialog.toggle_full_screen()
    assert dialog.isFullScreen()
    assert dialog.full_screen_button.text() == "Exit full screen"

    dialog.toggle_full_screen()
    assert dialog.isFullScreen() is False
    assert dialog.full_screen_button.text() == "Full screen"
    dialog.close()


def test_escape_leaves_full_screen_before_it_closes_the_window(qapp):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent

    dialog = SpendingTrendDialog(months(6))
    dialog.show()
    dialog.toggle_full_screen()

    escape = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    dialog.keyPressEvent(escape)

    assert dialog.isFullScreen() is False
    assert dialog.isVisible()

    dialog.keyPressEvent(escape)

    assert dialog.isVisible() is False
