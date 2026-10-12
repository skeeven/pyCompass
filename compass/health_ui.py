"""Streamlit guided onboarding for Compass Health."""

import streamlit as st

from compass.health import HealthService, ONBOARDING_STEPS

PRIORITIES = ["Sleep", "Energy", "Weight", "Nutrition", "Movement", "Stress", "Other"]
ACTIVITY = ["Prefer not to say", "Mostly seated", "Lightly active", "Moderately active", "Very active"]


def health_screen(db, user_id):
    """Render an optional, resumable, user-owned health intake."""
    service = HealthService(db, user_id)
    profile = service.load()
    answers = profile["answers"]
    step = min(profile["step"], len(ONBOARDING_STEPS) - 1)

    st.title("Your Health Journey")
    st.caption("Private wellness onboarding · optional questions · not medical care")
    if profile["completed_at"]:
        st.success("Your starting profile is saved. You can update it below.")
    st.progress((step + 1) / len(ONBOARDING_STEPS))
    st.caption(f"Step {step + 1} of {len(ONBOARDING_STEPS)}")

    with st.form(f"health_onboarding_{step}"):
        updates = {}
        if step == 0:
            st.subheader("About you")
            st.write("Only share what you feel comfortable recording.")
            age = st.number_input("Age (0 = skip)", 0, 120, int(answers.get("age") or 0))
            height = st.number_input("Height in centimeters (0 = skip)", 0.0, 250.0, float(answers.get("height_cm") or 0.0))
            weight = st.number_input("Starting weight in pounds (0 = skip)", 0.0, 1000.0, float(answers.get("starting_weight_lb") or 0.0))
            activity = st.selectbox("Usual activity", ACTIVITY, index=ACTIVITY.index(answers.get("activity_level", ACTIVITY[0])) if answers.get("activity_level") in ACTIVITY else 0)
            updates = {"age": age or None, "height_cm": height or None, "starting_weight_lb": weight or None, "activity_level": activity}
        elif step == 1:
            st.subheader("Your priorities")
            updates["priorities"] = st.multiselect("What would you like to work on?", PRIORITIES, default=[x for x in answers.get("priorities", []) if x in PRIORITIES])
        elif step == 2:
            st.subheader("Sleep")
            st.write("Describe your usual routine; estimates are fine.")
            updates["usual_bedtime"] = st.text_input("Typical bedtime (e.g., 11:30 PM)", answers.get("usual_bedtime", ""), max_chars=40)
            updates["usual_wake_time"] = st.text_input("Typical wake time", answers.get("usual_wake_time", ""), max_chars=40)
            updates["sleep_quality"] = st.slider("How rested do you usually feel?", 1, 10, int(answers.get("sleep_quality") or 5))
        elif step == 3:
            st.subheader("Sleep therapy")
            uses = st.selectbox("Do you use CPAP?", ["Prefer not to say", "Yes", "No"], index=["Prefer not to say", "Yes", "No"].index(answers.get("uses_cpap", "Prefer not to say")) if answers.get("uses_cpap") in ["Prefer not to say", "Yes", "No"] else 0)
            updates["uses_cpap"] = uses
            st.info("CPAP and sleep-report PDF uploads are planned for the next Phase 1 release.")
        elif step == 4:
            st.subheader("Health context (optional)")
            updates["medications"] = st.text_area("Medications you want to record", answers.get("medications", ""), max_chars=1500)
            updates["supplements"] = st.text_area("Supplements", answers.get("supplements", ""), max_chars=1500)
            updates["health_notes"] = st.text_area("Other health context or limitations", answers.get("health_notes", ""), max_chars=2000)
            st.caption("Your answers are stored in your configured Compass database, not encrypted separately.")
        elif step == 5:
            st.subheader("Daily life")
            updates["barriers"] = st.text_area("What makes routines difficult?", answers.get("barriers", ""), max_chars=2000)
            updates["personal_time_minutes"] = st.number_input("Personal downtime you would like each day (minutes)", 0, 600, int(answers.get("personal_time_minutes") or 0))
        else:
            st.subheader("Your starting plan")
            st.write("Choose a few realistic goals. You can change them later.")
            updates["goals"] = st.text_area("My starting goals", answers.get("goals", ""), max_chars=3000, placeholder="For example: use CPAP whenever sleeping; walk 10 minutes after lunch.")
            st.caption("Compass does not diagnose conditions or change treatment.")

        back, next_col = st.columns(2)
        go_back = back.form_submit_button("Back", disabled=step == 0)
        go_next = next_col.form_submit_button("Save and finish" if step == 6 else "Save and continue", type="primary")

    if go_back:
        service.save(answers, step - 1)
        st.rerun()
    if go_next:
        service.save({**answers, **updates}, min(step + 1, 6), completed=step == 6)
        st.rerun()
