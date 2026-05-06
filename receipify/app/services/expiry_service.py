from datetime import date, datetime, timedelta


def add_days_to_iso_date(start_date: str, days: int) -> str | None:
    if days <= 0:
        return None

    parsed_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    expiry_date = parsed_date + timedelta(days=days)
    return expiry_date.isoformat()


def days_until_iso_date(target_date: str | None) -> int | None:
    if target_date is None:
        return None

    parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    return (parsed_date - date.today()).days


def expiry_status(
    days_remaining: int | None,
    warning_threshold: int,
    no_period_label: str,
) -> dict:
    if days_remaining is None:
        return {
            "label": no_period_label,
            "color": "grey",
        }

    if days_remaining < 0:
        return {
            "label": "expired",
            "color": "red",
        }

    if days_remaining <= warning_threshold:
        return {
            "label": "expiring soon",
            "color": "orange",
        }

    return {
        "label": "active",
        "color": "green",
    }
