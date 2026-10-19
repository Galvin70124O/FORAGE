"""Signed-in user context and cached personal data for the daily-use pages and the My data source.

Reads are cached for 60 seconds per user (st.cache_data, ttl=60) so pages do
not hit Neon on every rerun; `saved()` must be called after every write and
clears that cache, so the next page shows the change immediately.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from identity import ALLOWED, NOT_ALLOWED
from pantry import UNLOCK, analysis_frame, coverage, unlocked
from services import session
from store import Store
from ui.components import empty_state


def require_user() -> tuple[Store, int]:
    """(store, user_id) for the current person, or render the right screen and stop the page."""
    if session.current_mode() == "misconfigured":
        empty_state("Personal pages are not available",
                    "Sign-in is configured but no database is. Add [connections.sql] to the secrets "
                    "(see docs/deploy.md). The Insights pages still work.")
        st.stop()
    status, person = session.access_status()
    if status == NOT_ALLOWED:
        session.render_not_allowed_page(person)
        st.stop()
    if status != ALLOWED:
        session.render_sign_in_page()
        st.stop()
    db, uid = session.store(), session.user_id()
    if db is None or uid is None:
        empty_state("The database is not reachable", st.session_state.get("store_error", "Try again in a minute."))
        st.stop()
    session.demo_banner()
    return db, uid


@st.cache_data(ttl=60, show_spinner=False)
def _read(kind: str, user_id: int) -> pd.DataFrame:
    db = session.store()
    return {"purchases": db.purchases, "checks": db.checks, "foods": db.foods}[kind](user_id)


def purchases(user_id: int) -> pd.DataFrame:
    return _read("purchases", user_id)


def checks(user_id: int) -> pd.DataFrame:
    return _read("checks", user_id)


def foods(user_id: int) -> pd.DataFrame:
    return _read("foods", user_id)


def saved(message: str) -> None:
    """Call after every write: clears the cached reads and queues a confirmation toast for the next run."""
    _read.clear()
    st.session_state["toast"] = message


queue_toast = saved  # older name used by some pages


def toast_pending() -> None:
    """Show a toast queued before the last rerun."""
    if message := st.session_state.pop("toast", None):
        st.toast(message)


def personal_data() -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """(purchases, checks) of the current user, or None when personal data is unavailable."""
    if not session.personal_available():
        return None
    uid = session.user_id()
    if uid is None or session.store() is None:
        return None
    return purchases(uid), checks(uid)


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
