"""The spending chart, and the window that navigates through it.

Spending is drawn as a bar for each period rather than as a line through
points. A line joins its points together, which claims a continuity that a set
of separate purchases does not have; bars stand apart, and a period nothing was
bought in simply has no bar over its place on the axis. Nothing is invented to
fill a gap, and no gap has to be closed up to hide one.

The chart is navigated by period rather than by zooming: every view is a named
stretch of the calendar - all time, a year, a month, a week - which can be
stepped through and drilled into. There is no way to arrive at a view of
nothing, which free zooming made both possible and easy.
"""

import calendar
from datetime import date, timedelta

import matplotlib

# The canvas is embedded in a Qt widget, so the Qt backend has to be selected
# before pyplot-related modules pick an interactive one of their own.
matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.formatting import CURRENCY_PREFIX, format_currency
from app.ui.styles import app_stylesheet


CARD_BACKGROUND = "#FFFFFF"
BAR_COLOUR = "#2563EB"
GRID_COLOUR = "#E2E8F0"
AXIS_TEXT_COLOUR = "#64748B"

EMPTY_MESSAGE = "No Spending Data Available"
EMPTY_PERIOD_MESSAGE = "Nothing was recorded in this period"

ALL = "all"
YEAR = "year"
MONTH = "month"
WEEK = "week"
DAY = "day"

# What one bar covers in each view, and the view a bar opens when it is
# clicked. A day has no narrower period inside it, so clicking one opens the
# receipts it was added up from instead.
BARS_IN = {ALL: YEAR, YEAR: MONTH, MONTH: DAY, WEEK: DAY}
DRILLS_INTO = {ALL: YEAR, YEAR: MONTH}

SCOPE_OPTIONS = (
    ("All time", ALL),
    ("A year at a time", YEAR),
    ("A month at a time", MONTH),
    ("A week at a time", WEEK),
)

# Room one bar label needs before it touches its neighbour.
LABEL_WIDTH_PX = 52
AXIS_MARGIN_PX = 90
# Past this many bars the figures written over them run together.
MAX_ANNOTATED_BARS = 14
# A bar keeps a share of the room its period has, up to a width past which it
# reads as a slab rather than a bar - three years should not fill the panel.
BAR_SHARE_OF_SLOT = 0.66
MAX_BAR_WIDTH_PX = 88

# Room a statistics card needs before its figure has to wrap.
CARD_WIDTH_PX = 176


# --------------------------------------------------------------------- periods


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


def period_start(day, scope):
    """The first day of the year, month, or week a date falls in."""
    if scope == YEAR:
        return date(day.year, 1, 1)
    if scope == MONTH:
        return date(day.year, day.month, 1)
    if scope == WEEK:
        return day - timedelta(days=day.weekday())

    return day


def period_end(start, scope):
    """The last day of a period that begins on a date."""
    if scope == YEAR:
        return date(start.year, 12, 31)
    if scope == MONTH:
        return date(
            start.year, start.month, calendar.monthrange(start.year, start.month)[1]
        )
    if scope == WEEK:
        return start + timedelta(days=6)

    return start


def shift_period(start, scope, steps):
    """The period a number of steps before or after this one."""
    if scope == YEAR:
        return date(start.year + steps, 1, 1)
    if scope == MONTH:
        months = start.year * 12 + start.month - 1 + steps
        return date(months // 12, months % 12 + 1, 1)
    if scope == WEEK:
        return start + timedelta(weeks=steps)

    return start + timedelta(days=steps)


def slots_between(first, last, scope):
    """Every period from one date to another, however empty some of them are.

    The empty ones are what make the axis a calendar: a month with no receipts
    keeps its place in the year, and carries no bar to say so.
    """
    slots = []
    current = period_start(first, scope)
    while current <= last:
        slots.append(current)
        current = shift_period(current, scope, 1)

    return slots


def totals_by_slot(spending, first, last, scope):
    """``{period: cents}`` across a window, zero where nothing was spent."""
    totals = {slot: 0 for slot in slots_between(first, last, scope)}

    for day, cents in spending.items():
        slot = period_start(day, scope)
        if slot in totals:
            totals[slot] += cents

    return totals


def yearly_totals(spending):
    """Every recorded year, as one total each.

    The dashboard panel is a summary: a year to a bar says how spending is
    going without asking anybody to read a month off a small chart.
    """
    if not spending:
        return {}

    return totals_by_slot(spending, min(spending), max(spending), YEAR)


def recorded_span(spending):
    """The months the record runs between, e.g. ``'Jun 2026 - Aug 2026'``."""
    if not spending:
        return ""

    return format_slot_span(
        period_start(min(spending), MONTH), period_start(max(spending), MONTH), MONTH
    )


def format_period(start, scope, recorded=None):
    """What the view is called, e.g. ``'March 2026'``.

    All time is named after the spending it covers rather than left as a word,
    so the heading always says which dates are on screen.
    """
    if scope == ALL or start is None:
        if not recorded:
            return "All time"
        first, last = recorded

        return f"All time  ·  {first.strftime('%b %Y')} - {last.strftime('%b %Y')}"
    if scope == YEAR:
        return start.strftime("%Y")
    if scope == MONTH:
        return start.strftime("%B %Y")
    if scope == WEEK:
        week_start = period_start(start, WEEK)

        return (
            f"{week_start.strftime('%d %b')} - "
            f"{period_end(week_start, WEEK).strftime('%d %b %Y')}"
        )

    return start.strftime("%d %b %Y")


def format_slot(slot, scope):
    """A period as it is written in a figure, e.g. ``'Aug 2026'``."""
    if scope == YEAR:
        return slot.strftime("%Y")
    if scope == MONTH:
        return slot.strftime("%b %Y")

    return slot.strftime("%d %b %Y")


def format_slot_span(first, last, scope):
    """The stretch a run of periods covers, e.g. ``'Sep 2025 - Aug 2026'``."""
    if first is None or last is None:
        return ""
    if first == last:
        return format_slot(first, scope)

    return f"{format_slot(first, scope)} - {format_slot(last, scope)}"


def bar_labels(slots, bar_scope, view_scope=None):
    """What is written under each bar.

    The year is written under January so that a run of months still reads as a
    calendar without the year being repeated twelve times over.
    """
    if bar_scope == YEAR:
        return [slot.strftime("%Y") for slot in slots]

    if bar_scope == MONTH:
        return [
            slot.strftime("%b\n%Y")
            if index == 0 or slot.month == 1
            else slot.strftime("%b")
            for index, slot in enumerate(slots)
        ]

    if view_scope == WEEK:
        return [slot.strftime("%a\n%d") for slot in slots]

    return [str(slot.day) for slot in slots]


def opening_view(spending):
    """The narrowest view that still holds everything recorded.

    Opening on all time would show a single bar to somebody with a month of
    receipts, and a year of them to somebody with ten years.
    """
    if not spending:
        return (ALL, None)

    first, last = min(spending), max(spending)
    if period_start(first, MONTH) == period_start(last, MONTH):
        return (MONTH, first)
    if first.year == last.year:
        return (YEAR, first)

    return (ALL, None)


# ----------------------------------------------------------------------- chart


class SpendingBarChart(FigureCanvasQTAgg):
    """Spending as one bar per period, drawn to match the application theme."""

    bar_clicked = pyqtSignal(object)
    enlarge_requested = pyqtSignal()

    def __init__(self, parent=None, interactive=False):
        self.figure = Figure(figsize=(5, 3), dpi=100, facecolor=CARD_BACKGROUND)
        super().__init__(self.figure)
        self.setParent(parent)
        # The enlarged chart is drilled into by clicking a bar; the small one
        # opens the enlarged one when it is double-clicked.
        self.interactive = interactive
        self.slots = []
        self.totals = {}
        self.labels = []
        self.annotate = False
        self.label_step = 1
        self.bar_width = BAR_SHARE_OF_SLOT
        self.setMinimumHeight(330 if interactive else 250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(
            "Click a bar to open it" if interactive else "Double-click to enlarge"
        )

    # -------------------------------------------------------------------- draw

    def show_totals(self, totals, labels, annotate=False):
        """Draw ``{period: cents}`` in order, with a label under each bar."""
        self.totals = dict(totals)
        self.slots = list(self.totals)
        self.labels = list(labels)
        self.annotate = annotate
        self.draw_chart()

    def draw_chart(self):
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.set_facecolor(CARD_BACKGROUND)

        if not self.slots:
            self.draw_message(axes, EMPTY_MESSAGE)
            return

        amounts = [cents / 100 for cents in self.totals.values()]
        self.bar_width = self.width_of_bars(len(self.slots))
        axes.bar(
            range(len(self.slots)),
            amounts,
            width=self.bar_width,
            color=BAR_COLOUR,
            zorder=2,
        )

        self.style_axes(axes, amounts)
        if self.annotate and len(self.slots) <= MAX_ANNOTATED_BARS:
            self.write_amounts(axes, amounts)
        if not any(amounts):
            # The axis still shows the period; only the bars are missing. A
            # scale of its own would be a run of rounded-off zeroes and ones,
            # so it is left as the single line the bars would have stood on.
            axes.set_yticks([0])
            axes.text(
                0.5,
                0.5,
                EMPTY_PERIOD_MESSAGE,
                horizontalalignment="center",
                verticalalignment="center",
                color=AXIS_TEXT_COLOUR,
                fontsize=10,
                transform=axes.transAxes,
            )

        self.figure.tight_layout()
        self.draw_idle()

    def draw_message(self, axes, message):
        axes.text(
            0.5,
            0.5,
            message,
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
            f"Spending ({CURRENCY_PREFIX})",
            color=AXIS_TEXT_COLOUR,
            fontsize=label_size + 1,
        )
        axes.grid(True, axis="y", color=GRID_COLOUR, linewidth=1)
        axes.set_axisbelow(True)
        axes.tick_params(colors=AXIS_TEXT_COLOUR, labelsize=label_size, length=0)
        axes.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
        for side in ("top", "right", "left"):
            axes.spines[side].set_visible(False)
        axes.spines["bottom"].set_color(GRID_COLOUR)

        axes.set_xlim(-0.7, len(self.slots) - 0.3)
        # A period with nothing in it still needs a scale to draw its axis on.
        axes.set_ylim(bottom=0, top=(max(amounts) * 1.16) or 1)

        self.label_step = self.slot_label_step(len(self.slots))
        ticks = list(range(0, len(self.slots), self.label_step))
        axes.set_xticks(ticks)
        axes.set_xticklabels([self.labels[tick] for tick in ticks])

    def write_amounts(self, axes, amounts):
        for position, amount in enumerate(amounts):
            if not amount:
                continue
            axes.annotate(
                f"{amount:,.0f}",
                (position, amount),
                textcoords="offset points",
                xytext=(0, 5),
                horizontalalignment="center",
                color=AXIS_TEXT_COLOUR,
                fontsize=8,
                fontweight="bold",
            )

    def width_of_bars(self, slot_count):
        """How much of its slot a bar fills, as a fraction of the slot."""
        slot_width_px = max((self.width() - AXIS_MARGIN_PX) / max(slot_count, 1), 1)

        return min(BAR_SHARE_OF_SLOT, MAX_BAR_WIDTH_PX / slot_width_px)

    def slot_label_step(self, slot_count):
        """Label every nth bar, n chosen so the labels do not overlap."""
        usable_width = max(self.width() - AXIS_MARGIN_PX, LABEL_WIDTH_PX)
        room = max(int(usable_width // LABEL_WIDTH_PX), 1)

        # Ceiling division: 31 days into room for 8 labels is every 4th day.
        return max(-(-slot_count // room), 1)

    # ---------------------------------------------------------------- reactions

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.slots:
            return

        # Only a change of spacing needs the figure drawn again. Bar widths are
        # a share of a slot, so they hold their proportions until one is due.
        outgrown = abs(self.width_of_bars(len(self.slots)) - self.bar_width) > 0.05
        if outgrown or self.label_step != self.slot_label_step(len(self.slots)):
            self.draw_chart()

    def bar_at(self, position_x):
        """The period under a point across the canvas, or None if there is none."""
        if not self.slots or not self.figure.axes:
            return None

        axes = self.figure.axes[0]
        x_data, _ = axes.transData.inverted().transform(
            (position_x * self.device_pixel_ratio, 0)
        )
        index = round(x_data)
        if 0 <= index < len(self.slots) and abs(x_data - index) <= 0.5:
            return self.slots[index]

        return None

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if not self.interactive or event.button() != Qt.MouseButton.LeftButton:
            return

        slot = self.bar_at(event.position().x())
        if slot is not None:
            self.bar_clicked.emit(slot)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if not self.interactive:
            self.enlarge_requested.emit()


# ---------------------------------------------------------------------- window


class SpendingTrendDialog(QDialog):
    """The spending chart at full size, navigated a period at a time."""

    def __init__(self, daily_spending, receipts_by_day=None, parent=None):
        super().__init__(parent)
        self.daily_spending = dict(daily_spending)
        self.receipts_by_day = dict(receipts_by_day or {})
        self.spending = to_dates(daily_spending)
        self.scope, self.anchor = opening_view(self.spending)
        self.setWindowTitle("Spending over time")
        # Without this the window manager offers no way to maximise a dialog.
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(1040, 700)
        self.setMinimumSize(640, 480)
        self.build_ui()
        self.select_scope_quietly(self.scope)
        self.refresh()
        self.setStyleSheet(app_stylesheet())

    # ------------------------------------------------------------------ layout

    def build_ui(self):
        root = QWidget()
        root.setObjectName("dialogRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(14)

        title = QLabel("Spending over time")
        title.setObjectName("dialogTitle")
        root_layout.addWidget(title)

        self.period_label = QLabel()
        self.period_label.setObjectName("dialogSubtitle")
        root_layout.addWidget(self.period_label)

        root_layout.addLayout(self.build_controls())

        panel = QFrame()
        panel.setObjectName("dashboardPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        self.chart = SpendingBarChart(interactive=True)
        self.chart.bar_clicked.connect(self.drill_into)
        panel_layout.addWidget(self.chart)
        root_layout.addWidget(panel, stretch=1)

        root_layout.addLayout(self.build_buttons())

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root)

    def build_controls(self):
        controls = QHBoxLayout()
        controls.setSpacing(10)
        # The row runs from the same edge as the heading above it.
        controls.setContentsMargins(0, 0, 0, 0)

        self.scope_selector = QComboBox()
        self.scope_selector.setObjectName("chartRangeSelector")
        for label, scope in SCOPE_OPTIONS:
            self.scope_selector.addItem(label, scope)
        self.scope_selector.currentIndexChanged.connect(self.change_scope)
        controls.addWidget(self.scope_selector)

        self.previous_button = self.add_step_button(controls, "◀", -1, "Earlier")
        self.next_button = self.add_step_button(controls, "▶", 1, "Later")

        hint = QLabel("Click a bar to open it  ·  click a day to see what was bought")
        hint.setObjectName("panelCaption")
        controls.addWidget(hint)
        controls.addStretch(1)

        return controls

    def add_step_button(self, layout, arrow, direction, tooltip):
        button = QPushButton(arrow)
        button.setObjectName("stepButton")
        button.setToolTip(tooltip)
        button.clicked.connect(lambda: self.step(direction))
        layout.addWidget(button)

        return button

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

    # -------------------------------------------------------------- navigation

    def recorded_range(self):
        if not self.spending:
            return None

        return (min(self.spending), max(self.spending))

    def bounds(self):
        """The first and last day the view covers."""
        if self.scope == ALL or self.anchor is None:
            return self.recorded_range()

        return (
            period_start(self.anchor, self.scope),
            period_end(period_start(self.anchor, self.scope), self.scope),
        )

    def current_totals(self):
        bounds = self.bounds()
        if bounds is None:
            return {}

        return totals_by_slot(self.spending, *bounds, BARS_IN[self.scope])

    def refresh(self):
        totals = self.current_totals()
        self.chart.show_totals(
            totals,
            bar_labels(list(totals), BARS_IN[self.scope], self.scope),
            annotate=True,
        )
        self.period_label.setText(
            format_period(self.anchor, self.scope, self.recorded_range())
            if self.spending
            else "Nothing has been recorded yet."
        )
        self.statistics_button.setEnabled(bool(self.spending))
        self.previous_button.setEnabled(self.can_step(-1))
        self.next_button.setEnabled(self.can_step(1))

    def can_step(self, direction):
        """Whether any recorded spending lies the other side of this view."""
        recorded = self.recorded_range()
        if recorded is None or self.scope == ALL or self.anchor is None:
            return False

        start = period_start(self.anchor, self.scope)
        if direction > 0:
            return recorded[1] > period_end(start, self.scope)

        return recorded[0] < start

    def step(self, direction):
        if not self.can_step(direction):
            return

        self.anchor = shift_period(
            period_start(self.anchor, self.scope), self.scope, direction
        )
        self.refresh()

    def change_scope(self):
        scope = self.scope_selector.currentData()
        if scope == self.scope:
            return

        self.scope = scope
        # Widening or narrowing keeps a date that is already on screen in view.
        if scope != ALL and self.anchor is None:
            self.anchor = max(self.spending) if self.spending else date.today()
        self.refresh()

    def drill_into(self, slot):
        """Open what a bar holds: a narrower period, or the day's receipts."""
        narrower = DRILLS_INTO.get(self.scope)
        if narrower is None:
            self.show_purchases(slot)
            return

        self.scope = narrower
        self.anchor = slot
        self.select_scope_quietly(narrower)
        self.refresh()

    def show_purchases(self, day):
        """List the receipts a day's bar was added up from."""
        PurchasesDialog(day, self.receipts_by_day.get(day.isoformat(), []), parent=self).exec()

    def select_scope_quietly(self, scope):
        """Keep the selector in step with a view reached by clicking a bar."""
        self.scope_selector.blockSignals(True)
        self.scope_selector.setCurrentIndex(self.scope_selector.findData(scope))
        self.scope_selector.blockSignals(False)

    def open_statistics(self):
        StatisticsDialog(
            self.current_totals(),
            BARS_IN[self.scope],
            format_period(self.anchor, self.scope, self.recorded_range()),
            parent=self,
        ).exec()

    # -------------------------------------------------------------- full screen

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
        if event.key() == Qt.Key.Key_Left:
            self.step(-1)
            return
        if event.key() == Qt.Key.Key_Right:
            self.step(1)
            return

        super().keyPressEvent(event)


class PurchasesDialog(QDialog):
    """What was actually bought on one day, behind that day's bar."""

    def __init__(self, day, receipts, parent=None):
        super().__init__(parent)
        self.day = day
        self.receipts = list(receipts)
        self.setWindowTitle("Purchases")
        self.setMinimumWidth(560)
        self.build_ui()
        self.setStyleSheet(app_stylesheet())

    def build_ui(self):
        root = QWidget()
        root.setObjectName("dialogRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(14)

        title = QLabel(self.day.strftime("%d %B %Y"))
        title.setObjectName("dialogTitle")
        root_layout.addWidget(title)

        subtitle = QLabel(self.describe_day())
        subtitle.setObjectName("dialogSubtitle")
        root_layout.addWidget(subtitle)

        root_layout.addWidget(self.build_list(), stretch=1)

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

    def build_list(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("deadlineScrollArea")
        scroll_area.setMinimumHeight(180)

        content = QWidget()
        content.setObjectName("deadlineContent")
        layout = QVBoxLayout(content)
        # A right margin keeps the prices clear of the scrollbar.
        layout.setContentsMargins(0, 0, 16, 0)
        layout.setSpacing(8)

        for receipt in self.receipts:
            layout.addWidget(self.build_row(receipt))
        if not self.receipts:
            empty = QLabel("Nothing was bought on this day.")
            empty.setObjectName("dashboardEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
        layout.addStretch(1)

        scroll_area.setWidget(content)
        return scroll_area

    @staticmethod
    def build_row(receipt):
        row = QFrame()
        row.setObjectName("purchaseRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        details = QVBoxLayout()
        details.setSpacing(2)
        layout.addLayout(details, stretch=1)

        product = QLabel(receipt.product_name)
        product.setObjectName("purchaseProduct")
        product.setWordWrap(True)
        details.addWidget(product)

        meta = QLabel(f"{receipt.merchant_name}  ·  {receipt.category_name}")
        meta.setObjectName("purchaseMeta")
        meta.setWordWrap(True)
        details.addWidget(meta)

        price = QLabel(format_currency(receipt.price_cents))
        price.setObjectName("purchasePrice")
        layout.addWidget(price)

        return row

    def describe_day(self):
        if not self.receipts:
            return "This day has no receipts against it."

        total = sum(receipt.price_cents for receipt in self.receipts)
        counted = "purchase" if len(self.receipts) == 1 else "purchases"

        return f"{len(self.receipts)} {counted}  ·  {format_currency(total)} in total"


class StatisticsDialog(QDialog):
    """The figures behind the period on screen, a card to each."""

    def __init__(self, totals, scope, period_name, parent=None):
        super().__init__(parent)
        self.totals = dict(totals)
        self.scope = scope
        self.period_name = period_name
        self.setWindowTitle("Statistics")
        self.setMinimumWidth(4 * CARD_WIDTH_PX + 90)
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
        self.card_labels = []
        self.card_values = []
        for label_text, value_text in self.figures():
            label, value = self.add_card(cards, label_text, value_text)
            self.card_labels.append(label)
            self.card_values.append(value)

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
        """One figure, as a card. Returns its label and value to be measured."""
        card = QFrame()
        card.setObjectName("dashboardSummaryCard")
        card.setMinimumWidth(CARD_WIDTH_PX)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("dashboardMetricLabel")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        card_layout.addWidget(label)

        value = QLabel(value_text)
        value.setObjectName("statisticValue")
        # Figures are written on one line: a wrapped amount reads as two.
        value.setWordWrap(False)
        card_layout.addWidget(value)

        layout.addWidget(card, stretch=1)
        return label, value

    def showEvent(self, event):
        super().showEvent(event)
        # The stylesheet's fonts only reach these labels when the dialog is
        # polished, and the sizes they reported before that were measured in
        # the default font. Both are settled here, once the figures are as
        # large as they are going to be.
        for label in self.card_labels:
            # Two lines of room whether a label needs them or not, so one that
            # wraps cannot push its own figure out of line with the others.
            label.setFixedHeight(2 * QFontMetrics(label.font()).height())
        for value in self.card_values:
            value.setMinimumWidth(
                QFontMetrics(value.font()).horizontalAdvance(value.text())
            )

        for layout in self.findChildren(QLayout):
            layout.invalidate()
        self.layout().activate()
        self.resize(self.sizeHint())

    def describe_period(self):
        if not self.spent_slots():
            return f"Nothing was recorded in {self.period_name}."

        return f"Everything on the chart right now: {self.period_name}."

    def spent_slots(self):
        """The periods that hold spending, the empty ones left out."""
        return {slot: cents for slot, cents in self.totals.items() if cents}

    def figures(self):
        """The four figures, each as one card's label and value."""
        spent = self.spent_slots()
        if not spent:
            return [("Total spending", format_currency(0))]

        total_cents = sum(spent.values())
        highest = max(spent, key=spent.get)
        counted = f"{self.scope}s" if len(spent) != 1 else self.scope

        return [
            ("Total spending", format_currency(total_cents)),
            (f"{counted.capitalize()} with spending", str(len(spent))),
            (
                f"Average per {self.scope}",
                format_currency(round(total_cents / len(spent))),
            ),
            (
                # The date is put on its own line rather than left to wrap
                # wherever it happens to run out of card.
                f"Highest {self.scope}\n({format_slot(highest, self.scope)})",
                format_currency(spent[highest]),
            ),
        ]
