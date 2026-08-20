"""The analytics dashboard: headline figures, a spending trend, and deadlines."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.dashboard_service import DashboardService
from app.ui.formatting import format_currency
from app.ui.trend_chart import (
    YEAR,
    SpendingBarChart,
    SpendingTrendDialog,
    bar_labels,
    recorded_span,
    to_dates,
    yearly_totals,
)


# The bar is drawn in tenths of a percent so that it matches the share printed
# beside it to one decimal place.
CATEGORY_BAR_SCALE = 1000
CATEGORY_BAR_HEIGHT = 12
CATEGORY_BAR_TRACK_COLOUR = "#F1F5F9"
CATEGORY_BAR_FILL_COLOUR = "#2563EB"


class CategoryBar(QProgressBar):
    """A share of the total, drawn with round ends whatever the share is.

    Qt's stylesheet painter drops the corner radius as soon as a chunk is
    narrower than twice that radius, so a category worth a few percent came out
    as a hard rectangle, and one right on the boundary came out rounded at one
    end and cut square at the other.

    The fill is painted here instead, and always within the track's own outline:
    it is the shape the two have in common. That is what keeps a share of a
    fraction of a percent inside the rounded end of the track rather than
    standing a full-height line up against its curve. The fill is never widened
    to make it look better, so a small share still reads as a small share.
    """

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        track = QRectF(self.rect())
        track_radius = track.height() / 2
        track_path = QPainterPath()
        track_path.addRoundedRect(track, track_radius, track_radius)

        painter.setBrush(QColor(CATEGORY_BAR_TRACK_COLOUR))
        painter.drawPath(track_path)

        fill_width = track.width() * self.filled_fraction()
        if fill_width <= 0:
            return

        fill = QRectF(track.left(), track.top(), fill_width, track.height())
        # The far end carries as much of the track's curve as it has room for;
        # the near end is left to the track, which trims it just below.
        radius = min(track_radius, fill_width / 2)
        fill_path = QPainterPath()
        fill_path.addRoundedRect(fill, radius, radius)

        painter.setBrush(QColor(CATEGORY_BAR_FILL_COLOUR))
        painter.drawPath(fill_path.intersected(track_path))

    def filled_fraction(self):
        """How much of the bar is filled, from 0 to 1."""
        span = self.maximum() - self.minimum()
        if span <= 0:
            return 0.0

        return (self.value() - self.minimum()) / span


class DashboardPage(QWidget):
    def __init__(self, data_manager, user_id, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.user_id = user_id
        self.service = DashboardService(data_manager)
        self.daily_spending = {}
        self.receipts_by_day = {}
        self.yearly_totals = {}
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

        self.enlarge_button = QPushButton("Enlarge")
        self.enlarge_button.setObjectName("panelActionButton")
        self.enlarge_button.setToolTip("Open the chart in a window you can look through")
        self.enlarge_button.clicked.connect(self.open_trend_dialog)

        # The span the chart covers is stated rather than left to be read off
        # the axis, which only carries as many labels as it has room for.
        self.trend_range_label = QLabel()
        self.trend_range_label.setObjectName("panelCaption")

        trend_panel, trend_layout = self.create_panel(
            "Spending over time", actions=(self.trend_range_label, self.enlarge_button)
        )
        self.trend_chart = SpendingBarChart()
        self.trend_chart.enlarge_requested.connect(self.open_trend_dialog)
        trend_layout.addWidget(self.trend_chart)
        split_row.addWidget(trend_panel, stretch=3)

        category_panel, self.category_layout = self.create_panel("Category spending")
        split_row.addWidget(category_panel, stretch=2)

        return split_row

    def open_trend_dialog(self):
        """Show the chart at full size, where it can be zoomed into."""
        SpendingTrendDialog(
            self.daily_spending, receipts_by_day=self.receipts_by_day, parent=self
        ).exec()

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

    def create_panel(self, title_text, actions=()):
        panel = QFrame()
        panel.setObjectName("dashboardPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        panel_layout.addLayout(header)

        title = QLabel(title_text)
        title.setObjectName("dashboardPanelTitle")
        header.addWidget(title)
        header.addStretch(1)
        for action in actions:
            header.addWidget(action)

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

        self.daily_spending = self.service.get_daily_spending(self.user_id)
        self.receipts_by_day = self.service.get_receipts_by_day(self.user_id)
        self.show_yearly_bars()
        self.enlarge_button.setEnabled(bool(self.daily_spending))
        self.show_category_spending(self.service.get_category_spending(self.user_id))
        self.show_deadlines(self.service.get_upcoming_deadlines(self.user_id))

    def show_yearly_bars(self):
        """A bar for each recorded year.

        The panel is a summary; the enlarged window is where a year is opened
        up into its months and days.
        """
        spending = to_dates(self.daily_spending)
        self.yearly_totals = yearly_totals(spending)
        self.trend_chart.show_totals(
            self.yearly_totals, bar_labels(list(self.yearly_totals), YEAR)
        )
        self.trend_range_label.setText(recorded_span(spending))

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

        share = cents / total_cents * 100

        name_label = QLabel(category_name)
        name_label.setObjectName("categoryName")
        header.addWidget(name_label, stretch=1)

        # The share is stated beside the amount rather than printed on the bar,
        # where it would sit half on the fill and half off it and be unreadable.
        amount_label = QLabel(f"{share:.1f}%  ·  {format_currency(cents)}")
        amount_label.setObjectName("categoryAmount")
        header.addWidget(amount_label)

        bar = CategoryBar()
        bar.setObjectName("categoryBar")
        bar.setRange(0, CATEGORY_BAR_SCALE)
        bar.setValue(round(share * CATEGORY_BAR_SCALE / 100))
        bar.setTextVisible(False)
        bar.setFixedHeight(CATEGORY_BAR_HEIGHT)
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
