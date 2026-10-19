"""Signed-in user context and personal data for the daily-use pages and the My data source."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pantry import UNLOCK, analysis_frame, coverage, unlocked
from services import session
from store import Store
from ui.components import empty_state


def require_user() -> tuple[Store, int]:
    """(store, user_id) for the current person, or render the right empty state and stop the page."""
    mode = session.current_mode()
    if mode == "misconfigured":
        empty_state("Personal pages are not available",
                    "Sign-in is configured but no database is. Add [connections.sql] to the secrets "
                    "(see docs/deploy.md). The Insights pages still work.")
        st.stop()
    if session.identity() is None:
        empty_state("Sign in to log your food",
                    "FORAGE keeps each person's purchases and pantry checks private to their Google account. "
                    "The Insights pages are open without signing in.")
        st.button("Sign in with Google", on_click=st.login, type="primary")
        st.stop()
    db, uid = session.store(), session.user_id()
    if db is None or uid is None:
        empty_state("The database is not reachable", st.session_state.get("store_error", "Try again in a minute."))
        st.stop()
    session.demo_banner()
    return db, uid


def toast_pending() -> None:
    """Show a toast queued before the last rerun."""
    if message := st.session_state.pop("toast", None):
        st.toast(message)


def queue_toast(message: str) -> None:
    st.session_state["toast"] = message


def personal_data() -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """(purchases, checks) of the current user, or None when personal data is unavailable."""
    if not session.personal_available():
        return None
    db, uid = session.store(), session.user_id()
    if db is None or uid is None:
        return None
    return db.purchases(uid), db.checks(uid)


def personal_frame() -> pd.DataFrame | None:
    data = personal_data()
    return None if data is None else analysis_frame(*data)


def personal_coverage() -> dict:
    data = personal_data()
    return coverage(*data) if data is not None else {}


def gate(feature: str) -> tuple[bool, bool, str]:
    """(shown, reliable, note) for a personal analysis (see pantry.UNLOCK)."""
    assert feature in UNLOCK, feature
    return unlocked(feature, personal_coverage())
