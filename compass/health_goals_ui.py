"""Configure daily health goals without silently imposing medical targets."""

import streamlit as st

from compass.health import HealthService
from compass.health_goals import GOAL_OPTIONS, enriched_goal_progress, compare_weeks
from compass.health_daily import DailyHealthService
from compass.sleep_cycle_csv import SleepCycleCSVService
from compass.unified_sleep import unified_sleep_snapshot
from datetime import timedelta


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
            if key == "nutrition_on_track":
                values[key] = 1.0
                st.caption("Nutrition: track whether you followed your own plan (Yes/No) in the full Daily check-in.")
                continue
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
    rows = DailyHealthService(db, user_id).history(
        start=today - timedelta(days=29), end=today
    )
    cycle = SleepCycleCSVService(db, user_id).history(
        start=today - timedelta(days=29), end=today
    )
    nights = unified_sleep_snapshot(rows, cycle, [], today)["nights"]
    days = st.selectbox("Progress window", [7, 30], index=0,
                        format_func=lambda n: f"Last {n} days",
                        key="health_goal_progress_window")
    st.subheader("Progress on recorded days")
    for key, result in enriched_goal_progress(rows, nights, saved, today, days).items():
        label, unit = GOAL_OPTIONS[key][:2]
        if key == "weight_lb":
            st.write(f"**Weight target: {result['target']:g} lb**")
            if result["latest"] is None:
                st.caption("No weight measurements for this period.")
            else:
                change = (
                    f" · Change {result['change']:+.1f} lb"
                    if result["change"] is not None else ""
                )
                st.write(
                    f"Latest: **{result['latest']:.1f} lb** · "
                    f"{result['recorded']} readings{change}"
                )
                st.caption(
                    "At or below your chosen target."
                    if result["reached"] else
                    f"{result['remaining']:.1f} lb above your chosen target."
                )
        else:
            goal_label = (
                "Follow nutrition plan" if key == "nutrition_on_track" else
                f"{label} {result['target']:g} {unit}"
            )
            st.write(
                f"**{goal_label}** — "
                f"{result['met']} of {result['recorded']} measured days met"
            )
            if result["recorded"]:
                st.progress(result["met"] / result["recorded"])
            else:
                st.caption("No recorded observations for this goal yet.")
            if key == "sleep_hours":
                st.caption("Sleep Cycle nightly records are used first; manual sleep fills gaps.")
    st.caption(
        "Unrecorded days are not successes or failures. Nutrition only counts "
        "a deliberately logged Yes or No; weight is a trajectory rather "
        "than a daily streak. These are personal targets, not medical advice."
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
