"""Read-only Sleep Cycle context for daily check-ins.

Imported sleep is never copied to a manual daily log or modified here.
A sleep session is assigned to the date it ended (the waking date).
"""

from compass.sleep_cycle_csv import SleepCycleCSVService


def sleep_context_for_day(db, user_id, selected_day):
    sessions = SleepCycleCSVService(db, user_id).history(
        start=selected_day, end=selected_day
    )
    measured = [s for s in sessions if s["sleep_hours"] is not None]
    qualified = [s for s in sessions if s["sleep_quality_pct"] is not None]
    # A day can contain more than one session. Use total recorded sleep
    # (not an arbitrary last session) and session-weighted quality only if
    # every sleep session has both duration and quality.
    duration = sum(s["sleep_hours"] for s in measured) if measured else None
    if (sessions and len(qualified) == len(sessions)
            and len(measured) == len(sessions) and duration):
        quality = sum(
            s["sleep_quality_pct"] * s["sleep_hours"] for s in sessions
        ) / duration
    elif len(sessions) == 1 and qualified:
        quality = qualified[0]["sleep_quality_pct"]
    else:
        quality = None
    return {
        "session_count": len(sessions),
        "sleep_hours": duration,
        "sleep_quality_pct": quality,
        "source": "Sleep Cycle" if sessions else None,
    }


def manual_checkin_patch(existing, updates):
    """Preserve other manually entered values; never inject imported data."""
    return {**existing, **updates}
