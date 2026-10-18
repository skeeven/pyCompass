"""A unified, source-aware Sleep Health panel for Compass Overview."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from compass.health_report_display import format_duration, format_report_value


def unified_sleep_screen(snapshot):
    st.subheader("Sleep Health")
    st.caption(
        "One view of your sleep. Sleep Cycle supplies recorded nightly sleep and "
        "quality; manual sleep fills unrecorded nights. ResMed CPAP data is "
        "shown as report-period averages, never as individual nightly measurements."
    )
    latest = snapshot["latest"]
    cpap = snapshot["cpap_reports"]
    first = cpap[0] if cpap else None
    metrics = first["metrics"] if first else {}
    cols = st.columns(4)
    with cols[0]:
        if latest and latest["sleep_hours"] is not None:
            st.metric("Latest sleep", format_duration(latest["sleep_hours"]))
            st.caption(f"{latest['night']} · {latest['sleep_source']}")
        else:
            st.metric("Latest sleep", "—")
    with cols[1]:
        if latest and latest["sleep_quality_pct"] is not None:
            st.metric("Sleep quality", f"{latest['sleep_quality_pct']:.0f}%")
            st.caption(f"{latest['night']} · Sleep Cycle")
        else:
            quality_nights = [r for r in snapshot["nights"] if r["sleep_quality_pct"] is not None]
            if quality_nights:
                recorded = quality_nights[-1]
                st.metric("Sleep quality", f"{recorded['sleep_quality_pct']:.0f}%")
                st.caption(f"{recorded['night']} · Sleep Cycle")
            else:
                st.metric("Sleep quality", "—")
    with cols[2]:
        if "cpap_usage_hours" in metrics:
            st.metric("CPAP average use", format_duration(metrics["cpap_usage_hours"]["value"]))
            st.caption(f"{first['period_start']} – {first['period_end']} · ResMed")
        else:
            st.metric("CPAP average use", "—")
    with cols[3]:
        if "ahi" in metrics:
            st.metric("AHI", f"{metrics['ahi']['value']:.2f}")
            st.caption(f"{first['period_start']} – {first['period_end']} · ResMed")
        else:
            st.metric("AHI", "—")

    st.markdown("**Sleep at a glance**")
    for col, days in zip(st.columns(3), (7, 30, 90)):
        window = snapshot["windows"][days]
        with col:
            st.caption(f"Last {days} days")
            if window["sleep_hours"] is not None:
                st.write(f"Average sleep: **{format_duration(window['sleep_hours'])}**")
            else:
                st.write("Average sleep: —")
            if window["quality_pct"] is not None:
                st.write(f"Average quality: **{window['quality_pct']:.1f}%**")
            else:
                st.write("Average quality: —")
            st.caption(
                f"{window['sleep_count']} nights with sleep · "
                f"{window['quality_count']} quality readings"
            )
            st.caption(
                f"Sleep sources: {window['cycle_nights']} Sleep Cycle, "
                f"{window['manual_nights']} manual"
            )

    st.markdown("**Nightly sleep trend**")
    days = st.selectbox(
        "Time range", [7, 30, 90], index=1,
        format_func=lambda n: f"Last {n} days", key="unified_sleep_days",
    )
    chosen = st.selectbox(
        "Show", ["sleep_hours", "sleep_quality_pct"],
        format_func=lambda key: {
            "sleep_hours": "Time asleep (hours)",
            "sleep_quality_pct": "Sleep quality (%)",
        }[key], key="unified_sleep_metric",
    )
    start = (date.fromisoformat(snapshot["as_of"]) - timedelta(days=days - 1)).isoformat()
    chart_data = [
        {"Night": r["night"], "Value": r[chosen], "Source": (
            r["sleep_source"] if chosen == "sleep_hours" else "Sleep Cycle"
        )}
        for r in snapshot["nights"]
        if r["night"] >= start and r[chosen] is not None
    ]
    if chart_data:
        frame = pd.DataFrame(chart_data)
        frame["Night"] = pd.to_datetime(frame["Night"])
        st.line_chart(frame.set_index("Night")[["Value"]])
        with st.expander("View source for each reading"):
            st.dataframe(frame.sort_values("Night", ascending=False), hide_index=True)
    else:
        st.caption("No readings for this measurement and date range.")
    st.caption("One reading per night; Sleep Cycle takes priority over a manual sleep entry for the same date. No missing nights are zero-filled.")

    if cpap:
        st.markdown("**ResMed CPAP reporting periods**")
        periods = []
        for report in cpap:
            row = {"Period": f"{report['period_start']} – {report['period_end']}"}
            for key, label in (
                ("cpap_usage_hours", "Average use"),
                ("ahi", "AHI"),
                ("leak_l_min", "Mask leak (L/min)"),
            ):
                if key in report["metrics"]:
                    row[label] = format_report_value(key, report["metrics"][key]["value"])
                else:
                    row[label] = "—"
            periods.append(row)
        st.dataframe(pd.DataFrame(periods), hide_index=True, use_container_width=True)
        st.caption(
            "These overlapping 30-, 90-, and 365-day reports are alternative "
            "summaries ending on the same date—not independent nights. "
            "They cannot be averaged together or paired to specific nightly scores."
        )

    consistency = snapshot["cycle_insights"]
    bedtime, waking = consistency["bedtime"], consistency["wake_time"]
    if bedtime and waking:
        with st.expander("Bedtime and wake-time consistency · past 30 days"):
            st.write(
                f"Typical bedtime **{bedtime['typical']}** · "
                f"wake time **{waking['typical']}**"
            )
            st.caption(
                f"Average variation: bedtime {bedtime['mean_deviation_minutes']:.0f} min; "
                f"wake time {waking['mean_deviation_minutes']:.0f} min. "
                "Sleep Cycle local clock times are used; no timezone is inferred."
            )
