DEFAULT_SETTINGS = {
    "default_warranty_days": 365,
    "default_return_days": 30,
    "warranty_warning_threshold": 30,
    "return_warning_threshold": 7,
}


def validate_settings(
    default_warranty_days,
    default_return_days,
    warranty_warning_threshold,
    return_warning_threshold,
):
    errors = []
    values = {}
    fields = {
        "default_warranty_days": (default_warranty_days, "Default warranty days"),
        "default_return_days": (default_return_days, "Default return days"),
        "warranty_warning_threshold": (
            warranty_warning_threshold,
            "Warranty warning threshold",
        ),
        "return_warning_threshold": (
            return_warning_threshold,
            "Return warning threshold",
        ),
    }

    for key, (value, label) in fields.items():
        try:
            clean_value = int(str(value).strip())
        except ValueError:
            errors.append(f"{label} must be an integer.")
            continue

        if clean_value < 0:
            errors.append(f"{label} must be greater than or equal to 0.")
            continue

        values[key] = clean_value

    return len(errors) == 0, errors, values if not errors else {}
