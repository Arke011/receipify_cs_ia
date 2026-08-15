import csv
import json
from pathlib import Path


EXPORT_FIELDS = (
    "product_name",
    "merchant",
    "category",
    "price",
    "purchase_date",
    "warranty_days",
    "return_days",
    "warranty_expiry_date",
    "return_expiry_date",
    "warranty_status",
    "return_status",
    "image_path",
    "created_at",
)


def export_user_receipts(data_manager, user_id, output_path, export_format):
    """Export only one user's receipts and return the number written."""
    receipts = data_manager.get_all_receipts(user_id)
    settings = data_manager.get_settings(user_id)
    records = [
        receipt_to_export_record(
            receipt,
            warranty_warning_threshold=settings["warranty_warning_threshold"],
            return_warning_threshold=settings["return_warning_threshold"],
        )
        for receipt in receipts
    ]

    if export_format == "csv":
        write_csv(records, output_path)
    elif export_format == "json":
        write_json(records, output_path)
    else:
        raise ValueError(f"Unsupported export format: {export_format}")

    return len(records)


def receipt_to_export_record(
    receipt,
    warranty_warning_threshold=30,
    return_warning_threshold=7,
):
    return {
        "product_name": receipt.product_name,
        "merchant": receipt.merchant_name,
        "category": receipt.category_name,
        "price": f"{receipt.price_euros():.2f}",
        "purchase_date": receipt.purchase_date,
        "warranty_days": receipt.warranty_days,
        "return_days": receipt.return_days,
        "warranty_expiry_date": receipt.warranty_expiry_date(),
        "return_expiry_date": receipt.return_expiry_date(),
        "warranty_status": receipt.warranty_status(warranty_warning_threshold)["label"],
        "return_status": receipt.return_status(return_warning_threshold)["label"],
        "image_path": receipt.image_path,
        "created_at": receipt.created_at,
    }


def write_csv(records, output_path):
    with Path(output_path).open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(records)


def write_json(records, output_path):
    with Path(output_path).open("w", encoding="utf-8") as output_file:
        json.dump(records, output_file, ensure_ascii=False, indent=2)
