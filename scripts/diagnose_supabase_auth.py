r"""Minimal, credential-safe Supabase Auth transport diagnostic.

Run only with credentials supplied by the environment, never command history:
  $env:FORAGE_TEST_EMAIL = "an-inbox-you-control@example.com"
  $env:FORAGE_TEST_PASSWORD = "a-unique-test-password"
  .\.venv\Scripts\python.exe scripts\diagnose_supabase_auth.py

The script never prints supplied credentials, API keys, tokens, sessions, or
user details. It only attempts signup when both test environment variables are
set.
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from supabase_client import get_supabase_client  # noqa: E402


def safe_error(error: Exception) -> str:
    """Render only allow-listed error metadata and redact unexpected secrets."""
    message = str(getattr(error, "message", str(error)))
    message = re.sub(
        r"(?i)(password|access_token|refresh_token|apikey|api_key|authorization)\s*([=:])\s*[^\s,;]+",
        r"\1\2[redacted]",
        message,
    )
    message = re.sub(r"\beyJ[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+){2}\b", "[redacted-jwt]", message)
    return (
        f"type={type(error).__name__} "
        f"status={getattr(error, 'status', getattr(error, 'status_code', None))} "
        f"code={getattr(error, 'code', None)} message={message[:500]}"
    )


def main() -> int:
    try:
        client = get_supabase_client()
        hostname = urlparse(str(client.supabase_url)).hostname
        print(f"create_client: PASS target_hostname={hostname}")
    except Exception as error:
        print(f"create_client: FAIL {safe_error(error)}")
        return 1

    try:
        print(f"auth.get_session: PASS session_present={client.auth.get_session() is not None}")
    except Exception as error:
        print(f"auth.get_session: FAIL {safe_error(error)}")

    try:
        print(f"auth.get_user: PASS user_present={client.auth.get_user() is not None}")
    except Exception as error:
        print(f"auth.get_user: FAIL {safe_error(error)}")

    email = os.environ.get("FORAGE_TEST_EMAIL")
    password = os.environ.get("FORAGE_TEST_PASSWORD")
    if not email or not password:
        print("auth.sign_up: SKIPPED (set FORAGE_TEST_EMAIL and FORAGE_TEST_PASSWORD in the current shell)")
        return 0

    try:
        response = client.auth.sign_up({"email": email, "password": password})
        print(
            "auth.sign_up: PASS "
            f"user_returned={getattr(response, 'user', None) is not None} "
            f"session_returned={getattr(response, 'session', None) is not None}"
        )
        return 0
    except Exception as error:
        print(f"auth.sign_up: FAIL {safe_error(error)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
