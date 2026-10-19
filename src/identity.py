"""Who is using FORAGE and where their data lives, decided from the secrets alone.

Modes:
    online      [auth] and [connections.sql] are set: Google sign-in, Neon Postgres.
    single_user no [auth]: one local user. With no database configured the data
                goes to a local SQLite file ("demo mode", temporary online).

When [auth] is set, access needs BOTH a signed-in Google account AND its email
in ALLOWED_EMAILS (a list in the secrets). A missing or empty allowlist lets
nobody in, so a misconfigured deployment fails closed. The local single user is
the only identity that does not come from Google, and `access` makes it
impossible whenever [auth] is present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

LOCAL_EMAIL = "local-user@forage.local"
LOCAL_NAME = "Local user"
SIGN_IN, NOT_ALLOWED, ALLOWED = "sign_in", "not_allowed", "allowed"


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


def allowed_emails(secrets: Mapping) -> set[str]:
    raw = secrets.get("ALLOWED_EMAILS", []) if hasattr(secrets, "get") else []
    if isinstance(raw, str):
        raw = raw.replace(";", ",").split(",")
    return {str(email).strip().lower() for email in raw if str(email).strip()}


def mode(secrets: Mapping) -> str:
    if auth_configured(secrets) and database_configured(secrets):
        return "online"
    if auth_configured(secrets):
        return "misconfigured"  # sign-in without a database: personal pages stay closed
    return "single_user"


def access(secrets: Mapping, user: Mapping | None) -> tuple[str, Identity | None]:
    """(status, identity): status is "allowed", "sign_in" or "not_allowed".

    `user` is st.user as a mapping (is_logged_in, email, name).
    """
    if not auth_configured(secrets):
        return ALLOWED, Identity(email=LOCAL_EMAIL, name=LOCAL_NAME, local=True)
    if not (user and user.get("is_logged_in") and user.get("email")):
        return SIGN_IN, None
    person = Identity(email=str(user["email"]).strip().lower(), name=str(user.get("name") or user["email"]))
    return (ALLOWED, person) if person.email in allowed_emails(secrets) else (NOT_ALLOWED, person)


def resolve_identity(secrets: Mapping, user: Mapping | None) -> Identity | None:
    """The person who may use the personal pages, or None (must sign in, or not on the allowlist)."""
    status, person = access(secrets, user)
    return person if status == ALLOWED else None
