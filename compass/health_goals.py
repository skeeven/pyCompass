"""Explicit, user-configured daily goal targets and honest progress counts."""

import math
from datetime import timedelta

GOAL_OPTIONS = {
    "sleep_hours": ("Sleep at least", "hours", 0.5, 16.0),
    "cpap_hours": ("Use CPAP at least", "hours", 0.5, 16.0),
    "movement_minutes": ("Move at least", "minutes", 1.0, 600.0),
    "downtime_minutes": ("Personal time at least", "minutes", 1.0, 600.0),
    "energy": ("Energy at least", "/10", 1.0, 10.0),
    "stress": ("Stress at most", "/10", 1.0, 10.0),
    "weight_lb": ("Weight goal", "lb", 50.0, 1000.0),
    "nutrition_on_track": ("Nutrition plan followed", "days", 1.0, 1.0),
}


def validate_goals(goals):
    """Return a small set of explicit daily thresholds; no medical defaults."""
    if not isinstance(goals, dict) or len(goals) > len(GOAL_OPTIONS):
        raise ValueError("Invalid goals.")
    result = {}
    for key, target in goals.items():
        if key not in GOAL_OPTIONS:
            raise ValueError("Unknown goal.")
        low, high = GOAL_OPTIONS[key][2:]
        if (isinstance(target, bool) or not isinstance(target, (int, float))
                or not math.isfinite(target) or not low <= target <= high):
            raise ValueError("Invalid goal target.")
        result[key] = float(target)
    return result


def goal_progress(rows, goals, end_day):
    """Count met days only among observed days with the relevant value."""
    targets = validate_goals(goals)
    start = end_day - timedelta(days=6)
    current = [row for row in rows
               if start.isoformat() <= row["day"] <= end_day.isoformat()]
    output = {}
    for key, target in targets.items():
        observed = [row[key] for row in current if key in row]
        output[key] = {
            "target": target,
            "met": sum((value <= target if key in {"stress", "weight_lb"}
                         else value >= target) for value in observed),
            "recorded": len(observed),
        }
    return output


def compare_weeks(rows, end_day):
    """Compare two adjacent seven-day windows, never filling missing values."""
    from compass.health_daily import weekly_summary

    current = weekly_summary(rows, end_day)
    previous = weekly_summary(rows, end_day - timedelta(days=7))
    comparisons = {}
    for key in current["averages"].keys() & previous["averages"].keys():
        now_values = [
            r for r in rows if current["start"].isoformat()
            <= r["day"] <= current["end"].isoformat() and key in r
        ]
        old_values = [
            r for r in rows if previous["start"].isoformat()
            <= r["day"] <= previous["end"].isoformat() and key in r
        ]
        comparisons[key] = {
            "current": current["averages"][key],
            "previous": previous["averages"][key],
            "change": current["averages"][key] - previous["averages"][key],
            "current_count": len(now_values),
            "previous_count": len(old_values),
        }
    return {"current": current, "previous": previous,
            "comparisons": comparisons}


def enriched_goal_progress(manual_rows, sleep_nights, goals, today, days=7):
    """Report a single source-aware sleep measure per night for goal progress.

    Weight is a trajectory toward a chosen value, not a daily success streak.
    Nutrition uses explicitly logged adherence, never inferred from free text.
    """
    if days not in (7, 30):
        raise ValueError("Unsupported progress window.")
    targets = validate_goals(goals)
    start = (today - timedelta(days=days - 1)).isoformat()
    finish = today.isoformat()
    by_day = {
        row["day"]: dict(row) for row in manual_rows
        if start <= row["day"] <= finish
    }
    for night in sleep_nights:
        day = night["night"]
        if not start <= day <= finish:
            continue
        entry = by_day.setdefault(day, {"day": day})
        if night.get("sleep_source") == "Sleep Cycle" and night.get("sleep_hours") is not None:
            entry["sleep_hours"] = night["sleep_hours"]
    result = {}
    for key, target in targets.items():
        observations = [
            (day, row[key]) for day, row in sorted(by_day.items())
            if key in row and row[key] is not None
        ]
        if key == "weight_lb":
            first = observations[0][1] if observations else None
            latest = observations[-1][1] if observations else None
            result[key] = {
                "target": target, "recorded": len(observations),
                "first": first, "latest": latest,
                "change": (latest - first) if len(observations) >= 2 else None,
                "remaining": max(0.0, latest - target) if latest is not None else None,
                "reached": latest is not None and latest <= target,
            }
        else:
            observed = [value for _, value in observations]
            result[key] = {
                "target": target,
                "met": sum(value <= target if key == "stress"
                           else value >= target for value in observed),
                "recorded": len(observed),
                "mean": sum(observed) / len(observed) if observed else None,
                "source": "Sleep Cycle preferred; manual fallback" if key == "sleep_hours"
                          else "Manual daily check-in",
            }
    return result
