"""Landing shortcuts use Compass's existing sidebar routing."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def open_app(monkeypatch, db):
    monkeypatch.setenv("DATABASE_PATH", db.settings.database_path)
    monkeypatch.setenv("SQLITECLOUD_URL", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    monkeypatch.setenv("APP_TIMEZONE", "America/Denver")
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=20,
    )
    app.secrets.update({
        "DATABASE_PATH": db.settings.database_path,
        "SQLITECLOUD_URL": "",
        "OPENAI_API_KEY": "",
        "ALLOW_REGISTRATION": "true",
        "APP_TIMEZONE": "America/Denver",
        "ZOHO_CLIENT_ID": "",
        "ZOHO_CLIENT_SECRET": "",
        "ZOHO_REFRESH_TOKEN": "",
        "ZOHO_ACCOUNT_ID": "",
        "MAIL_FROM": "",
        "APP_BASE_URL": "",
    })
    return app


def test_navigation_buttons_on_every_page(monkeypatch, users):
    """Every main page offers shared navigation, including a way Home."""
    first, _ = users
    app = open_app(monkeypatch, first.db)
    app.session_state["user_id"] = first.user_id
    app.run()
    shortcuts = (
        ("home_to_Health", "Health"),
        ("home_to_Journal", "Journal"),
        ("home_to_Companion", "Companion"),
        ("home_to_Insights", "Insights"),
        ("home_to_Weekly_reflection", "Weekly reflection"),
    )
    for key, destination in shortcuts:
        app.button(key=key).click().run()
        assert not app.exception
        assert app.session_state["compass_navigation"] == destination
        assert app.button(key="home_to_Today")
        app.button(key="home_to_Today").click().run()
        assert not app.exception
        assert app.session_state["compass_navigation"] == "Today"


def test_sidebar_uses_short_health_label(monkeypatch, users):
    first, _ = users
    app = open_app(monkeypatch, first.db)
    app.session_state["user_id"] = first.user_id
    app.run()
    choices = app.radio(key="compass_navigation").options
    assert "Health" in choices
    assert "Compass Health" not in choices
