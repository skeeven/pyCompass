"""Exercise the actual Streamlit UI with no cloud credentials."""

import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def open_app(monkeypatch, db):
    """Use only the test database and disable external providers."""
    monkeypatch.setenv("DATABASE_PATH", db.settings.database_path)
    monkeypatch.setenv("SQLITECLOUD_URL", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    monkeypatch.setenv("APP_TIMEZONE", "America/Denver")
    monkeypatch.setenv("SESSION_TIMEOUT_MINUTES", "30")
    return AppTest.from_file(str(APP), default_timeout=20)


def test_login_screen(monkeypatch, db):
    """The app starts without a secrets file or pre-created account."""
    app = open_app(monkeypatch, db).run()
    assert not app.exception
    assert app.title[0].value == "🧭 Compass"
    assert len(app.tabs) == 2


def test_registration_and_login_forms(monkeypatch, db):
    """Create and authenticate an account through the actual UI forms."""
    app = open_app(monkeypatch, db).run()
    app.text_input[2].set_value("steve")
    app.text_input[3].set_value("a-long-password-123")
    app.text_input[4].set_value("a-long-password-123")
    app.button(key="FormSubmitter:register-Create account").click().run()
    assert not app.exception
    assert app.success
    app.text_input(key="login_username").set_value("steve")
    app.text_input(key="login_password").set_value("a-long-password-123")
    app.button(key="FormSubmitter:login-Sign in").click().run()
    assert not app.exception
    assert app.title[0].value == "How are you arriving today?"
    assert "last_activity" in app.session_state


def test_expired_session_returns_to_login(monkeypatch, users):
    """Expired state is cleared before any protected screen renders."""
    first, _ = users
    app = open_app(monkeypatch, first.db)
    app.session_state["user_id"] = first.user_id
    app.session_state["last_activity"] = time.time() - 2000
    app.session_state["draft"] = "Private"
    app.run()
    assert not app.exception
    assert "user_id" not in app.session_state
    assert "draft" not in app.session_state
    assert app.info[0].value == "Your session expired. Please sign in again."


def test_checkin_journal_navigation_and_logout(monkeypatch, users):
    """Save records through forms and ensure logout clears the session."""
    first, _ = users
    app = open_app(monkeypatch, first.db)
    app.session_state["user_id"] = first.user_id
    app.run()
    assert not app.exception
    app.slider[0].set_value(8)
    app.button(key="FormSubmitter:checkin-Save today's check-in").click().run()
    assert not app.exception
    assert first.rows("checkins")[0]["mood"] == 8
    app.radio[0].set_value("Journal").run()
    app.text_input[0].set_value("Today")
    app.text_area[0].set_value("I enjoyed a short walk.")
    app.button(key="FormSubmitter:journal-Save entry").click().run()
    assert not app.exception
    assert first.rows("journal")[0]["body"] == "I enjoyed a short walk."
    for page in (
        "Insights",
        "Weekly reflection",
        "Companion",
        "Privacy & data",
    ):
        app.radio[0].set_value(page).run()
        assert not app.exception
    next(
        button for button in app.button if button.label == "Sign out"
    ).click().run()
    assert not app.exception
    assert "user_id" not in app.session_state


def test_optional_checkin_fields_survive_reload(monkeypatch, users):
    """Optional form inputs return after restarting the app session."""
    first, _ = users
    app = open_app(monkeypatch, first.db)
    app.session_state["user_id"] = first.user_id
    app.run()
    app.multiselect[0].set_value(["Calm", "Hopeful"])
    app.multiselect[1].set_value(["Personal time"])
    app.text_area[1].set_value("A little rest")
    app.checkbox[0].check()
    app.button(key="FormSubmitter:checkin-Save today's check-in").click().run()
    assert not app.exception
    reloaded = open_app(monkeypatch, first.db)
    reloaded.session_state["user_id"] = first.user_id
    reloaded.run()
    assert not reloaded.exception
    assert reloaded.multiselect[0].value == ["Calm", "Hopeful"]
    assert reloaded.text_area[1].value == "A little rest"
    assert reloaded.checkbox[0].value


def test_guided_journal_validation_edit_and_delete(monkeypatch, users):
    """A draft survives rejection; saved entries can be edited and removed."""
    first, _ = users
    app = open_app(monkeypatch, first.db)
    app.session_state["user_id"] = first.user_id
    app.run()
    app.radio[0].set_value("Journal").run()
    app.selectbox[0].set_value("Understand a reaction").run()
    app.text_input(key="journal_title").set_value("My reaction")
    app.button(key="FormSubmitter:journal-Save entry").click().run()
    assert app.error
    assert app.text_input(key="journal_title").value == "My reaction"
    app.text_area[0].set_value("A busy afternoon")
    app.button(key="FormSubmitter:journal-Save entry").click().run()
    assert not app.exception
    row = first.rows("journal")[0]
    assert (
        row["body"] == "What happened? Describe what you observed.\n"
        "A busy afternoon"
    )
    app.text_area[-1].set_value("I need some rest.")
    app.button(
        key=f"FormSubmitter:edit_journal_{row['id']}-Save changes"
    ).click().run()
    assert not app.exception
    assert first.rows("journal")[0]["body"] == "I need some rest."
    assert app.button(key=f"delete_{row['id']}").disabled
    app.checkbox(key=f"confirm_{row['id']}").check().run()
    app.button(key=f"delete_{row['id']}").click().run()
    assert not app.exception
    assert not first.rows("journal")


def test_companion_consent_failure_and_retry(monkeypatch, users):
    """Consent gates sending; a failed save reuses the received reply."""
    from unittest.mock import Mock

    from compass.reflection import ReflectionService
    from compass.repository import Repository

    first, second = users
    second.add_exchange("Someone else's question", "Private reply")
    app = open_app(monkeypatch, first.db)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-a-real-credential")
    chat = Mock(side_effect=[RuntimeError("provider unavailable"), "A reply"])
    monkeypatch.setattr(ReflectionService, "chat", chat)
    app.session_state["user_id"] = first.user_id
    app.run()
    app.radio[0].set_value("Companion").run()
    app.text_area(key="companion_draft").set_value("Help me reflect").run()
    assert app.button(key="companion_send").disabled
    assert not chat.called
    app.checkbox(key="chat_consent").check().run()
    app.button(key="companion_send").click().run()
    assert app.error
    assert app.text_area(key="companion_draft").value == "Help me reflect"
    assert not first.rows("messages")
    original = Repository.add_exchange
    save = Mock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr(Repository, "add_exchange", save)
    app.button(key="companion_send").click().run()
    assert app.error
    assert chat.call_count == 2
    assert chat.call_args.args[0] == []
    monkeypatch.setattr(Repository, "add_exchange", original)
    app.checkbox(key="chat_consent").uncheck().run()
    assert app.button(key="companion_send").disabled
    app.checkbox(key="chat_consent").check().run()
    app.button(key="companion_send").click().run()
    assert not app.exception
    assert chat.call_count == 2
    assert len(first.rows("messages")) == 2
    assert app.text_area(key="companion_draft").value == ""
    assert len(second.rows("messages")) == 2
