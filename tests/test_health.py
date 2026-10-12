"""Regression tests for private Compass Health onboarding."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from compass.db import Database
from compass.health import HealthService
from compass.repository import Repository


@pytest.fixture
def setup(tmp_path):
    db = Database(SimpleNamespace(database_url="", database_path=str(tmp_path / "health.db")))
    db.initialize()
    users = [str(uuid4()), str(uuid4())]
    with db.connect() as conn:
        for i, user in enumerate(users):
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (user, f"testuser{i}", "testhash", "2026-01-01"),
            )
    return db, users


def test_onboarding_is_private_and_resumable(setup):
    db, users = setup
    one, two = (HealthService(db, user) for user in users)
    one.save({"priorities": ["Sleep"], "uses_cpap": "Yes"}, 4)
    assert one.load()["answers"]["uses_cpap"] == "Yes"
    assert one.load()["step"] == 4
    assert two.load()["answers"] == {}
    two.save({"priorities": ["Movement"]}, 2)
    assert one.load()["answers"]["priorities"] == ["Sleep"]


def test_validation_and_completion(setup):
    db, users = setup
    service = HealthService(db, users[0])
    with pytest.raises(ValueError):
        service.save({"unknown_field": "secret"}, 0)
    with pytest.raises(ValueError):
        service.save({}, 99)
    service.save({"goals": "Walk after lunch"}, 6, completed=True)
    assert service.load()["completed_at"] is not None


def test_health_export_and_account_deletion(setup):
    db, users = setup
    HealthService(db, users[0]).save({"priorities": ["Sleep"]}, 1)
    exported = json.loads(Repository(db, users[0]).export())
    assert exported["health_profiles"][0]["user_id"] == users[0]
    assert json.loads(Repository(db, users[1]).export())["health_profiles"] == []
    Repository(db, users[0]).delete_account()
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM health_profiles WHERE user_id = ?",
            (users[0],),
        ).fetchone()[0] == 0
    assert HealthService(db, users[1]).load()["answers"] == {}
