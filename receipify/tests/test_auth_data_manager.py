import pytest

from app.data.data_manager import DataManager
from app.services import auth_service


@pytest.fixture
def data_manager(tmp_path):
    return DataManager(tmp_path / "receipify-test.db")


@pytest.fixture
def legacy_data_manager(tmp_path):
    """A database shaped exactly like the current canonical one: unclaimed user 1 with data."""
    manager = DataManager(tmp_path / "receipify-legacy.db")
    manager.add_receipt(
        product_name="Minecraft",
        merchant_name="Game Store",
        category_name="Games",
        price_cents=2499,
        purchase_date="2021-02-10",
        warranty_days=0,
        return_days=0,
    )
    manager.add_receipt(
        product_name="MacBook Pro M5",
        merchant_name="Tech Store",
        category_name="Electronics",
        price_cents=599999,
        purchase_date="2026-08-15",
        warranty_days=365,
        return_days=0,
    )
    manager.save_settings(730, 14, 45, 10)
    return manager


def test_seeded_account_starts_unclaimed(data_manager):
    with data_manager.connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE user_id = 1").fetchone()

    assert row["username"] == "default_user"
    assert row["password_hash"] == "not_used_yet"
    assert data_manager.count_claimed_accounts() == 0


def test_create_user_stores_a_hashed_password(data_manager):
    user_id = data_manager.create_user("alice", "password123")

    with data_manager.connect() as connection:
        row = connection.execute(
            "SELECT username, password_hash FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

    assert row["username"] == "alice"
    assert "password123" not in row["password_hash"]
    assert auth_service.is_usable_hash(row["password_hash"])
    assert auth_service.verify_password("password123", row["password_hash"])


def test_create_user_rejects_duplicate_usernames(data_manager):
    data_manager.create_user("alice", "password123")

    with pytest.raises(ValueError, match="already taken"):
        data_manager.create_user("alice", "different123")


@pytest.mark.parametrize("duplicate", ["ALICE", "Alice", "aLiCe"])
def test_create_user_rejects_duplicates_case_insensitively(data_manager, duplicate):
    data_manager.create_user("alice", "password123")

    with pytest.raises(ValueError, match="already taken"):
        data_manager.create_user(duplicate, "password123")


def test_create_user_rejects_invalid_credentials(data_manager):
    with pytest.raises(ValueError, match="Password must be at least 8 characters."):
        data_manager.create_user("alice", "short")


@pytest.mark.parametrize("lookup", ["alice", "ALICE", "Alice", "  alice  "])
def test_get_user_by_username_is_case_insensitive(data_manager, lookup):
    user_id = data_manager.create_user("alice", "password123")

    assert data_manager.get_user_by_username(lookup)["user_id"] == user_id


def test_get_user_by_username_returns_none_for_unknown_users(data_manager):
    assert data_manager.get_user_by_username("nobody") is None


def test_authenticate_user_returns_the_user_id_for_valid_credentials(data_manager):
    user_id = data_manager.create_user("alice", "password123")

    assert data_manager.authenticate_user("alice", "password123") == user_id
    assert data_manager.authenticate_user("ALICE", "password123") == user_id


def test_authenticate_user_rejects_a_wrong_password(data_manager):
    data_manager.create_user("alice", "password123")

    assert data_manager.authenticate_user("alice", "wrong-password") is None


def test_authenticate_user_rejects_an_unknown_username(data_manager):
    assert data_manager.authenticate_user("nobody", "password123") is None


def test_authenticate_user_rejects_the_unclaimed_legacy_account(data_manager):
    """The seeded default_user must not be a usable login."""
    assert data_manager.authenticate_user("default_user", "not_used_yet") is None
    assert data_manager.authenticate_user("default_user", "") is None


def test_count_claimed_accounts_tracks_registrations(data_manager):
    assert data_manager.count_claimed_accounts() == 0

    data_manager.register_user("alice", "password123")
    assert data_manager.count_claimed_accounts() == 1

    data_manager.register_user("bob", "password123")
    assert data_manager.count_claimed_accounts() == 2


def test_first_registration_claims_the_legacy_account_in_place(legacy_data_manager):
    user_id = legacy_data_manager.register_user("alice", "password123")

    assert user_id == 1
    with legacy_data_manager.connect() as connection:
        rows = connection.execute("SELECT user_id, username FROM users").fetchall()
    assert [(row["user_id"], row["username"]) for row in rows] == [(1, "alice")]


def test_existing_receipts_and_settings_survive_the_first_registration(legacy_data_manager):
    """The whole point of claiming in place: user 1's data stays attached."""
    receipts_before = legacy_data_manager.get_all_receipts(1)
    settings_before = legacy_data_manager.get_settings(1)

    user_id = legacy_data_manager.register_user("alice", "password123")

    assert user_id == 1
    assert legacy_data_manager.get_all_receipts(user_id) == receipts_before
    assert [r.product_name for r in receipts_before] == ["MacBook Pro M5", "Minecraft"]
    assert legacy_data_manager.get_settings(user_id) == settings_before
    assert settings_before["default_warranty_days"] == 730
    assert legacy_data_manager.authenticate_user("alice", "password123") == 1


def test_second_registration_creates_a_new_user_and_does_not_inherit_legacy_data(
    legacy_data_manager,
):
    legacy_data_manager.register_user("alice", "password123")

    bob_id = legacy_data_manager.register_user("bob", "password123")

    assert bob_id != 1
    assert legacy_data_manager.get_all_receipts(bob_id) == []
    assert len(legacy_data_manager.get_all_receipts(1)) == 2


def test_claim_unclaimed_account_returns_none_once_an_account_is_claimed(data_manager):
    assert data_manager.claim_unclaimed_account("alice", "password123") == 1
    assert data_manager.claim_unclaimed_account("bob", "password123") is None


def test_register_user_rejects_a_duplicate_username_when_claiming(legacy_data_manager):
    legacy_data_manager.register_user("alice", "password123")

    with pytest.raises(ValueError, match="already taken"):
        legacy_data_manager.register_user("alice", "password123")


def test_registered_users_keep_separate_receipts(data_manager):
    alice_id = data_manager.register_user("alice", "password123")
    bob_id = data_manager.register_user("bob", "password123")

    data_manager.add_receipt(
        product_name="Alice Item",
        merchant_name="Shop",
        category_name="Home",
        price_cents=100,
        purchase_date="2026-01-01",
        user_id=alice_id,
    )

    assert [r.product_name for r in data_manager.get_all_receipts(alice_id)] == ["Alice Item"]
    assert data_manager.get_all_receipts(bob_id) == []
    assert data_manager.search_receipts(bob_id, "Alice") == []


def test_new_users_start_from_the_default_settings(data_manager):
    from app.services.settings_service import DEFAULT_SETTINGS

    data_manager.register_user("alice", "password123")
    bob_id = data_manager.register_user("bob", "password123")

    assert data_manager.get_settings(bob_id) == DEFAULT_SETTINGS
