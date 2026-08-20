"""Shared display formatting, so every view spells a figure the same way."""

CURRENCY_PREFIX = "EUR"


def format_currency(cents):
    """Money with thousands separators, e.g. 124550 -> 'EUR 1,245.50'."""
    return f"{CURRENCY_PREFIX} {cents / 100:,.2f}"
