from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def validate_receipt_input(
    product_name,
    merchant_name,
    price,
    purchase_date,
    warranty_days,
    return_days,
    category_name="Uncategorised",
    image_path=None,
):
    errors = []
    cleaned_values = {}

    product_name = str(product_name).strip()
    merchant_name = str(merchant_name).strip()
    category_name = str(category_name).strip() or "Uncategorised"
    purchase_date = str(purchase_date).strip()

    if not product_name:
        errors.append("Product name cannot be empty.")

    if not merchant_name:
        errors.append("Merchant name cannot be empty.")

    price_cents = _clean_price_to_cents(price, errors)
    valid_purchase_date = _clean_iso_date(purchase_date, errors)
    clean_warranty_days = _clean_non_negative_integer(
        warranty_days,
        "Warranty days",
        errors,
    )
    clean_return_days = _clean_non_negative_integer(
        return_days,
        "Return days",
        errors,
    )

    if not errors:
        cleaned_values = {
            "product_name": product_name,
            "merchant_name": merchant_name,
            "category_name": category_name,
            "price_cents": price_cents,
            "purchase_date": valid_purchase_date,
            "warranty_days": clean_warranty_days,
            "return_days": clean_return_days,
            "image_path": image_path,
        }

    return len(errors) == 0, errors, cleaned_values


def _clean_price_to_cents(price, errors):
    try:
        price_text = str(price).strip().replace(",", ".")
        price_value = Decimal(price_text)
    except InvalidOperation:
        errors.append("Price must be numeric.")
        return None

    if not price_value.is_finite():
        errors.append("Price must be numeric.")
        return None

    if price_value < Decimal("0"):
        errors.append("Price must be greater than or equal to 0.")
        return None

    cents = (price_value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def _clean_iso_date(date_text, errors):
    try:
        parsed_date = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        errors.append("Purchase date must be a valid date in YYYY-MM-DD format.")
        return None

    return parsed_date.isoformat()


def _clean_non_negative_integer(value, field_name, errors):
    try:
        clean_value = int(str(value).strip())
    except ValueError:
        errors.append(f"{field_name} must be an integer.")
        return None

    if clean_value < 0:
        errors.append(f"{field_name} must be greater than or equal to 0.")
        return None

    return clean_value
