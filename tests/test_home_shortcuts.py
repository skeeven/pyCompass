"""Landing shortcuts use Compass's existing sidebar routing."""

from tests.test_app import open_app


def test_landing_shortcut_navigation(monkeypatch, users):
    first, _ = users
    app = open_app(monkeypatch, first.db)
    app.session_state["user_id"] = first.user_id
    app.run()
    shortcuts = (
        ("home_to_Compass_Health", "Compass Health"),
        ("home_to_Journal", "Journal"),
        ("home_to_Companion", "Companion"),
        ("home_to_Insights", "Insights"),
        ("home_to_Weekly_reflection", "Weekly reflection"),
    )
    for key, destination in shortcuts:
        app.button(key=key).click().run()
        assert not app.exception
        assert app.session_state["compass_navigation"] == destination
        app.radio(key="compass_navigation").set_value("Today").run()
        assert not app.exception
