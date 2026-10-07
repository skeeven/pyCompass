"""Verify durable evidence, review transitions, and observation privacy."""

from datetime import datetime
from zoneinfo import ZoneInfo

from test_app import open_app

from compass.observations import PREFIX, read_observation, save_observation
from compass.reflection import ReflectionService, weekly_context


def test_evidence_survives_source_edits_and_is_owner_scoped(users):
    """A saved suggestion keeps its input, not later replacements."""
    first, second = users
    day = datetime.now(ZoneInfo("America/Denver")).date()
    first.save_checkin(str(day), 7, 6, 3, 8, "A short walk helped.")
    second.save_checkin(str(day), 1, 1, 9, 2, "Other account's note")
    first.add_insight(
        save_observation(
            "Walking may have helped.", weekly_context(first, day)
        )
    )
    record = first.rows("insights")[0]
    first.save_checkin(str(day), 4, 4, 5, 6, "A later edit")
    second.review_insight(record["id"], "dismissed")
    second.delete("insights", record["id"])
    assert second.rows("insights") == []
    stored = first.rows("insights")[0]
    assert stored["status"] == "pending"
    text, evidence = read_observation(stored["content"])
    assert text == "Walking may have helped."
    assert evidence["checkins"][0]["note"] == "A short walk helped."
    assert len(evidence["checkins"]) == 1
    for status in ("approved", "dismissed", "pending"):
        first.review_insight(record["id"], status)
        assert first.rows("insights")[0]["status"] == status


def test_legacy_and_malformed_observations_remain_readable():
    """Plain-text history is retained; broken snapshots do not crash the UI."""
    for content in (
        "An earlier suggestion",
        PREFIX + "{broken",
        PREFIX + "{}",
    ):
        assert read_observation(content) == (content, None)


def test_generation_review_filters_and_confirmed_deletion(monkeypatch, users):
    """Generate saved evidence and exercise review through the screen."""
    first, second = users
    day = datetime.now(ZoneInfo("America/Denver")).date()
    first.save_checkin(str(day), 7, 6, 3, 8, "A short walk helped.")
    second.add_insight("Do not show another account's observation")
    app = open_app(monkeypatch, first.db)
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    sent = []

    def review(_self, context, observation=False):
        assert observation
        sent.append(context)
        return f"On {day}, you noted that a short walk helped. Does that fit?"

    monkeypatch.setattr(ReflectionService, "review", review)
    app.session_state["user_id"] = first.user_id
    app.run()
    app.radio[0].set_value("Insights").run()
    generate = next(
        b for b in app.button if b.label == "Suggest an observation"
    )
    assert generate.disabled
    app.checkbox(key="insight_consent").check().run()
    next(b for b in app.button if b.label == "Suggest an observation").click()
    app.run()
    assert not app.exception
    row = first.rows("insights")[0]
    text, evidence = read_observation(row["content"])
    assert evidence == sent[0]
    assert "short walk" in text
    assert not any("another account" in m.value for m in app.markdown)
    assert any(
        e.label == "Context used for this observation" for e in app.expander
    )
    app.button(key=f"approve_{row['id']}").click().run()
    assert first.rows("insights")[0]["status"] == "approved"
    app.button(key=f"dismiss_{row['id']}").click().run()
    app.selectbox(key="observation_status").set_value("Pending").run()
    assert not any(b.label == "Review again" for b in app.button)
    app.selectbox(key="observation_status").set_value("Dismissed").run()
    app.button(key=f"reset_{row['id']}").click().run()
    assert first.rows("insights")[0]["status"] == "pending"
    app.selectbox(key="observation_status").set_value("All").run()
    assert app.button(key=f"delete_observation_{row['id']}").disabled
    app.checkbox(key=f"confirm_observation_{row['id']}").check().run()
    app.button(key=f"delete_observation_{row['id']}").click().run()
    assert not app.exception
    assert first.rows("insights") == []
    assert len(second.rows("insights")) == 1
