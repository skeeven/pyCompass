"""Reproducible, source-aware weekly wellness summaries.

No AI or external services are called. No health values are inferred on
missing dates, and overlapping ResMed periods stay separate context.
"""

from datetime import timedelta
from statistics import mean

from compass.health_goals import GOAL_OPTIONS, enriched_goal_progress
from compass.unified_sleep import unified_sleep_snapshot

MEASURES = {
    "mood": ("Mood", "/10"),
    "sleep_hours": ("Sleep duration", "hours"),
    "sleep_quality_pct": ("Sleep quality", "%"),
    "energy": ("Energy", "/10"),
    "stress": ("Stress", "/10"),
    "movement_minutes": ("Movement", "minutes"),
    "downtime_minutes": ("Personal time", "minutes"),
    "weight_lb": ("Weight", "lb"),
}


def _summarize(rows, manual, start, end):
    start_text, end_text = start.isoformat(), end.isoformat()
    nights = [row for row in rows
              if start_text <= row["night"] <= end_text]
    logged = [row for row in manual
              if start_text <= row["day"] <= end_text]
    measurements = {}
    for key in MEASURES:
        source = nights if key in {"sleep_hours", "sleep_quality_pct"} else logged
        values = [row[key] for row in source if row.get(key) is not None]
        if values:
            measurements[key] = {"average": mean(values), "count": len(values)}
    return {
        "recorded_sleep_nights": sum(r.get("sleep_hours") is not None for r in nights),
        "checkin_days": len(logged),
        "measurements": measurements,
    }


def personalized_weekly_summary(manual, sessions, reports, goals, start, end):
    """Summarize the selected inclusive Mon-Sun week (or its elapsed portion)."""
    if end < start or (end - start).days > 6:
        raise ValueError("Choose a valid weekly review interval.")
    first_previous = start - timedelta(days=7)
    last_previous = start - timedelta(days=1)
    unified = unified_sleep_snapshot(
        manual, sessions, reports, end
    )
    current = _summarize(unified["nights"], manual, start, end)
    previous = _summarize(
        unified["nights"], manual, first_previous, last_previous
    )
    change = {}
    for key in current["measurements"].keys() & previous["measurements"].keys():
        new = current["measurements"][key]
        old = previous["measurements"][key]
        if new["count"] >= 2 and old["count"] >= 2:
            change[key] = {
                "difference": new["average"] - old["average"],
                "current_count": new["count"],
                "previous_count": old["count"],
            }
    # Goals use only this week's elapsed dates. enriched_goal_progress uses
    # a seven-day lookback ending on end, so exclude prior-week days first.
    current_logs = [
        row for row in manual if start.isoformat() <= row["day"] <= end.isoformat()
    ]
    current_nights = [
        row for row in unified["nights"]
        if start.isoformat() <= row["night"] <= end.isoformat()
    ]
    goal_results = enriched_goal_progress(
        current_logs, current_nights, goals, end, days=7
    ) if goals else {}
    overlapping = [
        {
            "source": report["report_type"],
            "period_start": report["period_start"],
            "period_end": report["period_end"],
        }
        for report in reports
        if report["period_start"] <= end.isoformat()
        and report["period_end"] >= start.isoformat()
        and report["status"] == "verified"
    ]
    return {
        "start": start, "end": end,
        "current": current, "previous": previous,
        "changes": change, "goals": goal_results,
        "report_context": overlapping,
        "goal_labels": {key: GOAL_OPTIONS[key][0] for key in goal_results},
    }
