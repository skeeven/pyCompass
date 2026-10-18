"""Descriptive Sleep Cycle insights; never blend CSV sessions with CPAP aggregates."""

from datetime import date, datetime, timedelta
from statistics import mean, median


def _clock_minute(timestamp):
    parsed = datetime.fromisoformat(timestamp)
    return parsed.hour * 60 + parsed.minute + parsed.second / 60


def _clock_summary(values):
    """Return a representative clock time and spread, including midnight.

    Values are unwrapped around the circular median, avoiding an invalid
    mean such as noon when bedtime observations straddle midnight.
    """
    if not values:
        return None
    # Anchor on an observed value that minimizes absolute circular deviations.
    anchor = min(values, key=lambda pivot: sum(
        abs(((value - pivot + 720) % 1440) - 720) for value in values
    ))
    unwrapped = [anchor + ((value - anchor + 720) % 1440) - 720
                 for value in values]
    center = median(unwrapped)
    deviation = mean(abs(value - center) for value in unwrapped)
    minute = round(center) % 1440
    return {
        "typical": f"{minute // 60:02d}:{minute % 60:02d}",
        "mean_deviation_minutes": round(deviation, 1),
        "count": len(values),
    }


def sleep_cycle_insights(rows, today):
    """Summaries use only recorded sessions through today, not missing nights."""
    if not isinstance(today, date):
        raise ValueError("Select a valid date.")
    available = [row for row in rows if row["night"] <= today.isoformat()]
    available.sort(key=lambda row: (row["night"], row["session_end"]))
    windows = {}
    for days in (7, 30, 90):
        start = (today - timedelta(days=days - 1)).isoformat()
        subset = [row for row in available if row["night"] >= start]
        averages = {}
        counts = {}
        for key in ("sleep_quality_pct", "sleep_hours", "time_in_bed_hours"):
            measured = [row[key] for row in subset if row[key] is not None]
            if measured:
                averages[key] = mean(measured)
                counts[key] = len(measured)
        windows[days] = {
            "sessions": len(subset),
            "nights": len({r["night"] for r in subset}),
            "averages": averages,
            "counts": counts,
        }

    current_start = today - timedelta(days=6)
    previous_start = today - timedelta(days=13)
    last_week = [
        row for row in available if row["night"] >= current_start.isoformat()
    ]
    prior_week = [
        row for row in available
        if previous_start.isoformat() <= row["night"] < current_start.isoformat()
    ]
    comparison = {}
    for key in ("sleep_quality_pct", "sleep_hours"):
        current = [row[key] for row in last_week if row[key] is not None]
        previous = [row[key] for row in prior_week if row[key] is not None]
        if current and previous:
            comparison[key] = {
                "current": mean(current), "previous": mean(previous),
                "change": mean(current) - mean(previous),
                "current_count": len(current), "previous_count": len(previous),
            }

    recent_start = (today - timedelta(days=29)).isoformat()
    recent = [row for row in available if row["night"] >= recent_start]
    return {
        "latest": available[-1] if available else None,
        "as_of": today.isoformat(),
        "windows": windows,
        "comparison": comparison,
        "bedtime": _clock_summary([
            _clock_minute(row["session_start"]) for row in recent
        ]),
        "wake_time": _clock_summary([
            _clock_minute(row["session_end"]) for row in recent
        ]),
        "chart_rows": [
            row for row in available
            if row["night"] >= (today - timedelta(days=89)).isoformat()
        ],
    }
