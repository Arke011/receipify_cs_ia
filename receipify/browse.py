"""Searching, filtering and sorting the Receipts tab, and the Filters dialog."""

from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout

from receipt import MAX_PRICE, parse_amount, parse_date, to_cents

ALL = "All"
STATUS_OPTIONS = (ALL, "Active", "Expiring soon", "Expired", "Not tracked")
# Sort option -> (value to sort by, largest first?). The receipt id breaks ties, so the order is stable.
SORTS = {
    "Purchase date (newest)": (lambda r: (r.purchase_date, r.id), True),
    "Purchase date (oldest)": (lambda r: (r.purchase_date, r.id), False),
    "Price (highest)": (lambda r: (r.price_cents, r.id), True),
    "Price (lowest)": (lambda r: (r.price_cents, r.id), False),
    "Product name (A-Z)": (lambda r: (r.product.casefold(), r.id), False),
    "Product name (Z-A)": (lambda r: (r.product.casefold(), r.id), True),
    "Recently added": (lambda r: (r.created_at, r.id), True),
}
DEFAULT_FILTERS = {
    "merchant": ALL,
    "category": ALL,
    "warranty_status": ALL,
    "return_status": ALL,
    "date_from": "",
    "date_to": "",
    "sort_by": "Purchase date (newest)",
}


def count_active(filters):
    """How many filters differ from the defaults (shown on the Filters button)."""
    return sum(filters[key] != default for key, default in DEFAULT_FILTERS.items())


def search_cents(query):
    """The price a search such as '24.99' refers to, in cents, or None if the search is not a price."""
    amount = parse_amount(query)
    if amount is None or abs(amount) > MAX_PRICE:
        return None
    return to_cents(amount)


def status_matches(status, choice):
    """Whether a status label matches a Filters choice; 'no ... period' counts as Not tracked."""
    if choice == ALL:
        return True
    if status.startswith("no "):
        status = "not tracked"
    return status == choice.lower()


def filter_receipts(receipts, query, filters, settings):
    """The receipts that match the search text and every filter, in the chosen order."""
    query = query.strip().casefold()
    query_cents = search_cents(query)
    date_from = parse_date(filters["date_from"])
    date_to = parse_date(filters["date_to"])
    matches = []
    for receipt in receipts:
        if query:
            in_text = any(query in text.casefold() for text in (receipt.product, receipt.merchant, receipt.category))
            if not in_text and receipt.price_cents != query_cents:
                continue
        if filters["merchant"] != ALL and receipt.merchant != filters["merchant"]:
            continue
        if filters["category"] != ALL and receipt.category != filters["category"]:
            continue
        if not status_matches(receipt.warranty_status(settings["warranty_warning_threshold"]), filters["warranty_status"]):
            continue
        if not status_matches(receipt.return_status(settings["return_warning_threshold"]), filters["return_status"]):
            continue
        purchased = parse_date(receipt.purchase_date)
        if date_from and (purchased is None or purchased < date_from):
            continue
        if date_to and (purchased is None or purchased > date_to):
            continue
        matches.append(receipt)
    return sort_receipts(matches, filters["sort_by"])


def sort_receipts(receipts, sort_by):
    key, descending = SORTS.get(sort_by, SORTS["Purchase date (newest)"])
    return sorted(receipts, key=key, reverse=descending)


class FilterDialog(QDialog):
    def __init__(self, filters, receipts, parent=None):
        super().__init__(parent)
        self.values = dict(filters)
        self.setWindowTitle("Filter receipts")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Only merchants and categories this user has receipts for are offered.
        merchants = sorted({r.merchant for r in receipts}, key=str.casefold)
        categories = sorted({r.category for r in receipts}, key=str.casefold)
        self.combos = {}
        for key, label, options in (
            ("merchant", "Merchant", [ALL, *merchants]),
            ("category", "Category", [ALL, *categories]),
            ("sort_by", "Sort by", list(SORTS)),
            ("warranty_status", "Warranty status", STATUS_OPTIONS),
            ("return_status", "Return status", STATUS_OPTIONS),
        ):
            self.combos[key] = QComboBox()
            self.combos[key].addItems(options)
            form.addRow(label, self.combos[key])
        self.date_from = QLineEdit()
        self.date_to = QLineEdit()
        for label, field in (("Purchased from", self.date_from), ("Purchased until", self.date_to)):
            field.setPlaceholderText("YYYY-MM-DD (optional)")
            form.addRow(label, field)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        clear_button = buttons.addButton("Clear all", QDialogButtonBox.ButtonRole.ResetRole)
        clear_button.setAutoDefault(False)
        clear_button.clicked.connect(lambda: self.show_filters(DEFAULT_FILTERS))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.show_filters(filters)

    def show_filters(self, filters):
        for key, combo in self.combos.items():
            # A merchant chosen earlier may no longer be listed; it is added back
            # so the gallery keeps showing the same result.
            if combo.findText(filters[key]) == -1:
                combo.addItem(filters[key])
            combo.setCurrentText(filters[key])
        self.date_from.setText(filters["date_from"])
        self.date_to.setText(filters["date_to"])

    def chosen_filters(self):
        filters = {key: combo.currentText() for key, combo in self.combos.items()}
        filters["date_from"] = self.date_from.text().strip()
        filters["date_to"] = self.date_to.text().strip()
        return filters

    def accept(self):
        self.values = self.chosen_filters()
        super().accept()
