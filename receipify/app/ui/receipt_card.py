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
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        layout.addLayout(header_layout)

        title_area = QVBoxLayout()
        title_area.setSpacing(4)
        header_layout.addLayout(title_area, stretch=1)

        product_name = QLabel(self.receipt.product_name)
        product_name.setObjectName("cardTitle")
        product_name.setWordWrap(True)
        title_area.addWidget(product_name)

        merchant_line = QLabel(
            f"{self.receipt.merchant_name}  |  {self.receipt.category_name}"
        )
        merchant_line.setObjectName("cardSubtitle")
        merchant_line.setWordWrap(True)
        title_area.addWidget(merchant_line)

        price = QLabel(f"EUR {self.receipt.price_euros():.2f}")
        price.setObjectName("cardPrice")
        price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        header_layout.addWidget(price)

        details = QGridLayout()
        details.setHorizontalSpacing(22)
        details.setVerticalSpacing(8)
        layout.addLayout(details)

        self.add_detail(details, 0, 0, "Purchase date", self.receipt.purchase_date)
        self.add_detail(
            details,
            0,
            1,
            "Warranty expiry",
            self.receipt.warranty_expiry_date() or "No warranty period",
        )
        self.add_detail(
            details,
            1,
            0,
            "Return expiry",
            self.receipt.return_expiry_date() or "No return period",
        )

        badges = QWidget()
        badge_layout = QHBoxLayout(badges)
        badge_layout.setContentsMargins(0, 2, 0, 0)
        badge_layout.setSpacing(8)

        badge_layout.addWidget(self.create_badge("Warranty", self.receipt.warranty_status()))
        badge_layout.addWidget(self.create_badge("Return", self.receipt.return_status()))
        badge_layout.addStretch(1)
        layout.addWidget(badges)

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
        badge = QLabel(f"{prefix}: {status['label']}")
        badge.setObjectName("statusBadge")
        badge.setProperty("statusColor", status["color"])
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return badge
