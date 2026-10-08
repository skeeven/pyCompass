"""Verified recovery addresses, one-use links, and Zoho email delivery."""

import hashlib
import json
import logging
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from compass.auth import (
    AuthService,
    hash_password,
    normalize_email,
    verify_password,
)

DELIVERY = ThreadPoolExecutor(max_workers=4)
LOGGER = logging.getLogger(__name__)
REQUEST_MESSAGE = (
    "If an account has this verified email, a reset link will be sent. "
    "Check your inbox and spam folder. Requests are limited."
)


def digest(token):
    """Store a fingerprint instead of a usable recovery credential."""
    return hashlib.sha256(token.encode()).hexdigest()


class ZohoMailer:
    """Send over HTTPS with narrowly scoped OAuth credentials."""

    def __init__(self, settings):
        self.settings = settings

    def send(self, recipient, subject, body):
        """Refresh access and send plain text without exposing API errors."""
        s = self.settings
        if not s.recovery_enabled:
            raise ValueError("Email recovery is not configured.")
        try:
            request = Request(
                f"https://accounts.zoho.{s.zoho_domain}/oauth/v2/token",
                data=urlencode(
                    {
                        "client_id": s.zoho_client_id,
                        "client_secret": s.zoho_client_secret,
                        "refresh_token": s.zoho_refresh_token,
                        "grant_type": "refresh_token",
                    }
                ).encode(),
                method="POST",
            )
            with urlopen(request, timeout=10) as response:
                access = json.load(response)["access_token"]
            request = Request(
                f"https://mail.zoho.{s.zoho_domain}/api/accounts/"
                f"{s.zoho_account_id}/messages",
                data=json.dumps(
                    {
                        "fromAddress": s.mail_from,
                        "toAddress": recipient,
                        "subject": subject,
                        "content": body,
                        "mailFormat": "plaintext",
                    }
                ).encode(),
                headers={
                    "Authorization": "Zoho-oauthtoken " + access,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=10) as response:
                result = json.load(response)
            if result.get("status", {}).get("code") not in (200, 201, 202):
                raise ValueError("Delivery rejected.")
        except Exception:
            raise ValueError(
                "Email delivery failed. Try again later."
            ) from None


class RecoveryService:
    """Bind reset credentials to verified accounts and revoke old sessions."""

    def __init__(self, db, mailer=None, executor=None):
        self.db = db
        self.auth = AuthService(db)
        self.mailer = mailer or ZohoMailer(db.settings)
        self.executor = executor or DELIVERY

    def _allowed(self, conn, bucket, limit, cooldown=60):
        """Atomically enforce hourly and cooldown limits across sessions."""
        now = time.time()
        conn.execute(
            """INSERT OR IGNORE INTO account_limits
            VALUES (?, 0, 0, 0)""",
            (bucket,),
        )
        cursor = conn.execute(
            """UPDATE account_limits SET
            requests = CASE WHEN window_start <= ? THEN 1
                ELSE requests + 1 END,
            window_start = CASE WHEN window_start <= ? THEN ?
                ELSE window_start END,
            last_request = ?
            WHERE bucket = ? AND last_request <= ?
                AND (window_start <= ? OR requests < ?)""",
            (
                now - 3600,
                now - 3600,
                now,
                now,
                bucket,
                now - cooldown,
                now - 3600,
                limit,
            ),
        )
        return cursor.rowcount == 1

    def _issue(self, conn, user_id, purpose, email):
        """Replace earlier links of this purpose and return the raw secret."""
        token = secrets.token_urlsafe(32)
        conn.execute(
            "DELETE FROM account_tokens WHERE user_id = ? AND purpose = ?",
            (user_id, purpose),
        )
        conn.execute(
            "INSERT INTO account_tokens VALUES (?, ?, ?, ?, ?)",
            (digest(token), user_id, purpose, email, time.time() + 1800),
        )
        return token

    def _deliver(self, email, purpose, token):
        """Invalidate undelivered credentials and log no personal details."""
        link = (
            self.db.settings.app_base_url.rstrip("/")
            + "/?"
            + urlencode({"account_action": purpose, "account_token": token})
        )
        subject = (
            "Verify your Compass recovery email"
            if purpose == "verify"
            else "Reset your Compass password"
        )
        body = (
            f"{subject}\n\nOpen this link within 30 minutes:\n{link}\n\n"
            "The link works once. If you did not request it, ignore it. "
            "Never share this link. Compass will not ask for your password "
            "by email."
        )
        try:
            self.mailer.send(email, subject, body)
        except Exception:
            with self.db.connect() as conn:
                conn.execute(
                    "DELETE FROM account_tokens WHERE token_hash = ?",
                    (digest(token),),
                )
            LOGGER.warning("Compass account email delivery failed.")
            raise ValueError(
                "Email delivery failed. Try again later."
            ) from None

    def _background_delivery(self, email, purpose, token):
        """Keep reset-request responses independent of provider latency."""
        try:
            self._deliver(email, purpose, token)
        except Exception:
            LOGGER.warning("Compass reset delivery did not complete.")

    def request_reset(self, email):
        """Return the same message for known and unknown addresses."""
        if not self.db.settings.recovery_enabled:
            raise ValueError("Email recovery is not configured.")
        email = normalize_email(email)
        token = None
        with self.db.connect() as conn:
            conn.execute(
                "DELETE FROM account_limits WHERE window_start < ?",
                (time.time() - 7200,),
            )
            if not self._allowed(conn, "reset-global", 100, cooldown=0):
                return REQUEST_MESSAGE
            if not self._allowed(conn, "reset:" + digest(email), 5):
                return REQUEST_MESSAGE
            row = conn.execute(
                """SELECT user_id FROM account_security
                WHERE verified_email = ?""",
                (email,),
            ).fetchone()
            if row:
                token = self._issue(conn, row[0], "reset", email)
        if token:
            try:
                self.executor.submit(
                    self._background_delivery, email, "reset", token
                )
            except Exception:
                LOGGER.warning("Compass reset delivery could not be queued.")
        return REQUEST_MESSAGE

    def request_verification(self, user_id, email, current):
        """Reauthenticate before sending to a chosen recovery address."""
        if not self.db.settings.recovery_enabled:
            raise ValueError("Email recovery is not configured.")
        email = normalize_email(email)
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT username FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if not row or self.auth.login(row[0], current) != user_id:
            raise ValueError("Current password is incorrect or locked.")
        with self.db.connect() as conn:
            if not self._allowed(conn, "verify-global", 100, cooldown=0):
                raise ValueError("Please try again later.")
            if not self._allowed(conn, "verify:" + user_id, 5):
                raise ValueError("Please wait before requesting another link.")
            row = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if not row or not verify_password(current, row[0]):
                raise ValueError(
                    "Your account changed. Sign in and try again."
                )
            token = self._issue(conn, user_id, "verify", email)
        self._deliver(email, "verify", token)

    def consume(self, token, purpose, password=""):
        """Atomically consume a valid link without signing the user in."""
        if purpose not in {"verify", "reset"} or not 20 <= len(token) <= 100:
            raise ValueError("This link is invalid or expired.")
        if purpose == "reset" and not 12 <= len(password) <= 256:
            raise ValueError("Use a password between 12 and 256 characters.")
        encoded = hash_password(password) if purpose == "reset" else ""
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT user_id, email FROM account_tokens
                WHERE token_hash = ? AND purpose = ? AND expires_at > ?""",
                (digest(token), purpose, time.time()),
            ).fetchone()
            if not row:
                raise ValueError("This link is invalid or expired.")
            user_id, email = row
            claimed = conn.execute(
                """DELETE FROM account_tokens WHERE token_hash = ?
                AND purpose = ? AND expires_at > ?""",
                (digest(token), purpose, time.time()),
            )
            if claimed.rowcount != 1:
                raise ValueError("This link is invalid or expired.")
            if purpose == "verify":
                owner = conn.execute(
                    """SELECT user_id FROM account_security
                    WHERE verified_email = ? AND user_id != ?""",
                    (email, user_id),
                ).fetchone()
                if owner:
                    raise ValueError(
                        "This address cannot be added. Use another."
                    )
                conn.execute(
                    """UPDATE account_security SET verified_email = ?,
                    session_version = session_version + 1 WHERE user_id = ?""",
                    (email, user_id),
                )
            else:
                row = conn.execute(
                    """SELECT verified_email FROM account_security
                    WHERE user_id = ?""",
                    (user_id,),
                ).fetchone()
                if row is None or row[0] != email:
                    raise ValueError("This link is invalid or expired.")
                self._set_password(conn, user_id, encoded)
            conn.execute(
                "DELETE FROM account_tokens WHERE user_id = ?",
                (user_id,),
            )
        if purpose == "reset":
            self._queue_notice(email)

    def _set_password(self, conn, user_id, encoded, previous=None):
        """Replace the hash, reset throttling, and revoke existing sessions."""
        cursor = conn.execute(
            """UPDATE users SET password_hash = ?, failed_attempts = 0,
            locked_until = 0 WHERE id = ?
            AND (? IS NULL OR password_hash = ?)""",
            (encoded, user_id, previous, previous),
        )
        if cursor.rowcount != 1:
            raise ValueError("Your account changed. Sign in and try again.")
        conn.execute(
            """UPDATE account_security
            SET session_version = session_version + 1 WHERE user_id = ?""",
            (user_id,),
        )

    def change_password(self, user_id, username, current, new):
        """Require the current password before changing a signed-in account."""
        if not 12 <= len(new) <= 256:
            raise ValueError("Use a password between 12 and 256 characters.")
        if new == current:
            raise ValueError("Choose a different new password.")
        if self.auth.login(username, current) != user_id:
            raise ValueError(
                "Current password is incorrect or temporarily locked."
            )
        encoded = hash_password(new)
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if not row or not verify_password(current, row[0]):
                raise ValueError(
                    "Your account changed. Sign in and try again."
                )
            self._set_password(conn, user_id, encoded, previous=row[0])
            conn.execute(
                "DELETE FROM account_tokens WHERE user_id = ?",
                (user_id,),
            )
        email = self.auth.security(user_id)["email"]
        if email and self.db.settings.recovery_enabled:
            self._queue_notice(email)

    def _queue_notice(self, email):
        """Notification failures must not undo a completed password change."""
        try:
            self.executor.submit(self._notify, email)
        except Exception:
            LOGGER.warning(
                "Compass password-change notice could not be queued."
            )

    def _notify(self, email):
        """Send a password-change notice without the password or any token."""
        try:
            self.mailer.send(
                email,
                "Your Compass password changed",
                "Your Compass password was changed. Sign in with your new "
                "password. If you did not make this change, contact the app "
                "owner and recover your account immediately.",
            )
        except Exception:
            LOGGER.warning("Compass password-change notice could not be sent.")
