from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class ReceiptCard(QFrame):
    def __init__(self, receipt, parent=None):
        super().__init__(parent)
        self.receipt = receipt
        self.setObjectName("receiptCard")
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(18)
        layout.addLayout(header_layout)

        title_area = QVBoxLayout()
        title_area.setSpacing(6)
        header_layout.addLayout(title_area, stretch=1)

        product_name = QLabel(self.receipt.product_name)
        product_name.setObjectName("cardTitle")
        product_name.setWordWrap(True)
        title_area.addWidget(product_name)

        merchant_line = QLabel(
            f"{self.receipt.merchant_name}  -  {self.receipt.category_name}"
        )
        merchant_line.setObjectName("cardMeta")
        merchant_line.setWordWrap(True)
        title_area.addWidget(merchant_line)

        price = QLabel(f"EUR {self.receipt.price_euros():.2f}")
        price.setObjectName("cardPrice")
        price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        header_layout.addWidget(price)

        details = QGridLayout()
        details.setHorizontalSpacing(28)
        details.setVerticalSpacing(8)
        layout.addLayout(details)

        self.add_detail(details, 0, 0, "Purchase date", self.receipt.purchase_date)

        status_layout = QHBoxLayout()
        status_layout.setSpacing(12)
        layout.addLayout(status_layout)

        status_layout.addWidget(
            self.create_status_block(
                "Warranty",
                self.receipt.warranty_status(),
                self.receipt.warranty_expiry_date(),
                self.receipt.days_until_warranty_expiry(),
            ),
            stretch=1,
        )
        status_layout.addWidget(
            self.create_status_block(
                "Return",
                self.receipt.return_status(),
                self.receipt.return_expiry_date(),
                self.receipt.days_until_return_expiry(),
            ),
            stretch=1,
        )

    def add_detail(self, layout, row, column, label_text, value_text):
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(3)

        label = QLabel(label_text)
        label.setObjectName("detailLabel")

        value = QLabel(str(value_text))
        value.setObjectName("detailValue")
        value.setWordWrap(True)

        detail_layout.addWidget(label)
        detail_layout.addWidget(value)
        layout.addWidget(detail, row, column)

    def create_badge(self, prefix, status):
        badge = QLabel(self.clean_status_label(status["label"]))
        badge.setObjectName("statusBadge")
        badge.setProperty("statusColor", status["color"])
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return badge

    def create_status_block(self, label_text, status, expiry_date, days_remaining):
        block = QFrame()
        block.setObjectName("statusBlock")

        layout = QVBoxLayout(block)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        layout.addLayout(top_row)

        label = QLabel(label_text)
        label.setObjectName("statusLabel")
        top_row.addWidget(label, stretch=1)
        top_row.addWidget(self.create_badge(label_text, status))

        date_label = QLabel(f"Expiry: {expiry_date}" if expiry_date else "Expiry: None")
        date_label.setObjectName("statusDate")
        layout.addWidget(date_label)

        days_label = QLabel(self.days_text(days_remaining))
        days_label.setObjectName("statusDays")
        layout.addWidget(days_label)

        return block

    def clean_status_label(self, status_label):
        if status_label.startswith("no "):
            return "None"

        return status_label.capitalize()

    def days_text(self, days_remaining):
        if days_remaining is None:
            return "Not tracked"

        if days_remaining < 0:
            return f"Expired {abs(days_remaining)} days ago"

        if days_remaining == 0:
            return "Expires today"

        return f"{days_remaining} days remaining"
