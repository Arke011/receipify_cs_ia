"""Dashboard tab: total spending, a spending chart, category shares and upcoming deadlines."""

from calendar import month_abbr
from dataclasses import dataclass
from datetime import date

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QScrollArea,
    QSizePolicy, QStyle, QToolTip, QVBoxLayout, QWidget,
)

from receipt import Receipt, days_until, format_euros, parse_date

DEADLINE_WINDOW_DAYS = 30


@dataclass
class Deadline:
    receipt: Receipt
    period: str  # "Warranty" or "Return"
    expiry: str
    days_left: int


@dataclass
class Summary:
    total_cents: int
    active_warranties: int
    expired_warranties: int
    by_category: dict[str, int]  # category -> cents, largest first
    by_month: dict[int, list[int]]  # year -> twelve monthly totals in cents
    deadlines: list[Deadline]  # periods ending in the next 30 days, soonest first


def summarize(receipts, today=None):
    """All the dashboard's figures, worked out in one pass over the receipts."""
    today = today or date.today()
    total = active = expired = 0
    by_category = {}
    by_month = {}
    deadlines = []
    for receipt in receipts:
        total += receipt.price_cents
        by_category[receipt.category] = by_category.get(receipt.category, 0) + receipt.price_cents
        purchased = parse_date(receipt.purchase_date)
        if purchased is None:
            continue  # still counted in the totals above, but it cannot be placed on the chart
        by_month.setdefault(purchased.year, [0] * 12)[purchased.month - 1] += receipt.price_cents

        for period, expiry in (("Warranty", receipt.warranty_expiry()), ("Return", receipt.return_expiry())):
            if expiry is None:
                continue
            days_left = days_until(expiry, today)
            if period == "Warranty":
                if days_left >= 0:
                    active += 1
                else:
                    expired += 1
            if 0 <= days_left <= DEADLINE_WINDOW_DAYS:
                deadlines.append(Deadline(receipt, period, expiry, days_left))

    return Summary(
        total_cents=total,
        active_warranties=active,
        expired_warranties=expired,
        by_category=dict(sorted(by_category.items(), key=lambda item: (-item[1], item[0].casefold()))),
        by_month=dict(sorted(by_month.items())),
        deadlines=sorted(deadlines, key=lambda d: (d.days_left, d.receipt.product.casefold(), d.period)),
    )


class SpendingChart(FigureCanvasQTAgg):
    """A bar chart of spending, coloured to match the system theme, with the exact amount on hover."""

    def __init__(self):
        super().__init__(Figure(figsize=(5, 3), layout="constrained"))
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.labels = []
        self.cents = []

    def show_totals(self, labels, cents):
        self.labels, self.cents = list(labels), list(cents)
        self.figure.clear()
        # Matplotlib draws on white by default; use the app's colours instead.
        palette = QApplication.palette()
        background = palette.color(QPalette.ColorRole.Window).name()
        foreground = palette.color(QPalette.ColorRole.WindowText).name()
        accent = palette.color(QPalette.ColorRole.Highlight).name()
        self.figure.set_facecolor(background)
        axes = self.figure.add_subplot(111)
        axes.set_facecolor(background)
        if not self.labels:
            axes.text(0.5, 0.5, "No Spending Data Available", ha="center", va="center",
                      color=foreground, transform=axes.transAxes)
            axes.set_axis_off()
        else:
            amounts = [value / 100 for value in self.cents]
            axes.bar(range(len(amounts)), amounts, width=0.55, color=accent, zorder=2)
            axes.set_xticks(range(len(amounts)), self.labels)
            axes.set_ylabel("Spending (EUR)", color=foreground, fontsize=9)
            axes.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.2f}"))
            axes.tick_params(colors=foreground, labelsize=8, length=0)
            axes.set_ylim(0, max(amounts) * 1.16 or 1)
            axes.grid(axis="y", color=foreground, alpha=0.2)
            axes.set_axisbelow(True)
            for side in ("top", "right", "left"):
                axes.spines[side].set_visible(False)
            axes.spines["bottom"].set_color(foreground)
        self.draw_idle()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.labels:
            axes = self.figure.axes[0]
            # Qt measures from the top-left in logical pixels, Matplotlib from the bottom-left in device pixels.
            x = event.position().x() * self.device_pixel_ratio
            y = (self.height() - event.position().y()) * self.device_pixel_ratio
            if axes.bbox.contains(x, y):
                bar = round(axes.transData.inverted().transform((x, y))[0])
                if 0 <= bar < len(self.labels):
                    QToolTip.showText(event.globalPosition().toPoint(),
                                      f"{self.labels[bar]}: {format_euros(self.cents[bar])}", self)
                    return
        QToolTip.hideText()

    def changeEvent(self, event):
        super().changeEvent(event)
        # Redraw when the system switches between light and dark mode. The palette
        # can change before __init__ has created self.labels, hence the hasattr.
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange) and hasattr(self, "labels"):
            self.show_totals(self.labels, self.cents)


class DashboardPage(QWidget):
    def __init__(self, db, user_id):
        super().__init__()
        self.db = db
        self.user_id = user_id

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)
        content = QWidget()
        scroll_area.setWidget(content)
        layout = QVBoxLayout(content)

        stats = QHBoxLayout()
        self.total_label = self.add_stat(stats, "Total spending")
        self.active_label = self.add_stat(stats, "Active warranties")
        self.expired_label = self.add_stat(stats, "Expired records")
        layout.addLayout(stats)

        middle = QHBoxLayout()
        chart_panel = QGroupBox("Spending over time")
        chart_layout = QVBoxLayout(chart_panel)
        period_row = QHBoxLayout()
        self.year_selector = QComboBox()
        self.year_selector.setAccessibleName("Chart spending period")
        self.year_selector.setToolTip("All years shows yearly totals; choose a year to see its months.")
        self.year_selector.currentIndexChanged.connect(self.show_chart)
        period_row.addWidget(QLabel("Period"))
        period_row.addWidget(self.year_selector)
        period_row.addStretch()
        chart_layout.addLayout(period_row)
        self.chart = SpendingChart()
        chart_layout.addWidget(self.chart)
        middle.addWidget(chart_panel, stretch=3)
        category_panel = QGroupBox("Category spending")
        self.category_layout = QVBoxLayout(category_panel)
        middle.addWidget(category_panel, stretch=2)
        layout.addLayout(middle)

        deadline_panel = QGroupBox(f"Upcoming deadlines (next {DEADLINE_WINDOW_DAYS} days)")
        deadline_scroll = QScrollArea()
        deadline_scroll.setWidgetResizable(True)
        deadline_scroll.setMinimumHeight(180)
        QVBoxLayout(deadline_panel).addWidget(deadline_scroll)
        deadline_content = QWidget()
        self.deadline_layout = QVBoxLayout(deadline_content)
        self.deadline_layout.setContentsMargins(0, 0, 16, 0)  # keeps the badges clear of the scrollbar
        self.deadline_layout.setSpacing(8)
        deadline_scroll.setWidget(deadline_content)
        layout.addWidget(deadline_panel)
        layout.addStretch(1)
        self.refresh()

    @staticmethod
    def add_stat(row, title):
        box = QGroupBox(title)
        value = QLabel("0")
        QVBoxLayout(box).addWidget(value)
        row.addWidget(box, stretch=1)
        return value

    def refresh(self):
        """Reload the receipts once and redraw everything, keeping the chart's chosen year if it still exists."""
        self.summary = summarize(self.db.receipts(self.user_id))
        self.total_label.setText(format_euros(self.summary.total_cents))
        self.active_label.setText(str(self.summary.active_warranties))
        self.expired_label.setText(str(self.summary.expired_warranties))
        self.show_categories()
        self.show_deadlines()

        chosen_year = self.year_selector.currentData()
        self.year_selector.blockSignals(True)
        self.year_selector.clear()
        self.year_selector.addItem("All years", None)
        for year in reversed(self.summary.by_month):
            self.year_selector.addItem(str(year), year)
        self.year_selector.setCurrentIndex(max(self.year_selector.findData(chosen_year), 0))
        self.year_selector.blockSignals(False)
        self.show_chart()

    def show_chart(self):
        """Yearly totals for "All years" (including years with no spending), or one year's months."""
        year = self.year_selector.currentData()
        by_month = self.summary.by_month
        if year is not None:
            self.chart.show_totals(month_abbr[1:], by_month[year])
        elif by_month:
            years = range(min(by_month), max(by_month) + 1)
            self.chart.show_totals([str(y) for y in years], [sum(by_month.get(y, [])) for y in years])
        else:
            self.chart.show_totals([], [])

    def show_categories(self):
        clear_layout(self.category_layout)
        total = sum(self.summary.by_category.values())
        if not total:
            self.category_layout.addWidget(placeholder("No Spending Data Available"))
            self.category_layout.addStretch(1)
            return
        for category, cents in self.summary.by_category.items():
            share = cents / total * 100
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            header = QHBoxLayout()
            header.setSpacing(8)
            name = QLabel(category)
            name.setTextFormat(Qt.TextFormat.PlainText)
            name.setWordWrap(True)
            header.addWidget(name, stretch=1)
            # The share sits beside the amount; printed on the bar it would be half unreadable.
            header.addWidget(QLabel(f"{share:.1f}%  ·  {format_euros(cents)}"))
            row_layout.addLayout(header)
            bar = QProgressBar()
            bar.setRange(0, 1000)  # tenths of a percent, to match the printed share
            bar.setValue(round(share * 10))
            bar.setTextVisible(False)
            row_layout.addWidget(bar)
            self.category_layout.addWidget(row)
        self.category_layout.addStretch(1)  # rows start at the top of the panel

    def show_deadlines(self):
        clear_layout(self.deadline_layout)
        if not self.summary.deadlines:
            self.deadline_layout.addWidget(placeholder(f"Nothing is expiring in the next {DEADLINE_WINDOW_DAYS} days."))
        warning_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(16, 16)
        for deadline in self.summary.deadlines:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 4, 0, 4)
            row_layout.setSpacing(12)
            details = QVBoxLayout()
            details.setSpacing(2)
            for text in (deadline.receipt.product, f"{deadline.receipt.merchant}  ·  {deadline.period}"):
                label = QLabel(text)
                label.setTextFormat(Qt.TextFormat.PlainText)
                label.setWordWrap(True)
                details.addWidget(label)
            row_layout.addLayout(details, stretch=1)
            row_layout.addWidget(QLabel(deadline.expiry))
            icon = QLabel()
            icon.setPixmap(warning_icon)
            row_layout.addWidget(icon)
            badge = QLabel("Expiring soon")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row_layout.addWidget(badge)
            self.deadline_layout.addWidget(row)
        self.deadline_layout.addStretch(1)


def placeholder(message):
    label = QLabel(message)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


def clear_layout(layout):
    """Remove every row from a layout. Rows are hidden at once, then deleted by Qt when it is idle."""
    while layout.count():
        widget = layout.takeAt(0).widget()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
