import sqlite3
from contextlib import closing
from pathlib import Path

from app.models.receipt import Receipt
from app.paths import DATABASE_PATH
from app.services.auth_service import (
    dummy_password_hash,
    hash_password,
    is_usable_hash,
    validate_credentials,
    verify_password,
)
from app.services.settings_service import DEFAULT_SETTINGS, validate_settings


LIKE_ESCAPE_CHARACTER = "\\"

# A second instance, or an open database browser, can hold a write lock briefly.
# Waiting is better than failing the user's action immediately.
CONNECTION_TIMEOUT_SECONDS = 10.0
BUSY_TIMEOUT_MILLISECONDS = 10000


class DataManager:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path is not None else self.default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.create_tables()
        self.create_default_user()

    @staticmethod
    def default_database_path():
        return DATABASE_PATH

    def connect(self):
        """Open a connection. Callers must close it, normally via ``closing``."""
        connection = sqlite3.connect(self.db_path, timeout=CONNECTION_TIMEOUT_SECONDS)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MILLISECONDS}")
        return connection

    def create_tables(self):
        with closing(self.connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS merchants (
                    merchant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    merchant_name TEXT UNIQUE NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_name TEXT UNIQUE NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    merchant_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    price_cents INTEGER NOT NULL DEFAULT 0,
                    purchase_date TEXT NOT NULL,
                    warranty_days INTEGER NOT NULL DEFAULT 0,
                    return_days INTEGER NOT NULL DEFAULT 0,
                    image_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id),
                    FOREIGN KEY (category_id) REFERENCES categories(category_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    user_id INTEGER PRIMARY KEY,
                    default_warranty_days INTEGER NOT NULL,
                    default_return_days INTEGER NOT NULL,
                    warranty_warning_threshold INTEGER NOT NULL,
                    return_warning_threshold INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
                """
            )

    def create_default_user(self):
        with closing(self.connect()) as connection, connection:
            existing_user = connection.execute(
                "SELECT user_id FROM users LIMIT 1"
            ).fetchone()

            if existing_user is None:
                connection.execute(
                    """
                    INSERT INTO users (user_id, username, password_hash)
                    VALUES (?, ?, ?)
                    """,
                    (1, "default_user", "not_used_yet"),
                )

    def get_user_by_username(self, username):
        with closing(self.connect()) as connection:
            return connection.execute(
                """
                SELECT user_id, username, password_hash
                FROM users
                WHERE username = ? COLLATE NOCASE
                """,
                (str(username).strip(),),
            ).fetchone()

    def count_claimed_accounts(self):
        """Accounts with a usable password hash, i.e. excluding the seeded placeholder."""
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT password_hash FROM users").fetchall()

        return sum(1 for row in rows if is_usable_hash(row["password_hash"]))

    def authenticate_user(self, username, password):
        user = self.get_user_by_username(username)
        if user is None:
            # Spend the same hashing work an existing account would, so the
            # response time cannot be used to discover which usernames exist.
            verify_password(password, dummy_password_hash())
            return None

        if not verify_password(password, user["password_hash"]):
            return None

        return user["user_id"]

    def register_user(self, username, password):
        """Create an account: the first registration claims the seeded legacy account."""
        claimed_user_id = self.claim_unclaimed_account(username, password)
        if claimed_user_id is not None:
            return claimed_user_id

        return self.create_user(username, password)

    def create_user(self, username, password):
        values = self.clean_credentials(username, password)

        if self.get_user_by_username(values["username"]) is not None:
            raise ValueError("That username is already taken.")

        try:
            with closing(self.connect()) as connection, connection:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (values["username"], hash_password(values["password"])),
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError as error:
            raise ValueError("That username is already taken.") from error

    def claim_unclaimed_account(self, username, password):
        """Give the seeded account real credentials, keeping its user_id and data.

        Only applies on genuine first run, so a later registration can never
        inherit the receipts already attached to the seeded account.
        """
        if self.count_claimed_accounts() > 0:
            return None

        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT user_id, password_hash FROM users ORDER BY user_id"
            ).fetchall()

        unclaimed_user = next(
            (row for row in rows if not is_usable_hash(row["password_hash"])), None
        )
        if unclaimed_user is None:
            return None

        values = self.clean_credentials(username, password)
        existing_user = self.get_user_by_username(values["username"])
        if existing_user is not None and existing_user["user_id"] != unclaimed_user["user_id"]:
            raise ValueError("That username is already taken.")

        with closing(self.connect()) as connection, connection:
            connection.execute(
                "UPDATE users SET username = ?, password_hash = ? WHERE user_id = ?",
                (
                    values["username"],
                    hash_password(values["password"]),
                    unclaimed_user["user_id"],
                ),
            )

        return unclaimed_user["user_id"]

    @staticmethod
    def clean_credentials(username, password):
        is_valid, errors, values = validate_credentials(username, password)
        if not is_valid:
            raise ValueError(" ".join(errors))

        return values

    def get_or_create_merchant(self, merchant_name):
        merchant_name = merchant_name.strip()

        with closing(self.connect()) as connection, connection:
            existing_merchant = connection.execute(
                "SELECT merchant_id FROM merchants WHERE merchant_name = ?",
                (merchant_name,),
            ).fetchone()

            if existing_merchant:
                return existing_merchant["merchant_id"]

            cursor = connection.execute(
                "INSERT INTO merchants (merchant_name) VALUES (?)",
                (merchant_name,),
            )
            return cursor.lastrowid

    def get_or_create_category(self, category_name):
        category_name = category_name.strip()

        with closing(self.connect()) as connection, connection:
            existing_category = connection.execute(
                "SELECT category_id FROM categories WHERE category_name = ?",
                (category_name,),
            ).fetchone()

            if existing_category:
                return existing_category["category_id"]

            cursor = connection.execute(
                "INSERT INTO categories (category_name) VALUES (?)",
                (category_name,),
            )
            return cursor.lastrowid

    def add_receipt(
        self,
        product_name,
        merchant_name,
        category_name,
        price_cents,
        purchase_date,
        warranty_days=0,
        return_days=0,
        image_path=None,
        user_id=1,
    ):
        merchant_id = self.get_or_create_merchant(merchant_name)
        category_id = self.get_or_create_category(category_name)

        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO receipts (
                    user_id,
                    merchant_id,
                    category_id,
                    product_name,
                    price_cents,
                    purchase_date,
                    warranty_days,
                    return_days,
                    image_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    merchant_id,
                    category_id,
                    product_name,
                    price_cents,
                    purchase_date,
                    warranty_days,
                    return_days,
                    image_path,
                ),
            )
            return cursor.lastrowid

    def get_all_receipts(self, user_id=1):
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    receipts.receipt_id,
                    receipts.user_id,
                    receipts.product_name,
                    merchants.merchant_name,
                    categories.category_name,
                    receipts.price_cents,
                    receipts.purchase_date,
                    receipts.warranty_days,
                    receipts.return_days,
                    receipts.image_path,
                    receipts.created_at
                FROM receipts
                JOIN merchants ON receipts.merchant_id = merchants.merchant_id
                JOIN categories ON receipts.category_id = categories.category_id
                WHERE receipts.user_id = ?
                ORDER BY receipts.purchase_date DESC, receipts.receipt_id DESC
                """,
                (user_id,),
            ).fetchall()

        return [self.row_to_receipt(row) for row in rows]

    def get_receipt_filter_options(self, user_id=1):
        """Return only the merchants and categories used by this user's receipts."""
        with closing(self.connect()) as connection:
            merchants = connection.execute(
                """
                SELECT DISTINCT merchants.merchant_name
                FROM receipts
                JOIN merchants ON receipts.merchant_id = merchants.merchant_id
                WHERE receipts.user_id = ?
                ORDER BY merchants.merchant_name COLLATE NOCASE
                """,
                (user_id,),
            ).fetchall()
            categories = connection.execute(
                """
                SELECT DISTINCT categories.category_name
                FROM receipts
                JOIN categories ON receipts.category_id = categories.category_id
                WHERE receipts.user_id = ?
                ORDER BY categories.category_name COLLATE NOCASE
                """,
                (user_id,),
            ).fetchall()

        return {
            "merchants": [row["merchant_name"] for row in merchants],
            "categories": [row["category_name"] for row in categories],
        }

    def search_receipts(self, user_id, query):
        search_text = f"%{self.escape_like_pattern(query.strip())}%"

        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    receipts.receipt_id,
                    receipts.user_id,
                    receipts.product_name,
                    merchants.merchant_name,
                    categories.category_name,
                    receipts.price_cents,
                    receipts.purchase_date,
                    receipts.warranty_days,
                    receipts.return_days,
                    receipts.image_path,
                    receipts.created_at
                FROM receipts
                JOIN merchants ON receipts.merchant_id = merchants.merchant_id
                JOIN categories ON receipts.category_id = categories.category_id
                WHERE receipts.user_id = ?
                    AND (
                        receipts.product_name LIKE ? ESCAPE '\\'
                        OR merchants.merchant_name LIKE ? ESCAPE '\\'
                        OR categories.category_name LIKE ? ESCAPE '\\'
                    )
                ORDER BY receipts.purchase_date DESC, receipts.receipt_id DESC
                """,
                (user_id, search_text, search_text, search_text),
            ).fetchall()

        return [self.row_to_receipt(row) for row in rows]

    def update_receipt(
        self,
        receipt_id,
        product_name,
        merchant_name,
        category_name,
        price_cents,
        purchase_date,
        warranty_days,
        return_days,
        image_path=None,
        user_id=1,
    ):
        merchant_id = self.get_or_create_merchant(merchant_name)
        category_id = self.get_or_create_category(category_name)

        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE receipts
                SET
                    merchant_id = ?,
                    category_id = ?,
                    product_name = ?,
                    price_cents = ?,
                    purchase_date = ?,
                    warranty_days = ?,
                    return_days = ?,
                    image_path = ?
                WHERE receipt_id = ? AND user_id = ?
                """,
                (
                    merchant_id,
                    category_id,
                    product_name,
                    price_cents,
                    purchase_date,
                    warranty_days,
                    return_days,
                    image_path,
                    receipt_id,
                    user_id,
                ),
            )
            return cursor.rowcount > 0

    def delete_receipt(self, receipt_id, user_id=1):
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM receipts WHERE receipt_id = ? AND user_id = ?",
                (receipt_id, user_id),
            )
            return cursor.rowcount > 0

    def get_settings(self, user_id=1):
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    default_warranty_days,
                    default_return_days,
                    warranty_warning_threshold,
                    return_warning_threshold
                FROM settings
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return DEFAULT_SETTINGS.copy()

        return dict(row)

    def save_settings(
        self,
        default_warranty_days,
        default_return_days,
        warranty_warning_threshold,
        return_warning_threshold,
        user_id=1,
    ):
        is_valid, errors, values = validate_settings(
            default_warranty_days,
            default_return_days,
            warranty_warning_threshold,
            return_warning_threshold,
        )
        if not is_valid:
            raise ValueError(" ".join(errors))

        with closing(self.connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO settings (
                    user_id,
                    default_warranty_days,
                    default_return_days,
                    warranty_warning_threshold,
                    return_warning_threshold
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    default_warranty_days = excluded.default_warranty_days,
                    default_return_days = excluded.default_return_days,
                    warranty_warning_threshold = excluded.warranty_warning_threshold,
                    return_warning_threshold = excluded.return_warning_threshold
                """,
                (user_id, *values.values()),
            )

    @staticmethod
    def escape_like_pattern(query):
        """Escape LIKE wildcards so '%' and '_' are searched for literally."""
        for character in (LIKE_ESCAPE_CHARACTER, "%", "_"):
            query = query.replace(character, LIKE_ESCAPE_CHARACTER + character)

        return query

    def row_to_receipt(self, row):
        return Receipt(
            receipt_id=row["receipt_id"],
            user_id=row["user_id"],
            product_name=row["product_name"],
            merchant_name=row["merchant_name"],
            category_name=row["category_name"],
            price_cents=row["price_cents"],
            purchase_date=row["purchase_date"],
            warranty_days=row["warranty_days"],
            return_days=row["return_days"],
            image_path=row["image_path"],
            created_at=row["created_at"],
        )
