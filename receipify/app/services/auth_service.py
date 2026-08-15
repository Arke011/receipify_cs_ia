"""Password hashing and credential validation for local, offline accounts.

Passwords are stored as PBKDF2-HMAC-SHA256 digests in a self-describing format:

    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>

Recording the iteration count in the string means the cost can be raised later
without invalidating hashes that were created with the old cost.
"""

import hmac
import re
from hashlib import pbkdf2_hmac
from secrets import token_bytes


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600000
SALT_BYTES = 16

MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 32
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def hash_password(password, iterations=ITERATIONS):
    salt = token_bytes(SALT_BYTES)
    derived_key = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{ALGORITHM}${iterations}${salt.hex()}${derived_key.hex()}"


def verify_password(password, encoded_hash):
    """Check a password against a stored hash, returning False for unusable hashes.

    Never raises: the seeded 'not_used_yet' placeholder and any other malformed
    value simply fail to verify, so they can never be used to log in.
    """
    parsed_hash = _parse_hash(encoded_hash)
    if parsed_hash is None:
        return False

    iterations, salt, expected_key = parsed_hash
    derived_key = pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived_key, expected_key)


def is_usable_hash(encoded_hash):
    """True when a stored hash could ever authenticate, used to spot unclaimed accounts."""
    return _parse_hash(encoded_hash) is not None


def validate_credentials(username, password, confirm_password=None):
    errors = []
    username = str(username).strip()
    password = str(password)

    if not username:
        errors.append("Username cannot be empty.")
    elif not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        errors.append(
            f"Username must be between {MIN_USERNAME_LENGTH} and "
            f"{MAX_USERNAME_LENGTH} characters."
        )
    elif not USERNAME_PATTERN.match(username):
        errors.append(
            "Username can only contain letters, numbers, dots, hyphens, and underscores."
        )

    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    elif len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"Password must be {MAX_PASSWORD_LENGTH} characters or fewer.")

    if confirm_password is not None and password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return False, errors, {}

    return True, [], {"username": username, "password": password}


def _parse_hash(encoded_hash):
    if not isinstance(encoded_hash, str):
        return None

    parts = encoded_hash.split("$")
    if len(parts) != 4:
        return None

    algorithm, iterations_text, salt_hex, hash_hex = parts
    if algorithm != ALGORITHM:
        return None

    try:
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(hash_hex)
    except ValueError:
        return None

    if iterations <= 0 or not salt or not expected_key:
        return None

    return iterations, salt, expected_key
