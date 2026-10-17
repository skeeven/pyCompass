"""Daily health check-ins, retrospective edits, and descriptive trends."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from compass.health_daily import DailyHealthService, weekly_summary

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
    st.subheader("Daily health check-in")
    st.caption(
        "All answers are optional. Empty answers are not counted as zero. "
        "This is personal tracking, not medical advice."
    )
    selected_day = st.date_input(
        "Check-in date", value=today, max_value=today,
        key="health_checkin_day",
    )
    existing = service.get(selected_day)
    if existing:
        st.info("A check-in exists for this day. Saving will update it.")
    st.caption("Quick entry: record a few core measurements, or expand the full check-in.")
    with st.form(f"health_quick_{selected_day.isoformat()}"):
        quick = {}
        for key, label in (
            ("sleep_hours", "Sleep (hours)"),
            ("energy", "Energy (1–10)"),
            ("movement_minutes", "Movement (minutes)"),
        ):
            bounds = next(field for field in NUMERIC_FIELDS if field[0] == key)
            value = st.number_input(
                label + " · optional",
                min_value=bounds[2],
                max_value=bounds[3],
                value=float(existing[key]) if key in existing else None,
                step=bounds[4],
                key=f"quick_{selected_day}_{key}",
            )
            if value is not None:
                quick[key] = value
        quick_save = st.form_submit_button("Save quick check-in")
    if quick_save:
        if not quick:
            st.warning("Enter at least one measurement to save.")
        else:
            service.save(selected_day, {**existing, **quick})
            st.success("Quick check-in saved.")
            st.rerun()
    with st.expander("Full health check-in", expanded=False):
        full_health_form(service, selected_day, existing)
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
            service.save(selected_day, values)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"Saved check-in for {selected_day:%b %d, %Y}.")
            st.rerun()


def trends_screen(db, user_id, today):
    service = DailyHealthService(db, user_id)
    st.subheader("Your health trends")
    days = st.selectbox("Time window", [7, 14, 30, 90], index=2)
    records = service.history(start=today - timedelta(days=days - 1), end=today)
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
        service.history(start=today - timedelta(days=6), end=today), today
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
