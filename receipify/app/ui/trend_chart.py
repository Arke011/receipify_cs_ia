"""The monthly spending chart, and the enlarged window it opens into.

The chart lives here rather than on the dashboard page because the enlarged
view draws the very same figure, only larger and over a range the user picks.
"""

from datetime import datetime

import matplotlib

# The canvas is embedded in a Qt widget, so the Qt backend has to be selected
# before pyplot-related modules pick an interactive one of their own.
matplotlib.use("QtAgg")

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

# About the width one "Aug 26" label needs before it touches its neighbour.
# Labels are thinned out to fit rather than rotated into an unreadable fan.
LABEL_WIDTH_PX = 58
# Room the y axis and its label take out of the canvas before months start.
AXIS_MARGIN_PX = 90

# Points stop being marked, then annotated, once the months get this dense.
MAX_MARKED_MONTHS = 30
MAX_ANNOTATED_MONTHS = 14

RANGE_OPTIONS = (
    ("Last 6 months", 6),
    ("Last 12 months", 12),
    ("Last 24 months", 24),
    ("All recorded months", None),
)


def format_month(month, short=True):
    """``'2026-08'`` as ``'Aug 26'``, or ``'Aug 2026'`` when not shortened."""
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except (TypeError, ValueError):
        return str(month)

    return parsed.strftime("%b %y") if short else parsed.strftime("%b %Y")


def format_month_range(months):
    """The span a chart covers, e.g. ``'Jul 2025 - Aug 2026'``."""
    if not months:
        return ""
    if len(months) == 1:
        return format_month(months[0], short=False)

    return f"{format_month(months[0], short=False)} - {format_month(months[-1], short=False)}"


def take_recent_months(monthly_spending, limit):
    """The last ``limit`` months of a timeline, or all of it when limit is None."""
    if limit is None:
        return dict(monthly_spending)

    months = list(monthly_spending)[-limit:]
    return {month: monthly_spending[month] for month in months}


def available_ranges(month_count):
    """The range options worth offering for a history of this length.

    Ranges longer than the history all show the same chart, so only the ones
    that actually cut something off are kept.
    """
    options = [
        (label, limit)
        for label, limit in RANGE_OPTIONS
        if limit is not None and limit < month_count
    ]
    options.append(RANGE_OPTIONS[-1])
    return options


class MonthlyTrendChart(FigureCanvasQTAgg):
    """A line chart of spending per month, drawn to match the application theme."""

    enlarge_requested = pyqtSignal()

    def __init__(self, parent=None, detailed=False):
        self.figure = Figure(figsize=(5, 3), dpi=100, facecolor=CARD_BACKGROUND)
        super().__init__(self.figure)
        self.setParent(parent)
        # The enlarged copy has the room for year labels and figures on the points.
        self.detailed = detailed
        self.monthly_spending = {}
        self.months = []
        self.label_step = 1
        self.setMinimumHeight(320 if detailed else 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if not detailed:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Double-click to enlarge")

    # -------------------------------------------------------------------- draw

    def plot(self, monthly_spending):
        self.monthly_spending = dict(monthly_spending)
        self.months = list(self.monthly_spending)

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.set_facecolor(CARD_BACKGROUND)

        if not self.months:
            self.draw_empty_message(axes)
            return

        amounts = [cents / 100 for cents in self.monthly_spending.values()]
        positions = list(range(len(self.months)))

        axes.plot(
            positions,
            amounts,
            color=LINE_COLOUR,
            linewidth=2.2,
            marker="o" if len(self.months) <= MAX_MARKED_MONTHS else None,
            markersize=5,
            markerfacecolor=LINE_COLOUR,
            markeredgecolor=CARD_BACKGROUND,
        )
        axes.fill_between(positions, amounts, color=LINE_COLOUR, alpha=0.08)

        self.style_axes(axes, positions)
        if self.detailed and len(self.months) <= MAX_ANNOTATED_MONTHS:
            self.annotate_points(axes, positions, amounts)

        self.figure.tight_layout()
        self.draw_idle()

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

    def style_axes(self, axes, positions):
        label_size = 9 if self.detailed else 8

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

        # A single month has no line to read, so its marker is given room either side.
        if len(positions) == 1:
            axes.set_xlim(-0.5, 0.5)
        else:
            # The enlarged chart writes each figure over its point, so the end
            # months are given the room to carry one without it being cut off.
            edge = 0.5 if self.detailed else 0.3
            axes.set_xlim(positions[0] - edge, positions[-1] + edge)
        axes.set_ylim(bottom=0)

        self.label_step = self.month_label_step(len(positions))
        # Stepping back from the newest month keeps it labelled, which is the
        # one a reader looks for first.
        ticks = sorted(positions[::-1][:: self.label_step])
        axes.set_xticks(ticks)
        axes.set_xticklabels(
            [format_month(self.months[tick], short=not self.detailed) for tick in ticks]
        )

    def annotate_points(self, axes, positions, amounts):
        for position, amount in zip(positions, amounts):
            axes.annotate(
                f"{amount:,.0f}",
                (position, amount),
                textcoords="offset points",
                xytext=(0, 9),
                horizontalalignment="center",
                color=AXIS_TEXT_COLOUR,
                fontsize=8,
                fontweight="bold",
                # A steep line runs straight through where the figure sits, so
                # each one is backed by the card colour to stay readable.
                bbox={
                    "facecolor": CARD_BACKGROUND,
                    "edgecolor": "none",
                    "alpha": 0.75,
                    "pad": 1.4,
                },
            )
        # Annotations sit above the highest point, so the axis makes room for them.
        axes.set_ylim(top=max(amounts) * 1.18 if max(amounts) else 1)

    def month_label_step(self, month_count):
        """Label every nth month, n chosen so the labels do not overlap."""
        usable_width = max(self.width() - AXIS_MARGIN_PX, LABEL_WIDTH_PX)
        label_room = max(int(usable_width // LABEL_WIDTH_PX), 1)
        # Ceiling division: 14 months into room for 6 labels is every 3rd month.
        return max(-(-month_count // label_room), 1)

    # ---------------------------------------------------------------- reactions

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Only a change of spacing needs the figure drawn again; every other
        # resize is handled by the canvas itself.
        if self.months and self.label_step != self.month_label_step(len(self.months)):
            self.plot(self.monthly_spending)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if not self.detailed:
            self.enlarge_requested.emit()


class SpendingTrendDialog(QDialog):
    """The spending chart at full size, over a range the user chooses."""

    def __init__(self, monthly_spending, parent=None):
        super().__init__(parent)
        self.monthly_spending = dict(monthly_spending)
        self.setWindowTitle("Monthly spending trend")
        # Without this the window manager offers no way to maximise a dialog.
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(1040, 700)
        self.setMinimumSize(600, 460)
        self.build_ui()
        self.show_selected_range()
        self.setStyleSheet(app_stylesheet())

    def build_ui(self):
        root = QWidget()
        root.setObjectName("dialogRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(14)

        title = QLabel("Monthly spending trend")
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
        self.chart = MonthlyTrendChart(detailed=True)
        panel_layout.addWidget(self.chart)
        root_layout.addWidget(panel, stretch=1)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("dashboardMetricLabel")
        root_layout.addWidget(self.summary_label)

        root_layout.addLayout(self.build_buttons())

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root)

    def build_controls(self):
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.range_selector = QComboBox()
        self.range_selector.setObjectName("filterCombo")
        for label, limit in available_ranges(len(self.monthly_spending)):
            self.range_selector.addItem(label, limit)
        # The whole history is what someone opens this window to look through;
        # the shorter ranges are there to narrow it down afterwards. The default
        # is chosen before connecting, as the chart it would redraw is not built yet.
        self.range_selector.setCurrentIndex(self.range_selector.count() - 1)
        self.range_selector.currentIndexChanged.connect(self.show_selected_range)
        self.range_prompt = QLabel("Show")
        # One option means one possible chart, so the control would do nothing.
        has_choice = self.range_selector.count() > 1
        self.range_selector.setVisible(has_choice)
        self.range_prompt.setVisible(has_choice)

        controls.addWidget(self.range_prompt)
        controls.addWidget(self.range_selector)
        controls.addStretch(1)

        return controls

    def build_buttons(self):
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
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
        months = take_recent_months(
            self.monthly_spending, self.range_selector.currentData()
        )
        self.chart.plot(months)
        self.range_label.setText(
            format_month_range(list(months)) or "Nothing has been recorded yet."
        )
        self.summary_label.setText(self.summarise(months))

    @staticmethod
    def summarise(months):
        if not months:
            return ""

        total_cents = sum(months.values())
        highest_month = max(months, key=months.get)
        average_cents = round(total_cents / len(months))

        return (
            f"{len(months)} months  ·  "
            f"Total {format_currency(total_cents)}  ·  "
            f"Average {format_currency(average_cents)} a month  ·  "
            f"Highest {format_month(highest_month, short=False)} "
            f"({format_currency(months[highest_month])})"
        )

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
