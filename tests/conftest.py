"""Isolated database fixtures."""

import pytest

from compass.auth import AuthService
from compass.config import Settings
from compass.db import Database
from compass.repository import Repository


@pytest.fixture
def db(tmp_path):
    """Initialize an empty database for each test."""
    database = Database(Settings(database_path=str(tmp_path / "test.db")))
    database.initialize()
    return database


@pytest.fixture
def users(db):
    """Create two independent account repositories."""
    auth = AuthService(db)
    first = auth.register("alice", "a-long-password-123")
    second = auth.register("bob", "another-password-456")
    return Repository(db, first), Repository(db, second)
