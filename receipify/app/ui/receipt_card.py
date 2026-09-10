from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.services.image_service import resolve_image_path
from app.ui.formatting import format_currency, status_icon_label


class ReceiptThumbnail(QLabel):
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class ReceiptCard(QFrame):
    def __init__(self, receipt, on_edit=None, on_delete=None, on_view_image=None,
                 warranty_warning_threshold=30, return_warning_threshold=7, parent=None):
        super().__init__(parent)
        self.receipt = receipt
        self.on_edit, self.on_delete, self.on_view_image = on_edit, on_delete, on_view_image
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)
        self.image_label = ReceiptThumbnail()
        self.image_label.setFixedSize(80, 72)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.image_label.setAccessibleName("View receipt image")
        self.image_label.setToolTip("View receipt image")
        self.image_label.clicked.connect(self.handle_view_image)
        self.set_receipt_image()
        layout.addWidget(self.image_label)
        details = QVBoxLayout()
        layout.addLayout(details, stretch=1)
        title = QHBoxLayout()
        name = QLabel(receipt.product_name)
        name.setTextFormat(Qt.TextFormat.PlainText)
        name.setWordWrap(True)
        font = name.font()
        font.setBold(True)
        name.setFont(font)
        title.addWidget(name, stretch=1)
        title.addWidget(QLabel(format_currency(receipt.price_cents)))
        details.addLayout(title)
        meta = QLabel(f"{receipt.merchant_name} · {receipt.category_name} · Purchased {receipt.purchase_date}")
        meta.setTextFormat(Qt.TextFormat.PlainText)
        meta.setWordWrap(True)
        details.addWidget(meta)
        for label, status, expiry, days in (
            ("Warranty", receipt.warranty_status(warranty_warning_threshold), receipt.warranty_expiry_date(), receipt.days_until_warranty_expiry()),
            ("Return", receipt.return_status(return_warning_threshold), receipt.return_expiry_date(), receipt.days_until_return_expiry()),
        ):
            row = QHBoxLayout()
            row.addWidget(status_icon_label(status["color"]))
            text = f"{label}: {status['label'].capitalize()}"
            if expiry:
                text += f" · {expiry} · {self.days_text(days)}"
            info = QLabel(text)
            info.setWordWrap(True)
            row.addWidget(info, stretch=1)
            details.addLayout(row)
        actions = QVBoxLayout()
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.handle_edit)
        actions.addWidget(self.edit_button)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.handle_delete)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        layout.addLayout(actions)

    def set_receipt_image(self):
        if not self.receipt.image_path:
            self.image_label.setText("No image")
            return

        image_path = resolve_image_path(self.receipt.image_path)
        pixmap = QPixmap(str(image_path)) if image_path.is_file() else QPixmap()
        if pixmap.isNull():
            self.image_label.setText("Image\nunavailable")
            return

        self.image_label.setPixmap(
            pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def handle_edit(self):
        if self.on_edit is not None:
            self.on_edit(self.receipt)

    def handle_delete(self):
        if self.on_delete is not None:
            self.on_delete(self.receipt)

    def handle_view_image(self):
        if self.receipt.image_path and self.on_view_image is not None:
            self.on_view_image(self.receipt)

    def days_text(self, days_remaining):
        if days_remaining is None:
            return "Not tracked"

        if days_remaining < 0:
            return f"Expired {abs(days_remaining)} days ago"

        if days_remaining == 0:
            return "Expires today"

        return f"{days_remaining} days remaining"
