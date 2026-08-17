from dataclasses import dataclass
from datetime import datetime

from app.models.receipt import Receipt


@dataclass(frozen=True)
class ExpiryItem:
    receipt: Receipt
    period_name: str
    expiry_date: str
    days_remaining: int


@dataclass
class DashboardSummary:
    total_receipt_count: int
    total_spending_cents: int
    recent_receipts: list[Receipt]
    expiring_soon: list[ExpiryItem]
    expired: list[ExpiryItem]
    category_spending: list[tuple[str, int]]
    monthly_spending: dict[str, int]


def build_dashboard_summary(
    receipts,
    recent_limit=5,
    warranty_warning_threshold=30,
    return_warning_threshold=7,
):
    receipts = list(receipts)
    expiring_soon = []
    expired = []
    category_totals = {}

    for receipt in receipts:
        category_totals[receipt.category_name] = (
            category_totals.get(receipt.category_name, 0) + receipt.price_cents
        )

        _add_expiry_item(
            receipt,
            "Warranty",
            receipt.warranty_expiry_date(),
            receipt.days_until_warranty_expiry(),
            warning_threshold=warranty_warning_threshold,
            expiring_soon=expiring_soon,
            expired=expired,
        )
        _add_expiry_item(
            receipt,
            "Return",
            receipt.return_expiry_date(),
            receipt.days_until_return_expiry(),
            warning_threshold=return_warning_threshold,
            expiring_soon=expiring_soon,
            expired=expired,
        )

    return DashboardSummary(
        total_receipt_count=len(receipts),
        total_spending_cents=sum(receipt.price_cents for receipt in receipts),
        recent_receipts=sorted(
            receipts,
            key=lambda receipt: (receipt.purchase_date, receipt.receipt_id),
            reverse=True,
        )[:recent_limit],
        expiring_soon=sorted(
            expiring_soon,
            key=lambda item: (
                item.days_remaining,
                item.receipt.product_name,
                item.period_name,
            ),
        ),
        expired=sorted(
            expired,
            key=lambda item: (
                item.days_remaining,
                item.receipt.product_name,
                item.period_name,
            ),
        ),
        category_spending=sorted(
            category_totals.items(),
            key=lambda item: (-item[1], item[0].casefold()),
        ),
        monthly_spending=build_monthly_spending(receipts),
    )


def build_monthly_spending(receipts) -> dict[str, int]:
    """Total spending per purchase month, keyed by "YYYY-MM" in date order.

    A stored purchase date that cannot be parsed belongs to no month, so it is
    left out rather than allowed to break the whole breakdown.
    """
    monthly_totals = {}

    for receipt in receipts:
        month = _purchase_month(receipt.purchase_date)
        if month is None:
            continue

        monthly_totals[month] = monthly_totals.get(month, 0) + receipt.price_cents

    return dict(sorted(monthly_totals.items()))


def _purchase_month(purchase_date):
    try:
        return datetime.strptime(purchase_date, "%Y-%m-%d").strftime("%Y-%m")
    except (TypeError, ValueError):
        return None


def _add_expiry_item(
    receipt,
    period_name,
    expiry_date,
    days_remaining,
    warning_threshold,
    expiring_soon,
    expired,
):
    if days_remaining is None:
        return

    item = ExpiryItem(receipt, period_name, expiry_date, days_remaining)
    if days_remaining < 0:
        expired.append(item)
    elif days_remaining <= warning_threshold:
        expiring_soon.append(item)
