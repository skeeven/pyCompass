"""Load configuration without requiring Streamlit during service tests."""

import os
from dataclasses import dataclass
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
        )
        settings.validate()
        return settings
