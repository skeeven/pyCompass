"""Password hashing, registration, and login throttling."""

import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timezone
from uuid import uuid4

ITERATIONS = 600_000


def hash_password(password):
    """Hash a password using salted PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password, encoded):
    """Compare a candidate password in constant time."""
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class AuthService:
    """Own account creation and persisted per-account throttling."""

    def __init__(self, db):
        self.db = db
        self.dummy_hash = hash_password(secrets.token_urlsafe(24))

    def register(self, username, password):
        """Create an account; reject invalid and duplicate usernames."""
        if not self.db.settings.allow_registration:
            raise ValueError("Account creation is disabled.")
        username = username.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{3,32}", username):
            raise ValueError("Use 3–32 letters, numbers, or underscores.")
        if not 12 <= len(password) <= 256:
            raise ValueError("Use a password between 12 and 256 characters.")
        user_id = str(uuid4())
        with self.db.connect() as conn:
            if conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone():
                raise ValueError("That username is unavailable.")
            conn.execute(
                """INSERT INTO users
                (id, username, password_hash, created_at)
                VALUES (?, ?, ?, ?)""",
                (
                    user_id,
                    username,
                    hash_password(password),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return user_id

    def login(self, username, password):
        """Return an account id or None with a generic failure message."""
        username = username.strip().lower()
        if len(password) > 256:
            return None
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT id, password_hash, failed_attempts, locked_until
                FROM users WHERE username = ?""",
                (username,),
            ).fetchone()
            if not row:
                verify_password(password, self.dummy_hash)
                return None
            user_id, encoded, failures, locked_until = row
            if locked_until > time.time():
                return None
            if verify_password(password, encoded):
                conn.execute(
                    """UPDATE users SET failed_attempts = 0,
                    locked_until = 0 WHERE id = ?""",
                    (user_id,),
                )
                return user_id
            failures = failures + 1 if locked_until == 0 else 1
            conn.execute(
                """UPDATE users SET failed_attempts = ?, locked_until = ?
                WHERE id = ?""",
                (failures, time.time() + 300 if failures >= 5 else 0, user_id),
            )
            return None
