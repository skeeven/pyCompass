"""Explicit, user-configured daily goal targets and honest progress counts."""

from datetime import timedelta

GOAL_OPTIONS = {
    "sleep_hours": ("Sleep at least", "hours", 0.5, 16.0),
    "cpap_hours": ("Use CPAP at least", "hours", 0.5, 16.0),
    "movement_minutes": ("Move at least", "minutes", 1.0, 600.0),
    "downtime_minutes": ("Personal time at least", "minutes", 1.0, 600.0),
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
                or not low <= target <= high):
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
            "met": sum(value >= target for value in observed),
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
