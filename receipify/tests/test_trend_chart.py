from datetime import date, timedelta

from app.ui.trend_chart import (
    ALL,
    DAY,
    MONTH,
    WEEK,
    YEAR,
    SpendingBarChart,
    SpendingTrendDialog,
    StatisticsDialog,
    bar_labels,
    format_period,
    format_slot,
    format_slot_span,
    opening_view,
    PurchasesDialog,
    period_end,
    period_start,
    recorded_span,
    shift_period,
    slots_between,
    to_dates,
    totals_by_slot,
    yearly_totals,
)


def daily(*pairs):
    """Spending as the service hands it over: {'YYYY-MM-DD': cents}."""
    return {day: cents for day, cents in pairs}


def spread_over(days, start="2026-01-01", cents=1000, every=1):
    """A purchase every so many days from a starting date."""
    first = date.fromisoformat(start)
    return {
        (first + timedelta(days=n)).isoformat(): cents + n
        for n in range(0, days, every)
    }


def x_labels(chart):
    return [label.get_text() for label in chart.figure.axes[0].get_xticklabels()]


def bar_heights(chart):
    return [round(patch.get_height(), 2) for patch in chart.figure.axes[0].patches]


# ---------------------------------------------------------------- plain periods


def test_unreadable_dates_are_left_out_rather_than_charted():
    assert to_dates({"2026-08-15": 100, "whenever": 500}) == {date(2026, 8, 15): 100}


def test_a_date_belongs_to_a_year_a_month_and_a_week():
    thursday = date(2026, 3, 12)

    assert period_start(thursday, YEAR) == date(2026, 1, 1)
    assert period_start(thursday, MONTH) == date(2026, 3, 1)
    # Weeks run from the Monday.
    assert period_start(thursday, WEEK) == date(2026, 3, 9)
    assert period_start(thursday, DAY) == thursday


def test_a_period_ends_where_the_calendar_ends_it():
    assert period_end(date(2026, 1, 1), YEAR) == date(2026, 12, 31)
    assert period_end(date(2026, 2, 1), MONTH) == date(2026, 2, 28)
    # A leap February is a day longer.
    assert period_end(date(2024, 2, 1), MONTH) == date(2024, 2, 29)
    assert period_end(date(2026, 3, 9), WEEK) == date(2026, 3, 15)


def test_stepping_a_period_crosses_the_turn_of_the_year():
    assert shift_period(date(2026, 12, 1), MONTH, 1) == date(2027, 1, 1)
    assert shift_period(date(2026, 1, 1), MONTH, -1) == date(2025, 12, 1)
    assert shift_period(date(2026, 1, 1), YEAR, 2) == date(2028, 1, 1)
    assert shift_period(date(2026, 3, 9), WEEK, -1) == date(2026, 3, 2)


def test_a_window_holds_a_slot_for_every_period_in_it():
    slots = slots_between(date(2026, 1, 15), date(2026, 4, 2), MONTH)

    # January to April, whether or not anything was bought in between.
    assert slots == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
        date(2026, 4, 1),
    ]


def test_empty_periods_are_totalled_as_zero_so_they_keep_their_place():
    spending = to_dates(daily(("2026-01-05", 100), ("2026-01-20", 50), ("2026-03-02", 700)))

    totals = totals_by_slot(spending, date(2026, 1, 1), date(2026, 3, 31), MONTH)

    assert totals == {date(2026, 1, 1): 150, date(2026, 2, 1): 0, date(2026, 3, 1): 700}


def test_spending_outside_the_window_is_not_counted_into_it():
    spending = to_dates(daily(("2025-12-30", 900), ("2026-01-05", 100)))

    totals = totals_by_slot(spending, date(2026, 1, 1), date(2026, 1, 31), DAY)

    assert sum(totals.values()) == 100


def test_the_panel_totals_the_record_a_year_to_a_bar():
    spending = to_dates(
        daily(("2024-07-15", 8000), ("2026-02-20", 3000), ("2026-08-20", 1500))
    )

    totals = yearly_totals(spending)

    # 2025 holds no receipts and still keeps its place between the two years
    # that do, so the run of years reads as a calendar.
    assert totals == {date(2024, 1, 1): 8000, date(2025, 1, 1): 0, date(2026, 1, 1): 4500}


def test_the_panel_is_empty_for_an_account_with_nothing_in_it():
    assert yearly_totals({}) == {}
    assert recorded_span({}) == ""


def test_the_panel_caption_names_the_months_the_record_runs_between():
    spending = to_dates(daily(("2026-06-30", 8000), ("2026-08-15", 3000)))

    assert recorded_span(spending) == "Jun 2026 - Aug 2026"


def test_periods_are_named_the_way_they_are_read():
    assert format_period(date(2026, 3, 12), YEAR) == "2026"
    assert format_period(date(2026, 3, 12), MONTH) == "March 2026"
    assert format_period(date(2026, 3, 12), WEEK) == "09 Mar - 15 Mar 2026"
    assert format_period(None, ALL, (date(2025, 6, 1), date(2026, 8, 1))) == (
        "All time  ·  Jun 2025 - Aug 2026"
    )
    assert format_period(None, ALL) == "All time"


def test_figures_name_their_period_in_short():
    assert format_slot(date(2026, 3, 1), YEAR) == "2026"
    assert format_slot(date(2026, 3, 1), MONTH) == "Mar 2026"
    assert format_slot(date(2026, 3, 12), DAY) == "12 Mar 2026"
    assert format_slot_span(date(2025, 9, 1), date(2026, 8, 1), MONTH) == (
        "Sep 2025 - Aug 2026"
    )
    assert format_slot_span(date(2026, 8, 1), date(2026, 8, 1), MONTH) == "Aug 2026"


def test_month_bars_carry_the_year_where_it_turns_over():
    slots = [date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)]

    assert bar_labels(slots, MONTH) == ["Nov\n2025", "Dec", "Jan\n2026", "Feb"]


def test_day_bars_are_numbered_and_a_week_names_its_days():
    slots = [date(2026, 3, 9), date(2026, 3, 10)]

    assert bar_labels(slots, DAY) == ["9", "10"]
    assert bar_labels(slots, DAY, view_scope=WEEK) == ["Mon\n09", "Tue\n10"]


def test_the_window_opens_on_the_narrowest_view_that_holds_everything():
    assert opening_view({}) == (ALL, None)
    assert opening_view(to_dates(daily(("2026-08-02", 1), ("2026-08-20", 1)))) == (
        MONTH,
        date(2026, 8, 2),
    )
    assert opening_view(to_dates(daily(("2026-02-02", 1), ("2026-08-20", 1)))) == (
        YEAR,
        date(2026, 2, 2),
    )
    assert opening_view(to_dates(daily(("2024-02-02", 1), ("2026-08-20", 1)))) == (
        ALL,
        None,
    )


# ------------------------------------------------------------------- bar chart


def test_the_chart_draws_a_bar_for_every_slot_it_is_given(qapp):
    chart = SpendingBarChart()
    totals = {date(2026, 1, 1): 8000, date(2026, 2, 1): 0, date(2026, 3, 1): 3000}

    chart.show_totals(totals, bar_labels(list(totals), MONTH))

    # February keeps its place but has no height: nothing was spent, and
    # nothing is drawn to suggest otherwise.
    assert bar_heights(chart) == [80.0, 0.0, 30.0]
    assert chart.slots == list(totals)


def test_an_account_with_nothing_in_it_says_so_instead_of_drawing_axes(qapp):
    chart = SpendingBarChart()

    chart.show_totals({}, [])

    assert [text.get_text() for text in chart.figure.axes[0].texts] == [
        "No Spending Data Available"
    ]


def test_a_period_with_no_spending_keeps_its_axis_and_says_it_is_empty(qapp):
    chart = SpendingBarChart()
    totals = {date(2026, 5, 1): 0, date(2026, 6, 1): 0}

    chart.show_totals(totals, bar_labels(list(totals), MONTH))

    assert [text.get_text() for text in chart.figure.axes[0].texts] == [
        "Nothing was recorded in this period"
    ]
    # The months are still named, so it is clear which period is empty.
    assert x_labels(chart) == ["May\n2026", "Jun"]
    # A scale over nothing would round off to a run of zeroes and ones.
    assert [label.get_text() for label in chart.figure.axes[0].get_yticklabels()] == ["0"]


def test_bar_labels_are_thinned_out_rather_than_left_to_collide(qapp):
    chart = SpendingBarChart()
    chart.resize(420, 260)
    totals = totals_by_slot({}, date(2026, 3, 1), date(2026, 3, 31), DAY)

    chart.show_totals(totals, bar_labels(list(totals), DAY))

    assert len(x_labels(chart)) <= max(chart.width() // 52, 1)
    # The first bar is always named, so the axis says where it starts.
    assert x_labels(chart)[0] == "1"


def test_amounts_are_written_over_the_bars_only_where_there_is_room(qapp):
    chart = SpendingBarChart(interactive=True)
    few = {date(2026, 1, 1): 8000, date(2026, 2, 1): 0, date(2026, 3, 1): 3000}

    chart.show_totals(few, bar_labels(list(few), MONTH), annotate=True)

    # The empty month is left blank rather than labelled with a zero.
    assert [text.get_text() for text in chart.figure.axes[0].texts] == ["80", "30"]


def test_double_clicking_the_panel_chart_asks_for_the_enlarged_one(qapp):
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtGui import QMouseEvent

    chart = SpendingBarChart()
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


def test_a_bar_can_be_picked_out_by_where_it_was_clicked(qapp):
    chart = SpendingBarChart(interactive=True)
    chart.resize(600, 300)
    totals = {date(2026, 1, 1): 100, date(2026, 2, 1): 200, date(2026, 3, 1): 300}
    chart.show_totals(totals, bar_labels(list(totals), MONTH))

    middle_bar_x, _ = chart.figure.axes[0].transData.transform((1, 0))

    assert chart.bar_at(middle_bar_x / chart.device_pixel_ratio) == date(2026, 2, 1)
    # Off the end of the axis there is no bar to name.
    assert chart.bar_at(0) is None


def test_the_panel_chart_does_not_answer_clicks(qapp):
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QMouseEvent

    chart = SpendingBarChart()
    chart.resize(600, 300)
    totals = {date(2026, 1, 1): 100, date(2026, 2, 1): 200}
    chart.show_totals(totals, bar_labels(list(totals), MONTH))
    clicked = []
    chart.bar_clicked.connect(clicked.append)

    chart.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(300, 150),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert clicked == []


# ----------------------------------------------------------------- the window


def test_the_window_opens_on_the_year_when_the_record_sits_inside_one(qapp):
    dialog = SpendingTrendDialog(spread_over(200, start="2026-01-05", every=9))

    assert dialog.scope == YEAR
    assert dialog.period_label.text() == "2026"
    # A year is twelve months, whether or not each one holds a receipt.
    assert len(dialog.chart.slots) == 12
    dialog.close()


def test_clicking_a_month_opens_that_month(qapp):
    dialog = SpendingTrendDialog(spread_over(200, start="2026-01-05", every=9))

    dialog.drill_into(date(2026, 3, 1))

    assert dialog.scope == MONTH
    assert dialog.period_label.text() == "March 2026"
    assert dialog.chart.slots[0] == date(2026, 3, 1)
    assert len(dialog.chart.slots) == 31
    # The control that would have got you here says where you are.
    assert dialog.scope_selector.currentData() == MONTH
    dialog.close()


def test_drilling_runs_from_all_time_down_to_a_month(qapp):
    dialog = SpendingTrendDialog(spread_over(900, start="2024-06-01", every=11))

    assert dialog.scope == ALL

    dialog.drill_into(date(2025, 1, 1))
    assert dialog.scope == YEAR
    assert dialog.period_label.text() == "2025"

    dialog.drill_into(date(2025, 4, 1))
    assert dialog.scope == MONTH
    assert dialog.period_label.text() == "April 2025"
    assert len(dialog.chart.slots) == 30
    dialog.close()


def test_a_week_is_reached_through_the_selector(qapp):
    dialog = SpendingTrendDialog(spread_over(900, start="2024-06-01", every=11))
    dialog.drill_into(date(2025, 1, 1))
    dialog.drill_into(date(2025, 4, 1))

    dialog.scope_selector.setCurrentIndex(3)

    assert dialog.scope == WEEK
    assert len(dialog.chart.slots) == 7
    dialog.close()


def test_stepping_moves_one_period_at_a_time(qapp):
    dialog = SpendingTrendDialog(spread_over(200, start="2026-01-05", every=9))
    dialog.drill_into(date(2026, 3, 1))

    dialog.next_button.click()
    assert dialog.period_label.text() == "April 2026"

    dialog.previous_button.click()
    dialog.previous_button.click()
    assert dialog.period_label.text() == "February 2026"
    dialog.close()


def test_stepping_stops_at_the_ends_of_the_record(qapp):
    dialog = SpendingTrendDialog(daily(("2026-03-10", 5000), ("2026-04-10", 5000)))
    dialog.drill_into(date(2026, 3, 1))

    assert dialog.previous_button.isEnabled() is False
    assert dialog.next_button.isEnabled() is True

    dialog.next_button.click()

    assert dialog.period_label.text() == "April 2026"
    assert dialog.previous_button.isEnabled() is True
    # Nothing is recorded after April, so there is nowhere further to go.
    assert dialog.next_button.isEnabled() is False
    dialog.close()


def test_all_time_has_nothing_to_step_through(qapp):
    dialog = SpendingTrendDialog(spread_over(900, start="2024-06-01", every=11))

    assert dialog.scope == ALL
    assert dialog.previous_button.isEnabled() is False
    assert dialog.next_button.isEnabled() is False
    dialog.close()


def test_the_arrow_keys_step_through_periods(qapp):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent

    dialog = SpendingTrendDialog(spread_over(200, start="2026-01-05", every=9))
    dialog.drill_into(date(2026, 3, 1))

    dialog.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier
        )
    )

    assert dialog.period_label.text() == "April 2026"
    dialog.close()


def test_choosing_a_wider_scope_pulls_back_out(qapp):
    dialog = SpendingTrendDialog(spread_over(900, start="2024-06-01", every=11))
    dialog.drill_into(date(2025, 1, 1))
    dialog.drill_into(date(2025, 4, 1))

    dialog.scope_selector.setCurrentIndex(0)

    assert dialog.scope == ALL
    assert "All time" in dialog.period_label.text()
    dialog.close()


def test_a_period_with_no_receipts_can_be_opened_without_trouble(qapp):
    """The chart this replaced could be zoomed into an empty stretch, and died there."""
    dialog = SpendingTrendDialog(daily(("2026-01-10", 5000), ("2026-06-10", 5000)))

    dialog.drill_into(date(2026, 3, 1))

    assert dialog.period_label.text() == "March 2026"
    assert bar_heights(dialog.chart) == [0.0] * 31
    assert "Nothing was recorded" in dialog.chart.figure.axes[0].texts[0].get_text()
    dialog.close()


def test_an_empty_account_leaves_the_window_saying_so(qapp):
    dialog = SpendingTrendDialog({})

    assert dialog.period_label.text() == "Nothing has been recorded yet."
    assert dialog.statistics_button.isEnabled() is False
    assert dialog.chart.slots == []
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


# ------------------------------------------------------------------ purchases


class FakeReceipt:
    """Just the fields a purchase row shows."""

    def __init__(self, product_name, merchant_name, category_name, price_cents):
        self.product_name = product_name
        self.merchant_name = merchant_name
        self.category_name = category_name
        self.price_cents = price_cents


def test_clicking_a_day_opens_what_was_bought_that_day(qapp, monkeypatch):
    dialog = SpendingTrendDialog(
        daily(("2026-03-14", 9500)),
        receipts_by_day={
            "2026-03-14": [
                FakeReceipt("Blender", "Kitchen Co", "Home", 8000),
                FakeReceipt("Mouse", "Tech Store", "Electronics", 1500),
            ]
        },
    )
    opened = []
    monkeypatch.setattr(PurchasesDialog, "exec", lambda self: opened.append(self))

    # A month of days is the finest chart there is, so a day opens its receipts
    # rather than a narrower period.
    dialog.drill_into(date(2026, 3, 14))

    assert len(opened) == 1
    assert opened[0].day == date(2026, 3, 14)
    assert [receipt.product_name for receipt in opened[0].receipts] == ["Blender", "Mouse"]
    dialog.close()


def test_a_day_with_no_receipts_behind_it_opens_an_empty_list(qapp, monkeypatch):
    dialog = SpendingTrendDialog(daily(("2026-03-14", 9500)), receipts_by_day={})
    opened = []
    monkeypatch.setattr(PurchasesDialog, "exec", lambda self: opened.append(self))

    dialog.drill_into(date(2026, 3, 2))

    assert opened[0].receipts == []
    dialog.close()


def test_the_purchase_list_totals_the_day_it_covers(qapp):
    dialog = PurchasesDialog(
        date(2026, 3, 14),
        [
            FakeReceipt("Blender", "Kitchen Co", "Home", 8000),
            FakeReceipt("Mouse", "Tech Store", "Electronics", 1500),
        ],
    )

    assert dialog.describe_day() == "2 purchases  ·  EUR 95.00 in total"
    dialog.close()


def test_one_purchase_is_not_reported_as_purchases(qapp):
    dialog = PurchasesDialog(
        date(2026, 3, 14), [FakeReceipt("Blender", "Kitchen Co", "Home", 8000)]
    )

    assert dialog.describe_day() == "1 purchase  ·  EUR 80.00 in total"
    dialog.close()


def test_an_empty_day_says_so_rather_than_showing_a_bare_list(qapp):
    from PyQt6.QtWidgets import QLabel

    dialog = PurchasesDialog(date(2026, 3, 2), [])

    assert dialog.describe_day() == "This day has no receipts against it."
    assert "Nothing was bought" in " ".join(
        label.text() for label in dialog.findChildren(QLabel)
    )
    dialog.close()


def test_a_purchase_row_shows_the_product_its_shop_and_its_price(qapp):
    from PyQt6.QtWidgets import QLabel

    row = PurchasesDialog.build_row(
        FakeReceipt("Blender", "Kitchen Co", "Home", 8000)
    )

    assert [label.text() for label in row.findChildren(QLabel)] == [
        "Blender",
        "Kitchen Co  ·  Home",
        "EUR 80.00",
    ]


# ------------------------------------------------------------------ statistics


def test_the_statistics_button_reports_on_the_period_on_screen(qapp, monkeypatch):
    dialog = SpendingTrendDialog(spread_over(200, start="2026-01-05", every=9))
    dialog.drill_into(date(2026, 3, 1))
    opened = []
    monkeypatch.setattr(StatisticsDialog, "exec", lambda self: opened.append(self))

    dialog.statistics_button.click()

    assert len(opened) == 1
    # March counted by day, rather than the whole record counted by month.
    assert opened[0].scope == DAY
    assert opened[0].period_name == "March 2026"
    assert opened[0].totals == dialog.current_totals()
    dialog.close()


def test_the_statistics_are_four_cards_rather_than_a_line_of_text(qapp):
    dialog = StatisticsDialog(
        {date(2026, 1, 1): 5000, date(2026, 2, 1): 15000, date(2026, 3, 1): 10000},
        MONTH,
        "2026",
    )

    # Every figure is one line, and the highest period names its date in the
    # label so that the four figures stay in line with each other.
    assert dialog.figures() == [
        ("Total spending", "EUR 300.00"),
        ("Months with spending", "3"),
        ("Average per month", "EUR 100.00"),
        ("Highest month\n(Feb 2026)", "EUR 150.00"),
    ]
    assert len(dialog.card_values) == 4
    dialog.close()


def test_empty_periods_are_left_out_of_the_figures(qapp):
    """A month with no receipts is not a month that averages the rest down."""
    dialog = StatisticsDialog(
        {
            date(2026, 1, 1): 5000,
            date(2026, 2, 1): 0,
            date(2026, 3, 1): 0,
            date(2026, 4, 1): 15000,
        },
        MONTH,
        "2026",
    )

    assert dialog.figures()[1] == ("Months with spending", "2")
    assert dialog.figures()[2] == ("Average per month", "EUR 100.00")
    dialog.close()


def test_the_statistics_name_the_grain_they_were_counted_at(qapp):
    dialog = StatisticsDialog(
        {date(2026, 1, 10): 5000, date(2026, 1, 11): 15000}, DAY, "January 2026"
    )

    assert [label for label, _ in dialog.figures()] == [
        "Total spending",
        "Days with spending",
        "Average per day",
        "Highest day\n(11 Jan 2026)",
    ]
    dialog.close()


def test_the_statistics_cards_line_their_figures_up(qapp):
    """The figures were wrapping onto second lines and sitting out of line."""
    from PyQt6.QtGui import QFontMetrics

    dialog = StatisticsDialog(
        {date(2024, 1, 1): 5441648, date(2025, 1, 1): 2201404}, YEAR, "2024 - 2026"
    )
    dialog.show()
    qapp.processEvents()

    tops = {
        value.mapTo(dialog, value.rect().topLeft()).y() for value in dialog.card_values
    }
    # Every figure starts on the same line as the others...
    assert len(tops) == 1
    assert len({label.height() for label in dialog.card_labels}) == 1
    for value in dialog.card_values:
        # ... on one line, and inside its own card rather than cut off by it.
        assert "\n" not in value.text()
        assert value.width() >= QFontMetrics(value.font()).horizontalAdvance(value.text())
    dialog.close()


def test_statistics_over_an_empty_period_do_not_divide_by_zero(qapp):
    dialog = StatisticsDialog({date(2026, 3, 1): 0}, DAY, "March 2026")

    assert dialog.figures() == [("Total spending", "EUR 0.00")]
    assert dialog.describe_period() == "Nothing was recorded in March 2026."
    dialog.close()
