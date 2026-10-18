"""Evidence-first personalized patterns inside Compass Health Overview."""

import streamlit as st


def personalized_patterns_screen(report):
    st.subheader("Personalized health insights")
    st.caption(
        f"Last {report['days']} days · Sleep Cycle and/or manual nightly sleep "
        "matched to your wellness check-in on the same wake-date. "
        "This is descriptive, not a diagnosis or a causal finding."
    )
    st.write(
        f"**{report['sleep_nights']} recorded sleep nights** · "
        f"**{report['checkin_days']} daily health check-ins**"
    )
    supported = 0
    with st.expander("Sleep and wellness patterns", expanded=True):
        for item in report["patterns"]:
            st.markdown(f"**{item['sleep_label']} × {item['checkin_label']}**")
            n = item["matched_days"]
            if n < item["minimum"]:
                st.caption(
                    f"Not enough paired observations yet: {n} of at least "
                    f"{item['minimum']} matched days needed."
                )
            elif item["correlation"] is None:
                st.caption(
                    f"{n} matched days, but the data has too little variation "
                    "to calculate a reliable linear association."
                )
            else:
                supported += 1
                st.write(item["finding"])
                st.caption(
                    f"{n} matched days · exploratory linear correlation "
                    f"r = {item['correlation']:+.2f}. "
                    "A correlation does not establish cause and effect."
                )
        if supported == 0:
            st.info(
                "Keep recording daily energy and stress ratings. "
                "Compass will only describe possible patterns after enough "
                "nights and same-day check-ins overlap."
            )
    st.caption(
        "ResMed CPAP report averages are not converted into nightly observations. "
        "Missing dates aren't assigned values. Multiple exploratory comparisons "
        "can produce coincidental associations, even when sample size is sufficient."
    )
