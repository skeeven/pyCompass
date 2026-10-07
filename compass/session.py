"""Bound the lifetime of authenticated Streamlit sessions."""

import time


def start_session(state, user_id):
    """Remove stale account data before recording an authenticated login."""
    state.clear()
    state["user_id"] = user_id
    state["last_activity"] = time.time()


def check_session(state, timeout_minutes, now=None):
    """Expire idle sessions on the next interaction and clear all state."""
    if "user_id" not in state:
        return False
    current = time.time() if now is None else now
    previous = state.get("last_activity", current)
    if current - previous >= timeout_minutes * 60:
        state.clear()
        return False
    state["last_activity"] = current
    return True
