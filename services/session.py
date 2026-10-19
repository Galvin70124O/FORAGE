"""Mode, identity and the per-user store for the running Streamlit session.

Nothing here writes files when the app is online: personal data goes to the
database in [connections.sql]. Only single-user mode without a database uses a
local SQLite file, and the app says so with a "Demo mode" banner.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from sqlalchemy import create_engine, inspect, text

from identity import Identity, auth_configured, database_configured, mode, resolve_identity
from store import Store, normalise_database_url

LOCAL_DB = Path(__file__).resolve().parent.parent / "data" / "forage_local.db"


def secrets() -> dict:
    """st.secrets as a plain dict, or {} when there is no secrets file (never raises, never logged)."""
    try:
        return st.secrets.to_dict()
    except Exception:
        return {}


def current_mode() -> str:
    return mode(secrets())


def _user_mapping() -> dict | None:
    try:
        return dict(st.user.to_dict()) if hasattr(st.user, "to_dict") else dict(st.user)
    except Exception:
        return None


def identity() -> Identity | None:
    return resolve_identity(secrets(), _user_mapping())


@st.cache_resource(show_spinner="Waking up the database...")
def _store(url: str, local: bool) -> Store:
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)
    store = Store(engine)
    if local:
        LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
        store.create_tables()
    with engine.connect() as conn:  # first round trip wakes a suspended Neon compute
        conn.execute(text("SELECT 1"))
    return store


def store() -> Store | None:
    """The personal-data store, or None if the database cannot be reached or is not initialised."""
    config = secrets()
    if database_configured(config):
        url, local = normalise_database_url(config["connections"]["sql"]["url"]), False
    else:
        url, local = f"sqlite:///{LOCAL_DB.as_posix()}", True
    try:
        result = _store(url, local)
    except Exception:
        st.session_state["store_error"] = "The database could not be reached. Try again in a minute."
        return None
    if not local and "purchases" not in inspect(result.engine).get_table_names():
        st.session_state["store_error"] = "The database has no FORAGE tables yet. Run scripts/init_db.py once."
        return None
    return result


def user_id() -> int | None:
    """The signed-in (or local) user's id in the store, cached for the session."""
    person = identity()
    if person is None:
        return None
    if st.session_state.get("user_email") != person.email:
        db = store()
        if db is None:
            return None
        st.session_state["user_id"] = db.user_id_for(person.email, person.name)
        st.session_state["user_email"] = person.email
    return st.session_state["user_id"]


def personal_available() -> bool:
    """Whether personal pages can be used in this session right now."""
    return identity() is not None and current_mode() != "misconfigured"


def render_account() -> None:
    """Sidebar block: signed-in user and Log out, a sign-in button, or the demo-mode notice."""
    config = secrets()
    person = identity()
    if auth_configured(config):
        if person is None:
            st.caption("Sign in to log your food. Insights are open to everyone.")
            st.button("Sign in with Google", on_click=st.login, type="primary", width="stretch")
        else:
            st.caption(f"Signed in as **{person.name}**  \n{person.email}")
            st.button("Log out", on_click=st.logout, width="stretch")
    elif not database_configured(config):
        st.caption("Single local user. No sign-in configured.")


def demo_banner() -> None:
    """Shown on personal pages when no database is configured."""
    if not database_configured(secrets()) and not auth_configured(secrets()):
        st.info("Demo mode, data is temporary and resets. No database is configured, so entries are kept in a "
                "local file on this machine only.")
