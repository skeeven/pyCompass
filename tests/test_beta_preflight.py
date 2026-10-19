"""Beta static checks report configuration risks without exposing secrets."""

from dataclasses import replace

from compass.beta_preflight import inspect_beta_configuration
from compass.config import Settings


def test_default_configuration_is_not_beta_ready():
    issues = inspect_beta_configuration(Settings())
    assert any("registration" in issue.lower() for issue in issues)
    assert any("database" in issue.lower() for issue in issues)
    assert any("recovery" in issue.lower() for issue in issues)


def test_checks_do_not_include_secrets():
    secret = "SENSITIVE_TOKEN_NEVER_LOG"
    settings = replace(
        Settings(), database_url="sqlitecloud://db.example/?secret=" + secret,
        openai_api_key=secret, zoho_client_secret=secret,
        allow_registration=False, session_timeout_minutes=30
    )
    issues = inspect_beta_configuration(settings)
    assert secret not in repr(issues)


def test_checks_are_only_static_hints():
    settings = replace(
        Settings(), database_url="sqlitecloud://beta.example",
        allow_registration=False, session_timeout_minutes=30,
        zoho_client_id="client", zoho_client_secret="secret",
        zoho_refresh_token="refresh", zoho_account_id="12345",
        mail_from="mail@example.com",
        app_base_url="https://beta.example",
    )
    # A clean static result is NOT a verification of isolation, TLS, IAM,
    # service permissions, retention or backup protection.
    assert inspect_beta_configuration(settings) == []
