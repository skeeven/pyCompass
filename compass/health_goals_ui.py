"""Configure daily health goals without silently imposing medical targets."""

import streamlit as st

from compass.health import HealthService
from compass.health_goals import GOAL_OPTIONS, goal_progress, compare_weeks
from compass.health_daily import DailyHealthService


def goals_screen(db, user_id, today):
    profile_service = HealthService(db, user_id)
    profile = profile_service.load()
    saved = profile["answers"].get("tracked_goals", {})
    st.subheader("My daily goals")
    st.caption("Choose your own targets. None are prescribed by Compass.")
    with st.form("configure_health_goals"):
        selected = st.multiselect(
            "Choose goals to track",
            list(GOAL_OPTIONS),
            default=list(saved),
            format_func=lambda key: GOAL_OPTIONS[key][0],
        )
        values = {}
        for key in selected:
            label, unit, low, high = GOAL_OPTIONS[key]
            values[key] = st.number_input(
                f"{label} ({unit})",
                min_value=float(low),
                max_value=float(high),
                value=float(saved.get(key, low)),
                key=f"goal_target_{key}",
            )
        submit = st.form_submit_button("Save my goals")
    if submit:
        try:
            profile_service.save(
                {**profile["answers"], "tracked_goals": values},
                profile["step"], completed=False,
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("Goals updated.")
            st.rerun()

    if not saved:
        st.info("Select and save a goal to see its progress here.")
        return
    rows = DailyHealthService(db, user_id).history()
    st.subheader("Progress over the past seven days")
    for key, result in goal_progress(rows, saved, today).items():
        label, unit = GOAL_OPTIONS[key][:2]
        st.write(
            f"**{label} {result['target']:g} {unit}** — "
            f"{result['met']} of {result['recorded']} recorded days met"
        )
        if result["recorded"]:
            st.progress(result["met"] / result["recorded"])
        else:
            st.caption("No days with this measurement recorded yet.")
    st.caption(
        "Progress uses only days with a recorded measurement. "
        "Missing days are not counted as successes or failures."
    )


def comparison_screen(db, user_id, today):
    st.subheader("Two-week comparison")
    rows = DailyHealthService(db, user_id).history()
    data = compare_weeks(rows, today)
    st.caption(
        f"Current: {data['current']['start']:%b %d}–"
        f"{data['current']['end']:%b %d} "
        f"({data['current']['days_logged']} logged days). "
        f"Previous: {data['previous']['start']:%b %d}–"
        f"{data['previous']['end']:%b %d} "
        f"({data['previous']['days_logged']} logged days)."
    )
    from compass.health_daily_ui import NUMERIC_FIELDS
    labels = {key: label for key, label, *_ in NUMERIC_FIELDS}
    if not data["comparisons"]:
        st.info("Log the same measurement in both weeks to compare averages.")
        return
    for key, stats in sorted(data["comparisons"].items()):
        st.write(
            f"**{labels[key]}:** {stats['previous']:.1f} → "
            f"{stats['current']:.1f} (change {stats['change']:+.1f}). "
            f"Recorded on {stats['previous_count']} and "
            f"{stats['current_count']} day(s), respectively."
        )
    st.caption(
        "Changes describe recorded entries only. Different recording "
        "patterns can affect comparisons; no trend implies causation."
    )
