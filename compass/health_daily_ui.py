"""Daily health check-ins, retrospective edits, and descriptive trends."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from compass.health_daily import DailyHealthService, weekly_summary, FIELDS
from compass.unified_daily import UnifiedDailyService
from compass.health_checkin_context import sleep_context_for_day, manual_checkin_patch
from compass.health_report_display import format_duration

NUMERIC_FIELDS = (
    ("weight_lb", "Weight (lb)", 50.0, 1000.0, 0.1),
    ("waist_in", "Waist (in)", 10.0, 100.0, 0.1),
    ("sleep_hours", "Sleep (hours)", 0.0, 24.0, 0.25),
    ("cpap_hours", "CPAP use (hours)", 0.0, 24.0, 0.25),
    ("energy", "Energy (1–10)", 1.0, 10.0, 1.0),
    ("stress", "Stress (1–10)", 1.0, 10.0, 1.0),
    ("hunger", "Hunger (1–10)", 1.0, 10.0, 1.0),
    ("movement_minutes", "Movement (minutes)", 0.0, 1440.0, 5.0),
    ("downtime_minutes", "Personal downtime (minutes)", 0.0, 1440.0, 5.0),
)


def daily_screen(db, user_id, today):
    service = DailyHealthService(db, user_id)
    unified = UnifiedDailyService(db, user_id)
    st.subheader("Additional health measurements")
    st.caption(
        "All answers are optional. Empty answers are not counted as zero. "
        "This is personal tracking, not medical advice."
    )
    selected_day = st.date_input(
        "Check-in date", value=today, max_value=today,
        key="health_checkin_day",
    )
    current_values = unified.get(selected_day)["values"]
    existing = {key: value for key, value in current_values.items()
                if key in FIELDS}
    imported = sleep_context_for_day(db, user_id, selected_day)
    if imported['session_count']:
        details = []
        if imported['sleep_hours'] is not None:
            details.append('Time asleep: ' + format_duration(imported['sleep_hours']))
        if imported['sleep_quality_pct'] is not None:
            details.append(f"Quality: {imported['sleep_quality_pct']:.1f}%")
        st.info('Sleep Cycle (read-only) · ' + (' · '.join(details) if details else 'No measurements'))
    else:
        st.caption('No Sleep Cycle recording for this date. Manual sleep remains optional below.')
    if existing:
        st.info("A check-in exists for this day. Saving will update it.")
    st.caption("For your everyday mood, energy and stress check-in, use Today. You can also update measurements for earlier dates here.")
    with st.expander("Additional health measurements", expanded=True):
        full_health_form(unified, selected_day, existing)
    if existing:
        with st.expander("Delete this day's health check-in"):
            if st.checkbox(
                "I understand this permanently deletes this day's health log",
                key=f"health_delete_confirm_{selected_day}",
            ) and st.button(
                "Delete check-in", key=f"health_delete_{selected_day}"
            ):
                service.delete(selected_day)
                st.rerun()


def full_health_form(service, selected_day, existing):
    """Optional detailed entries keep all previously saved values editable."""
    with st.form(f"daily_health_{selected_day.isoformat()}"):
        values = {}
        for key, label, minimum, maximum, step in NUMERIC_FIELDS:
            if key == "sleep_hours":
                st.caption("Manual sleep is optional; it does not modify your imported Sleep Cycle sessions.")
            existing_value = existing.get(key)
            entered = st.number_input(
                label + " (leave blank to skip)",
                value=float(existing_value) if existing_value is not None else None,
                min_value=minimum,
                max_value=maximum,
                step=step,
                key=f"daily_{selected_day}_{key}",
            )
            if entered is not None:
                values[key] = entered
        nutrition_choices = ["Not recorded", "Yes", "No"]
        saved_nutrition = existing.get("nutrition_on_track")
        nutrition_choice = st.selectbox(
            "Did you follow your own nutrition plan today? (optional)",
            nutrition_choices,
            index=0 if saved_nutrition is None else (1 if saved_nutrition == 1 else 2),
            key=f"daily_{selected_day}_nutrition_on_track",
        )
        if nutrition_choice != "Not recorded":
            values["nutrition_on_track"] = 1 if nutrition_choice == "Yes" else 0
        nutrition = st.text_area(
            "Nutrition notes (optional)",
            value=existing.get("nutrition_note", ""), max_chars=2000,
        )
        notes = st.text_area(
            "Other observations (optional)",
            value=existing.get("notes", ""), max_chars=2000,
        )
        if nutrition.strip():
            values["nutrition_note"] = nutrition.strip()
        if notes.strip():
            values["notes"] = notes.strip()
        submitted = st.form_submit_button("Save daily check-in", type="primary")
    if submitted:
        try:
            service.save_health(selected_day, values)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"Saved check-in for {selected_day:%b %d, %Y}.")
            st.rerun()


def trends_screen(db, user_id, today):
    service = DailyHealthService(db, user_id)
    st.subheader("Your health trends")
    days = st.selectbox("Time window", [7, 14, 30, 90], index=2)
    records = UnifiedDailyService(db, user_id).measurements(
        start=today - timedelta(days=days - 1), end=today
    )
    if not records:
        st.info("No check-ins in this period yet. Log a day to see trends.")
        return
    st.caption(
        f"{len(records)} of {days} days logged. Missing measurements "
        "are excluded from averages and charts."
    )
    available = [field for field, *_ in NUMERIC_FIELDS
                 if any(field in record for record in records)]
    options = {field: label for field, label, *_ in NUMERIC_FIELDS}
    if not available:
        st.info("Only notes have been logged in this window. Add a numeric measurement to see a chart.")
        return
    selected = st.selectbox(
        "Measurement to chart", available,
        format_func=lambda key: options[key],
    )
    frame = pd.DataFrame(records)
    frame["day"] = pd.to_datetime(frame["day"])
    # Only plot actual observations; no imputation of unrecorded days.
    chart_frame = frame[["day", selected]].dropna()
    st.line_chart(chart_frame.set_index("day"), y=selected)
    with st.expander("Recorded days"):
        st.dataframe(frame, hide_index=True, use_container_width=True)
    review = weekly_summary(
        UnifiedDailyService(db, user_id).measurements(
            start=today - timedelta(days=6), end=today
        ), today
    )
    st.subheader("Past seven days")
    st.caption(
        f"{review['start']:%b %d} – {review['end']:%b %d} · "
        f"{review['days_logged']} of 7 days logged"
    )
    for key, average in review["averages"].items():
        st.write(f"{options[key]}: {average:.1f} average on recorded days")
    st.caption(
        "ResMed PDF summaries cover overlapping periods and are kept in "
        "Health history, separate from these daily check-in trends."
    )
