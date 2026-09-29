import pytest

from database import DEFAULT_SETTINGS, Database, hash_password, verify_password


def test_passwords_are_stored_as_salted_hashes():
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second  # a new random salt every time
    assert "same-password" not in first
    assert first.startswith("pbkdf2_sha256$600000$")
    assert verify_password("same-password", first)
    assert verify_password("same-password", second)
    assert not verify_password("Same-password", first)


@pytest.mark.parametrize("stored", [
    "", "not_used_yet", None, "md5$1$aa$bb", "pbkdf2_sha256$0$aa$bb", "pbkdf2_sha256$1$not-hex$bb",
])
def test_unusable_hashes_never_match(stored):
    assert verify_password("anything", stored) is False


def test_register_then_log_in(empty_db):
    db = empty_db
    assert not db.has_users()
    user_id = db.register("alice", "password123")
    assert db.has_users()
    assert "password123" not in db.find_user("alice")["password_hash"]
    assert db.log_in("ALICE", "password123")["user_id"] == user_id  # usernames ignore case
    assert db.log_in("alice", "wrong-password") is None
    assert db.log_in("nobody", "password123") is None


def test_usernames_are_unique_ignoring_case(db):
    with pytest.raises(ValueError, match="already taken"):
        db.register("Alice", "password123")


def test_receipts_are_listed_newest_first_and_can_be_updated_and_deleted(db, add_receipt):
    mouse = add_receipt(purchase_date="2026-08-15")
    keyboard = add_receipt(product="Keyboard", merchant="Office Shop", purchase_date="2026-08-16")
    assert [r.id for r in db.receipts(1)] == [keyboard, mouse]

    db.update_receipt(1, mouse, "Ergonomic Mouse", "New Store", "Accessories", 3599, "2026-08-20", 730, 14, "/img.png")
    updated = db.receipts(1)[0]
    assert (updated.id, updated.product, updated.merchant, updated.category, updated.price_cents,
            updated.purchase_date, updated.warranty_days, updated.return_days, updated.image_path) == (
        mouse, "Ergonomic Mouse", "New Store", "Accessories", 3599, "2026-08-20", 730, 14, "/img.png")

    db.delete_receipt(1, mouse)
    assert [r.id for r in db.receipts(1)] == [keyboard]


def test_accounts_cannot_see_or_change_each_others_receipts(db, add_receipt):
    bob = db.register("bob", "password123")
    alice_receipt = add_receipt()
    assert db.receipts(bob) == []
    db.update_receipt(bob, alice_receipt, "Changed", "Shop", "Other", 1, "2026-01-01", 0, 0, None)
    db.delete_receipt(bob, alice_receipt)
    assert [r.product for r in db.receipts(1)] == ["Wireless Mouse"]


def test_settings_start_at_the_defaults_and_are_kept(db, tmp_path):
    assert db.get_settings(1) == DEFAULT_SETTINGS
    chosen = {"default_warranty_days": 730, "default_return_days": 14,
              "warranty_warning_threshold": 45, "return_warning_threshold": 10}
    db.save_settings(1, chosen)
    reopened = Database(tmp_path / "test.db")
    assert reopened.get_settings(1) == chosen  # still there after reopening
    reopened.close()
