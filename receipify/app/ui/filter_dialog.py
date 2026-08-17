"""One dialog holding every gallery filter, opened from a single button.

The receipts page previously carried a row of unlabelled controls that was hard
to read at a glance. Collecting them here keeps the page to a search bar and one
button, and gives every control the room for a proper label.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.receipt_browsing_service import (
    ALL_OPTION,
    SORT_OPTIONS,
    STATUS_OPTIONS,
    default_filters,
)
from app.ui.styles import app_stylesheet


def filter_icon(bar_count=3, color="#1E293B"):
    """The stacked-bars icon used for the filter button.

    Drawn rather than typed so it cannot fall back to a missing-glyph box on a
    machine whose fonts lack the symbol.
    """
    size = 18
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)

    bar_height = 2
    spacing = (size - bar_count * bar_height) / (bar_count + 1)
    for index in range(bar_count):
        top = spacing + index * (bar_height + spacing)
        # Shorter bars towards the bottom read as "filter" rather than "menu".
        inset = index * 3
        painter.drawRoundedRect(
            int(inset / 2), int(top), int(size - inset), bar_height, 1, 1
        )
    painter.end()

    return QIcon(pixmap)


class FilterDialog(QDialog):
    def __init__(self, filters, merchants, categories, parent=None):
        super().__init__(parent)
        self.values = dict(filters)
        self.setWindowTitle("Filter receipts")
        self.setMinimumWidth(640)
        self.build_ui(merchants, categories)
        self.apply_filters_to_inputs(filters)
        self.setStyleSheet(app_stylesheet())

    def build_ui(self, merchants, categories):
        root = QWidget()
        root.setObjectName("dialogRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(18)

        title = QLabel("Filter receipts")
        title.setObjectName("dialogTitle")
        root_layout.addWidget(title)

        subtitle = QLabel("Narrow the gallery down and choose how it is ordered.")
        subtitle.setObjectName("dialogSubtitle")
        root_layout.addWidget(subtitle)

        form_container = QFrame()
        form_container.setObjectName("formContainer")
        form_layout = QHBoxLayout(form_container)
        form_layout.setContentsMargins(22, 22, 22, 22)
        form_layout.setSpacing(18)
        root_layout.addWidget(form_container)

        left_column = QVBoxLayout()
        left_column.setSpacing(14)
        right_column = QVBoxLayout()
        right_column.setSpacing(14)
        form_layout.addLayout(left_column, stretch=1)
        form_layout.addLayout(right_column, stretch=1)

        self.merchant_filter = self.create_combo([ALL_OPTION, *merchants])
        self.category_filter = self.create_combo([ALL_OPTION, *categories])
        self.sort_filter = self.create_combo(SORT_OPTIONS)
        self.warranty_filter = self.create_combo(STATUS_OPTIONS)
        self.return_filter = self.create_combo(STATUS_OPTIONS)
        self.purchase_date_from = self.create_date_input()
        self.purchase_date_to = self.create_date_input()

        left_column.addWidget(self.create_field("Merchant", self.merchant_filter))
        left_column.addWidget(self.create_field("Category", self.category_filter))
        left_column.addWidget(self.create_field("Sort by", self.sort_filter))
        left_column.addStretch(1)

        right_column.addWidget(
            self.create_field("Warranty status", self.warranty_filter)
        )
        right_column.addWidget(self.create_field("Return status", self.return_filter))

        date_row = QWidget()
        date_layout = QHBoxLayout(date_row)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(10)
        date_layout.addWidget(self.create_field("Purchased from", self.purchase_date_from))
        date_layout.addWidget(self.create_field("Purchased until", self.purchase_date_to))
        right_column.addWidget(date_row)
        right_column.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        root_layout.addLayout(button_row)

        clear_button = QPushButton("Clear all")
        clear_button.setObjectName("secondaryButton")
        clear_button.clicked.connect(self.clear_all)
        button_row.addWidget(clear_button)
        button_row.addStretch(1)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)

        apply_button = QPushButton("Apply filters")
        apply_button.setObjectName("primaryButton")
        apply_button.setDefault(True)
        apply_button.clicked.connect(self.apply_and_accept)
        button_row.addWidget(apply_button)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root)

    def create_combo(self, options):
        combo = QComboBox()
        combo.setObjectName("filterCombo")
        combo.setMinimumHeight(42)
        combo.addItems(list(options))
        return combo

    def create_date_input(self):
        date_input = QLineEdit()
        date_input.setObjectName("formInput")
        date_input.setPlaceholderText("YYYY-MM-DD")
        date_input.setMinimumHeight(42)
        return date_input

    def create_field(self, label_text, input_widget):
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(input_widget)

        return field

    def apply_filters_to_inputs(self, filters):
        self.set_combo_value(self.merchant_filter, filters["merchant"])
        self.set_combo_value(self.category_filter, filters["category"])
        self.set_combo_value(self.warranty_filter, filters["warranty_status"])
        self.set_combo_value(self.return_filter, filters["return_status"])
        self.set_combo_value(self.sort_filter, filters["sort_by"])
        self.purchase_date_from.setText(filters["purchase_date_from"])
        self.purchase_date_to.setText(filters["purchase_date_to"])

    @staticmethod
    def set_combo_value(combo, value):
        # A merchant kept from an earlier selection may no longer be in the list;
        # it is added back so the gallery keeps showing the same result.
        if combo.findText(value) == -1:
            combo.addItem(value)
        combo.setCurrentText(value)

    def clear_all(self):
        self.apply_filters_to_inputs(default_filters())

    def collect_values(self):
        return {
            "merchant": self.merchant_filter.currentText(),
            "category": self.category_filter.currentText(),
            "warranty_status": self.warranty_filter.currentText(),
            "return_status": self.return_filter.currentText(),
            "sort_by": self.sort_filter.currentText(),
            "purchase_date_from": self.purchase_date_from.text().strip(),
            "purchase_date_to": self.purchase_date_to.text().strip(),
        }

    def apply_and_accept(self):
        self.values = self.collect_values()
        self.accept()
