"""Verify account isolation, authentication, and scoped reflection context."""

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from compass.auth import AuthService, hash_password, verify_password
from compass.config import Settings
from compass.reflection import ReflectionService, weekly_context


def test_password_hashes_are_salted():
    """The same password receives distinct, verifiable hashes."""
    first = hash_password("password-example")
    second = hash_password("password-example")
    assert first != second
    assert verify_password("password-example", first)
    assert not verify_password("wrong-password", first)
    assert not verify_password("password-example", "invalid")


def test_login_and_lockout(db):
    """Wrong attempts lock the account; successful login returns its id."""
    auth = AuthService(db)
    user_id = auth.register("steve", "a-long-password-123")
    assert auth.login(" STEVE ", "a-long-password-123") == user_id
    for _ in range(5):
        assert auth.login("steve", "incorrect") is None
    assert auth.login("steve", "a-long-password-123") is None
    with db.connect() as conn:
        conn.execute(
            "UPDATE users SET locked_until = 1 WHERE id = ?", (user_id,)
        )
    assert auth.login("steve", "a-long-password-123") == user_id
    assert auth.login("unknown", "a-long-password-123") is None


def test_registration_validation(db):
    """Invalid credentials and duplicate usernames are rejected."""
    auth = AuthService(db)
    with pytest.raises(ValueError):
        auth.register("bad name", "a-long-password-123")
    with pytest.raises(ValueError):
        auth.register("valid_name", "short")
    auth.register("valid_name", "a-long-password-123")
    with pytest.raises(ValueError):
        auth.register("VALID_NAME", "a-long-password-123")


def test_checkin_upsert_and_validation(users):
    """One check-in per account/day; ratings must remain in range."""
    first, second = users
    first.save_checkin("2026-10-06", 3, 4, 8, 6, "First")
    first.save_checkin("2026-10-06", 7, 8, 2, 8, "Updated")
    second.save_checkin("2026-10-06", 5, 5, 5, 7, "Other user")
    assert len(first.rows("checkins")) == 1
    assert first.rows("checkins")[0]["mood"] == 7
    with pytest.raises(ValueError):
        first.save_checkin("2026-10-06", 11, 5, 5, 7, "")


def test_read_review_delete_are_owner_scoped(users):
    """Knowing another record id cannot bypass the ownership predicate."""
    first, second = users
    first.add_journal("Private", "My private entry", "work")
    first.add_exchange("Private question", "Private answer")
    first.add_insight("Tentative suggestion")
    first.save_checkin("2026-10-06", 5, 5, 5, 7, "Private")
    for table in ("journal", "messages", "insights", "checkins"):
        assert second.rows(table) == []
        record_id = first.rows(table)[0]["id"]
        second.delete(table, record_id)
        assert first.rows(table)
    record_id = first.rows("insights")[0]["id"]
    second.review_insight(record_id, "approved")
    assert first.rows("insights")[0]["status"] == "pending"
    first.review_insight(record_id, "approved")
    assert first.rows("insights")[0]["status"] == "approved"


def test_export_and_account_deletion(users):
    """Export excludes credentials and deletion preserves other accounts."""
    first, second = users
    for repo in users:
        repo.add_journal("Title", "Entry", "")
        repo.add_insight("A suggestion")
        repo.add_exchange("Hello", "How are you?")
        repo.save_checkin("2026-10-06", 5, 5, 5, 7, "")
    exported = json.loads(first.export())
    assert "users" not in exported
    assert len(exported["journal"]) == 1
    first.delete_account()
    for table in exported:
        assert first.rows(table) == []
        assert second.rows(table)


def test_weekly_window_uses_local_journal_dates(users):
    """UTC timestamps are assigned to the account's local calendar date."""
    first, _ = users
    for day in ("2026-09-29", "2026-09-30", "2026-10-06"):
        first.save_checkin(day, 5, 5, 5, 7, "")
    first.add_journal("Inside", "Keep me", "")
    first.add_journal("Outside", "Exclude me", "")
    with first.db.connect() as conn:
        conn.execute(
            "UPDATE journal SET created_at = ? WHERE title = ?",
            ("2026-10-07T01:00:00+00:00", "Inside"),
        )
        conn.execute(
            "UPDATE journal SET created_at = ? WHERE title = ?",
            ("2026-09-30T01:00:00+00:00", "Outside"),
        )
    context = weekly_context(first, date(2026, 10, 6))
    assert len(context["checkins"]) == 2
    assert [entry["title"] for entry in context["journal"]] == ["Inside"]


def test_ai_context_and_storage_flag():
    """Chat sends bounded messages and requests no stored API response."""
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output_text="What did you need in that moment?"
    )
    service = ReflectionService(Settings(), client)
    history = [
        {"role": "user", "content": f"Entry {index}", "private_id": "x"}
        for index in range(30)
    ]
    service.chat(history, "Hello")
    kwargs = client.responses.create.call_args.kwargs
    payload = json.loads(kwargs["input"])
    assert kwargs["store"] is False
    assert len(payload) == 13
    assert set(payload[0]) == {"role", "content"}
    assert payload[-1]["content"] == "Hello"


def test_table_allowlist(users):
    """Reject SQL table names outside the fixed allowlist."""
    with pytest.raises(ValueError):
        users[0].rows("users")
    with pytest.raises(ValueError):
        users[0].delete("journal; DROP TABLE users", "123")
