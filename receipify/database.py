"""SQLite storage for accounts, receipts and settings.

Data lives in the per-user folder Qt reports for the platform (on macOS,
~/Library/Application Support/Receipify), never inside the program folder,
which may be read-only.
"""

import hmac
import sqlite3
from hashlib import pbkdf2_hmac
from pathlib import Path
from secrets import token_bytes

from PyQt6.QtCore import QCoreApplication, QStandardPaths

from receipt import Receipt

# Qt names the data folder after the application, so the name is set before asking for it.
QCoreApplication.setApplicationName("Receipify")
DATA_DIR = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
DB_PATH = DATA_DIR / "receipify.db"

DEFAULT_SETTINGS = {
    "default_warranty_days": 365,
    "default_return_days": 30,
    "warranty_warning_threshold": 30,
    "return_warning_threshold": 7,
}

# Merchants and categories have their own tables so each name is stored once.
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS merchants (
    merchant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_name TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT UNIQUE NOT NULL
);
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
);
CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER PRIMARY KEY,
    default_warranty_days INTEGER NOT NULL,
    default_return_days INTEGER NOT NULL,
    warranty_warning_threshold INTEGER NOT NULL,
    return_warning_threshold INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""

# Column names are renamed to match the Receipt fields, so a row converts with Receipt(**row).
RECEIPTS_QUERY = """
SELECT r.receipt_id AS id, r.user_id, r.product_name AS product, m.merchant_name AS merchant,
       c.category_name AS category, r.price_cents, r.purchase_date, r.warranty_days,
       r.return_days, r.image_path, r.created_at
FROM receipts r
JOIN merchants m ON m.merchant_id = r.merchant_id
JOIN categories c ON c.category_id = r.category_id
WHERE r.user_id = ?
ORDER BY r.purchase_date DESC, r.receipt_id DESC
"""


def hash_password(password, iterations=600_000):
    """A salted PBKDF2 hash, stored as 'pbkdf2_sha256$iterations$salt$hash'.

    The random salt gives two users with the same password different hashes,
    and the high iteration count makes every password guess slow to check.
    """
    salt = token_bytes(16)
    key = pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${key.hex()}"


def verify_password(password, stored):
    """True if the password matches the stored hash; False if it is wrong or the hash is unusable."""
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        key = pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        # compare_digest takes the same time wherever the first difference is.
        return hmac.compare_digest(key, bytes.fromhex(expected))
    except (AttributeError, ValueError, OverflowError):
        return False


class Database:
    def __init__(self, path=DB_PATH):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row  # rows can be read by column name
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    # ---- accounts

    def has_users(self):
        return self.conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def find_user(self, username):
        """The account with this username, ignoring upper/lower case, or None."""
        return self.conn.execute(
            "SELECT user_id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()

    def register(self, username, password):
        """Create an account and return its user_id."""
        if self.find_user(username) is not None:
            raise ValueError("That username is already taken.")
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hash_password(password)),
            )
        return cursor.lastrowid

    def log_in(self, username, password):
        """The account row if the username and password are correct, otherwise None."""
        user = self.find_user(username)
        if user is not None and verify_password(password, user["password_hash"]):
            return user
        return None

    # ---- receipts

    def receipts(self, user_id):
        """All of a user's receipts, newest purchase first."""
        return [Receipt(**row) for row in self.conn.execute(RECEIPTS_QUERY, (user_id,))]

    def add_receipt(self, user_id, product, merchant, category, price_cents, purchase_date,
                    warranty_days=0, return_days=0, image_path=None):
        with self.conn:
            merchant_id, category_id = self.name_ids(merchant, category)
            cursor = self.conn.execute(
                """INSERT INTO receipts (user_id, merchant_id, category_id, product_name, price_cents,
                                         purchase_date, warranty_days, return_days, image_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, merchant_id, category_id, product, price_cents,
                 purchase_date, warranty_days, return_days, image_path),
            )
        return cursor.lastrowid

    def update_receipt(self, user_id, receipt_id, product, merchant, category, price_cents,
                       purchase_date, warranty_days, return_days, image_path):
        with self.conn:
            merchant_id, category_id = self.name_ids(merchant, category)
            # Checking user_id as well means one account can never change another's receipt.
            self.conn.execute(
                """UPDATE receipts
                   SET merchant_id = ?, category_id = ?, product_name = ?, price_cents = ?,
                       purchase_date = ?, warranty_days = ?, return_days = ?, image_path = ?
                   WHERE receipt_id = ? AND user_id = ?""",
                (merchant_id, category_id, product, price_cents, purchase_date,
                 warranty_days, return_days, image_path, receipt_id, user_id),
            )

    def delete_receipt(self, user_id, receipt_id):
        with self.conn:
            self.conn.execute(
                "DELETE FROM receipts WHERE receipt_id = ? AND user_id = ?", (receipt_id, user_id)
            )

    def name_ids(self, merchant, category):
        """The ids of a merchant and a category name, adding each name the first time it is used."""
        self.conn.execute("INSERT OR IGNORE INTO merchants (merchant_name) VALUES (?)", (merchant,))
        self.conn.execute("INSERT OR IGNORE INTO categories (category_name) VALUES (?)", (category,))
        merchant_id = self.conn.execute(
            "SELECT merchant_id FROM merchants WHERE merchant_name = ?", (merchant,)
        ).fetchone()[0]
        category_id = self.conn.execute(
            "SELECT category_id FROM categories WHERE category_name = ?", (category,)
        ).fetchone()[0]
        return merchant_id, category_id

    # ---- settings

    def get_settings(self, user_id):
        row = self.conn.execute(
            """SELECT default_warranty_days, default_return_days,
                      warranty_warning_threshold, return_warning_threshold
               FROM settings WHERE user_id = ?""",
            (user_id,),
        ).fetchone()
        return dict(row) if row else dict(DEFAULT_SETTINGS)

    def save_settings(self, user_id, settings):
        with self.conn:
            self.conn.execute(
                """INSERT OR REPLACE INTO settings (user_id, default_warranty_days, default_return_days,
                                                    warranty_warning_threshold, return_warning_threshold)
                   VALUES (:user_id, :default_warranty_days, :default_return_days,
                           :warranty_warning_threshold, :return_warning_threshold)""",
                {"user_id": user_id, **settings},
            )
