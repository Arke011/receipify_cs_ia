"""The analytics dashboard: headline figures, a spending trend, and deadlines."""

import matplotlib

# The canvas is embedded in a Qt widget, so the Qt backend has to be selected
# before pyplot-related modules pick an interactive one of their own.
matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.dashboard_service import DashboardService


CURRENCY_PREFIX = "EUR"

CARD_BACKGROUND = "#FFFFFF"
PAGE_BACKGROUND = "#F4F7FB"
LINE_COLOUR = "#2563EB"
GRID_COLOUR = "#E2E8F0"
AXIS_TEXT_COLOUR = "#64748B"


def format_currency(cents):
    """Money with thousands separators, e.g. 124550 -> 'EUR 1,245.50'."""
    return f"{CURRENCY_PREFIX} {cents / 100:,.2f}"


class MonthlyTrendChart(FigureCanvasQTAgg):
    """A line chart of spending per month, drawn to match the application theme."""

    def __init__(self, parent=None):
        self.figure = Figure(figsize=(5, 3), dpi=100, facecolor=CARD_BACKGROUND)
        super().__init__(self.figure)
        self.setParent(parent)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def plot(self, monthly_spending):
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.set_facecolor(CARD_BACKGROUND)

        if not monthly_spending:
            axes.text(
                0.5,
                0.5,
                "No Spending Data Available",
                horizontalalignment="center",
                verticalalignment="center",
                color=AXIS_TEXT_COLOUR,
                fontsize=11,
                transform=axes.transAxes,
            )
            axes.set_axis_off()
            self.figure.tight_layout()
            self.draw_idle()
            return

        months = list(monthly_spending)
        amounts = [cents / 100 for cents in monthly_spending.values()]

        axes.plot(
            months,
            amounts,
            color=LINE_COLOUR,
            linewidth=2.2,
            marker="o",
            markersize=5,
            markerfacecolor=LINE_COLOUR,
            markeredgecolor=CARD_BACKGROUND,
        )
        axes.fill_between(months, amounts, color=LINE_COLOUR, alpha=0.08)

        axes.set_ylabel(f"Spending ({CURRENCY_PREFIX})", color=AXIS_TEXT_COLOUR, fontsize=9)
        axes.grid(True, axis="y", color=GRID_COLOUR, linewidth=1)
        axes.set_axisbelow(True)
        axes.tick_params(colors=AXIS_TEXT_COLOUR, labelsize=8)
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axes.spines[side].set_color(GRID_COLOUR)

        # A single month has no line to read, so its marker is given room either side.
        if len(months) == 1:
            axes.set_xlim(-0.5, 0.5)
        axes.set_ylim(bottom=0)
        if len(months) > 6:
            for label in axes.get_xticklabels():
                label.set_rotation(45)
                label.set_horizontalalignment("right")

        self.figure.tight_layout()
        self.draw_idle()


class DashboardPage(QWidget):
    def __init__(self, data_manager, user_id, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.user_id = user_id
        self.service = DashboardService(data_manager)
        self.build_ui()
        self.refresh()

    # ------------------------------------------------------------------ layout

    def build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("dashboardScrollArea")
        root_layout.addWidget(scroll_area)

        content = QWidget()
        content.setObjectName("dashboardContent")
        scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 0, 10, 20)
        layout.setSpacing(20)

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel("A simple overview of your purchases and important dates.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        layout.addLayout(self.build_summary_row())
        layout.addLayout(self.build_split_section())
        layout.addWidget(self.build_deadlines_section())
        layout.addStretch(1)

    def build_summary_row(self):
        summary_row = QHBoxLayout()
        summary_row.setSpacing(16)

        self.total_spending_value = self.add_stat_card(summary_row, "Total spending")
        self.active_warranties_value = self.add_stat_card(summary_row, "Active warranties")
        self.expired_records_value = self.add_stat_card(summary_row, "Expired records")

        return summary_row

    def add_stat_card(self, layout, label_text):
        card = QFrame()
        card.setObjectName("dashboardSummaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("dashboardMetricLabel")
        card_layout.addWidget(label)

        value = QLabel("0")
        value.setObjectName("dashboardMetricValue")
        card_layout.addWidget(value)

        layout.addWidget(card, stretch=1)
        return value

    def build_split_section(self):
        split_row = QHBoxLayout()
        split_row.setSpacing(16)

        trend_panel, trend_layout = self.create_panel("Monthly spending trend")
        self.trend_chart = MonthlyTrendChart()
        trend_layout.addWidget(self.trend_chart)
        split_row.addWidget(trend_panel, stretch=3)

        category_panel, self.category_layout = self.create_panel("Category spending")
        split_row.addWidget(category_panel, stretch=2)

        return split_row

    def build_deadlines_section(self):
        panel, panel_layout = self.create_panel("Upcoming deadlines (next 30 days)")

        deadline_scroll = QScrollArea()
        deadline_scroll.setWidgetResizable(True)
        deadline_scroll.setObjectName("deadlineScrollArea")
        deadline_scroll.setMinimumHeight(180)
        panel_layout.addWidget(deadline_scroll)

        deadline_content = QWidget()
        deadline_content.setObjectName("deadlineContent")
        self.deadline_layout = QVBoxLayout(deadline_content)
        # Right margin keeps the status badges clear of the scrollbar.
        self.deadline_layout.setContentsMargins(0, 0, 16, 0)
        self.deadline_layout.setSpacing(8)
        deadline_scroll.setWidget(deadline_content)

        return panel

    def create_panel(self, title_text):
        panel = QFrame()
        panel.setObjectName("dashboardPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)

        title = QLabel(title_text)
        title.setObjectName("dashboardPanelTitle")
        panel_layout.addWidget(title)

        item_layout = QVBoxLayout()
        item_layout.setSpacing(10)
        panel_layout.addLayout(item_layout)

        return panel, item_layout

    # ------------------------------------------------------------------ refresh

    def refresh(self):
        """Reload every figure. Called whenever the receipts behind them change."""
        counts = self.service.get_active_and_expired_counts(self.user_id)
        self.total_spending_value.setText(
            format_currency(self.service.get_total_spending(self.user_id))
        )
        self.active_warranties_value.setText(str(counts["active"]))
        self.expired_records_value.setText(str(counts["expired"]))

        self.trend_chart.plot(self.service.get_monthly_spending(self.user_id))
        self.show_category_spending(self.service.get_category_spending(self.user_id))
        self.show_deadlines(self.service.get_upcoming_deadlines(self.user_id))

    def show_category_spending(self, category_spending):
        self.clear_layout(self.category_layout)
        total_cents = sum(category_spending.values())

        if not total_cents:
            self.category_layout.addWidget(
                self.create_placeholder("No Spending Data Available")
            )
            # Without this the panel spreads its two items out and the heading
            # drifts to the middle of an otherwise empty card.
            self.category_layout.addStretch(1)
            return

        for category_name, cents in category_spending.items():
            self.category_layout.addWidget(
                self.create_category_row(category_name, cents, total_cents)
            )
        # Rows read from the top of the panel rather than spreading down it.
        self.category_layout.addStretch(1)

    def create_category_row(self, category_name, cents, total_cents):
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)
        layout.addLayout(header)

        share = round(cents / total_cents * 100)

        name_label = QLabel(category_name)
        name_label.setObjectName("categoryName")
        header.addWidget(name_label, stretch=1)

        # The share is stated beside the amount rather than printed on the bar,
        # where it would sit half on the fill and half off it and be unreadable.
        amount_label = QLabel(f"{share}%  ·  {format_currency(cents)}")
        amount_label.setObjectName("categoryAmount")
        header.addWidget(amount_label)

        bar = QProgressBar()
        bar.setObjectName("categoryBar")
        bar.setRange(0, 100)
        bar.setValue(share)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)
        layout.addWidget(bar)

        return row

    def show_deadlines(self, deadlines):
        self.clear_layout(self.deadline_layout)

        if not deadlines:
            self.deadline_layout.addWidget(
                self.create_placeholder("Nothing is expiring in the next 30 days.")
            )
            self.deadline_layout.addStretch(1)
            return

        for item in deadlines:
            self.deadline_layout.addWidget(self.create_deadline_row(item))
        self.deadline_layout.addStretch(1)

    def create_deadline_row(self, item):
        row = QFrame()
        row.setObjectName("deadlineRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        details = QVBoxLayout()
        details.setSpacing(2)
        layout.addLayout(details, stretch=1)

        product = QLabel(item.receipt.product_name)
        product.setObjectName("deadlineProduct")
        details.addWidget(product)

        merchant = QLabel(f"{item.receipt.merchant_name}  ·  {item.period_name}")
        merchant.setObjectName("deadlineMeta")
        details.addWidget(merchant)

        date_label = QLabel(item.expiry_date)
        date_label.setObjectName("deadlineDate")
        layout.addWidget(date_label)

        layout.addWidget(self.create_status_badge(item.days_remaining))

        return row

    @staticmethod
    def create_status_badge(days_remaining):
        is_expired = days_remaining < 0
        badge = QLabel("Expired" if is_expired else "Expiring soon")
        badge.setObjectName("statusBadge")
        badge.setProperty("statusColor", "red" if is_expired else "orange")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setMinimumWidth(104)
        return badge

    @staticmethod
    def create_placeholder(message):
        placeholder = QLabel(message)
        placeholder.setObjectName("dashboardEmpty")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        return placeholder

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
