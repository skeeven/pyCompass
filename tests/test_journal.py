"""Verify journal editing, ownership and local calendar search."""

from datetime import date

import pytest

from compass.journal import filter_entries, normalize_tags


def test_owned_edit_preserves_timestamp_and_isolation(users):
    """Edits cannot touch another account's entries or reset their date."""
    first, second = users
    first.add_journal("Original", "A walk", " rest, Rest, outdoors ")
    original = first.rows("journal")[0]
    assert original["tags"] == "rest, outdoors"
    with pytest.raises(ValueError, match="unavailable"):
        second.update_journal(original["id"], "Changed", "Private", "")
    with pytest.raises(ValueError, match="Write something"):
        first.update_journal(original["id"], "Changed", "  ", "")
    assert first.rows("journal")[0] == original
    first.update_journal(original["id"], " Updated ", " A good walk ", "Joy")
    updated = first.rows("journal")[0]
    assert updated["created_at"] == original["created_at"]
    assert updated["title"] == "Updated"
    assert updated["body"] == "A good walk"
    assert not second.rows("journal")


def test_filter_respects_local_date_and_whole_tags():
    """UTC midnight belongs to the previous Denver day in history."""
    entries = [
        dict(
            id="1",
            title="Walk",
            body="Sunshine",
            tags="rest, outside",
            created_at="2026-10-01T01:00:00+00:00",
        ),
        dict(
            id="2",
            title="REST",
            body="Home",
            tags="restful",
            created_at="2026-10-01T17:00:00+00:00",
        ),
        dict(
            id="3",
            title="Walk",
            body="SUNSHINE",
            tags="Rest, outside",
            created_at="2026-10-06T17:00:00+00:00",
        ),
    ]
    results = filter_entries(
        entries,
        "sunshine",
        ["rest", "outside"],
        7,
        date(2026, 10, 6),
        "America/Denver",
    )
    assert [row["id"] for row in results] == ["3", "1"]
    assert (
        len(
            filter_entries(
                entries, "", ["rest"], 1, date(2026, 10, 1), "America/Denver"
            )
        )
        == 0
    )
    assert normalize_tags(" Rest, , REST, joy ") == "Rest, joy"
