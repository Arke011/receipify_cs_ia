from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.dashboard_service import build_dashboard_summary


class DashboardPage(QWidget):
    def __init__(self, data_manager, user_id, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.user_id = user_id
        self.build_ui()
        self.refresh()

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

        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(14)
        layout.addLayout(metrics_layout)
        self.total_receipts_value = self.add_metric(metrics_layout, "Receipts")
        self.total_spending_value = self.add_metric(metrics_layout, "Total spending")
        self.expiring_soon_value = self.add_metric(metrics_layout, "Expiring soon")
        self.expired_value = self.add_metric(metrics_layout, "Expired")

        content_row = QHBoxLayout()
        content_row.setSpacing(16)
        layout.addLayout(content_row)
        recent_panel, self.recent_layout = self.create_panel("Recent receipts")
        content_row.addWidget(recent_panel, stretch=1)
        category_panel, self.category_layout = self.create_panel("Category spending")
        content_row.addWidget(category_panel, stretch=1)

        expiry_row = QHBoxLayout()
        expiry_row.setSpacing(16)
        layout.addLayout(expiry_row)
        expiring_panel, self.expiring_layout = self.create_panel("Expiring soon")
        expiry_row.addWidget(expiring_panel, stretch=1)
        expired_panel, self.expired_layout = self.create_panel("Expired")
        expiry_row.addWidget(expired_panel, stretch=1)
        layout.addStretch(1)

    def add_metric(self, layout, label_text):
        card = QFrame()
        card.setObjectName("dashboardSummaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(5)

        label = QLabel(label_text)
        label.setObjectName("dashboardMetricLabel")
        card_layout.addWidget(label)

        value = QLabel("0")
        value.setObjectName("dashboardMetricValue")
        card_layout.addWidget(value)
        layout.addWidget(card, stretch=1)
        return value

    def create_panel(self, title_text):
        panel = QFrame()
        panel.setObjectName("dashboardPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(10)

        title = QLabel(title_text)
        title.setObjectName("dashboardPanelTitle")
        panel_layout.addWidget(title)

        item_layout = QVBoxLayout()
        item_layout.setSpacing(8)
        panel_layout.addLayout(item_layout)
        return panel, item_layout

    def refresh(self):
        receipts = self.data_manager.get_all_receipts(self.user_id)
        settings = self.data_manager.get_settings(self.user_id)
        summary = build_dashboard_summary(
            receipts,
            warranty_warning_threshold=settings["warranty_warning_threshold"],
            return_warning_threshold=settings["return_warning_threshold"],
        )

        self.total_receipts_value.setText(str(summary.total_receipt_count))
        self.total_spending_value.setText(
            f"EUR {summary.total_spending_cents / 100:.2f}"
        )
        self.expiring_soon_value.setText(str(len(summary.expiring_soon)))
        self.expired_value.setText(str(len(summary.expired)))

        self.replace_items(
            self.recent_layout,
            [
                f"{receipt.product_name} · {receipt.merchant_name} · EUR {receipt.price_euros():.2f}"
                for receipt in summary.recent_receipts
            ],
            "No receipts yet.",
        )
        self.replace_items(
            self.category_layout,
            [
                f"{category} · EUR {cents / 100:.2f}"
                for category, cents in summary.category_spending
            ],
            "No category spending yet.",
        )
        self.replace_items(
            self.expiring_layout,
            [self.format_expiry_item(item) for item in summary.expiring_soon],
            "Nothing is expiring soon.",
        )
        self.replace_items(
            self.expired_layout,
            [self.format_expiry_item(item) for item in summary.expired],
            "No expired items.",
        )

    def replace_items(self, layout, item_texts, empty_text):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for text in item_texts or [empty_text]:
            label = QLabel(text)
            label.setObjectName("dashboardItem" if item_texts else "dashboardEmpty")
            label.setWordWrap(True)
            layout.addWidget(label)

    def format_expiry_item(self, item):
        if item.days_remaining < 0:
            timing = f"expired {abs(item.days_remaining)} days ago"
        elif item.days_remaining == 0:
            timing = "expires today"
        else:
            timing = f"{item.days_remaining} days remaining"

        return (
            f"{item.receipt.product_name} · {item.period_name} · "
            f"{item.expiry_date} ({timing})"
        )
