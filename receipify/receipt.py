"""The Receipt record, plus the rules for dates, prices, expiry status and form validation."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MAX_PERIOD_DAYS = 36500  # 100 years; longer periods overflow date arithmetic
MAX_PRICE = Decimal("99999999.99")


def parse_date(text):
    """A 'YYYY-MM-DD' string as a date, or None if it is not a real date."""
    try:
        return datetime.strptime(str(text).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def days_until(day, today=None):
    """Days from today until a 'YYYY-MM-DD' date; negative once it has passed."""
    return (parse_date(day) - (today or date.today())).days


def parse_amount(text):
    """A typed amount such as '24.99' or '24,99' as a Decimal, or None if it is not a number."""
    try:
        amount = Decimal(str(text).strip().replace(",", "."))
    except InvalidOperation:
        return None
    return amount if amount.is_finite() else None


def to_cents(amount):
    """Decimal euros as whole cents, rounding half a cent up (24.995 -> 2500)."""
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_euros(cents):
    """Cents as money with thousands separators: 124550 -> 'EUR 1,245.50'."""
    return f"EUR {cents / 100:,.2f}"


def expiry_status(expiry, warning_days, no_period_label):
    """'active', 'expiring soon' (within warning_days), 'expired', or the no-period label."""
    if expiry is None:
        return no_period_label
    days_left = days_until(expiry)
    if days_left < 0:
        return "expired"
    if days_left <= warning_days:
        return "expiring soon"
    return "active"


@dataclass
class Receipt:
    id: int
    user_id: int
    product: str
    merchant: str
    category: str
    price_cents: int
    purchase_date: str
    warranty_days: int
    return_days: int
    image_path: str | None
    created_at: str

    def expiry(self, days):
        """The date a period of `days` after purchase ends, or None if there is no period.

        Rows saved by older versions may hold an unreadable date or a huge day
        count; those count as "no period" instead of crashing the app.
        """
        purchased = parse_date(self.purchase_date)
        if days <= 0 or purchased is None:
            return None
        try:
            return (purchased + timedelta(days=days)).isoformat()
        except OverflowError:
            return None

    def warranty_expiry(self):
        return self.expiry(self.warranty_days)

    def return_expiry(self):
        return self.expiry(self.return_days)

    def warranty_status(self, warning_days):
        return expiry_status(self.warranty_expiry(), warning_days, "no warranty period")

    def return_status(self, warning_days):
        return expiry_status(self.return_expiry(), warning_days, "no return period")


def whole_number(text, name, errors, maximum=None):
    """Read a whole number of 0 or more; on failure add a message to errors and return None."""
    try:
        number = int(str(text).strip())
    except ValueError:
        errors.append(f"{name} must be an integer.")
        return None
    if number < 0:
        errors.append(f"{name} must be greater than or equal to 0.")
        return None
    if maximum is not None and number > maximum:
        errors.append(f"{name} must be {maximum} or fewer.")
        return None
    return number


def validate_receipt(product, merchant, category, price, purchase_date, warranty_days, return_days):
    """Check the receipt form's text. Returns (errors, values); values is empty unless every field is valid."""
    errors = []
    product = product.strip()
    merchant = merchant.strip()
    if not product:
        errors.append("Product name cannot be empty.")
    if not merchant:
        errors.append("Merchant name cannot be empty.")

    amount = parse_amount(price)
    if amount is None:
        errors.append("Price must be numeric.")
    elif amount <= 0:
        errors.append("Price must be greater than 0.")
    elif amount > MAX_PRICE:
        errors.append("Price is too large.")

    purchased = parse_date(purchase_date)
    if purchased is None:
        errors.append("Purchase date must be a valid date in YYYY-MM-DD format.")
    elif purchased > date.today():
        errors.append("Purchase date cannot be in the future.")

    warranty = whole_number(warranty_days, "Warranty days", errors, MAX_PERIOD_DAYS)
    returns = whole_number(return_days, "Return days", errors, MAX_PERIOD_DAYS)

    if errors:
        return errors, {}
    return [], {
        "product": product,
        "merchant": merchant,
        "category": category.strip() or "Uncategorised",
        "price_cents": to_cents(amount),
        "purchase_date": purchased.isoformat(),
        "warranty_days": warranty,
        "return_days": returns,
    }
