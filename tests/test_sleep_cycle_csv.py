"""Sleep Cycle CSV import respects exact timestamps, duplicates, and privacy."""

import json
from datetime import date

import pytest

from compass.sleep_cycle_csv import (
    SleepCycleCSVService, parse_sleep_cycle_csv, MAX_CSV_BYTES,
)

HEADER = (
    "Start;End;Sleep Quality;Regularity;Awake (seconds);"
    "Time asleep (seconds);Time in bed (seconds);City;Notes"
)


def sample(lines):
    return ("\n".join([HEADER, *lines]) + "\n").encode()


ROW1 = "2026-10-13 23:10:00;2026-10-14 06:00:00;73%;70%;200;21000;24600;Somewhere;Private"
ROW2 = "2026-10-14 23:00:00;2026-10-15 07:00:00;80%;75%;120;25000;28800;Somewhere;Secret"


def test_parse_delimited_csv_extracts_only_safe_fields():
    parsed = parse_sleep_cycle_csv(sample([ROW1, ROW2, ROW1]))
    assert len(parsed) == 2
    assert parsed[0]["night"] == "2026-10-14"
    assert parsed[0]["sleep_quality_pct"] == 73
    assert parsed[0]["sleep_hours"] == round(21000 / 3600, 4)
    assert parsed[0]["session_start"] == "2026-10-13 23:10:00"
    assert "Notes" not in parsed[0] and "City" not in parsed[0]
    assert "Private" not in repr(parsed)


def test_csv_rejects_malformed_or_oversized_input():
    with pytest.raises(ValueError, match="Unrecognized"):
        parse_sleep_cycle_csv(b"Date,Quality\n2026-10-14,70\n")
    with pytest.raises(ValueError, match="8 MB"):
        parse_sleep_cycle_csv(b"z" * (MAX_CSV_BYTES + 1))
    with pytest.raises(ValueError, match="session"):
        parse_sleep_cycle_csv(sample([
            "2026-10-15 07:00:00;2026-10-14 23:00:00;80%;75%;120;25000;28800;here;none"
        ]))


def test_idempotent_import_preview_history_export_and_delete(users):
    owner, other = users
    parsed = parse_sleep_cycle_csv(sample([ROW1, ROW2, ROW1]))
    service = SleepCycleCSVService(owner.db, owner.user_id)
    strangers = SleepCycleCSVService(other.db, other.user_id)
    assert service.preview(parsed) == {"new": 2, "duplicates": 0}
    assert service.import_sessions(parsed) == {"imported": 2, "duplicates": 0}
    assert service.import_sessions(parsed) == {"imported": 0, "duplicates": 2}
    assert service.preview(parsed) == {"new": 0, "duplicates": 2}
    assert len(service.history(start=date(2026, 10, 15))) == 1
    assert strangers.history() == []
    exported = json.loads(owner.export())["sleep_cycle_sessions"]
    assert len(exported) == 2
    assert "Secret" not in repr(exported)
    assert json.loads(other.export())["sleep_cycle_sessions"] == []
    service.delete_all()
    assert service.history() == []
    assert service.import_sessions(parsed)["imported"] == 2
    owner.delete_account()
    with owner.db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM sleep_cycle_sessions WHERE user_id = ?",
            (owner.user_id,),
        ).fetchone()[0] == 0


def test_missing_sleep_duration_is_not_treated_as_zero():
    row = ROW1.replace(";21000;", ";0;")
    parsed = parse_sleep_cycle_csv(sample([row]))
    assert parsed[0]["sleep_hours"] is None


def test_overlong_and_nonfinite_quality_are_rejected():
    with pytest.raises(ValueError, match="Sleep Quality"):
        parse_sleep_cycle_csv(sample([ROW1.replace("73%", "NaN%")]))
