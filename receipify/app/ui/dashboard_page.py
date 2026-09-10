"""The analytics dashboard: headline figures, a spending trend, and deadlines."""

from calendar import month_abbr

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.dashboard_service import build_dashboard_summary
from app.ui.formatting import format_currency, status_icon_label
from app.ui.trend_chart import SpendingBarChart


class DashboardPage(QWidget):
    def __init__(self, data_manager, user_id, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.user_id = user_id
        self.build_ui()
        self.refresh()

    # ------------------------------------------------------------------ layout

    def build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        root_layout.addWidget(scroll_area)

        content = QWidget()
        scroll_area.setWidget(content)

        layout = QVBoxLayout(content)

        layout.addLayout(self.build_summary_row())
        layout.addLayout(self.build_split_section())
        layout.addWidget(self.build_deadlines_section())
        layout.addStretch(1)

    def build_summary_row(self):
        summary_row = QHBoxLayout()

        self.total_spending_value = self.add_stat_card(summary_row, "Total spending")
        self.active_warranties_value = self.add_stat_card(summary_row, "Active warranties")
        self.expired_records_value = self.add_stat_card(summary_row, "Expired records")

        return summary_row

    def add_stat_card(self, layout, label_text):
        group = QGroupBox(label_text)
        group_layout = QVBoxLayout(group)
        value = QLabel("0")
        group_layout.addWidget(value)
        layout.addWidget(group, stretch=1)
        return value

    def build_split_section(self):
        split_row = QHBoxLayout()

        self.year_selector = QComboBox()
        self.year_selector.setAccessibleName("Chart spending period")
        self.year_selector.setToolTip("All years shows yearly totals; choose a year to see its months.")
        self.year_selector.currentIndexChanged.connect(self.show_spending_chart)

        trend_panel, trend_layout = self.create_panel(
            "Spending over time", actions=(self.year_selector,)
        )
        self.trend_chart = SpendingBarChart()
        trend_layout.addWidget(self.trend_chart)
        split_row.addWidget(trend_panel, stretch=3)

        category_panel, self.category_layout = self.create_panel("Category spending")
        split_row.addWidget(category_panel, stretch=2)

        return split_row

    def build_deadlines_section(self):
        panel, panel_layout = self.create_panel("Upcoming deadlines (next 30 days)")

        deadline_scroll = QScrollArea()
        deadline_scroll.setWidgetResizable(True)
        deadline_scroll.setMinimumHeight(180)
        panel_layout.addWidget(deadline_scroll)

        deadline_content = QWidget()
        self.deadline_layout = QVBoxLayout(deadline_content)
        # Right margin keeps the status badges clear of the scrollbar.
        self.deadline_layout.setContentsMargins(0, 0, 16, 0)
        self.deadline_layout.setSpacing(8)
        deadline_scroll.setWidget(deadline_content)

        return panel

    def create_panel(self, title_text, actions=()):
        panel = QGroupBox(title_text)
        layout = QVBoxLayout(panel)
        if actions:
            controls = QHBoxLayout()
            controls.addWidget(QLabel("Period"))
            for action in actions:
                controls.addWidget(action)
            controls.addStretch()
            layout.addLayout(controls)
        items = QVBoxLayout()
        layout.addLayout(items)
        return panel, items

    # ------------------------------------------------------------------ refresh

    def refresh(self):
        """Read receipts once; keep chart selection separate from the overview."""
        self.summary = build_dashboard_summary(self.data_manager.get_all_receipts(self.user_id))
        self.total_spending_value.setText(format_currency(self.summary.total_spending_cents))
        self.active_warranties_value.setText(str(self.summary.active_warranties))
        self.expired_records_value.setText(str(self.summary.expired_warranties))
        self.show_category_spending(self.summary.category_spending)
        self.show_deadlines(self.summary.deadlines)

        selected_year = self.year_selector.currentData()
        self.year_selector.blockSignals(True)
        self.year_selector.clear()
        self.year_selector.addItem("All years", None)
        for year in reversed(self.summary.monthly_spending):
            self.year_selector.addItem(str(year), year)
        index = self.year_selector.findData(selected_year)
        self.year_selector.setCurrentIndex(max(index, 0))
        self.year_selector.blockSignals(False)
        self.show_spending_chart()

    def show_spending_chart(self, _index=None):
        year = self.year_selector.currentData()
        if year is None:
            totals = self.summary.monthly_spending
            years = list(range(min(totals), max(totals) + 1)) if totals else []
            self.trend_chart.show_totals(
                [str(year) for year in years],
                [sum(totals.get(year, [])) for year in years],
            )
        else:
            self.trend_chart.show_totals(
                list(month_abbr)[1:], self.summary.monthly_spending[year]
            )

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
        name_label.setTextFormat(Qt.TextFormat.PlainText)
        name_label.setWordWrap(True)
        header.addWidget(name_label, stretch=1)

        # The share is stated beside the amount rather than printed on the bar,
        # where it would sit half on the fill and half off it and be unreadable.
        amount_label = QLabel(f"{share:.1f}%  ·  {format_currency(cents)}")
        amount_label.setObjectName("categoryAmount")
        header.addWidget(amount_label)

        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(round(share * 10))
        bar.setTextVisible(False)
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
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        details = QVBoxLayout()
        details.setSpacing(2)
        layout.addLayout(details, stretch=1)

        product = QLabel(item.receipt.product_name)
        product.setTextFormat(Qt.TextFormat.PlainText)
        product.setWordWrap(True)
        details.addWidget(product)

        merchant = QLabel(f"{item.receipt.merchant_name}  ·  {item.period_name}")
        merchant.setTextFormat(Qt.TextFormat.PlainText)
        merchant.setWordWrap(True)
        details.addWidget(merchant)

        date_label = QLabel(item.expiry_date)
        layout.addWidget(date_label)

        layout.addWidget(status_icon_label("red" if item.days_remaining < 0 else "orange"))
        layout.addWidget(self.create_status_badge(item.days_remaining))

        return row

    @staticmethod
    def create_status_badge(days_remaining):
        is_expired = days_remaining < 0
        badge = QLabel("Expired" if is_expired else "Expiring soon")
        badge.setObjectName("statusBadge")
        badge.setProperty("statusColor", "red" if is_expired else "orange")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
                widget.hide()
                widget.deleteLater()
