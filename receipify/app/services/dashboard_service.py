"""All-time dashboard figures and chart periods from a single receipt snapshot."""

from dataclasses import dataclass
from datetime import date

from app.models.receipt import Receipt


@dataclass(frozen=True)
class ExpiryItem:
    receipt: Receipt
    period_name: str
    expiry_date: str
    days_remaining: int


@dataclass
class DashboardSummary:
    total_spending_cents: int
    active_warranties: int
    expired_warranties: int
    category_spending: dict[str, int]
    monthly_spending: dict[int, list[int]]
    deadlines: list[ExpiryItem]


def build_dashboard_summary(receipts, today=None):
    today = today or date.today()
    total = active = expired = 0
    categories = {}
    monthly = {}
    deadlines = []

    for receipt in receipts:
        total += receipt.price_cents
        categories[receipt.category_name] = categories.get(receipt.category_name, 0) + receipt.price_cents
        try:
            purchased = date.fromisoformat(receipt.purchase_date)
        except (TypeError, ValueError):
            continue
        monthly.setdefault(purchased.year, [0] * 12)[purchased.month - 1] += receipt.price_cents

        for period, expiry in (
            ("Warranty", receipt.warranty_expiry_date()),
            ("Return", receipt.return_expiry_date()),
        ):
            if expiry is None:
                continue
            remaining = (date.fromisoformat(expiry) - today).days
            if period == "Warranty":
                active += remaining >= 0
                expired += remaining < 0
            # Only deadlines still ahead (including today) within the next 30 days.
            if 0 <= remaining <= 30:
                deadlines.append(ExpiryItem(receipt, period, expiry, remaining))

    return DashboardSummary(
        total_spending_cents=total,
        active_warranties=active,
        expired_warranties=expired,
        category_spending=dict(sorted(categories.items(), key=lambda item: (-item[1], item[0].casefold()))),
        monthly_spending=dict(sorted(monthly.items())),
        deadlines=sorted(deadlines, key=lambda item: (item.days_remaining, item.receipt.product_name.casefold(), item.period_name)),
    )
