"""Account recovery forms; no tokens or provider responses are displayed."""

import streamlit as st

from compass.recovery import REQUEST_MESSAGE


def link_screen(recovery):
    """Clear a link from the URL and require explicit confirmation."""
    if "account_token" in st.query_params:
        token = st.query_params.get("account_token", "")
        purpose = st.query_params.get("account_action", "")
        st.session_state.clear()
        st.session_state["account_link"] = (token, purpose)
        st.query_params.clear()
    link = st.session_state.get("account_link")
    if not link:
        return
    token, purpose = link
    st.title("Reset your password" if purpose == "reset" else "Verify email")
    with st.form("account_link_form"):
        password = ""
        confirm = ""
        if purpose == "reset":
            password = st.text_input("New password", type="password")
            confirm = st.text_input("Confirm new password", type="password")
        st.caption("This link expires after 30 minutes and works once.")
        if st.form_submit_button(
            "Set new password" if purpose == "reset" else "Verify my email"
        ):
            if password != confirm:
                st.error("Your passwords do not match.")
            else:
                try:
                    recovery.consume(token, purpose, password)
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error(
                        "This action could not be completed. Try again later."
                    )
                else:
                    st.session_state.clear()
                    st.success(
                        "Password updated. Sign in with your new password."
                        if purpose == "reset"
                        else "Email verified. You can now sign in."
                    )
    if st.button("Back to sign in"):
        st.session_state.clear()
        st.rerun()
    st.stop()


def forgot_password(recovery, enabled):
    """Expose the same result for known, unknown and unverified mailboxes."""
    with st.expander("Forgot password?"):
        st.caption(
            "Use your verified recovery email. If you have not added one, "
            "contact the app owner to arrange identity-verified recovery."
        )
        if not enabled:
            st.info("Email recovery has not been configured by the app owner.")
        with st.form("forgot_password"):
            email = st.text_input("Recovery email", key="reset_email")
            if st.form_submit_button("Send reset link", disabled=not enabled):
                try:
                    recovery.request_reset(email)
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error(
                        "Recovery is temporarily unavailable. Try again later."
                    )
                else:
                    st.success(REQUEST_MESSAGE)


def account_screen(auth, recovery, user_id, enabled):
    """Reauthenticate before email enrollment or a password change."""
    security = auth.security(user_id)
    with auth.db.connect() as conn:
        username = conn.execute(
            "SELECT username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()[0]
    st.title("Account security")
    st.subheader("Recovery email")
    if security["email"]:
        st.write(f"Verified email: {security['email']}")
    else:
        st.info(
            "Add and verify a recovery email before you need a password reset."
        )
    st.caption(
        "A new address replaces your recovery email only after verification. "
        "Verification emails include a one-use link, "
        "not your wellness records."
    )
    with st.form("recovery_email"):
        email = st.text_input("Email address", key="enroll_email")
        password = st.text_input(
            "Current password", type="password", key="enroll_password"
        )
        if st.form_submit_button(
            "Send verification link", disabled=not enabled
        ):
            try:
                recovery.request_verification(user_id, email, password)
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error(
                    "Verification is temporarily unavailable. Try again later."
                )
            else:
                st.success(
                    "Verification link sent. Check your inbox and spam."
                )
    if not enabled:
        st.info("Email recovery has not been configured by the app owner.")
    st.subheader("Change password")
    with st.form("change_password"):
        current = st.text_input(
            "Current password", type="password", key="change_current"
        )
        new = st.text_input("New password", type="password", key="change_new")
        confirm = st.text_input(
            "Confirm new password", type="password", key="change_confirm"
        )
        st.caption("Use 12–256 characters. You will need to sign in again.")
        if st.form_submit_button("Change password"):
            if new != confirm:
                st.error("Your passwords do not match.")
            else:
                try:
                    recovery.change_password(user_id, username, current, new)
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error(
                        "Password change is unavailable. Try again later."
                    )
                else:
                    st.session_state.clear()
                    st.success(
                        "Password changed. Sign in with your new password."
                    )
                    st.stop()
