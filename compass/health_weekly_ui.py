"""Human-readable, non-diagnostic weekly Compass Health review."""

import streamlit as st

from compass.health_weekly import WeeklyHealthService, week_bounds
from compass.health import HealthService
from compass.health_daily_ui import NUMERIC_FIELDS
from compass.health_weekly_summary import MEASURES
from compass.health_report_display import format_duration


def weekly_health_screen(db, user_id, today):
    service = WeeklyHealthService(db, user_id)
    st.subheader("Weekly health review")
    selected = st.date_input(
        "Review a week containing", today, max_value=today,
        key="health_weekly_date",
    )
    start, end = week_bounds(selected)
    overview = service.overview(selected, today=today)
    st.caption(
        f"{start:%b %d} – {end:%b %d, %Y} · "
        f"{overview['days_logged']} daily check-ins recorded"
    )
    if overview["averages"]:
        labels = {key: label for key, label, *_ in NUMERIC_FIELDS}
        st.write("**This week's recorded measurements**")
        for key, average in overview["averages"].items():
            count = overview["measurement_counts"][key]
            st.write(f"{labels[key]}: {average:.1f} · {count} recorded day(s)")
        st.caption(
            "These are averages of entries with values, not estimates for missing days."
        )
    else:
        st.info("No daily measurements for this week yet.")

    if overview["reports"]:
        with st.expander("Imported sleep reports covering this week"):
            st.caption(
                "These reports are period summaries, sometimes overlapping. "
                "They are not added to the daily averages above."
            )
            for report in overview["reports"]:
                st.write(
                    f"{report['source']}: {report['period_start']} – "
                    f"{report['period_end']}"
                )

    review = service.personalized_overview(selected, today=today)
    st.markdown("### Your week at a glance")
    st.caption(
        f"{review['current']['recorded_sleep_nights']} nights with recorded sleep · "
        f"{review['current']['checkin_days']} manual check-ins. "
        "Missing days are excluded, not treated as zero."
    )
    for key, measurement in review["current"]["measurements"].items():
        label, unit = MEASURES[key]
        value = (format_duration(measurement["average"])
                 if key == "sleep_hours" else
                 f"{measurement['average']:.1f} {unit}")
        st.write(
            f"**{label}:** {value} · "
            f"{measurement['count']} recorded measurement(s)"
        )
    if not review["current"]["measurements"]:
        st.info("No sleep or numeric wellness measurements for this week yet.")
    if review["changes"]:
        with st.expander("Compared with last week"):
            st.caption(
                "Changes are descriptive. Comparisons require at least two "
                "observations in each week."
            )
            for key, change in sorted(review["changes"].items()):
                label, unit = MEASURES[key]
                if key == "sleep_hours":
                    difference = f"{change['difference'] * 60:+.0f} minutes"
                elif key == "sleep_quality_pct":
                    difference = f"{change['difference']:+.1f} percentage points"
                else:
                    difference = f"{change['difference']:+.1f} {unit}"
                st.write(
                    f"{label}: **{difference}** · "
                    f"{change['previous_count']} previous and "
                    f"{change['current_count']} current measurements"
                )
    if review["goals"]:
        st.markdown("### Progress toward your goals")
        for key, result in review["goals"].items():
            label = review["goal_labels"][key]
            if key == "weight_lb":
                if result["latest"] is None:
                    st.write(f"**{label}:** No weight recorded this week.")
                else:
                    description = f"Latest {result['latest']:.1f} lb"
                    if result["change"] is not None:
                        description += f" · Change {result['change']:+.1f} lb"
                    st.write(f"**{label}:** {description}")
            else:
                st.write(
                    f"**{label}:** {result['met']} of "
                    f"{result['recorded']} measured day(s) met your target"
                )
        st.caption(
            "Goals use your configured targets and observed days only. "
            "Sleep Cycle is used before manual sleep; ResMed period "
            "averages aren't counted as nightly goal completions."
        )
    if review["report_context"]:
        with st.expander("Sleep report context (not daily readings)"):
            st.caption(
                "Overlapping report periods are listed for context only. "
                "They are not averaged into nightly data."
            )
            for item in review["report_context"]:
                st.write(
                    f"{item['source']}: {item['period_start']} to "
                    f"{item['period_end']}"
                )
    st.caption(
        "Your reflection below is written and saved by you. "
        "Compass does not automatically invent wins, challenges, "
        "or medical recommendations from these measurements."
    )

    goals = HealthService(db, user_id).load()["answers"].get("goals")
    if goals:
        with st.expander("My starting goals"):
            st.write(goals)
    saved = service.get(selected)
    st.write("**Reflect on your week**")
    with st.form(f"health_weekly_review_{start}"):
        wins = st.text_area(
            "What went well?", value=saved.get("wins", ""), max_chars=2000
        )
        challenges = st.text_area(
            "What made things difficult?",
            value=saved.get("challenges", ""), max_chars=2000
        )
        next_step = st.text_area(
            "One realistic step for next week",
            value=saved.get("next_step", ""), max_chars=2000
        )
        submitted = st.form_submit_button("Save weekly reflection", type="primary")
    if submitted:
        service.save(selected, {
            "wins": wins, "challenges": challenges, "next_step": next_step
        })
        st.success("Weekly reflection saved.")
    with st.expander("Earlier reflections"):
        history = service.history()
        if not history:
            st.caption("No weekly reflections saved yet.")
        for item in history:
            st.markdown(f"**Week of {item['week_start']}**")
            for label, key in (
                ("What went well", "wins"),
                ("Challenges", "challenges"),
                ("Next step", "next_step"),
            ):
                if item.get(key):
                    st.write(f"{label}: {item[key]}")
    st.caption(
        "Weekly reflections describe your observations, not diagnoses or "
        "treatment recommendations. The numeric summary updates if you edit "
        "past check-ins; your written reflection stays as you saved it."
    )
