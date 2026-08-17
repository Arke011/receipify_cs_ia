"""Rules for narrowing and ordering the receipt gallery.

Keeping these rules outside the Qt widgets makes the gallery behaviour easy to
test and keeps the page focused on collecting the user's choices.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


SORT_OPTIONS = (
    "Purchase date (newest)",
    "Purchase date (oldest)",
    "Price (highest)",
    "Price (lowest)",
    "Product name (A-Z)",
    "Product name (Z-A)",
    "Recently added",
)

ALL_OPTION = "All"
STATUS_OPTIONS = (ALL_OPTION, "Active", "Expiring soon", "Expired", "Not tracked")


def browse_receipts(
    receipts,
    *,
    query="",
    merchant=ALL_OPTION,
    category=ALL_OPTION,
    warranty_status=ALL_OPTION,
    return_status=ALL_OPTION,
    purchase_date_from="",
    purchase_date_to="",
    sort_by="Purchase date (newest)",
    warranty_warning_threshold=30,
    return_warning_threshold=7,
):
    """Return receipts matching all active criteria in the requested order."""
    query = query.strip().casefold()
    query_price_cents = parse_price_query(query)
    start_date = parse_iso_date(purchase_date_from)
    end_date = parse_iso_date(purchase_date_to)

    def matches_receipt(receipt):
        searchable_values = (
            receipt.product_name,
            receipt.merchant_name,
            receipt.category_name,
        )
        if query:
            matches_text = any(
                query in value.casefold() for value in searchable_values
            )
            matches_price = (
                query_price_cents is not None
                and receipt.price_cents == query_price_cents
            )
            if not (matches_text or matches_price):
                return False
        if merchant != ALL_OPTION and receipt.merchant_name != merchant:
            return False
        if category != ALL_OPTION and receipt.category_name != category:
            return False
        if not matches_status(
            receipt.warranty_status(warranty_warning_threshold)["label"], warranty_status
        ):
            return False
        if not matches_status(
            receipt.return_status(return_warning_threshold)["label"], return_status
        ):
            return False

        receipt_date = parse_iso_date(receipt.purchase_date)
        if start_date and (receipt_date is None or receipt_date < start_date):
            return False
        if end_date and (receipt_date is None or receipt_date > end_date):
            return False
        return True

    return sort_receipts(
        [receipt for receipt in receipts if matches_receipt(receipt)], sort_by
    )


def matches_status(actual_status, selected_status):
    if selected_status == ALL_OPTION:
        return True
    if actual_status.startswith("no ") and actual_status.endswith(" period"):
        actual_status = "not tracked"
    return actual_status.casefold() == selected_status.casefold()


def sort_receipts(receipts, sort_by):
    """Sort a copy of receipts with stable receipt-id tie breakers."""
    receipts = list(receipts)
    if sort_by == "Purchase date (oldest)":
        return sorted(receipts, key=lambda receipt: (receipt.purchase_date, receipt.receipt_id))
    if sort_by == "Price (highest)":
        return sorted(receipts, key=lambda receipt: (receipt.price_cents, receipt.receipt_id), reverse=True)
    if sort_by == "Price (lowest)":
        return sorted(receipts, key=lambda receipt: (receipt.price_cents, receipt.receipt_id))
    if sort_by == "Product name (A-Z)":
        return sorted(receipts, key=lambda receipt: (receipt.product_name.casefold(), receipt.receipt_id))
    if sort_by == "Product name (Z-A)":
        return sorted(receipts, key=lambda receipt: (receipt.product_name.casefold(), receipt.receipt_id), reverse=True)
    if sort_by == "Recently added":
        return sorted(receipts, key=lambda receipt: (receipt.created_at, receipt.receipt_id), reverse=True)

    # The default and an unrecognised saved value are newest purchase first.
    return sorted(receipts, key=lambda receipt: (receipt.purchase_date, receipt.receipt_id), reverse=True)


def parse_price_query(value):
    """Convert a numeric query into cents, or None when it is not a price.

    A search for "24.99" has to reach a price stored as 2499, so the query is
    converted the same way validation converts a typed price. Non-numeric
    queries simply do not take part in price matching.
    """
    value = str(value).strip().replace(",", ".")
    if not value:
        return None

    try:
        price = Decimal(value)
        if not price.is_finite():
            return None

        return int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None


def parse_iso_date(value):
    """Parse an optional ISO date; invalid input simply does not constrain results."""
    value = str(value).strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
