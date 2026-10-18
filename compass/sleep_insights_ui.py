"""Sleep Cycle overview: real nightly readings, never blended with CPAP periods."""

import pandas as pd
import streamlit as st

from compass.health_report_display import format_duration

MEASUREMENTS = {
    "sleep_quality_pct": ("Sleep quality", "%"),
    "sleep_hours": ("Time asleep", "hours"),
}


def sleep_insights_screen(insights):
    st.subheader("Sleep insights · Sleep Cycle")
    latest = insights["latest"]
    if not latest:
        st.info("Import a Sleep Cycle CSV to see your nightly sleep insights.")
        return
    st.caption(
        f"Latest recorded session: {latest['night']}. "
        "These are Sleep Cycle recordings, not CPAP device measurements."
    )
    a, b = st.columns(2)
    if latest["sleep_quality_pct"] is not None:
        a.metric("Latest quality", f"{latest['sleep_quality_pct']:.0f}%")
    else:
        a.metric("Latest quality", "Not recorded")
    if latest["sleep_hours"] is not None:
        b.metric("Latest time asleep", format_duration(latest["sleep_hours"]))
    else:
        b.metric("Latest time asleep", "Not recorded")

    st.markdown("**Recorded-session averages**")
    columns = st.columns(3)
    for col, days in zip(columns, (7, 30, 90)):
        window = insights["windows"][days]
        with col:
            st.caption(f"Last {days} days · {window['nights']} nights recorded")
            quality = window["averages"].get("sleep_quality_pct")
            duration = window["averages"].get("sleep_hours")
            st.write(f"Quality: **{quality:.1f}%**" if quality is not None else "Quality: —")
            st.write(
                f"Sleep: **{format_duration(duration)}**"
                if duration is not None else "Sleep: —"
            )
            st.caption(
                f"Based on {window['counts'].get('sleep_quality_pct', 0)} quality / "
                f"{window['counts'].get('sleep_hours', 0)} duration measurements"
            )

    compare = insights["comparison"]
    if compare:
        st.markdown("**Compared with the previous seven days**")
        for key, label in (("sleep_quality_pct", "Sleep quality"),
                           ("sleep_hours", "Time asleep")):
            if key not in compare:
                continue
            record = compare[key]
            if key == "sleep_quality_pct":
                description = f"{record['change']:+.1f} percentage points"
            else:
                description = f"{record['change'] * 60:+.0f} minutes"
            st.write(
                f"{label}: **{description}** "
                f"({record['previous_count']} previous and "
                f"{record['current_count']} recent observations)"
            )
        st.caption(
            "Descriptive differences only. Different recording patterns "
            "can affect comparisons."
        )

    if insights["chart_rows"]:
        st.markdown("**Nightly trend**")
        chosen = st.selectbox(
            "Sleep Cycle measurement",
            list(MEASUREMENTS),
            format_func=lambda key: MEASUREMENTS[key][0],
            key="overview_sleep_cycle_measurement",
        )
        time_window = st.selectbox(
            "Sleep Cycle chart range", [7, 30, 90], index=1,
            format_func=lambda days: f"Last {days} days",
            key="overview_sleep_cycle_window",
        )
        chart = pd.DataFrame(insights["chart_rows"])
        chart["night"] = pd.to_datetime(chart["night"])
        # Keep the selected window anchored to the dashboard date rather
        # than the latest recorded session (which might be old).
        from datetime import date, timedelta
        today = date.fromisoformat(insights["as_of"])
        chart = chart[chart["night"] >= pd.Timestamp(today - timedelta(days=time_window - 1))]
        observed = chart[["night", chosen]].dropna()
        if observed.empty:
            st.caption("No measurements recorded for this chart window.")
        else:
            # One or more sessions on the same date remain distinct
            # observations; do not zero-fill missing dates.
            st.line_chart(observed.set_index("night"))
        st.caption("Chart plots only recorded sessions. Missing days are not filled in.")

    st.markdown("**Sleep schedule consistency · past 30 days**")
    bedtime, waking = insights["bedtime"], insights["wake_time"]
    if bedtime and waking:
        st.write(
            f"Typical bedtime: **{bedtime['typical']}** · "
            f"Typical wake time: **{waking['typical']}**"
        )
        st.caption(
            "Average absolute variation from the typical time: "
            f"bedtime {bedtime['mean_deviation_minutes']:.0f} minutes; "
            f"wake time {waking['mean_deviation_minutes']:.0f} minutes "
            f"(over {bedtime['count']} recorded sessions). "
            "Clock times are as exported by Sleep Cycle; timezone offsets "
            "are not inferred."
        )
    else:
        st.caption("Not enough sessions in the past 30 days for a schedule summary.")
