"""Who is using FORAGE and where their data lives, decided from the secrets alone.

Modes:
    online      [auth] and [connections.sql] are set: Google sign-in, Neon Postgres.
    single_user no [auth]: one local user. With no database configured the data
                goes to a local SQLite file ("demo mode", temporary online).

The local single user is the only identity that does not come from Google, and
`resolve_identity` makes it impossible whenever [auth] is present: then the
only way in is a signed-in Google account.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

LOCAL_EMAIL = "local-user@forage.local"
LOCAL_NAME = "Local user"


@dataclass(frozen=True)
class Identity:
    email: str
    name: str
    local: bool = False


def auth_configured(secrets: Mapping) -> bool:
    return "auth" in secrets


def database_configured(secrets: Mapping) -> bool:
    connections = secrets.get("connections", {}) if hasattr(secrets, "get") else {}
    return "sql" in connections


def mode(secrets: Mapping) -> str:
    if auth_configured(secrets) and database_configured(secrets):
        return "online"
    if auth_configured(secrets):
        return "misconfigured"  # sign-in without a database: personal pages stay closed
    return "single_user"


def resolve_identity(secrets: Mapping, user: Mapping | None) -> Identity | None:
    """The current user, or None if they must sign in first.

    `user` is st.user as a mapping (is_logged_in, email, name). When [auth] is
    configured nothing but a signed-in user with an email is accepted.
    """
    if auth_configured(secrets):
        if user and user.get("is_logged_in") and user.get("email"):
            return Identity(email=str(user["email"]).lower(), name=str(user.get("name") or user["email"]))
        return None
    return Identity(email=LOCAL_EMAIL, name=LOCAL_NAME, local=True)
