"""Shared display formatting, so every view spells a figure the same way."""

CURRENCY_PREFIX = "EUR"


def format_currency(cents):
    """Money with thousands separators, e.g. 124550 -> 'EUR 1,245.50'."""
    return f"{CURRENCY_PREFIX} {cents / 100:,.2f}"


def status_icon_label(color):
    """Use Qt's standard colored icons alongside readable expiry text."""
    from PyQt6.QtWidgets import QApplication, QLabel, QStyle

    icons = {
        "green": QStyle.StandardPixmap.SP_DialogApplyButton,
        "orange": QStyle.StandardPixmap.SP_MessageBoxWarning,
        "red": QStyle.StandardPixmap.SP_DialogCancelButton,
        "grey": QStyle.StandardPixmap.SP_MessageBoxInformation,
    }
    label = QLabel()
    label.setPixmap(QApplication.style().standardIcon(icons[color]).pixmap(16, 16))
    return label
