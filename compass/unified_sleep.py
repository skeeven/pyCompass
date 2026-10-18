"""One sleep overview built from independently attributed wellness sources.

Sleep Cycle provides nightly sleep when recorded; manual sleep is a fallback
for a day without a Cycle duration. CPAP reports stay period summaries.
"""

from datetime import timedelta
from statistics import mean

from compass.sleep_insights import sleep_cycle_insights


def unified_sleep_snapshot(manual_logs, cycle_sessions, reports, today):
    """No double counting, invented nightly CPAP, or blended source scores."""
    by_day = {}
    for log in manual_logs:
        day = log["day"]
        if day <= today.isoformat() and log.get("sleep_hours") is not None:
            by_day[day] = {
                "night": day, "sleep_hours": log["sleep_hours"],
                "sleep_source": "Manual check-in",
                "sleep_quality_pct": None,
            }
    for session in sorted(cycle_sessions, key=lambda row: row["session_end"]):
        day = session["night"]
        if day > today.isoformat():
            continue
        entry = by_day.setdefault(day, {
            "night": day, "sleep_hours": None, "sleep_source": None,
            "sleep_quality_pct": None,
        })
        if session["sleep_hours"] is not None:
            entry["sleep_hours"] = session["sleep_hours"]
            entry["sleep_source"] = "Sleep Cycle"
        if session["sleep_quality_pct"] is not None:
            entry["sleep_quality_pct"] = session["sleep_quality_pct"]
    nights = sorted(by_day.values(), key=lambda r: r["night"])
    windows = {}
    for days in (7, 30, 90):
        start = (today - timedelta(days=days - 1)).isoformat()
        period = [r for r in nights if r["night"] >= start]
        sleeps = [r["sleep_hours"] for r in period if r["sleep_hours"] is not None]
        qualities = [r["sleep_quality_pct"] for r in period if r["sleep_quality_pct"] is not None]
        windows[days] = {
            "nights": len(period),
            "sleep_hours": mean(sleeps) if sleeps else None,
            "sleep_count": len(sleeps),
            "quality_pct": mean(qualities) if qualities else None,
            "quality_count": len(qualities),
            "cycle_nights": sum(r["sleep_source"] == "Sleep Cycle" for r in period),
            "manual_nights": sum(r["sleep_source"] == "Manual check-in" for r in period),
        }
    recent_cpap = [
        r for r in reports
        if r["report_type"] == "ResMed CPAP"
        and r["status"] == "verified"
        and r["period_end"] <= today.isoformat()
    ]
    if recent_cpap:
        last_end = max(r["period_end"] for r in recent_cpap)
        recent_cpap = [r for r in recent_cpap if r["period_end"] == last_end]
        recent_cpap.sort(key=lambda r: (
            (r["period_end"], r["period_start"]), r["uploaded_at"]
        ), reverse=True)
        # Most recent end date first, shortest date window first.
        recent_cpap.sort(key=lambda r: r["period_start"], reverse=True)
    return {
        "as_of": today.isoformat(),
        "latest": nights[-1] if nights else None,
        "nights": nights,
        "windows": windows,
        "cpap_reports": recent_cpap,
        "cycle_insights": sleep_cycle_insights(cycle_sessions, today),
    }
