"""Session-safe Supabase authentication helpers for the FORAGE UI."""

from __future__ import annotations

import logging
import re
from typing import Any

import streamlit as st

from supabase_client import SupabaseConfigurationError, get_supabase_client


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
AUTH_SESSION_KEYS = ("user", "user_id", "supabase_access_token", "supabase_refresh_token")
LOGGER = logging.getLogger(__name__)


def _safe_auth_error_details(error: Exception) -> dict[str, str | int | None]:
    """Return diagnostic fields without logging credentials or session data."""
    message = str(getattr(error, "message", str(error)))
    # Do not permit an unexpected upstream response to leak token/password-like
    # values into developer logs.
    message = re.sub(
        r"(?i)(password|access_token|refresh_token|apikey|api_key|authorization)\s*([=:])\s*[^\s,;]+",
        r"\1\2[redacted]",
        message,
    )
    message = re.sub(r"\beyJ[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+){2}\b", "[redacted-jwt]", message)
    message = re.sub(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[redacted-email]", message)
    return {
        "type": type(error).__name__,
        "status": getattr(error, "status", getattr(error, "status_code", None)),
        "code": getattr(error, "code", None),
        "message": message[:500],
    }


def _log_signup_failure(error: Exception) -> None:
    """Log only safe Supabase diagnostic metadata for local developer debugging."""
    details = _safe_auth_error_details(error)
    LOGGER.warning(
        "FORAGE Supabase signup failed: type=%s status=%s code=%s message=%s",
        details["type"], details["status"], details["code"], details["message"],
    )


def _attribute(value: Any, name: str, default=None):
    """Read values from the Pydantic response models used by supabase-py."""
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _clear_auth_state() -> None:
    for key in AUTH_SESSION_KEYS:
        st.session_state.pop(key, None)


def _store_authenticated_response(response: Any) -> bool:
    """Store only the authenticated user's Supabase-issued session in this UI session."""
    user = _attribute(response, "user")
    session = _attribute(response, "session")
    user_id = _attribute(user, "id")
    access_token = _attribute(session, "access_token")
    refresh_token = _attribute(session, "refresh_token")
    if not user_id or not access_token or not refresh_token:
        return False
    st.session_state.user = user
    st.session_state.user_id = str(user_id)
    st.session_state.supabase_access_token = access_token
    st.session_state.supabase_refresh_token = refresh_token
    return True


def validate_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(email.strip()))


def get_current_user():
    """Validate and restore the current user's Supabase session on reruns.

    ``get_user`` validates the access token with Supabase rather than trusting
    a UI-only flag.  An expired or invalid token returns the user to login.
    """
    access_token = st.session_state.get("supabase_access_token")
    refresh_token = st.session_state.get("supabase_refresh_token")
    if not access_token or not refresh_token:
        return None
    try:
        client = get_supabase_client()
        restored = client.auth.set_session(access_token, refresh_token)
        if _attribute(restored, "session"):
            _store_authenticated_response(restored)
        response = client.auth.get_user()
        user = _attribute(response, "user")
        if user and _attribute(user, "id"):
            st.session_state.user = user
            st.session_state.user_id = str(_attribute(user, "id"))
            return user
    except Exception:
        # An expired session is expected authentication state, not a UI error.
        pass
    _clear_auth_state()
    return None


def login(email: str, password: str) -> tuple[bool, str]:
    if not email or not password:
        return False, "Enter your email address and password."
    if not validate_email(email):
        return False, "Enter a valid email address."
    try:
        response = get_supabase_client().auth.sign_in_with_password(
            {"email": email.strip(), "password": password}
        )
        if _store_authenticated_response(response):
            return True, ""
        return False, "Please verify your email before logging in."
    except SupabaseConfigurationError as error:
        return False, str(error)
    except Exception:
        return False, "Invalid email or password."


def signup(name: str, email: str, password: str, confirmation: str) -> tuple[bool, str, bool]:
    """Create an account and report whether the user is authenticated now."""
    LOGGER.warning(
        "FORAGE signup entered: email_present=%s password_present=%s "
        "confirmation_present=%s name_present=%s",
        bool(email.strip()), bool(password), bool(confirmation), bool(name.strip()),
    )
    if not all([email.strip(), password, confirmation]):
        return False, "Enter your email address and password.", False
    if not validate_email(email):
        return False, "Enter a valid email address.", False
    if password != confirmation:
        return False, "Passwords do not match.", False
    if len(password) < 8:
        return False, "Use a password with at least 8 characters.", False
    try:
        credentials: dict[str, Any] = {"email": email.strip(), "password": password}
        # Name is optional profile metadata. It is not the auth identifier and
        # is omitted entirely when blank, so email/password signup stays simple.
        if name.strip():
            credentials["options"] = {"data": {"full_name": name.strip()}}
        LOGGER.warning("FORAGE signup client creation started")
        client = get_supabase_client()
        LOGGER.warning(
            "FORAGE signup client created; payload_shape=email,password,options=%s,"
            "metadata_keys=%s,email_redirect_to=%s",
            "options" in credentials,
            sorted(credentials.get("options", {}).get("data", {}).keys()),
            "email_redirect_to" in credentials.get("options", {}),
        )
        LOGGER.warning("FORAGE signup sign_up started")
        response = client.auth.sign_up(credentials)
        LOGGER.warning(
            "FORAGE signup sign_up returned: user_returned=%s session_returned=%s",
            _attribute(response, "user") is not None,
            _attribute(response, "session") is not None,
        )
        if _store_authenticated_response(response):
            return True, "Your account has been created.", True
        return True, "Your account was created. Please verify your email before logging in.", False
    except SupabaseConfigurationError as error:
        _log_signup_failure(error)
        return False, "Unable to create your account. Please try again.", False
    except Exception as error:
        _log_signup_failure(error)
        return False, "Unable to create your account. Please try again.", False


def logout() -> None:
    """End the current Supabase session, then remove local session references."""
    try:
        access_token = st.session_state.get("supabase_access_token")
        refresh_token = st.session_state.get("supabase_refresh_token")
        if access_token and refresh_token:
            client = get_supabase_client()
            client.auth.set_session(access_token, refresh_token)
            client.auth.sign_out()
    except Exception:
        # Local cleanup still protects this Streamlit session if the network is unavailable.
        pass
    finally:
        _clear_auth_state()
