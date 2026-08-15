import pytest

from app.services import auth_service


def test_hash_password_uses_the_self_describing_pbkdf2_format():
    encoded = auth_service.hash_password("correct horse battery")

    algorithm, iterations, salt_hex, hash_hex = encoded.split("$")

    assert algorithm == "pbkdf2_sha256"
    assert int(iterations) == auth_service.ITERATIONS == 600000
    assert len(bytes.fromhex(salt_hex)) == auth_service.SALT_BYTES
    assert len(bytes.fromhex(hash_hex)) == 32


def test_hashing_the_same_password_twice_produces_different_hashes():
    """A unique random salt per user means identical passwords never collide."""
    first = auth_service.hash_password("same-password")
    second = auth_service.hash_password("same-password")

    assert first != second
    assert auth_service.verify_password("same-password", first)
    assert auth_service.verify_password("same-password", second)


def test_hash_never_contains_the_plaintext_password():
    password = "SuperSecret123"

    encoded = auth_service.hash_password(password)

    assert password not in encoded
    assert password.lower() not in encoded.lower()


def test_verify_password_accepts_the_correct_password():
    encoded = auth_service.hash_password("correct-password")

    assert auth_service.verify_password("correct-password", encoded) is True


@pytest.mark.parametrize(
    "wrong_password",
    ["wrong-password", "correct-passwor", "correct-password ", "", "CORRECT-PASSWORD"],
)
def test_verify_password_rejects_wrong_passwords(wrong_password):
    encoded = auth_service.hash_password("correct-password")

    assert auth_service.verify_password(wrong_password, encoded) is False


def test_verify_password_rejects_the_legacy_placeholder_hash():
    """The seeded 'not_used_yet' account must never be able to authenticate."""
    assert auth_service.verify_password("not_used_yet", "not_used_yet") is False
    assert auth_service.verify_password("", "not_used_yet") is False
    assert auth_service.verify_password("anything", "not_used_yet") is False


@pytest.mark.parametrize(
    "malformed",
    [
        "",
        "not_used_yet",
        "pbkdf2_sha256$600000$deadbeef",
        "pbkdf2_sha256$600000$deadbeef$cafe$extra",
        "md5$600000$deadbeef$cafe",
        "pbkdf2_sha256$notanumber$deadbeef$cafe",
        "pbkdf2_sha256$600000$nothex$cafe",
        "pbkdf2_sha256$0$deadbeef$cafe",
        "pbkdf2_sha256$-1$deadbeef$cafe",
        "pbkdf2_sha256$600000$$cafe",
        None,
        12345,
    ],
)
def test_verify_password_returns_false_for_malformed_hashes_without_raising(malformed):
    assert auth_service.verify_password("anything", malformed) is False
    assert auth_service.is_usable_hash(malformed) is False


def test_is_usable_hash_accepts_a_real_hash():
    assert auth_service.is_usable_hash(auth_service.hash_password("a-password")) is True


def test_iteration_count_round_trips_so_the_cost_can_be_raised_later():
    encoded = auth_service.hash_password("a-password", iterations=1000)

    assert encoded.split("$")[1] == "1000"
    assert auth_service.verify_password("a-password", encoded) is True


@pytest.mark.parametrize(
    ("username", "expected_error"),
    [
        ("", "Username cannot be empty."),
        ("   ", "Username cannot be empty."),
        ("ab", "Username must be between 3 and 32 characters."),
        ("a" * 33, "Username must be between 3 and 32 characters."),
        (
            "has space",
            "Username can only contain letters, numbers, dots, hyphens, and underscores.",
        ),
        (
            "hello!",
            "Username can only contain letters, numbers, dots, hyphens, and underscores.",
        ),
    ],
)
def test_validate_credentials_rejects_invalid_usernames(username, expected_error):
    is_valid, errors, values = auth_service.validate_credentials(username, "password123")

    assert is_valid is False
    assert expected_error in errors
    assert values == {}


@pytest.mark.parametrize(
    ("password", "expected_error"),
    [
        ("", "Password must be at least 8 characters."),
        ("short", "Password must be at least 8 characters."),
        ("a" * 129, "Password must be 128 characters or fewer."),
    ],
)
def test_validate_credentials_rejects_invalid_passwords(password, expected_error):
    is_valid, errors, values = auth_service.validate_credentials("valid_user", password)

    assert is_valid is False
    assert expected_error in errors
    assert values == {}


def test_validate_credentials_rejects_mismatched_confirmation():
    is_valid, errors, values = auth_service.validate_credentials(
        "valid_user", "password123", confirm_password="password124"
    )

    assert is_valid is False
    assert errors == ["Passwords do not match."]
    assert values == {}


def test_validate_credentials_returns_trimmed_values_when_valid():
    is_valid, errors, values = auth_service.validate_credentials(
        "  valid.user-1  ", "password123", confirm_password="password123"
    )

    assert is_valid is True
    assert errors == []
    assert values == {"username": "valid.user-1", "password": "password123"}


def test_validate_credentials_does_not_trim_passwords():
    """Leading/trailing spaces are legitimate password characters."""
    is_valid, _, values = auth_service.validate_credentials("valid_user", "  spaced  ")

    assert is_valid is True
    assert values["password"] == "  spaced  "
