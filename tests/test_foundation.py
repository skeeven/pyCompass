"""Foundation configuration, schema compatibility and session tests."""

import pytest

from compass.config import Settings
from compass.session import check_session, start_session


def test_config_precedence_and_false_registration(monkeypatch):
    """Explicit environment values override TOML, including blank secrets."""
    monkeypatch.setenv("SQLITECLOUD_URL", "")
    monkeypatch.setenv("ALLOW_REGISTRATION", "false")
    settings = Settings.load({"SQLITECLOUD_URL": "sqlitecloud://example"})
    assert not settings.database_url
    assert not settings.allow_registration


@pytest.mark.parametrize(
    "values",
    [
        {"APP_TIMEZONE": "Not/A_Timezone"},
        {"SESSION_TIMEOUT_MINUTES": "zero"},
        {"SESSION_TIMEOUT_MINUTES": "0"},
        {"SESSION_TIMEOUT_MINUTES": "1441"},
        {"ALLOW_REGISTRATION": "maybe"},
        {"DATABASE_PATH": "", "SQLITECLOUD_URL": ""},
        {"SQLITECLOUD_URL": "https://secret-credential"},
    ],
)
def test_bad_config_is_rejected(monkeypatch, values):
    """Fail before connecting and never echo configured secret values."""
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError) as error:
        Settings.load()
    assert "secret-credential" not in str(error.value)


def test_initialization_preserves_legacy_records(users):
    """Adopt the earlier unversioned schema without deleting account data."""
    first, _ = users
    first.add_journal("Keep", "My existing entry", "")
    with first.db.connect() as conn:
        conn.execute("DROP TABLE schema_migrations")
    first.db.initialize()
    first.db.initialize()
    assert first.rows("journal")[0]["body"] == "My existing entry"
    with first.db.connect() as conn:
        assert conn.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall() == [(1,), (2,)]


def test_newer_schema_requires_newer_app(db):
    """An older app refuses a newer database version."""
    with db.connect() as conn:
        conn.execute("INSERT INTO schema_migrations (version) VALUES (3)")
    with pytest.raises(ValueError, match="newer version"):
        db.initialize()


def test_session_expiry_clears_sensitive_state():
    """No previous user's drafts or consent survive an expired session."""
    state = {
        "user_id": "alice",
        "last_activity": 100,
        "journal_draft": "Private",
        "chat_consent": True,
    }
    assert check_session(state, 30, now=1899)
    assert not check_session(state, 30, now=3700)
    assert state == {}


def test_login_replaces_previous_state():
    """A fresh login clears stale values and starts an activity clock."""
    state = {"user_id": "alice", "draft": "Private"}
    start_session(state, "bob")
    assert state["user_id"] == "bob"
    assert "draft" not in state
    assert "last_activity" in state


def test_version_one_upgrade_keeps_checkin(users):
    """Upgrade an original check-in without losing its ratings or note."""
    first, _ = users
    first.save_checkin("2026-10-06", 7, 6, 4, 8, "Keep this")
    with first.db.connect() as conn:
        for column in ("emotions", "contexts", "needs", "activity_done"):
            conn.execute(f"ALTER TABLE checkins DROP COLUMN {column}")
        conn.execute("DELETE FROM schema_migrations WHERE version = 2")
    first.db.initialize()
    first.db.initialize()
    row = first.rows("checkins")[0]
    assert row["mood"] == 7
    assert row["note"] == "Keep this"
    assert row["emotions"] == "[]"
    assert row["needs"] == ""
    assert row["activity_done"] == 0


def test_checkin_context_upsert_and_export(users):
    """Optional fields persist, update and stay within the owner's data."""
    import json

    first, second = users
    first.save_checkin(
        "2026-10-06",
        7,
        6,
        4,
        8,
        "Note",
        emotions=["Calm"],
        contexts=["Work"],
        needs="Rest",
        activity_done=True,
    )
    row = json.loads(first.export())["checkins"][0]
    assert json.loads(row["emotions"]) == ["Calm"]
    assert row["activity_done"] == 1
    assert second.rows("checkins") == []
    first.save_checkin("2026-10-06", 7, 6, 4, 8, "Note")
    assert first.rows("checkins")[0]["activity_done"] == 0
    assert first.rows("checkins")[0]["needs"] == ""
    with pytest.raises(ValueError):
        first.save_checkin(
            "2026-10-06", 7, 6, 4, 8, "", emotions=["Not an emotion"]
        )
