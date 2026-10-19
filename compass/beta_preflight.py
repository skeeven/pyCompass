"""Conservative static checks for a planned isolated Compass closed beta.

Passing these checks is NOT proof that hosting, encryption, backups, or
service permissions are secure. Never print secret values.
"""

from urllib.parse import urlsplit


def inspect_beta_configuration(settings):
    """Return release blockers without returning any credential values."""
    issues = []
    if settings.allow_registration:
        issues.append(
            "Self-service registration is enabled. Set ALLOW_REGISTRATION=false "
            "and establish a private account invitation process."
        )
    if not settings.database_url:
        issues.append(
            "No dedicated cloud database URL is configured; verify a "
            "separate beta database and narrowly scoped credentials."
        )
    if settings.database_url and not settings.database_url.startswith("sqlitecloud://"):
        issues.append("Beta database URL must use the expected SQLiteCloud scheme.")
    if settings.session_timeout_minutes > 60:
        issues.append(
            "Session timeout exceeds the recommended 60 minutes for a "
            "sensitive-data closed beta."
        )
    if not settings.recovery_enabled:
        issues.append(
            "Email-based recovery is not fully configured. Confirm an "
            "identity-verified recovery procedure before inviting testers."
        )
    else:
        parsed = urlsplit(settings.app_base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            issues.append("Account recovery base URL is not a valid HTTPS URL.")
    return issues
