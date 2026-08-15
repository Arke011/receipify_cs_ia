from dataclasses import dataclass

from app.services.expiry_service import (
    add_days_to_iso_date,
    days_until_iso_date,
    expiry_status,
)


@dataclass
class Receipt:
    receipt_id: int
    user_id: int
    product_name: str
    merchant_name: str
    category_name: str
    price_cents: int
    purchase_date: str
    warranty_days: int
    return_days: int
    image_path: str | None
    created_at: str

    def price_euros(self) -> float:
        return self.price_cents / 100

    def warranty_expiry_date(self) -> str | None:
        return add_days_to_iso_date(self.purchase_date, self.warranty_days)

    def return_expiry_date(self) -> str | None:
        return add_days_to_iso_date(self.purchase_date, self.return_days)

    def days_until_warranty_expiry(self) -> int | None:
        return days_until_iso_date(self.warranty_expiry_date())

    def days_until_return_expiry(self) -> int | None:
        return days_until_iso_date(self.return_expiry_date())

    def warranty_status(self, warning_threshold=30) -> dict:
        return expiry_status(
            self.days_until_warranty_expiry(),
            warning_threshold=warning_threshold,
            no_period_label="no warranty period",
        )

    def return_status(self, warning_threshold=7) -> dict:
        return expiry_status(
            self.days_until_return_expiry(),
            warning_threshold=warning_threshold,
            no_period_label="no return period",
        )

    def to_dict(self, warranty_warning_threshold=30, return_warning_threshold=7) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "user_id": self.user_id,
            "product_name": self.product_name,
            "merchant_name": self.merchant_name,
            "category_name": self.category_name,
            "price_cents": self.price_cents,
            "price_euros": self.price_euros(),
            "purchase_date": self.purchase_date,
            "warranty_days": self.warranty_days,
            "return_days": self.return_days,
            "warranty_expiry_date": self.warranty_expiry_date(),
            "return_expiry_date": self.return_expiry_date(),
            "days_until_warranty_expiry": self.days_until_warranty_expiry(),
            "days_until_return_expiry": self.days_until_return_expiry(),
            "warranty_status": self.warranty_status(warranty_warning_threshold),
            "return_status": self.return_status(return_warning_threshold),
            "image_path": self.image_path,
            "created_at": self.created_at,
        }
