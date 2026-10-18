"""Streamlit home view for personal Compass Health observations."""

import pandas as pd
from datetime import timedelta
import streamlit as st

from compass.health_dashboard import dashboard_snapshot
from compass.health_goals import GOAL_OPTIONS, goal_progress
from compass.unified_sleep_ui import unified_sleep_screen
from compass.health_report_display import format_report_value

SUMMARY_FIELDS = {
    "sleep_hours": ("Manual sleep", "hours"),
    "cpap_hours": ("CPAP use", "hours"),
    "energy": ("Energy", "/10"),
    "stress": ("Stress", "/10"),
    "hunger": ("Hunger", "/10"),
    "movement_minutes": ("Movement", "minutes"),
    "downtime_minutes": ("Downtime", "minutes"),
    "weight_lb": ("Weight", "lb"),
}


def dashboard_screen(db, user_id, today):
    snapshot = dashboard_snapshot(db, user_id, today)
    st.subheader("Health overview")
    latest = snapshot["latest_checkin"]
    if latest:
        st.caption(f"Most recent check-in in the past seven days: {latest['day']}")
        cards = [
            (label, f"{latest[key]:.1f} {unit}")
            for key, (label, unit) in SUMMARY_FIELDS.items()
            if key in latest and key not in {"sleep_hours", "cpap_hours"}
        ]
        if cards:
            for i in range(0, len(cards), 3):
                cols = st.columns(min(3, len(cards) - i))
                for col, (label, value) in zip(cols, cards[i:i + 3]):
                    col.metric(label, value)
        else:
            st.info("Your recent check-in includes notes but no numeric measurements.")
    else:
        st.info("No daily check-in in the past seven days. Use Daily check-in to begin.")

    summary = snapshot["weekly"]
    st.subheader("Past seven days")
    st.caption(
        f"{summary['days_logged']} of 7 days logged. "
        "Averages exclude missing measurements."
    )
    metrics = summary["averages"]
    if metrics:
        cols = st.columns(3)
        for index, key in enumerate(("energy", "movement_minutes", "downtime_minutes")):
            if key in metrics:
                label, unit = SUMMARY_FIELDS[key]
                cols[index].metric(f"Average {label.lower()}", f"{metrics[key]:.1f} {unit}")
    if snapshot["profile"]["answers"].get("goals"):
        with st.expander("My personal goals", expanded=True):
            st.write(snapshot["profile"]["answers"]["goals"])
    else:
        st.caption("Add personal goals in My health profile to see them here.")

    configured = snapshot["profile"]["answers"].get("tracked_goals", {})
    if configured:
        st.subheader("Daily goal progress")
        from compass.health_daily import DailyHealthService
        logged = DailyHealthService(db, user_id).history(
            start=today - timedelta(days=6), end=today
        )
        for key, status in goal_progress(logged, configured, today).items():
            label, unit = GOAL_OPTIONS[key][:2]
            st.write(
                f"{label} {status['target']:g} {unit}: "
                f"{status['met']} of {status['recorded']} measured days met"
            )
        st.caption("Unrecorded days are not treated as missed goals.")

    reflection = snapshot["reflection"]
    if reflection.get("next_step"):
        st.subheader("My next small step")
        st.write(reflection["next_step"])
    else:
        st.caption("Your next step from Weekly review will appear here.")

    unified_sleep_screen(snapshot["unified_sleep"])

    st.subheader("Other daily measurements")
    from compass.health_daily import DailyHealthService
    history = DailyHealthService(db, user_id).history(
        start=today - timedelta(days=6), end=today
    )
    available = [
        key for key in ("energy", "weight_lb", "movement_minutes", "stress")
        if any(key in record for record in history)
    ]
    if available:
        frame = pd.DataFrame(history)
        frame["day"] = pd.to_datetime(frame["day"])
        selected = st.selectbox(
            "Chart measurement", available,
            format_func=lambda key: SUMMARY_FIELDS[key][0],
            key="health_dashboard_chart",
        )
        st.line_chart(frame[["day", selected]].dropna().set_index("day"))
        st.caption("Only recorded days are plotted; no values are inferred.")
    else:
        st.caption("Record non-sleep daily measurements to display a chart.")
