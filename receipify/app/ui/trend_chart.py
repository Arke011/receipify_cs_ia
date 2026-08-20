"""The spending chart, and the enlarged window it opens into.

The chart lives here rather than on the dashboard page because the enlarged
view draws the same figure, only larger and with the room to be zoomed into.

Spending is plotted against real dates, not against a row of equally spaced
month names. A gap in the line is then a gap in time, which is what lets the
chart leave out the periods nothing was bought in instead of marking them with
a point that no purchase stands behind.
"""

from datetime import date, timedelta

import matplotlib

# The canvas is embedded in a Qt widget, so the Qt backend has to be selected
# before pyplot-related modules pick an interactive one of their own.
matplotlib.use("QtAgg")

from matplotlib import dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.formatting import CURRENCY_PREFIX, format_currency
from app.ui.styles import app_stylesheet


CARD_BACKGROUND = "#FFFFFF"
LINE_COLOUR = "#2563EB"
GRID_COLOUR = "#E2E8F0"
AXIS_TEXT_COLOUR = "#64748B"

EMPTY_MESSAGE = "No Spending Data Available"

DAY = "day"
MONTH = "month"
YEAR = "year"

# How wide the view has to be before spending is totalled over longer periods.
# Below a season the days themselves are worth seeing; past a few years the
# months become too many to tell apart.
YEARLY_ABOVE_DAYS = 4 * 365
MONTHLY_ABOVE_DAYS = 120

# A single purchase has no line to read, so its point is given room either side.
LONE_POINT_PADDING = timedelta(days=15)
ZOOM_STEP = 1.25
# Zooming closer than this would land between two days.
MINIMUM_SPAN = timedelta(days=6)
# Past this many points the markers merge into the line and only clutter it.
MAX_MARKED_POINTS = 40

RANGE_OPTIONS = (
    ("All recorded spending", None),
    ("Last 12 months", 365),
    ("Last 6 months", 182),
    ("Last 30 days", 30),
)


def parse_date(value):
    """A stored ``'YYYY-MM-DD'`` as a date, or None if it cannot be read."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def to_dates(daily_spending):
    """Stored spending as ``{date: cents}``, skipping anything unreadable."""
    dated = {}
    for day, cents in daily_spending.items():
        parsed = parse_date(day)
        if parsed is not None:
            dated[parsed] = dated.get(parsed, 0) + cents

    return dict(sorted(dated.items()))


def period_start(day, resolution):
    """The day, month, or year a date belongs to."""
    if resolution == YEAR:
        return date(day.year, 1, 1)
    if resolution == MONTH:
        return date(day.year, day.month, 1)

    return day


def group_spending(spending, resolution):
    """Total spending over each day, month, or year that holds any.

    Periods with nothing in them are left out rather than carried as zero, so
    the chart never marks a purchase that was not made.
    """
    grouped = {}
    for day, cents in spending.items():
        period = period_start(day, resolution)
        grouped[period] = grouped.get(period, 0) + cents

    return dict(sorted(grouped.items()))


def resolution_for_span(span_days):
    """How finely to total spending for a view of this width."""
    if span_days > YEARLY_ABOVE_DAYS:
        return YEAR
    if span_days > MONTHLY_ABOVE_DAYS:
        return MONTH

    return DAY


def format_period(period, resolution):
    """A period as it is written in a heading, e.g. ``'Aug 2026'``."""
    if resolution == YEAR:
        return period.strftime("%Y")
    if resolution == MONTH:
        return period.strftime("%b %Y")

    return period.strftime("%d %b %Y")


def format_date_range(first, last):
    """The span a chart covers, e.g. ``'Jul 2025 - Aug 2026'``."""
    if first is None or last is None:
        return ""
    if (first.year, first.month) == (last.year, last.month):
        return first.strftime("%b %Y")

    return f"{first.strftime('%b %Y')} - {last.strftime('%b %Y')}"


def periods_within(grouped, first, last):
    """The totals whose points fall inside a window of dates."""
    return {period: cents for period, cents in grouped.items() if first <= period <= last}


def spending_in_periods(spending, periods, resolution):
    """The purchases behind a set of totals.

    A month's total is plotted at the start of that month, so a purchase made
    later in it sits beyond its own point. Picking the purchases out by the
    period they belong to keeps the two in step: everything counted into a
    point on screen is counted into the figures for it as well.
    """
    wanted = set(periods)

    return {
        day: cents
        for day, cents in spending.items()
        if period_start(day, resolution) in wanted
    }


class SpendingChart(FigureCanvasQTAgg):
    """Spending over time, totalled as finely as the view has room for."""

    enlarge_requested = pyqtSignal()
    view_changed = pyqtSignal()

    def __init__(self, parent=None, interactive=False):
        self.figure = Figure(figsize=(5, 3), dpi=100, facecolor=CARD_BACKGROUND)
        super().__init__(self.figure)
        self.setParent(parent)
        # Only the enlarged chart is zoomed and panned. The small one is read
        # as a shape, and opens the enlarged one when it is double-clicked.
        self.interactive = interactive
        self.spending = {}
        self.resolution = MONTH
        self.periods = []
        self.view = None
        self.pan_origin = None
        self.setMinimumHeight(320 if interactive else 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if not interactive:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Double-click to enlarge")

    # -------------------------------------------------------------------- data

    def show_spending(self, daily_spending):
        """Draw a series of ``{'YYYY-MM-DD': cents}`` over its whole span."""
        self.spending = to_dates(daily_spending)
        self.view = self.full_view()
        self.draw_chart()

    def full_view(self):
        """The window holding everything, padded when it would be a single point."""
        if not self.spending:
            return None

        # The window runs to the points that will be drawn rather than to the
        # purchase dates behind them: a month's spending is plotted at the
        # start of that month, and the line should not stop short of the frame.
        recorded = (max(self.spending) - min(self.spending)).days
        periods = group_spending(self.spending, self.resolution_for_view(recorded))
        first, last = min(periods), max(periods)
        if first == last:
            return (first - LONE_POINT_PADDING, last + LONE_POINT_PADDING)

        # A margin either side keeps the end points clear of the frame.
        margin = max((last - first) / 25, timedelta(days=5))
        return (first - margin, last + margin)

    def visible_periods(self):
        """The totals currently drawn, keyed by the period each covers."""
        if self.view is None:
            return {}

        return periods_within(
            group_spending(self.spending, self.resolution), *self.view
        )

    def visible_spending(self):
        """The purchases behind the points currently drawn."""
        return spending_in_periods(
            self.spending, self.visible_periods(), self.resolution
        )

    # -------------------------------------------------------------------- draw

    def draw_chart(self):
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.set_facecolor(CARD_BACKGROUND)

        if not self.spending or self.view is None:
            self.draw_empty_message(axes)
            self.view_changed.emit()
            return

        first, last = self.view
        self.resolution = self.resolution_for_view((last - first).days)
        visible = self.visible_periods()
        self.periods = list(visible)
        amounts = [cents / 100 for cents in visible.values()]

        axes.plot(
            self.periods,
            amounts,
            color=LINE_COLOUR,
            linewidth=2.2,
            marker="o" if len(self.periods) <= MAX_MARKED_POINTS else None,
            markersize=5,
            markerfacecolor=LINE_COLOUR,
            markeredgecolor=CARD_BACKGROUND,
        )
        if self.periods:
            axes.fill_between(self.periods, amounts, color=LINE_COLOUR, alpha=0.08)

        self.style_axes(axes, amounts)
        self.figure.tight_layout()
        self.draw_idle()
        self.view_changed.emit()

    def resolution_for_view(self, span_days):
        """How finely to total spending for the view this chart is showing.

        The small chart never goes down to single days: it is read as a shape,
        and one point a month keeps that shape the same whether it is covering
        two months of receipts or two years of them.
        """
        resolution = resolution_for_span(span_days)
        if not self.interactive and resolution == DAY:
            return MONTH

        return resolution

    def draw_empty_message(self, axes):
        axes.text(
            0.5,
            0.5,
            EMPTY_MESSAGE,
            horizontalalignment="center",
            verticalalignment="center",
            color=AXIS_TEXT_COLOUR,
            fontsize=11,
            transform=axes.transAxes,
        )
        axes.set_axis_off()
        self.figure.tight_layout()
        self.draw_idle()

    def style_axes(self, axes, amounts):
        label_size = 9 if self.interactive else 8

        axes.set_ylabel(
            f"Spending ({CURRENCY_PREFIX})", color=AXIS_TEXT_COLOUR, fontsize=label_size + 1
        )
        axes.grid(True, axis="y", color=GRID_COLOUR, linewidth=1)
        axes.set_axisbelow(True)
        axes.tick_params(colors=AXIS_TEXT_COLOUR, labelsize=label_size)
        axes.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axes.spines[side].set_color(GRID_COLOUR)

        axes.set_xlim(*self.view)
        axes.set_ylim(bottom=0, top=(max(amounts) if amounts else 1) * 1.12)
        self.label_time_axis(axes)

    def label_time_axis(self, axes):
        """Date labels at the grain the chart is being read at.

        The small chart is read as a shape rather than looked up month by
        month, so it keeps a scale of years however long it runs. The enlarged
        one names the months, then the days, as it is zoomed into them.
        """
        if not self.interactive or self.resolution == YEAR:
            self.label_by_year(axes)
            return

        axes.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=9))
        axes.xaxis.set_major_formatter(
            mdates.DateFormatter("%b %Y" if self.resolution == MONTH else "%d %b")
        )

    def label_by_year(self, axes):
        first, last = self.view
        # A run of years is marked where each one begins. A view sitting inside
        # a single year holds no such date, so that year is named once in the
        # middle rather than the axis being left with no labels at all.
        starts = [
            date(year, 1, 1)
            for year in range(first.year, last.year + 1)
            if first <= date(year, 1, 1) <= last
        ]
        if starts:
            axes.set_xticks(starts)
            axes.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
            return

        middle = first + (last - first) / 2
        axes.set_xticks([middle])
        axes.set_xticklabels([str(middle.year)])

    # ---------------------------------------------------------------- zoom, pan

    def zoom(self, factor, focus=None):
        """Zoom about a date, keeping it where it was under the pointer."""
        if self.view is None:
            return

        first, last = self.view
        focus = focus or first + (last - first) / 2
        span = (last - first) / factor
        if span < MINIMUM_SPAN and factor > 1:
            return

        share = (focus - first) / (last - first)
        self.set_view(focus - span * share, focus + span * (1 - share))

    def set_view(self, first, last):
        """Look at a window of dates, kept over the spending that was recorded."""
        limits = self.full_view()
        if limits is None:
            return

        # There is nothing to see on either side of the recorded spending, so
        # panning and zooming stay within it.
        span = min(last - first, limits[1] - limits[0])
        first = max(min(first, limits[1] - span), limits[0])
        self.view = (first, first + span)
        self.draw_chart()

    def reset_view(self):
        self.view = self.full_view()
        self.draw_chart()

    def date_at(self, position_x):
        """The date under a point across the canvas, or None if it has none."""
        if not self.figure.axes or not self.spending:
            return None

        axes = self.figure.axes[0]
        x_data, _ = axes.transData.inverted().transform(
            (position_x * self.device_pixel_ratio, 0)
        )
        try:
            return mdates.num2date(x_data).date()
        except (ValueError, OverflowError):
            return None

    def wheelEvent(self, event):
        if not self.interactive or self.view is None:
            super().wheelEvent(event)
            return

        steps = event.angleDelta().y() / 120
        if steps:
            self.zoom(ZOOM_STEP**steps, focus=self.date_at(event.position().x()))

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.interactive and event.button() == Qt.MouseButton.LeftButton:
            self.pan_origin = (event.position().x(), self.view)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.pan_origin is None or self.view is None:
            return

        start_x, (first, last) = self.pan_origin
        grabbed = self.date_at(start_x)
        now_under = self.date_at(event.position().x())
        if grabbed is None or now_under is None:
            return

        # The date the drag started on stays under the pointer.
        shift = grabbed - now_under
        self.set_view(first + shift, last + shift)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.pan_origin is not None:
            self.pan_origin = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if self.interactive:
            self.reset_view()
        else:
            self.enlarge_requested.emit()


class SpendingTrendDialog(QDialog):
    """The spending chart at full size, zoomable down to single days."""

    def __init__(self, daily_spending, parent=None):
        super().__init__(parent)
        self.daily_spending = dict(daily_spending)
        self.setWindowTitle("Spending over time")
        # Without this the window manager offers no way to maximise a dialog.
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(1040, 700)
        self.setMinimumSize(640, 480)
        self.build_ui()
        self.chart.show_spending(self.daily_spending)
        self.setStyleSheet(app_stylesheet())

    def build_ui(self):
        root = QWidget()
        root.setObjectName("dialogRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(14)

        title = QLabel("Spending over time")
        title.setObjectName("dialogTitle")
        root_layout.addWidget(title)

        self.range_label = QLabel()
        self.range_label.setObjectName("dialogSubtitle")
        root_layout.addWidget(self.range_label)

        root_layout.addLayout(self.build_controls())

        panel = QFrame()
        panel.setObjectName("dashboardPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        self.chart = SpendingChart(interactive=True)
        self.chart.view_changed.connect(self.describe_view)
        panel_layout.addWidget(self.chart)
        root_layout.addWidget(panel, stretch=1)

        root_layout.addLayout(self.build_buttons())

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root)

    def build_controls(self):
        controls = QHBoxLayout()
        controls.setSpacing(10)
        # The row runs from the same edge as the heading above it, rather than
        # being pushed in by a label of its own.
        controls.setContentsMargins(0, 0, 0, 0)

        self.range_selector = QComboBox()
        self.range_selector.setObjectName("chartRangeSelector")
        for label, days in RANGE_OPTIONS:
            self.range_selector.addItem(label, days)
        self.range_selector.currentIndexChanged.connect(self.show_selected_range)
        controls.addWidget(self.range_selector)

        self.reset_button = QPushButton("Reset zoom")
        self.reset_button.setObjectName("panelActionButton")
        self.reset_button.clicked.connect(self.reset_view)
        controls.addWidget(self.reset_button)

        hint = QLabel("Scroll to zoom  ·  drag to move  ·  double-click to reset")
        hint.setObjectName("panelCaption")
        controls.addWidget(hint)
        controls.addStretch(1)

        return controls

    def build_buttons(self):
        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.statistics_button = QPushButton("Statistics")
        self.statistics_button.setObjectName("secondaryButton")
        self.statistics_button.setToolTip("The figures behind the period on screen")
        self.statistics_button.clicked.connect(self.open_statistics)
        button_row.addWidget(self.statistics_button)
        button_row.addStretch(1)

        self.full_screen_button = QPushButton("Full screen")
        self.full_screen_button.setObjectName("secondaryButton")
        self.full_screen_button.clicked.connect(self.toggle_full_screen)
        button_row.addWidget(self.full_screen_button)

        close_button = QPushButton("Close")
        close_button.setObjectName("primaryButton")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)

        return button_row

    # ------------------------------------------------------------------ content

    def show_selected_range(self):
        days = self.range_selector.currentData()
        if days is None or not self.chart.spending:
            self.chart.reset_view()
            return

        last = max(self.chart.spending)
        self.chart.set_view(last - timedelta(days=days), last)

    def reset_view(self):
        # Setting the range back to everything redraws through the same path.
        if self.range_selector.currentIndex() == 0:
            self.chart.reset_view()
        else:
            self.range_selector.setCurrentIndex(0)

    def describe_view(self):
        visible = self.chart.visible_spending()
        if not visible:
            self.range_label.setText("Nothing has been recorded yet.")
            self.statistics_button.setEnabled(False)
            return

        self.range_label.setText(
            f"{format_date_range(min(visible), max(visible))}"
            f"  ·  totalled by {self.chart.resolution}"
        )
        self.statistics_button.setEnabled(True)

    def open_statistics(self):
        StatisticsDialog(
            self.chart.visible_spending(), self.chart.resolution, parent=self
        ).exec()

    # ---------------------------------------------------------------- full screen

    def toggle_full_screen(self):
        if self.isFullScreen():
            self.showNormal()
            self.full_screen_button.setText("Full screen")
        else:
            self.showFullScreen()
            self.full_screen_button.setText("Exit full screen")

    def keyPressEvent(self, event):
        # Escape leaves full screen first; closing the window as well would
        # take two presses' worth of work away from one.
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.toggle_full_screen()
            return
        super().keyPressEvent(event)


class StatisticsDialog(QDialog):
    """The figures behind the stretch of chart on screen, a card to each."""

    def __init__(self, visible_spending, resolution, parent=None):
        super().__init__(parent)
        self.visible_spending = dict(visible_spending)
        self.resolution = resolution
        self.setWindowTitle("Statistics")
        self.setMinimumWidth(620)
        self.build_ui()
        self.setStyleSheet(app_stylesheet())

    def build_ui(self):
        root = QWidget()
        root.setObjectName("dialogRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(18)

        title = QLabel("Statistics")
        title.setObjectName("dialogTitle")
        root_layout.addWidget(title)

        subtitle = QLabel(self.describe_period())
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        root_layout.addWidget(subtitle)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        root_layout.addLayout(cards)
        self.card_values = [
            self.add_card(cards, label, value) for label, value in self.figures()
        ]

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = QPushButton("Close")
        close_button.setObjectName("primaryButton")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        root_layout.addLayout(button_row)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root)

    @staticmethod
    def add_card(layout, label_text, value_text):
        card = QFrame()
        card.setObjectName("dashboardSummaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("dashboardMetricLabel")
        label.setWordWrap(True)
        card_layout.addWidget(label)

        value = QLabel(value_text)
        value.setObjectName("statisticValue")
        value.setWordWrap(True)
        card_layout.addWidget(value)

        layout.addWidget(card, stretch=1)
        return value

    def describe_period(self):
        if not self.visible_spending:
            return "There is nothing on the chart to report on."

        span = format_date_range(min(self.visible_spending), max(self.visible_spending))
        return f"Everything on the chart right now: {span}."

    def figures(self):
        """The four figures, each as one card's label and value."""
        if not self.visible_spending:
            return [("Total spending", format_currency(0))]

        grouped = group_spending(self.visible_spending, self.resolution)
        total_cents = sum(grouped.values())
        highest = max(grouped, key=grouped.get)
        counted = f"{self.resolution}s" if len(grouped) != 1 else self.resolution

        return [
            ("Total spending", format_currency(total_cents)),
            (f"{counted.capitalize()} with spending", str(len(grouped))),
            (
                f"Average per {self.resolution}",
                format_currency(round(total_cents / len(grouped))),
            ),
            (
                f"Highest {self.resolution}",
                f"{format_period(highest, self.resolution)}\n"
                f"{format_currency(grouped[highest])}",
            ),
        ]
