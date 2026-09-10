"""Search filters, using a standard labelled dialog."""

from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout

from app.services.receipt_browsing_service import ALL_OPTION, SORT_OPTIONS, STATUS_OPTIONS, default_filters


class FilterDialog(QDialog):
    def __init__(self, filters, merchants, categories, parent=None):
        super().__init__(parent)
        self.values = dict(filters)
        self.setWindowTitle("Filter receipts")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for attribute, label, options in (
            ("merchant_filter", "Merchant", [ALL_OPTION, *merchants]),
            ("category_filter", "Category", [ALL_OPTION, *categories]),
            ("sort_filter", "Sort by", SORT_OPTIONS),
            ("warranty_filter", "Warranty status", STATUS_OPTIONS),
            ("return_filter", "Return status", STATUS_OPTIONS),
        ):
            combo = QComboBox()
            combo.addItems(options)
            setattr(self, attribute, combo)
            form.addRow(label, combo)
        self.purchase_date_from = QLineEdit()
        self.purchase_date_to = QLineEdit()
        for label, field in (("Purchased from", self.purchase_date_from), ("Purchased until", self.purchase_date_to)):
            field.setPlaceholderText("YYYY-MM-DD (optional)")
            form.addRow(label, field)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        clear = buttons.addButton("Clear all", QDialogButtonBox.ButtonRole.ResetRole)
        clear.setAutoDefault(False)
        clear.clicked.connect(self.clear_all)
        buttons.accepted.connect(self.apply_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.apply_filters_to_inputs(filters)

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
