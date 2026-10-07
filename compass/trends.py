"""Summarize reported ratings in adjacent calendar periods."""

from datetime import date, timedelta

RATINGS = ("mood", "energy", "stress")


def trend_summary(rows, end_day, days):
    """Compare recorded-day means without filling in missing check-ins."""
    if days not in (7, 30, 90):
        raise ValueError("Choose a 7, 30 or 90 day window.")
    start = end_day - timedelta(days=days - 1)
    previous_end = start - timedelta(days=1)
    previous_start = start - timedelta(days=days)
    current = []
    previous = []
    for row in rows:
        day = date.fromisoformat(row["day"])
        if start <= day <= end_day:
            current.append(row)
        elif previous_start <= day <= previous_end:
            previous.append(row)
    current.sort(key=lambda row: row["day"])
    means = {}
    changes = {}
    for rating in RATINGS:
        means[rating] = (
            sum(row[rating] for row in current) / len(current)
            if current
            else None
        )
        previous_mean = (
            sum(row[rating] for row in previous) / len(previous)
            if previous
            else None
        )
        changes[rating] = (
            means[rating] - previous_mean if current and previous else None
        )
    return {
        "start": start,
        "end": end_day,
        "previous_start": previous_start,
        "previous_end": previous_end,
        "current": current,
        "previous_count": len(previous),
        "means": means,
        "changes": changes,
    }
