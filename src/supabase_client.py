"""One safe, reusable entry point for the public Supabase client."""

from __future__ import annotations

import base64
import json

import streamlit as st


class SupabaseConfigurationError(RuntimeError):
    """Raised when local Supabase settings have not been configured."""


def _is_safe_publishable_key(key: str) -> bool:
    """Accept public Supabase keys and reject privileged key types locally.

    Current Supabase publishable keys begin with ``sb_publishable_``. Older
    projects can use an anonymous JWT, whose role must be ``anon``.  The
    checks deliberately inspect only key metadata and never expose the key.
    """
    key = key.strip()
    if key.startswith("sb_publishable_"):
        return True
    if key.startswith("sb_secret_") or key.lower().startswith(("service_role", "secret_")):
        return False

    # Legacy anon keys are JWTs. Decode the payload without verifying it: this
    # is only a local type guard; Supabase verifies the key when it is used.
    parts = key.split(".")
    if len(parts) != 3:
        return False
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False
    return claims.get("role") == "anon"


def get_supabase_client():
    """Create a public-key client from Streamlit secrets when configured.

    A new client is intentionally created for each operation.  Its session is
    restored from the current Streamlit session by ``auth.py``, preventing one
    browser user's auth state from ever being shared with another user.
    """
    try:
        url = str(st.secrets["SUPABASE_URL"]).strip()
        publishable_key = str(st.secrets["SUPABASE_PUBLISHABLE_KEY"]).strip()
    except (KeyError, FileNotFoundError) as error:
        raise SupabaseConfigurationError(
            "Supabase has not been configured. Add SUPABASE_URL and "
            "SUPABASE_PUBLISHABLE_KEY to .streamlit/secrets.toml."
        ) from error

    if (
        not url
        or not publishable_key
        or "your-project" in url
        or publishable_key == "your-publishable-key"
        or not _is_safe_publishable_key(publishable_key)
    ):
        raise SupabaseConfigurationError(
            "Supabase has not been configured with a valid public URL and "
            "publishable key. Do not use a secret or service-role key."
        )

    try:
        from supabase import create_client
    except ImportError as error:
        raise SupabaseConfigurationError(
            "The Supabase client is unavailable. Install the project's "
            "requirements before starting FORAGE."
        ) from error

    return create_client(url, publishable_key)
