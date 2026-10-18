"""Transparent, descriptive wellness patterns, not clinical inferences.

All comparisons pair the waking date of a Sleep Cycle night with a manual
check-in on that same calendar date. Never synthesize individual CPAP nights
from aggregate ResMed reports, or assume unrecorded days mean zero.
"""

from datetime import timedelta
from math import isfinite, sqrt
from statistics import mean

MIN_MATCHED_DAYS = 10
MIN_VARIATION = 1e-9

PAIRINGS = (
    ("sleep_hours", "energy", "Time asleep", "Energy rating"),
    ("sleep_hours", "stress", "Time asleep", "Stress rating"),
    ("sleep_quality_pct", "energy", "Sleep quality", "Energy rating"),
    ("sleep_quality_pct", "stress", "Sleep quality", "Stress rating"),
)


def pearson_r(pairs):
    """Simple Pearson correlation, or None for a degenerate sample."""
    if len(pairs) < MIN_MATCHED_DAYS:
        return None
    xs, ys = zip(*pairs)
    mx, my = mean(xs), mean(ys)
    xx = sum((x - mx) ** 2 for x in xs)
    yy = sum((y - my) ** 2 for y in ys)
    if xx < MIN_VARIATION or yy < MIN_VARIATION:
        return None
    value = sum((x - mx) * (y - my) for x, y in pairs) / sqrt(xx * yy)
    return max(-1.0, min(1.0, value)) if isfinite(value) else None


def personalized_health_insights(manual_logs, unified_sleep, today, days=90):
    """Return evidence counts and conservative observations without AI calls."""
    if days not in (30, 90):
        raise ValueError("Choose a supported insight period.")
    start = (today - timedelta(days=days - 1)).isoformat()
    end = today.isoformat()
    logs = {
        log["day"]: log for log in manual_logs
        if start <= log["day"] <= end
    }
    nights = {
        row["night"]: row for row in unified_sleep["nights"]
        if start <= row["night"] <= end
    }
    results = []
    for sleep_key, checkin_key, sleep_label, checkin_label in PAIRINGS:
        pairs = []
        for day, night in nights.items():
            checkin = logs.get(day)
            if checkin is None:
                continue
            x = night.get(sleep_key)
            y = checkin.get(checkin_key)
            # Quality must originate from Sleep Cycle; duration uses the
            # existing night-level source precedence.
            if (x is None or y is None or isinstance(x, bool)
                    or isinstance(y, bool)):
                continue
            try:
                x, y = float(x), float(y)
            except (TypeError, ValueError):
                continue
            if isfinite(x) and isfinite(y):
                pairs.append((x, y))
        r = pearson_r(pairs)
        if r is None:
            finding = None
        elif abs(r) < 0.3:
            finding = "No clear linear pattern in the recorded matched days."
        elif r > 0:
            finding = (
                f"Higher {sleep_label.lower()} tended to occur alongside "
                f"higher {checkin_label.lower()}."
            )
        else:
            finding = (
                f"Higher {sleep_label.lower()} tended to occur alongside "
                f"lower {checkin_label.lower()}."
            )
        results.append({
            "sleep_label": sleep_label,
            "checkin_label": checkin_label,
            "matched_days": len(pairs),
            "minimum": MIN_MATCHED_DAYS,
            "correlation": r,
            "finding": finding,
        })
    return {
        "days": days,
        "as_of": end,
        "checkin_days": len(logs),
        "sleep_nights": len(nights),
        "patterns": results,
    }
