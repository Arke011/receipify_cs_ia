import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # run the Qt tests without opening windows

import pytest
from PyQt6.QtWidgets import QApplication

import images
from database import Database
from receipt import Receipt


@pytest.fixture(scope="session", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    """Receipt images are copied into a temporary folder, never the real data folder."""
    folder = tmp_path / "images"
    monkeypatch.setattr(images, "IMAGE_DIR", folder)
    return folder


@pytest.fixture
def empty_db(tmp_path):
    """A new database with no accounts yet."""
    db = Database(tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def db(empty_db):
    """A new database with one account, alice (user 1)."""
    empty_db.register("alice", "password123")
    return empty_db


@pytest.fixture
def add_receipt(db):
    """Saves a receipt (for alice unless user_id is given) and returns its id; any field can be changed."""
    def add(**changes):
        values = {"product": "Wireless Mouse", "merchant": "Tech Store", "category": "Electronics",
                  "price_cents": 2499, "purchase_date": "2026-08-15", "warranty_days": 365,
                  "return_days": 30, "image_path": None}
        values.update(changes)
        return db.add_receipt(values.pop("user_id", 1), **values)
    return add


@pytest.fixture
def make_receipt():
    """Builds a Receipt without a database; any field can be changed."""
    def make(**changes):
        values = {"id": 1, "user_id": 1, "product": "Wireless Mouse", "merchant": "Tech Store",
                  "category": "Electronics", "price_cents": 2499, "purchase_date": "2026-08-15",
                  "warranty_days": 365, "return_days": 30, "image_path": None,
                  "created_at": "2026-08-15 10:00:00"}
        values.update(changes)
        return Receipt(**values)
    return make
