"""Mode, identity, sign-in screens and the per-user store for the running Streamlit session.

Nothing here writes files when the app is online: personal data goes to the
database in [connections.sql] through st.connection("sql") (pool_pre_ping, so a
Neon compute that went to sleep is reconnected). Only single-user mode without
a database uses a local SQLite file, and the app says so with a "Demo mode" banner.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from sqlalchemy import inspect, text

from identity import ALLOWED, NOT_ALLOWED, Identity, access, auth_configured, database_configured, mode
from store import Store, normalise_database_url

LOCAL_DB = Path(__file__).resolve().parent.parent / "data" / "forage_local.db"
TAGLINE = "Log what you buy and check your pantry; FORAGE works out what you waste and what to buy."


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


def access_status() -> tuple[str, Identity | None]:
    return access(secrets(), _user_mapping())


def identity() -> Identity | None:
    status, person = access_status()
    return person if status == ALLOWED else None


@st.cache_resource(show_spinner="Waking up the database...")
def _store(online: bool) -> Store:
    if online:
        url = normalise_database_url(secrets()["connections"]["sql"]["url"])
        connection = st.connection("sql", type="sql", url=url, pool_pre_ping=True, pool_recycle=300)
    else:
        LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
        connection = st.connection("forage_local", type="sql", url=f"sqlite:///{LOCAL_DB.as_posix()}",
                                   pool_pre_ping=True)
    store = Store(connection.engine)
    if not online:
        store.create_tables()
    with connection.engine.connect() as conn:  # the first round trip wakes a suspended Neon compute
        conn.execute(text("SELECT 1"))
    return store


def store() -> Store | None:
    """The personal-data store, or None if the database cannot be reached or is not initialised."""
    online = database_configured(secrets())
    try:
        result = _store(online)
    except Exception:
        st.session_state["store_error"] = "The database could not be reached. Try again in a minute."
        return None
    if online and "purchases" not in inspect(result.engine).get_table_names():
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


def sign_in() -> None:
    st.login("google")


def render_sign_in_page() -> None:
    """The page shown in place of a personal page until the visitor signs in."""
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        st.markdown('<p class="fg-brand" style="font-size:1.4rem;margin-top:2rem">FORAGE</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="fg-purpose">{TAGLINE}</p>', unsafe_allow_html=True)
        st.button("Continue with Google", on_click=sign_in, type="primary", width="stretch")
        st.caption("Your purchases and pantry checks are private to your account. The Insights pages are open to "
                   "everyone without signing in.")


def render_not_allowed_page(person: Identity) -> None:
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        st.markdown('<p class="fg-brand" style="font-size:1.4rem;margin-top:2rem">FORAGE</p>', unsafe_allow_html=True)
        st.subheader("Access not enabled for this account")
        st.write(f"{person.email} is not on this FORAGE team's list. Ask the person who runs the app to add it, "
                 "or sign in with another Google account.")
        st.button("Log out", on_click=st.logout, width="stretch")


def render_account() -> None:
    """Sidebar block: signed-in user and Log out, a sign-in button, or the local-user note."""
    config = secrets()
    status, person = access_status()
    if auth_configured(config):
        if status == ALLOWED:
            st.caption(f"Signed in as **{person.name}**  \n{person.email}")
            st.button("Log out", on_click=st.logout, width="stretch")
        elif status == NOT_ALLOWED:
            st.caption(f"{person.email}: access not enabled.")
            st.button("Log out", on_click=st.logout, width="stretch")
        else:
            st.caption("Sign in to log your food. Insights are open to everyone.")
            st.button("Continue with Google", on_click=sign_in, type="primary", width="stretch")
    elif not database_configured(config):
        st.caption("Single local user. No sign-in configured.")


def demo_banner() -> None:
    """Shown on personal pages when no database is configured."""
    if not database_configured(secrets()) and not auth_configured(secrets()):
        st.info("Demo mode, data is temporary and resets. No database is configured, so entries are kept in a "
                "local file on this machine only.")
