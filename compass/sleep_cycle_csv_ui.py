"""Review Sleep Cycle CSV sessions before importing and chart real recordings."""

from datetime import timedelta

import pandas as pd
import streamlit as st

from compass.sleep_cycle_csv import SleepCycleCSVService, parse_sleep_cycle_csv


def csv_import_screen(db, user_id, upload):
    service = SleepCycleCSVService(db, user_id)
    try:
        sessions = parse_sleep_cycle_csv(upload.getvalue())
        status = service.preview(sessions)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.success(
        f"Recognized {len(sessions):,} unique sleep sessions. "
        f"{status['new']:,} new; {status['duplicates']:,} already imported."
    )
    st.caption(
        f"Export spans {sessions[0]['night']} to {sessions[-1]['night']} "
        "(file order). Only sleep timestamps, sleep quality, time asleep "
        "and time in bed will be saved."
    )
    latest = sorted(sessions, key=lambda row: row["session_end"], reverse=True)[:10]
    with st.expander("Preview 10 latest sessions", expanded=True):
        st.dataframe(pd.DataFrame(latest), hide_index=True)
    with st.form("sleep_cycle_csv_confirm"):
        confirmed = st.checkbox(
            "I reviewed the import counts and agree to save these "
            "Sleep Cycle sessions to my Compass account."
        )
        submitted = st.form_submit_button(
            f"Import {status['new']:,} new sessions",
            disabled=status["new"] == 0,
            type="primary",
        )
    if submitted:
        if not confirmed:
            st.warning("Please confirm the session import.")
            return
        result = service.import_sessions(sessions)
        st.success(
            f"Imported {result['imported']:,} sessions. "
            f"{result['duplicates']:,} duplicates were left unchanged."
        )


def sleep_cycle_history_screen(db, user_id, today):
    service = SleepCycleCSVService(db, user_id)
    records = service.history()
    st.subheader("Sleep Cycle nightly history")
    if not records:
        st.info("No Sleep Cycle CSV sessions imported yet.")
        return
    st.caption(
        f"{len(records):,} saved sessions. These are individual Sleep Cycle "
        "recordings, not ResMed CPAP averages or daily check-in values."
    )
    days = st.selectbox("Show last", [7, 30, 90, 365], index=1,
                        format_func=lambda n: f"{n} days", key="cycle_history_window")
    recent = [
        row for row in records
        if (today - timedelta(days=days - 1)).isoformat()
        <= row["night"] <= today.isoformat()
    ]
    if not recent:
        st.info("No imported Sleep Cycle recordings in this date range.")
    else:
        frame = pd.DataFrame(recent)
        frame["night"] = pd.to_datetime(frame["night"])
        choices = {
            "sleep_quality_pct": "Sleep quality (%)",
            "sleep_hours": "Time asleep (hours)",
            "time_in_bed_hours": "Time in bed (hours)",
        }
        available = [key for key in choices if frame[key].notna().any()]
        if available:
            chosen = st.selectbox("Measurement", available,
                                  format_func=choices.get, key="cycle_history_metric")
            data = frame[["night", chosen]].dropna()
            st.line_chart(data.set_index("night"))
            st.caption(
                f"Average: {data[chosen].mean():.1f} "
                f"{'%' if chosen == 'sleep_quality_pct' else 'hours'} "
                f"across {len(data)} measured sessions."
            )
        st.dataframe(frame.tail(30).iloc[::-1], hide_index=True)
    with st.expander("Remove imported Sleep Cycle session history"):
        st.warning(
            "This removes all imported CSV sleep sessions from your account. "
            "It does not delete PDF reports, check-ins, or the original CSV."
        )
        confirmed = st.checkbox(
            "I understand that every imported Sleep Cycle CSV session will be deleted.",
            key="delete_cycle_csv_confirm",
        )
        if st.button("Delete all imported CSV sessions", disabled=not confirmed,
                     key="delete_cycle_csv"):
            service.delete_all()
            st.rerun()
