from datetime import date, timedelta

import pytest

from app.ui.trend_chart import (
    DAY,
    MONTH,
    YEAR,
    SpendingChart,
    SpendingTrendDialog,
    StatisticsDialog,
    format_date_range,
    format_period,
    group_spending,
    periods_within,
    resolution_for_span,
    spending_in_periods,
    to_dates,
)


def daily(*pairs):
    """Spending as the service hands it over: {'YYYY-MM-DD': cents}."""
    return {day: cents for day, cents in pairs}


def spread_over(days, start="2026-01-01", cents=1000):
    """A purchase on every nth day from a starting date."""
    first = date.fromisoformat(start)
    return {(first + timedelta(days=n)).isoformat(): cents + n for n in range(days)}


def x_labels(chart):
    return [label.get_text() for label in chart.figure.axes[0].get_xticklabels()]


def plotted_dates(chart):
    return chart.periods


# ---------------------------------------------------------------- plain functions


def test_unreadable_dates_are_left_out_rather_than_plotted():
    assert to_dates({"2026-08-15": 100, "whenever": 500}) == {date(2026, 8, 15): 100}


def test_spending_is_totalled_over_the_period_it_falls_in():
    spending = to_dates(daily(("2026-01-05", 100), ("2026-01-20", 50), ("2026-03-02", 700)))

    assert group_spending(spending, DAY) == {
        date(2026, 1, 5): 100,
        date(2026, 1, 20): 50,
        date(2026, 3, 2): 700,
    }
    # February holds nothing, and so appears nowhere: a zero there would be a
    # point on the chart that no purchase stands behind.
    assert group_spending(spending, MONTH) == {date(2026, 1, 1): 150, date(2026, 3, 1): 700}
    assert group_spending(spending, YEAR) == {date(2026, 1, 1): 850}


def test_the_grain_follows_how_much_time_is_on_screen():
    assert resolution_for_span(20) == DAY
    assert resolution_for_span(120) == DAY
    assert resolution_for_span(121) == MONTH
    assert resolution_for_span(4 * 365) == MONTH
    assert resolution_for_span(4 * 365 + 1) == YEAR


def test_periods_are_written_the_way_their_grain_reads():
    assert format_period(date(2026, 8, 1), YEAR) == "2026"
    assert format_period(date(2026, 8, 1), MONTH) == "Aug 2026"
    assert format_period(date(2026, 8, 4), DAY) == "04 Aug 2026"


def test_a_span_reads_from_its_first_month_to_its_last():
    assert format_date_range(date(2025, 11, 2), date(2026, 1, 30)) == "Nov 2025 - Jan 2026"
    assert format_date_range(date(2026, 1, 2), date(2026, 1, 30)) == "Jan 2026"
    assert format_date_range(None, None) == ""


def test_a_window_keeps_only_the_points_inside_it():
    grouped = group_spending(
        to_dates(daily(("2026-01-05", 100), ("2026-02-05", 200), ("2026-03-05", 300))), MONTH
    )

    kept = periods_within(grouped, date(2026, 2, 1), date(2026, 2, 20))

    assert kept == {date(2026, 2, 1): 200}


def test_the_purchases_behind_a_point_include_the_rest_of_its_month():
    """A month is plotted at its start, but its spending runs to its end."""
    spending = to_dates(daily(("2026-02-05", 200), ("2026-02-26", 700), ("2026-03-05", 300)))

    behind = spending_in_periods(spending, [date(2026, 2, 1)], MONTH)

    assert behind == {date(2026, 2, 5): 200, date(2026, 2, 26): 700}


# ------------------------------------------------------------------- small chart


def test_the_small_chart_plots_only_the_periods_that_hold_spending(qapp):
    chart = SpendingChart()

    chart.show_spending(daily(("2026-01-15", 8000), ("2026-04-20", 3000)))

    # February and March are missing from the data, and stay missing: the line
    # simply runs across the months nothing was bought in.
    assert plotted_dates(chart) == [date(2026, 1, 1), date(2026, 4, 1)]
    assert list(chart.figure.axes[0].lines[0].get_ydata()) == [80.0, 30.0]


def test_the_small_chart_is_scaled_in_years(qapp):
    chart = SpendingChart()

    chart.show_spending(spread_over(400, start="2025-06-01"))

    # Even over more than a year of daily purchases the axis stays a year scale.
    assert x_labels(chart) == ["2026"]


def test_the_small_chart_keeps_one_point_a_month_however_short_the_history(qapp):
    """A small panel is read as a shape, not looked up day by day."""
    chart = SpendingChart()

    chart.show_spending(spread_over(40, start="2026-01-01"))

    assert chart.resolution == MONTH
    assert plotted_dates(chart) == [date(2026, 1, 1), date(2026, 2, 1)]


def test_a_year_scale_names_the_year_when_the_span_sits_inside_one(qapp):
    chart = SpendingChart()

    chart.show_spending(daily(("2026-07-15", 8000), ("2026-08-20", 3000)))

    assert x_labels(chart) == ["2026"]


def test_a_multi_year_chart_is_marked_at_each_year(qapp):
    chart = SpendingChart()

    chart.show_spending(daily(("2024-05-01", 100), ("2025-06-01", 200), ("2026-07-01", 300)))

    assert x_labels(chart) == ["2025", "2026"]


def test_a_single_purchase_is_given_room_either_side_of_itself(qapp):
    chart = SpendingChart()

    chart.show_spending(daily(("2026-08-15", 8000)))

    first, last = chart.view
    assert first < date(2026, 8, 15) < last
    # One purchase, one point: the month it falls in, and nothing either side.
    assert plotted_dates(chart) == [date(2026, 8, 1)]


def test_an_empty_chart_carries_a_message_instead_of_bare_axes(qapp):
    chart = SpendingChart()

    chart.show_spending({})

    assert [text.get_text() for text in chart.figure.axes[0].texts] == [
        "No Spending Data Available"
    ]
    assert chart.view is None


def test_double_clicking_the_small_chart_asks_for_the_enlarged_one(qapp):
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtGui import QMouseEvent

    chart = SpendingChart()
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


# --------------------------------------------------------------- zoom and pan


def test_zooming_in_sharpens_the_grain_from_months_to_days(qapp):
    chart = SpendingChart(interactive=True)
    chart.show_spending(spread_over(365, start="2025-09-01", cents=2000))

    assert chart.resolution == MONTH
    month_points = len(plotted_dates(chart))

    chart.set_view(date(2026, 3, 1), date(2026, 4, 1))

    assert chart.resolution == DAY
    assert len(plotted_dates(chart)) > month_points
    # Only the days inside the window are drawn.
    assert all(chart.view[0] <= point <= chart.view[1] for point in plotted_dates(chart))


def test_a_long_history_is_totalled_by_year_until_it_is_zoomed_into(qapp):
    chart = SpendingChart(interactive=True)
    chart.show_spending(spread_over(2000, start="2021-01-01"))

    assert chart.resolution == YEAR
    assert x_labels(chart) == ["2021", "2022", "2023", "2024", "2025", "2026"]

    chart.set_view(date(2024, 1, 1), date(2024, 6, 30))

    assert chart.resolution == MONTH
    assert x_labels(chart) == [
        "Jan 2024",
        "Feb 2024",
        "Mar 2024",
        "Apr 2024",
        "May 2024",
        "Jun 2024",
    ]


def test_zooming_keeps_the_date_it_was_aimed_at(qapp):
    chart = SpendingChart(interactive=True)
    chart.show_spending(spread_over(600, start="2025-01-01"))
    focus = date(2025, 9, 1)

    chart.zoom(4, focus=focus)

    first, last = chart.view
    assert first < focus < last
    assert (last - first).days < 300


def test_zooming_stops_before_the_days_run_out(qapp):
    chart = SpendingChart(interactive=True)
    chart.show_spending(spread_over(300, start="2025-01-01"))

    for _ in range(60):
        chart.zoom(2)

    first, last = chart.view
    assert (last - first).days >= 5


def test_the_view_cannot_be_pushed_off_the_recorded_spending(qapp):
    chart = SpendingChart(interactive=True)
    chart.show_spending(spread_over(200, start="2025-01-01"))
    limits = chart.full_view()

    chart.set_view(date(2030, 1, 1), date(2030, 6, 1))

    assert chart.view[0] >= limits[0]
    assert chart.view[1] <= limits[1]


def test_resetting_puts_the_whole_history_back_on_screen(qapp):
    chart = SpendingChart(interactive=True)
    chart.show_spending(spread_over(400, start="2025-01-01"))
    chart.set_view(date(2025, 5, 1), date(2025, 6, 1))

    chart.reset_view()

    assert chart.view == chart.full_view()


def wheel_event(x, notches):
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent

    return QWheelEvent(
        QPointF(x, 150),
        QPointF(x, 150),
        QPoint(0, 0),
        QPoint(0, 120 * notches),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def drag(chart, from_x, to_x):
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QMouseEvent

    def event(kind, x):
        return QMouseEvent(
            kind,
            QPointF(x, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    chart.mousePressEvent(event(QMouseEvent.Type.MouseButtonPress, from_x))
    chart.mouseMoveEvent(event(QMouseEvent.Type.MouseMove, to_x))
    chart.mouseReleaseEvent(event(QMouseEvent.Type.MouseButtonRelease, to_x))


def test_scrolling_over_the_enlarged_chart_zooms_it(qapp):
    chart = SpendingChart(interactive=True)
    chart.resize(800, 300)
    chart.show_spending(spread_over(900, start="2024-01-01"))
    before = chart.view[1] - chart.view[0]

    chart.wheelEvent(wheel_event(400, 1))
    zoomed_in = chart.view[1] - chart.view[0]

    assert zoomed_in < before

    chart.wheelEvent(wheel_event(400, -1))

    assert chart.view[1] - chart.view[0] > zoomed_in


def test_dragging_the_enlarged_chart_moves_it_through_time(qapp):
    chart = SpendingChart(interactive=True)
    chart.resize(800, 300)
    chart.show_spending(spread_over(900, start="2024-01-01"))
    chart.zoom(4)
    first, last = chart.view

    # Dragging to the left pulls later dates into view.
    drag(chart, from_x=600, to_x=300)

    assert chart.view[0] > first
    assert chart.view[1] - chart.view[0] == last - first


def test_a_drag_leaves_the_chart_ready_for_the_next_one(qapp):
    chart = SpendingChart(interactive=True)
    chart.resize(800, 300)
    chart.show_spending(spread_over(900, start="2024-01-01"))

    drag(chart, from_x=600, to_x=300)

    assert chart.pan_origin is None


def test_the_small_chart_does_not_zoom(qapp):
    chart = SpendingChart()
    chart.show_spending(spread_over(400, start="2025-01-01"))
    before = chart.view

    chart.wheelEvent(wheel_event(50, 1))

    assert chart.view == before


# ----------------------------------------------------------------- the dialogs


def test_the_enlarged_window_opens_on_the_whole_history(qapp):
    dialog = SpendingTrendDialog(spread_over(400, start="2025-06-01"))

    assert dialog.chart.view == dialog.chart.full_view()
    assert dialog.chart.interactive is True
    assert "Jun 2025" in dialog.range_label.text()
    dialog.close()


def test_choosing_a_range_moves_the_enlarged_chart_to_it(qapp):
    dialog = SpendingTrendDialog(spread_over(400, start="2025-06-01"))

    dialog.range_selector.setCurrentIndex(3)

    assert dialog.range_selector.currentData() == 30
    first, last = dialog.chart.view
    assert (last - first).days <= 31
    # A month on screen is read day by day.
    assert dialog.chart.resolution == DAY
    dialog.close()


def test_resetting_the_zoom_returns_the_range_to_everything(qapp):
    dialog = SpendingTrendDialog(spread_over(400, start="2025-06-01"))
    dialog.range_selector.setCurrentIndex(3)

    dialog.reset_button.click()

    assert dialog.range_selector.currentIndex() == 0
    assert dialog.chart.view == dialog.chart.full_view()
    dialog.close()


def test_the_enlarged_window_says_what_is_on_screen(qapp):
    dialog = SpendingTrendDialog(spread_over(400, start="2025-06-01"))

    dialog.range_selector.setCurrentIndex(3)

    assert "totalled by day" in dialog.range_label.text()
    dialog.close()


def test_an_empty_history_leaves_the_enlarged_window_saying_so(qapp):
    dialog = SpendingTrendDialog({})

    assert dialog.range_label.text() == "Nothing has been recorded yet."
    assert dialog.statistics_button.isEnabled() is False
    dialog.close()


def test_the_statistics_button_reports_on_the_period_on_screen(qapp, monkeypatch):
    dialog = SpendingTrendDialog(spread_over(400, start="2025-06-01"))
    dialog.range_selector.setCurrentIndex(3)
    opened = []
    monkeypatch.setattr(StatisticsDialog, "exec", lambda self: opened.append(self))

    dialog.statistics_button.click()

    assert len(opened) == 1
    # Only the days on screen are counted, not the whole history.
    assert opened[0].visible_spending == dialog.chart.visible_spending()
    assert opened[0].resolution == DAY
    dialog.close()


def test_the_statistics_are_four_cards_rather_than_a_line_of_text(qapp):
    dialog = StatisticsDialog(
        to_dates(daily(("2026-01-10", 5000), ("2026-02-10", 15000), ("2026-03-10", 10000))),
        MONTH,
    )

    labels_and_values = dialog.figures()

    assert [label for label, _ in labels_and_values] == [
        "Total spending",
        "Months with spending",
        "Average per month",
        "Highest month",
    ]
    assert [value for _, value in labels_and_values] == [
        "EUR 300.00",
        "3",
        "EUR 100.00",
        "Feb 2026\nEUR 150.00",
    ]
    assert len(dialog.card_values) == 4
    dialog.close()


def test_the_statistics_name_the_grain_they_were_counted_at(qapp):
    dialog = StatisticsDialog(
        to_dates(daily(("2026-01-10", 5000), ("2026-01-11", 15000))), DAY
    )

    assert [label for label, _ in dialog.figures()] == [
        "Total spending",
        "Days with spending",
        "Average per day",
        "Highest day",
    ]
    dialog.close()


def test_statistics_over_nothing_do_not_divide_by_zero(qapp):
    dialog = StatisticsDialog({}, MONTH)

    assert dialog.figures() == [("Total spending", "EUR 0.00")]
    dialog.close()


def test_full_screen_is_a_toggle_that_names_its_own_way_back(qapp):
    dialog = SpendingTrendDialog(spread_over(60))
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

    dialog = SpendingTrendDialog(spread_over(60))
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
