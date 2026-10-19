"""Beta hardening: malformed credentials and non-finite report metrics."""

from datetime import date

import pytest

from compass.auth import ITERATIONS, hash_password, verify_password
from compass.health_reports import save_report
from compass.health_history import list_saved_reports


def test_verifier_rejects_malformed_work_factors_without_derivation(monkeypatch):
    expected = hash_password("long-test-password-123")
    assert verify_password("long-test-password-123", expected)
    original = expected.split("$")
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Malformed hash must never invoke PBKDF2.")

    monkeypatch.setattr("compass.auth.hashlib.pbkdf2_hmac", forbidden)
    for invalid in (
        "pbkdf2_sha256$9999999999999999999999999999999999$" + original[2] + "$" + original[3],
        "pbkdf2_sha256$-1$" + original[2] + "$" + original[3],
        "pbkdf2_sha256$" + str(ITERATIONS) + "$wrong$" + original[3],
        "pbkdf2_sha256$" + str(ITERATIONS) + "$" + original[2] + "$nothex",
        "garbage",
    ):
        assert verify_password("long-test-password-123", invalid) is False
    assert calls == []


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True])
def test_report_metrics_reject_nonfinite_and_boolean_before_storage(users, bad):
    owner, _ = users
    with pytest.raises(ValueError):
        save_report(
            owner.db, owner.user_id, "private.pdf", "ResMed CPAP",
            date(2026, 10, 1), date(2026, 10, 7),
            {"ahi": bad},
        )
    assert list_saved_reports(owner.db, owner.user_id) == []


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_sleep_quality_rejects_nonfinite_before_storage(users, bad):
    owner, _ = users
    with pytest.raises(ValueError, match="percentage"):
        save_report(
            owner.db, owner.user_id, "quality.pdf", "Sleep Cycle",
            date(2026, 10, 1), date(2026, 10, 7),
            {"sleep_quality_pct": bad},
        )
    assert list_saved_reports(owner.db, owner.user_id) == []
