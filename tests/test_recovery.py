"""Exercise recovery boundaries without sending real email."""

import io
import json
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import pytest

from compass.recovery import (
    REQUEST_MESSAGE,
    RecoveryService,
    ZohoMailer,
    digest,
)

PASSWORD = "a-long-password-123"
NEW = "my-new-password-456"
EMAIL = "alice@example.com"


class Immediate:
    """Run queued work synchronously for deterministic tests."""

    def submit(self, function, *args):
        return function(*args)


class Mailbox:
    """Capture emails or simulate an unavailable provider."""

    def __init__(self):
        self.messages = []
        self.fail = False

    def send(self, *message):
        if self.fail:
            raise RuntimeError("private provider response")
        self.messages.append(message)

    def token(self):
        link = self.messages[-1][2].splitlines()[3]
        return parse_qs(urlsplit(link).query)["account_token"][0]


@pytest.fixture
def recovery(users):
    """Enable delivery only after creating legacy accounts."""
    first, second = users
    db = first.db
    db.settings = replace(
        db.settings,
        zoho_client_id="test-client",
        zoho_client_secret="test-secret",
        zoho_refresh_token="test-refresh",
        zoho_account_id="123456",
        mail_from="compass@example.com",
        app_base_url="https://example.streamlit.app/",
    )
    mail = Mailbox()
    service = RecoveryService(db, mail, Immediate())
    return service, mail, first, second


def verified(service, mail, first):
    """Enroll an address through the full verification flow."""
    service.request_verification(first.user_id, EMAIL, PASSWORD)
    token = mail.token()
    service.consume(token, "verify")
    return token


def test_legacy_upgrade_and_new_account_gate(recovery):
    """Existing accounts keep access; configured new accounts need email."""
    service, _, first, _ = recovery
    assert service.auth.security(first.user_id)["required"] == 0
    new = service.auth.register("new_user", PASSWORD, "new@example.com")
    assert service.auth.security(new)["required"] == 1
    assert service.auth.security(new)["email"] is None
    with pytest.raises(ValueError, match="email"):
        service.auth.register("missing_email", PASSWORD)


def test_verification_requires_current_password_and_is_one_use(recovery):
    """Possessing a session alone cannot bind a new recovery address."""
    service, mail, first, second = recovery
    with pytest.raises(ValueError, match="password"):
        service.request_verification(first.user_id, EMAIL, "wrong-password")
    assert not mail.messages
    token = verified(service, mail, first)
    assert service.auth.security(first.user_id)["email"] == EMAIL
    assert service.auth.security(second.user_id)["email"] is None
    with pytest.raises(ValueError, match="invalid"):
        service.consume(token, "verify")


def test_reset_changes_password_preserves_data_and_revokes_sessions(recovery):
    """A reset affects only its owner and keeps wellness records intact."""
    service, mail, first, second = recovery
    first.add_journal("Keep", "Private entry", "")
    verified(service, mail, first)
    version = service.auth.security(first.user_id)["version"]
    assert service.request_reset(EMAIL) == REQUEST_MESSAGE
    token = mail.token()
    with first.db.connect() as conn:
        stored = conn.execute(
            "SELECT token_hash FROM account_tokens"
        ).fetchone()
        assert stored[0] == digest(token)
        assert stored[0] != token
    service.consume(token, "reset", NEW)
    assert service.auth.login("alice", PASSWORD) is None
    assert service.auth.login("alice", NEW) == first.user_id
    assert service.auth.login("bob", "another-password-456") == second.user_id
    assert first.rows("journal")[0]["body"] == "Private entry"
    assert service.auth.security(first.user_id)["version"] == version + 1
    with pytest.raises(ValueError, match="invalid"):
        service.consume(token, "reset", NEW)


def test_expiry_and_wrong_purpose_do_not_consume_valid_links(recovery):
    """An unrelated action cannot redeem the verification credential."""
    service, mail, first, _ = recovery
    service.request_verification(first.user_id, EMAIL, PASSWORD)
    token = mail.token()
    with pytest.raises(ValueError, match="invalid"):
        service.consume(token, "reset", NEW)
    with first.db.connect() as conn:
        conn.execute("UPDATE account_tokens SET expires_at = 0")
    with pytest.raises(ValueError, match="invalid"):
        service.consume(token, "verify")
    assert service.auth.security(first.user_id)["email"] is None


def test_generic_requests_and_persistent_rate_limit(recovery, monkeypatch):
    """Unknown addresses receive the same result; limits survive reruns."""
    service, mail, first, _ = recovery
    assert service.request_reset(EMAIL) == REQUEST_MESSAGE
    assert not mail.messages
    verified(service, mail, first)
    monkeypatch.setattr("compass.recovery.time.time", lambda: 2_000_000_000)
    baseline = len(mail.messages)
    other = RecoveryService(first.db, mail, Immediate())
    for i in range(6):
        monkeypatch.setattr(
            "compass.recovery.time.time", lambda i=i: 2_000_000_000 + i * 61
        )
        assert other.request_reset(EMAIL) == REQUEST_MESSAGE
    assert len(mail.messages) == baseline + 5
    assert other.request_reset("unknown@example.com") == REQUEST_MESSAGE
    assert len(mail.messages) == baseline + 5


def test_duplicate_verified_email_is_rejected(recovery):
    """One address cannot recover two different accounts."""
    service, mail, first, second = recovery
    verified(service, mail, first)
    service.request_verification(second.user_id, EMAIL, "another-password-456")
    with pytest.raises(ValueError, match="cannot be added"):
        service.consume(mail.token(), "verify")
    assert service.auth.security(second.user_id)["email"] is None


def test_failed_delivery_invalidates_link_and_hides_provider_details(recovery):
    """The database keeps no usable link after a provider rejection."""
    service, mail, first, _ = recovery
    mail.fail = True
    with pytest.raises(ValueError, match="Email delivery failed") as error:
        service.request_verification(first.user_id, EMAIL, PASSWORD)
    assert "private" not in str(error.value)
    with first.db.connect() as conn:
        assert conn.execute("SELECT * FROM account_tokens").fetchall() == []


def test_change_password_requires_owner_and_survives_notice_failure(recovery):
    """Notice failures cannot report an already committed change as failed."""
    service, mail, first, second = recovery
    verified(service, mail, first)
    with pytest.raises(ValueError, match="Current password"):
        service.change_password(first.user_id, "alice", "wrong", NEW)
    with pytest.raises(ValueError, match="Current password"):
        service.change_password(second.user_id, "alice", PASSWORD, NEW)

    class BrokenQueue:
        def submit(self, *args):
            raise RuntimeError("queue is shutting down")

    service.executor = BrokenQueue()
    service.change_password(first.user_id, "alice", PASSWORD, NEW)
    assert service.auth.login("alice", NEW) == first.user_id
    assert service.auth.security(first.user_id)["version"] == 2


def test_account_delete_removes_security_and_links(recovery):
    """Foreign keys allow deletion after security records are removed."""
    service, mail, first, _ = recovery
    verified(service, mail, first)
    service.request_reset(EMAIL)
    first.delete_account()
    with first.db.connect() as conn:
        assert not conn.execute(
            "SELECT * FROM account_security WHERE user_id = ?",
            (first.user_id,),
        ).fetchall()
        assert not conn.execute("SELECT * FROM account_tokens").fetchall()


def test_zoho_requests_refresh_then_send_plaintext(recovery, monkeypatch):
    """Use documented HTTPS OAuth and Mail endpoints, never SMTP."""
    service, _, first, _ = recovery
    calls = []

    def response(request, timeout):
        calls.append(request)
        assert timeout == 10
        data = (
            {"access_token": "test-access"}
            if len(calls) == 1
            else {"status": {"code": 200}}
        )
        return io.BytesIO(json.dumps(data).encode())

    monkeypatch.setattr("compass.recovery.urlopen", response)
    ZohoMailer(first.db.settings).send(EMAIL, "Subject", "Body")
    assert calls[0].full_url == "https://accounts.zoho.com/oauth/v2/token"
    assert parse_qs(calls[0].data.decode())["grant_type"] == ["refresh_token"]
    assert calls[1].full_url.endswith("/api/accounts/123456/messages")
    payload = json.loads(calls[1].data)
    assert payload["mailFormat"] == "plaintext"
    assert payload["toAddress"] == EMAIL
    assert (
        calls[1].get_header("Authorization") == "Zoho-oauthtoken test-access"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"app_base_url": "http://example.com"},
        {"app_base_url": "https://example.com/?secret=bad"},
        {"zoho_account_id": "compass"},
        {"zoho_domain": "invalid.example"},
    ],
)
def test_recovery_config_rejects_invalid_endpoints(recovery, change):
    """Only configured HTTPS app links and known Zoho regions are accepted."""
    _, _, first, _ = recovery
    with pytest.raises(ValueError):
        replace(first.db.settings, **change).validate()
