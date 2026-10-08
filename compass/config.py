"""Load configuration without requiring Streamlit during service tests."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Settings:
    """Runtime credentials and application settings."""

    database_url: str = ""
    database_path: str = "data/compass.db"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    timezone: str = "America/Denver"
    allow_registration: bool = True
    session_timeout_minutes: int = 30
    zoho_client_id: str = field(default="", repr=False)
    zoho_client_secret: str = field(default="", repr=False)
    zoho_refresh_token: str = field(default="", repr=False)
    zoho_account_id: str = ""
    zoho_domain: str = "com"
    mail_from: str = ""
    app_base_url: str = ""

    @property
    def recovery_enabled(self):
        """Enable email features when all delivery settings are present."""
        return all(
            (
                self.zoho_client_id,
                self.zoho_client_secret,
                self.zoho_refresh_token,
                self.zoho_account_id,
                self.mail_from,
                self.app_base_url,
            )
        )

    def validate(self):
        """Reject invalid configuration without echoing credential values."""
        try:
            ZoneInfo(self.timezone)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("APP_TIMEZONE must be a valid timezone.") from exc
        if not self.database_path.strip() and not self.database_url:
            raise ValueError("DATABASE_PATH cannot be empty in local mode.")
        if self.database_url and not self.database_url.startswith(
            "sqlitecloud://"
        ):
            raise ValueError("SQLITECLOUD_URL must use sqlitecloud://.")
        if not self.openai_model.strip():
            raise ValueError("OPENAI_MODEL cannot be empty.")
        if not 1 <= self.session_timeout_minutes <= 1440:
            raise ValueError(
                "SESSION_TIMEOUT_MINUTES must be between 1 and 1440."
            )
        if self.zoho_domain not in {
            "com",
            "eu",
            "in",
            "com.au",
            "jp",
            "ca",
            "com.cn",
            "sa",
        }:
            raise ValueError("ZOHO_DOMAIN is not a supported region.")
        if self.recovery_enabled:
            address = urlsplit(self.app_base_url)
            if (
                address.scheme != "https"
                or not address.hostname
                or address.username
                or address.password
                or address.query
                or address.fragment
            ):
                raise ValueError("APP_BASE_URL must be a plain HTTPS URL.")
            if not self.zoho_account_id.isdigit():
                raise ValueError(
                    "ZOHO_ACCOUNT_ID must be a quoted numeric ID."
                )

    @classmethod
    def load(cls, secrets=None):
        """Prefer environment variables over project secrets."""
        secrets = secrets or {}

        def value(name, default=""):
            return os.environ.get(name, secrets.get(name, default))

        registration = str(value("ALLOW_REGISTRATION", "true")).lower()
        if registration not in {"true", "false"}:
            raise ValueError("ALLOW_REGISTRATION must be true or false.")
        try:
            timeout = int(value("SESSION_TIMEOUT_MINUTES", "30"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "SESSION_TIMEOUT_MINUTES must be a whole number."
            ) from exc
        settings = cls(
            database_url=value("SQLITECLOUD_URL"),
            database_path=value("DATABASE_PATH", "data/compass.db"),
            openai_api_key=value("OPENAI_API_KEY"),
            openai_model=value("OPENAI_MODEL", "gpt-4.1-mini"),
            timezone=value("APP_TIMEZONE", "America/Denver"),
            allow_registration=registration == "true",
            session_timeout_minutes=timeout,
            zoho_client_id=str(value("ZOHO_CLIENT_ID")),
            zoho_client_secret=str(value("ZOHO_CLIENT_SECRET")),
            zoho_refresh_token=str(value("ZOHO_REFRESH_TOKEN")),
            zoho_account_id=str(value("ZOHO_ACCOUNT_ID")),
            zoho_domain=str(value("ZOHO_DOMAIN", "com")),
            mail_from=str(value("MAIL_FROM")),
            app_base_url=str(value("APP_BASE_URL")),
        )
        settings.validate()
        return settings
