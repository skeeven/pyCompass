"""Verify cloud failure boundaries and destructive-action confirmations."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_app import open_app

from compass.config import Settings
from compass.db import Database


def test_cloud_failure_never_creates_local_database(monkeypatch, tmp_path):
    """A failed configured cloud connection cannot silently switch storage."""
    path = tmp_path / "should_not_exist.db"
    connect = Mock(side_effect=RuntimeError("Unavailable"))
    monkeypatch.setitem(
        sys.modules, "sqlitecloud", SimpleNamespace(connect=connect)
    )
    db = Database(
        Settings(database_url="sqlitecloud://example", database_path=str(path))
    )
    with pytest.raises(RuntimeError, match="Unavailable"):
        with db.connect():
            pytest.fail("Failed cloud connection must not yield a connection.")
    assert not path.exists()
    connect.assert_called_once_with("sqlitecloud://example")


@pytest.mark.parametrize("failure", [None, "write", "commit"])
def test_cloud_transactions_close_and_rollback(monkeypatch, failure):
    """Cloud adapter commits success and closes after write/commit failures."""
    conn = Mock()
    if failure == "commit":

        def execute(statement):
            if statement == "COMMIT":
                raise RuntimeError("Commit failed")

        conn.execute.side_effect = execute
    monkeypatch.setitem(
        sys.modules,
        "sqlitecloud",
        SimpleNamespace(connect=Mock(return_value=conn)),
    )
    db = Database(Settings(database_url="sqlitecloud://example"))

    def write():
        with db.connect() as connection:
            assert connection is conn
            conn.execute.assert_called_once_with("BEGIN")
            if failure == "write":
                raise RuntimeError("Write failed")

    if failure is None:
        write()
        assert [call.args[0] for call in conn.execute.call_args_list] == [
            "BEGIN",
            "COMMIT",
        ]
    else:
        with pytest.raises(RuntimeError):
            write()
        assert conn.execute.call_args.args == ("ROLLBACK",)
    conn.close.assert_called_once()


def test_weekly_deletion_requires_confirmation(monkeypatch, users):
    """An accidental delete tap cannot remove a weekly reflection."""
    first, second = users
    first.add_insight("Saved weekly reflection", "weekly")
    second.add_insight("Another account's reflection", "weekly")
    row = first.rows("insights")[0]
    app = open_app(monkeypatch, first.db)
    app.session_state["user_id"] = first.user_id
    app.run()
    app.radio[0].set_value("Weekly reflection").run()
    assert not app.exception
    assert app.button(key=f"week_{row['id']}").disabled
    assert len(first.rows("insights")) == 1
    app.checkbox(key=f"confirm_week_{row['id']}").check().run()
    app.button(key=f"week_{row['id']}").click().run()
    assert not app.exception
    assert first.rows("insights") == []
    assert len(second.rows("insights")) == 1


def test_cloud_autocommit_is_wrapped_in_explicit_transaction(
    monkeypatch, tmp_path
):
    """Emulate the real cloud driver's default autocommit with SQLite."""
    import sqlite3

    path = str(tmp_path / "cloud_emulation.db")
    monkeypatch.setitem(
        sys.modules,
        "sqlitecloud",
        SimpleNamespace(
            connect=lambda _: sqlite3.connect(path, isolation_level=None)
        ),
    )
    db = Database(Settings(database_url="sqlitecloud://example"))
    with db.connect() as conn:
        conn.execute("CREATE TABLE example (value TEXT)")
    with pytest.raises(RuntimeError):
        with db.connect() as conn:
            conn.execute("INSERT INTO example VALUES ('must roll back')")
            raise RuntimeError("fail after first write")
    with db.connect() as conn:
        assert conn.execute("SELECT * FROM example").fetchall() == []
