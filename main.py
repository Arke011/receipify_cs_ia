from dataclasses import dataclass #a useful decorator, autogenerates boilerplate code
from datetime import date, timedelta #allows to work with dates


@dataclass
class Receipt:
    #Structure of a manually entered receipt
    product_name: str
    merchant_name: str
    price_cents: int
    purchase_date: str
    warranty_days: int
    return_days: int

    def validate(self) -> None:
        #Checks whether receipt data is valid
        if not self.product_name.strip(): #strips spaces
            raise ValueError("Product name cannot be empty.")

        if not self.merchant_name.strip(): #strips spaces
            raise ValueError("Merchant name cannot be empty.")

        if self.price_cents < 0:
            raise ValueError("Price cannot be negative.")

        if self.warranty_days < 0:
            raise ValueError("Warranty days cannot be negative.")

        if self.return_days < 0:
            raise ValueError("Return days cannot be negative.")

        try:
            date.fromisoformat(self.purchase_date) #chekcs if date is in regular iso format
        except ValueError:
            raise ValueError("Purchase date must use YYYY-MM-DD format.")

    def purchase_date_as_date(self) -> date:
        #Converts date from string to yyyy-mm-dd format
        return date.fromisoformat(self.purchase_date)

    def warranty_expiry_date(self) -> str | None:
        #Returns warranty expiry date
        if self.warranty_days == 0:
            return None

        expiry = self.purchase_date_as_date() + timedelta(days=self.warranty_days) #Calculates the date of expiry
        return expiry.isoformat() #Returns calculated date in iso format

    def return_expiry_date(self) -> str | None:
        #Returns product return expiry date
        if self.return_days == 0:
            return None

        expiry = self.purchase_date_as_date() + timedelta(days=self.return_days) #Calculates product return expiry date
        return expiry.isoformat()

    def warranty_status(self) -> str:
        #Calculates whether the warranty is active or expired
        expiry = self.warranty_expiry_date()

        if expiry is None:
            return "No warranty"

        days_left = (date.fromisoformat(expiry) - date.today()).days #Calculates days remaining til warranty expiry

        if days_left < 0:
            return "Expired"
        return "Active"

    def return_status(self) -> str:
        #Calculates whether the return period is active or expired
        expiry = self.return_expiry_date()

        if expiry is None:
            return "No return period"

        days_left = (date.fromisoformat(expiry) - date.today()).days #Calculates days remaining til the return period expires

        if days_left < 0:
            return "Expired"
        return "Active"

    def price_as_currency(self) -> str:
        #Formats price from cents into a money value like €9.99
        return f"€{self.price_cents / 100:.2f}"

    def display_summary(self) -> None:
        #Summary of receipt data for testing
        print(f"Product: {self.product_name}")
        print(f"Merchant: {self.merchant_name}")
        print(f"Price: {self.price_as_currency()}")
        print(f"Purchase date: {self.purchase_date}")
        print(f"Warranty expiry: {self.warranty_expiry_date() or 'None'}")
        print(f"Warranty status: {self.warranty_status()}")
        print(f"Return expiry: {self.return_expiry_date() or 'None'}")
        print(f"Return status: {self.return_status()}")


"""Testing of receipt validaion"""
def main() -> None:
    print("Here is an example of a valid receipt.")
    print("-" * 30)

    valid_receipt = Receipt(
        product_name="Logitech G Pro X SuperLight",
        merchant_name="Logitech",
        price_cents=10299,
        purchase_date="2026-04-23",
        warranty_days=700,
        return_days=7
    )

    try:
        valid_receipt.validate()
        valid_receipt.display_summary()
    except ValueError as error:
        print(f"Validation error: {error}")

    print("\nHere is an invalid receipt example.")
    print("-" * 30)

    invalid_receipt = Receipt(
        product_name="",
        merchant_name="Topo Centras",
        price_cents=-500,
        purchase_date="23-04-2026",
        warranty_days= -700,
        return_days= -7
    )

    try:
        invalid_receipt.display_summary()

        invalid_receipt.validate()
    except ValueError as error:
        print(f"Validation error: {error}")


if __name__ == "__main__": #Program entry point
    main()