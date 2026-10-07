"""Run pyCompass with: streamlit run app.py."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from compass.auth import AuthService
from compass.checkin import CONTEXTS, EMOTIONS
from compass.config import Settings
from compass.db import Database
from compass.journal import filter_entries
from compass.reflection import (
    PROMPTS,
    ReflectionService,
    activity,
    chat_context,
    local_summary,
    weekly_context,
)
from compass.repository import Repository
from compass.session import check_session, start_session
from compass.trends import RATINGS, trend_summary

st.set_page_config(
    page_title="Compass · Find your direction",
    page_icon="🧭",
    layout="centered",
)
st.markdown(
    """<style>
    .stApp {background: #f7faf8;}
    h1, h2, h3 {color: #214e43;}
    .block-container {max-width: 850px; padding-top: 2rem;}
    div[data-testid="stMetric"] {background: #eaf3ef; padding: 1rem;
      border-radius: 12px;}
    </style>""",
    unsafe_allow_html=True,
)
try:
    secrets = dict(st.secrets)
except FileNotFoundError:
    secrets = {}
except Exception:
    st.error("Cannot read secrets.toml. Check its TOML formatting.")
    st.stop()
try:
    settings = Settings.load(secrets)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
db = Database(settings)
try:
    db.initialize()
except ValueError as exc:
    st.error(str(exc))
    st.stop()
except Exception:
    st.error("Cannot open the database. Check your configuration.")
    st.stop()
auth = AuthService(db)
try:
    today = datetime.now(ZoneInfo(settings.timezone)).date()
except (ValueError, KeyError):
    st.error("APP_TIMEZONE must be a valid name, such as America/Denver.")
    st.stop()


def logout():
    """Clear the entire session to prevent data leaking between accounts."""
    st.session_state.clear()
    st.rerun()


def sign_in():
    """Present login and optional self-service registration."""
    st.title("🧭 Compass")
    st.write("A little space to understand yourself and find your direction.")
    tabs = st.tabs(
        ["Sign in", "Create account"]
        if settings.allow_registration
        else ["Sign in"]
    )
    with tabs[0], st.form("login"):
        username = st.text_input("Username", key="login_username")
        password = st.text_input(
            "Password", type="password", key="login_password"
        )
        if st.form_submit_button("Sign in", type="primary"):
            try:
                user_id = auth.login(username, password)
            except Exception:
                st.error("Sign-in is unavailable. Please try again later.")
                st.stop()
            if user_id:
                start_session(st.session_state, user_id)
                st.rerun()
            st.error(
                "Sign-in failed. Check your credentials or wait five "
                "minutes if you have made repeated attempts."
            )
    if settings.allow_registration:
        with tabs[1], st.form("register", clear_on_submit=True):
            username = st.text_input("Choose a username")
            password = st.text_input("Choose a password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            st.caption("Use 12+ characters. No email address is required.")
            if st.form_submit_button("Create account"):
                if password != confirm:
                    st.error("Your passwords do not match.")
                else:
                    try:
                        auth.register(username, password)
                        st.success("Account created. You can now sign in.")
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception:
                        st.error("Account creation failed. Please try again.")
    st.caption(
        "A personal wellness tool. No one monitors your entries. "
        "It does not provide diagnosis or treatment."
    )


had_session = "user_id" in st.session_state
if not check_session(st.session_state, settings.session_timeout_minutes):
    if had_session:
        st.info("Your session expired. Please sign in again.")
    sign_in()
    st.stop()
try:
    repo = Repository(db, st.session_state["user_id"])
except ValueError:
    logout()
ai = ReflectionService(settings)

with st.sidebar:
    st.title("🧭 Compass")
    page = st.radio(
        "Your space",
        [
            "Today",
            "Journal",
            "Companion",
            "Insights",
            "Weekly reflection",
            "Privacy & data",
        ],
    )
    st.caption("Pause. Notice. Choose a small next step.")
    if st.button("Sign out"):
        logout()
    with st.expander("Need urgent support?"):
        st.write(
            "If you are in immediate danger, contact local emergency "
            "services. In the U.S., call or text 988 for crisis support. "
            "This app is not monitored."
        )


def ai_consent(key, description):
    """Require consent on the feature screen before each AI action."""
    st.caption(description)
    return st.checkbox("I agree to send this context to OpenAI", key=key)


def run_reflection(context, kind):
    """Handle provider failures without exposing secrets or journal data."""
    try:
        with st.spinner("Making space for reflection…"):
            result = ai.review(context, observation=kind == "observation")
        repo.add_insight(result, kind)
        st.success("Saved for your review.")
        st.markdown(result)
    except Exception:
        st.error(
            "Reflection could not be completed. Check your API key, model, "
            "and billing, or try again later. Your entries are still saved."
        )


if page == "Today":
    st.title("How are you arriving today?")
    st.caption(today.strftime("%A, %B %d, %Y"))
    existing = next(
        (
            row
            for row in repo.rows("checkins")
            if row["day"] == today.isoformat()
        ),
        {},
    )
    st.write("Start with the ratings. Everything else is optional.")
    if existing:
        st.caption("Today's check-in is saved. You can update it below.")
    with st.form("checkin"):
        st.caption("1 = very low mood · 10 = very good mood")
        mood = st.slider("Mood · low to high", 1, 10, existing.get("mood", 5))
        st.caption("1 = exhausted · 10 = energized")
        energy = st.slider("Energy", 1, 10, existing.get("energy", 5))
        st.caption("1 = relaxed · 10 = extremely stressed")
        stress = st.slider("Stress", 1, 10, existing.get("stress", 5))
        sleep = st.number_input(
            "Hours of sleep",
            0.0,
            24.0,
            float(existing.get("sleep", 7.0)),
            0.5,
        )
        note = st.text_area(
            "What is on your mind?",
            existing.get("note", ""),
            max_chars=2000,
        )
        with st.expander("Add a little context (optional)"):
            emotions = st.multiselect(
                "What feelings are present?",
                EMOTIONS,
                default=json.loads(existing.get("emotions", "[]")),
            )
            contexts = st.multiselect(
                "What is influencing today?",
                CONTEXTS,
                default=json.loads(existing.get("contexts", "[]")),
            )
            needs = st.text_area(
                "What do I need today?",
                existing.get("needs", ""),
                placeholder="Rest, support, connection, space…",
                max_chars=1000,
            )
        st.subheader("One small thing")
        st.info(activity(today))
        activity_done = st.checkbox(
            "I completed today's activity",
            value=bool(existing.get("activity_done", 0)),
        )
        if st.form_submit_button("Save today's check-in", type="primary"):
            repo.save_checkin(
                today.isoformat(),
                mood,
                energy,
                stress,
                sleep,
                note,
                emotions=emotions,
                contexts=contexts,
                needs=needs,
                activity_done=activity_done,
            )
            st.success("Saved. You can update today's check-in anytime.")

elif page == "Journal":
    st.title("Your journal")
    st.write("Write freely or choose a few prompts. Skip any prompt you like.")
    mode = st.selectbox("Writing style", ["Free writing", *PROMPTS])
    if st.session_state.pop("journal_saved", False):
        st.success("Your entry is saved.")
    for key in st.session_state.pop("journal_clear_keys", []):
        st.session_state.pop(key, None)
    draft_keys = ["journal_title", "journal_tags", "journal_body"]
    draft_keys += [
        f"answer_{mode}_{i}" for i in range(len(PROMPTS.get(mode, [])))
    ]
    with st.form("journal"):
        title = st.text_input("Title", max_chars=120, key="journal_title")
        if mode == "Free writing":
            body = st.text_area(
                "Start wherever you are",
                height=230,
                max_chars=12000,
                key="journal_body",
            )
        else:
            answers = [
                st.text_area(prompt, key=f"answer_{mode}_{i}", max_chars=3500)
                for i, prompt in enumerate(PROMPTS[mode])
            ]
            body = "\n\n".join(
                f"{prompt}\n{answer}"
                for prompt, answer in zip(PROMPTS[mode], answers)
                if answer.strip()
            )
        tags = st.text_input(
            "Tags (comma separated)", max_chars=300, key="journal_tags"
        )
        if st.form_submit_button("Save entry", type="primary"):
            try:
                repo.add_journal(title.strip() or mode, body, tags)
                st.session_state["journal_clear_keys"] = draft_keys
                st.session_state["journal_saved"] = True
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error(
                    "Could not save. Your draft is still here. Try again."
                )
    st.caption("Drafts last for this session. Save before signing out.")
    st.subheader("Past entries")
    all_entries = repo.rows("journal")
    query = st.text_input("Search your journal", key="journal_search")
    window = st.selectbox(
        "Entry dates",
        ["All time", "Last 7 days", "Last 30 days", "Last 90 days"],
    )
    tag_options = sorted(
        {
            tag.strip()
            for row in all_entries
            for tag in row["tags"].split(",")
            if tag.strip()
        },
        key=str.casefold,
    )
    selected_tags = st.multiselect("Filter by tags", tag_options)
    days = {
        "All time": None,
        "Last 7 days": 7,
        "Last 30 days": 30,
        "Last 90 days": 90,
    }[window]
    entries = filter_entries(
        all_entries, query, selected_tags, days, today, settings.timezone
    )
    st.caption(f"Showing {len(entries)} of {len(all_entries)} entries.")
    if not all_entries:
        st.info("Your first saved entry will appear here.")
    elif not entries:
        st.info("No entries match. Try changing your search or filters.")
    for row in entries:
        local_date = (
            datetime.fromisoformat(row["created_at"])
            .astimezone(ZoneInfo(settings.timezone))
            .strftime("%b %d, %Y · %I:%M %p")
        )
        with st.expander(f"{local_date} · {row['title']}"):
            st.text(row["body"])
            if row["tags"]:
                st.caption(row["tags"])
            st.caption("Edit this entry")
            with st.form(f"edit_journal_{row['id']}"):
                edit_title = st.text_input(
                    "Title", row["title"], max_chars=120
                )
                edit_body = st.text_area(
                    "Entry", row["body"], height=230, max_chars=12000
                )
                edit_tags = st.text_input(
                    "Tags (comma separated)", row["tags"], max_chars=300
                )
                if st.form_submit_button("Save changes"):
                    try:
                        repo.update_journal(
                            row["id"], edit_title, edit_body, edit_tags
                        )
                        st.session_state["journal_saved"] = True
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception:
                        st.error("Could not update. Try again.")
            confirmed = st.checkbox(
                "Confirm deletion of this entry", key=f"confirm_{row['id']}"
            )
            if st.button(
                "Delete entry",
                key=f"delete_{row['id']}",
                disabled=not confirmed,
            ):
                repo.delete("journal", row["id"])
                st.rerun()

elif page == "Companion":
    st.title("Talk it through")
    st.write("A reflective conversation, one question at a time.")
    if not settings.openai_api_key:
        st.info("Add OPENAI_API_KEY to enable the companion.")
    consent = ai_consent(
        "chat_consent",
        "Each message sends your new text and up to 12 "
        "previous chat messages. Journal entries are not included. "
        "API use incurs charges on your OpenAI account.",
    )
    history = repo.rows("messages")
    for row in history[-40:]:
        with st.chat_message(row["role"]):
            st.markdown(row["content"])
    if st.session_state.pop("companion_clear_draft", False):
        st.session_state.pop("companion_draft", None)
    text = st.text_area(
        "What would you like to explore?",
        max_chars=3000,
        key="companion_draft",
        height=100,
    )
    with st.expander("Preview the context to be sent"):
        if text.strip():
            st.json(chat_context(history, text))
        else:
            st.caption("Write a message to preview its context.")
    st.caption(
        "Drafts last for this session. Only the last 12 chat messages "
        "and your new message are sent; check-ins and journals are excluded."
    )
    if st.button(
        "Send message",
        type="primary",
        key="companion_send",
        disabled=not (consent and settings.openai_api_key and text.strip()),
    ):
        # Recheck consent at the action boundary, including retries.
        if consent and settings.openai_api_key and text.strip():
            try:
                pending = st.session_state.get("companion_pending_reply")
                payload = chat_context(history, text)
                if pending and pending["context"] == payload:
                    reply = pending["reply"]
                else:
                    with st.spinner("Listening…"):
                        reply = ai.chat(history, text)
                    st.session_state["companion_pending_reply"] = {
                        "context": payload,
                        "reply": reply,
                    }
                repo.add_exchange(text.strip(), reply)
                st.session_state.pop("companion_pending_reply", None)
                st.session_state["companion_clear_draft"] = True
                st.rerun()
            except Exception:
                st.error(
                    "Could not complete your message. Your draft is still "
                    "here. Check API billing, model access or connection, "
                    "then try Send message again."
                )

elif page == "Insights":
    st.title("What am I learning about myself?")
    rows = repo.rows("checkins")
    if rows:
        days = st.selectbox("Chart window", [7, 30, 90], index=1)
        end_day = st.date_input(
            "Period ending",
            value=today,
            max_value=today,
            key="trend_end_day",
        )
        summary = trend_summary(rows, end_day, days)
        st.caption(
            f"{summary['start']:%b %d, %Y} – {end_day:%b %d, %Y} · "
            f"{len(summary['current'])} of {days} days recorded."
        )
        if summary["current"]:
            cols = st.columns(3)
            for col, key in zip(cols, RATINGS):
                change = summary["changes"][key]
                col.metric(
                    key.title(),
                    f"{summary['means'][key]:.1f}/10",
                    delta=f"{change:+.1f} points"
                    if change is not None
                    else None,
                    delta_color="inverse" if key == "stress" else "normal",
                )
            st.caption(
                "Averages use recorded days only. Higher mood and energy "
                "ratings mean more; higher stress means more stress."
            )
            st.caption(
                "Compared with "
                f"{summary['previous_start']:%b %d, %Y} – "
                f"{summary['previous_end']:%b %d, %Y}: "
                f"{summary['previous_count']} of {days} days recorded."
            )
            if not summary["previous_count"]:
                st.info("No check-ins in the previous period to compare yet.")
            else:
                st.caption(
                    "Different recording patterns can affect comparisons. "
                    "These changes describe your ratings, not their causes."
                )
            selected_ratings = st.multiselect(
                "Ratings to show",
                list(RATINGS),
                default=list(RATINGS),
                format_func=str.title,
            )
            style = st.selectbox(
                "Chart style", ["Daily points", "Trend lines"]
            )
            frame = pd.DataFrame(summary["current"])
            frame["day"] = pd.to_datetime(frame["day"])
            if selected_ratings:
                chart_data = frame.set_index("day")[selected_ratings]
                chart = (
                    st.scatter_chart
                    if style == "Daily points"
                    else st.line_chart
                )
                chart(chart_data, x_label="Day", y_label="Rating (1–10)")
                st.caption(
                    "Missing days are not filled in. Trend lines connect "
                    "recorded days; values between them are not measurements."
                )
            else:
                st.info("Choose at least one rating to show the chart.")
            with st.expander("View recorded days"):
                st.dataframe(
                    frame[["day", *RATINGS, "sleep"]].rename(
                        columns={
                            "day": "Day",
                            "mood": "Mood",
                            "energy": "Energy",
                            "stress": "Stress",
                            "sleep": "Sleep (hours)",
                        }
                    ),
                    hide_index=True,
                )
        else:
            st.info(
                "No check-ins in this date window. Try an earlier end date."
            )
    else:
        st.info("Save a check-in to start seeing your trends.")
    st.subheader("Explore the past seven days")
    st.caption("AI observations use the past seven days ending today.")
    context = weekly_context(repo, today)
    consent = ai_consent(
        "insight_consent",
        "Generate a tentative observation from the past "
        "seven days. Sends check-in ratings and notes, plus up to 20 "
        "journal entries (first 2,000 characters each). Check-in "
        "context includes emotion tags, context tags, needs "
        "and activity completion.",
    )
    with st.expander("Preview the context to be sent"):
        st.json(context)
    if st.button(
        "Suggest an observation",
        disabled=not (
            consent
            and settings.openai_api_key
            and (context["checkins"] or context["journal"])
        ),
    ):
        run_reflection(context, "observation")
    st.subheader("Your observations")
    for row in reversed(repo.rows("insights")):
        if row["kind"] != "observation" or row["status"] == "dismissed":
            continue
        with st.container(border=True):
            st.markdown(row["content"])
            st.caption(f"{row['status'].title()} · {row['created_at'][:10]}")
            left, right = st.columns(2)
            if left.button("This fits", key=f"approve_{row['id']}"):
                repo.review_insight(row["id"], "approved")
                st.rerun()
            if right.button("Dismiss", key=f"dismiss_{row['id']}"):
                repo.review_insight(row["id"], "dismissed")
                st.rerun()

elif page == "Weekly reflection":
    st.title("A moment to look back")
    end_day = st.date_input("Week ending", today, max_value=today)
    context = weekly_context(repo, end_day)
    st.write(local_summary(context))
    consent = ai_consent(
        "weekly_consent",
        "An AI reflection sends this week's check-ins "
        "and notes, plus up to 20 journal entries (first 2,000 characters "
        "each), including check-in tags, needs and activity completion. "
        "Chat history is not included.",
    )
    with st.expander("Preview the context to be sent"):
        st.json(context)
    if st.button(
        "Generate weekly reflection",
        disabled=not (
            consent
            and settings.openai_api_key
            and (context["checkins"] or context["journal"])
        ),
    ):
        run_reflection(context, "weekly")
    for row in reversed(repo.rows("insights")):
        if row["kind"] == "weekly":
            with st.expander(f"Reflection · {row['created_at'][:10]}"):
                st.markdown(row["content"])
                if st.button("Delete reflection", key=f"week_{row['id']}"):
                    repo.delete("insights", row["id"])
                    st.rerun()

elif page == "Privacy & data":
    st.title("Your data, your choices")
    st.write(
        "With no cloud configuration, your records stay in the local "
        "SQLite file. SQLiteCloud stores them remotely when configured. "
        "Journal text is not encrypted by this app. Protect your computer "
        "and backups, and control access to your database."
    )
    st.write(
        "AI features send only the context described on each screen. "
        "Requests set store=False, which disables stored API responses; "
        "it does not guarantee zero provider retention. "
        "Deleting records here does not delete database backups or "
        "provider logs. No analytics or advertising SDK is included."
    )
    st.download_button(
        "Export my data (JSON)",
        repo.export(),
        file_name="compass_export.json",
        mime="application/json",
    )
    if st.checkbox("I want to clear my companion conversation"):
        if st.button("Clear conversation"):
            for row in repo.rows("messages"):
                repo.delete("messages", row["id"])
            st.rerun()
    st.divider()
    st.warning("Deleting your account permanently removes its app records.")
    confirmation = st.text_input("Type DELETE to confirm account deletion")
    if st.button("Delete my account", disabled=confirmation != "DELETE"):
        repo.delete_account()
        logout()
