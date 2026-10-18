"""Streamlit guided onboarding for Compass Health."""

import streamlit as st

from compass.health import HealthService, ONBOARDING_STEPS
from compass.health_history import list_saved_reports, delete_saved_report
from compass.health_daily_ui import daily_screen, trends_screen
from compass.health_weekly_ui import weekly_health_screen
from compass.health_dashboard_ui import dashboard_screen
from compass.health_goals_ui import goals_screen, comparison_screen
from compass.health_reports import METRICS, extract_pdf_text, suggested_metrics, save_report
from datetime import date
from compass.resmed_ocr import recognize_resmed_pdf, parse_resmed_periods
from compass.sleep_cycle_ocr import recognize_sleep_cycle_pdf

PRIORITIES = ["Sleep", "Energy", "Weight", "Nutrition", "Movement", "Stress", "Other"]
ACTIVITY = ["Prefer not to say", "Mostly seated", "Lightly active", "Moderately active", "Very active"]


def health_screen(db, user_id):
    """Render an optional, resumable, user-owned health intake."""
    service = HealthService(db, user_id)
    profile = service.load()
    answers = profile["answers"]
    step = min(profile["step"], len(ONBOARDING_STEPS) - 1)

    st.title("Your Health Journey")
    dashboard_tab, onboarding_tab, daily_tab, goals_tab, trends_tab, weekly_tab, reports_tab, history_tab = st.tabs(
        ["Overview", "My health profile", "Daily check-in", "My goals", "Trends", "Weekly review", "Sleep report imports", "Health history"]
    )
    with dashboard_tab:
        dashboard_screen(db, user_id, date.today())
    with reports_tab:
        report_import_screen(db, user_id)
    with onboarding_tab:
        onboarding_screen(service, profile, answers, step)
    with history_tab:
        report_history_screen(db, user_id)
    with daily_tab:
        daily_screen(db, user_id, date.today())
    with goals_tab:
        goals_screen(db, user_id, date.today())
    with trends_tab:
        trends_screen(db, user_id, date.today())
        comparison_screen(db, user_id, date.today())
    with weekly_tab:
        weekly_health_screen(db, user_id, date.today())


def onboarding_screen(service, profile, answers, step):
    """Keep onboarding independent from report import state."""
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
            st.info("Your ResMed reports can be imported under Sleep report imports.")
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


def report_import_screen(db, user_id):
    st.subheader("Import a sleep report")
    st.caption("ResMed reports use OCR; Sleep Cycle uses embedded text or OCR when necessary. Original PDFs are not saved.")
    kind = st.selectbox("Report source", ["ResMed CPAP", "Sleep Cycle"])
    upload = st.file_uploader("Choose a PDF (8 MB maximum)", type=["pdf"])
    if upload is None:
        return
    if kind == "ResMed CPAP":
        resmed_review_screen(db, user_id, upload)
        return
    try:
        text = extract_pdf_text(upload.getvalue())
        extraction_method = "embedded PDF text"
    except ValueError as exc:
        # Only fall back when text is unavailable/unsupported; do not bypass
        # file size, password or page-count safety validation.
        if "No selectable text" not in str(exc) and "needs OCR" not in str(exc):
            st.warning(str(exc))
            return
        try:
            with st.spinner("Reading Sleep Cycle report visually (OCR)..."):
                text = recognize_sleep_cycle_pdf(upload.getvalue())
            extraction_method = "OCR"
        except ValueError as ocr_exc:
            st.warning(str(ocr_exc))
            return
    st.info(
        f"Read using {extraction_method}. Review the report text and enter "
        "the period covered. OCR and metric suggestions may be wrong."
    )
    with st.expander("View extracted text (not saved)", expanded=False):
        st.text_area("PDF text", text, height=220, disabled=True)
    suggestions = suggested_metrics(text)
    with st.form("confirm_health_pdf"):
        start = st.date_input("Report period starts", value=date.today())
        end = st.date_input("Report period ends", value=date.today())
        st.caption("These values describe the whole report period, not individual days.")
        selected = st.multiselect("Metrics to record", list(METRICS),
                                  format_func=lambda key: METRICS[key][0])
        metrics = {}
        for key in selected:
            metrics[key] = st.number_input(
                f"{METRICS[key][0]} ({METRICS[key][1]})",
                min_value=0.0,
                value=float(suggestions.get(key, 0.0)),
                step=0.1,
                key=f"report_metric_{key}",
            )
        confirmed = st.checkbox(
            "I checked the date range, units, and values against the original PDF."
        )
        submitted = st.form_submit_button("Save verified measurements")
    if submitted:
        if not selected:
            st.warning("Select at least one measurement to save.")
            return
        if not confirmed:
            st.warning("Please confirm the values, units, and date range before saving.")
            return
        try:
            save_report(db, user_id, upload.name, kind, start, end, metrics)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("Verified period measurements saved. The PDF was not stored.")


def resmed_review_screen(db, user_id, upload):
    """Present separately dated sections; never save without verification."""
    try:
        with st.spinner("Reading report visually (OCR)..."):
            text = recognize_resmed_pdf(upload.getvalue())
        periods = parse_resmed_periods(text)
    except ValueError as exc:
        st.error(str(exc))
        return
    if not periods:
        st.error("No dated ResMed report sections could be recognized. Nothing was saved.")
        return
    st.caption(
        f"Recognized {len(periods)} reporting period(s). "
        "Please compare all values to the PDF before saving."
    )
    with st.expander("OCR text for troubleshooting (not saved)"):
        st.text_area("Recognized text", text[:20000], disabled=True, height=180)
    with st.form("verify_resmed_periods"):
        confirmed_metrics = []
        for idx, period in enumerate(periods):
            st.subheader(
                f"{period['start']:%b %d, %Y} – {period['end']:%b %d, %Y}"
            )
            st.caption("Period summary, not measurements on individual days.")
            fields = {}
            for name, suggested in period["metrics"].items():
                label, unit = METRICS[name]
                denominator = period["denominators"].get(name)
                suffix = f" (out of {denominator} nights)" if denominator is not None else ""
                fields[name] = st.number_input(
                    f"{label} ({unit}){suffix}",
                    value=float(suggested),
                    min_value=0.0,
                    step=0.01 if name in {"ahi", "leak_l_min"} else 0.1,
                    key=f"resmed_{idx}_{name}",
                )
            confirmed_metrics.append(fields)
        confirmed = st.checkbox(
            "I checked each reporting period, value, and unit against the PDF."
        )
        submit = st.form_submit_button("Save verified report periods")
    if submit:
        if not confirmed:
            st.warning("Confirm the extracted measurements before saving.")
            return
        if any(not metrics for metrics in confirmed_metrics):
            st.warning("One or more periods have no recognized measurements.")
            return
        saved, skipped = 0, 0
        for period, metrics in zip(periods, confirmed_metrics):
            try:
                save_report(
                    db, user_id, upload.name, "ResMed CPAP",
                    period["start"], period["end"], metrics,
                    denominators=period["denominators"],
                )
            except ValueError as exc:
                if "already saved" in str(exc):
                    skipped += 1
                else:
                    st.error(f"{period['start']} – {period['end']}: {exc}")
            else:
                saved += 1
        if saved:
            st.success(f"Saved {saved} verified period(s). No PDF was retained.")
        if skipped:
            st.warning(
                f"Skipped {skipped} previously imported period(s). "
                "Delete existing records in Health history before replacing them."
            )


def report_history_screen(db, user_id):
    """Review verified reports after the upload session has ended."""
    st.subheader("Saved sleep reports")
    st.caption(
        "Each record summarizes its stated reporting period. "
        "Overlapping 30-, 90-, and 365-day periods are not separate daily measurements."
    )
    reports = list_saved_reports(db, user_id)
    if not reports:
        st.info("No saved reports yet. Import and verify a sleep report to see it here.")
        return

    st.caption(f"{len(reports)} saved reporting period(s)")
    for report in reports:
        with st.expander(
            f"{report['period_start']} to {report['period_end']} · "
            f"{report['report_type']}",
            expanded=False,
        ):
            st.caption(
                f"Source: {report['filename']} · "
                f"Imported {report['uploaded_at'][:10]} · "
                f"Status: {report['status']}"
            )
            rows = []
            for key, info in report["metrics"].items():
                label, unit = METRICS[key]
                value = info["value"]
                display = (
                    f"{value:.2f}" if key in {"ahi", "leak_l_min"}
                    else f"{value:.2f}" if key.endswith("_hours")
                    else str(int(value))
                )
                rows.append({
                    "Measurement": label,
                    "Value": display,
                    "Unit": unit,
                    "Details": info["source"],
                })
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.info("This reporting period has no recognized saved measurements.")
            st.caption("Delete an incorrect period before importing its replacement.")
            confirmation = st.checkbox(
                "I understand this permanently removes this report period and its metrics",
                key=f"confirm_report_delete_{report['id']}",
            )
            if st.button(
                "Delete report period",
                key=f"delete_report_{report['id']}",
                disabled=not confirmation,
            ):
                try:
                    delete_saved_report(db, user_id, report["id"])
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.success("Report period deleted.")
                    st.rerun()
