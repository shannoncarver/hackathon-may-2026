#!/usr/bin/env python3
"""Shared infrastructure for LINQ auth0-* skills.

This module isolates two seams that every auth0-* skill (auth0-logs, auth0-stats,
future skills) needs to share:

  1. Auth seam — AuthProvider Protocol + EnvAuthProvider implementation, with
     atomic-write 0o600 token cache and in-script .env loading. Per Decision
     0014, EnvAuthProvider is the temporary path. When Decision 0015 M4 lands
     and the centralized-platform IdentityBroker is specified in code, a second
     AuthProvider implementation will plug in here. Only this module changes.

  2. HTTP seam — auth0_get() handles proactive rate-limit back-off, reactive
     429 retry-once, and structured error envelopes for 400/401/403/414 plus a
     catch-all api_error. All Auth0 Management API GET callers route through it
     so error categories stay consistent across skills.

Used by:
  - .claude/skills/auth0-logs/scripts/auth0_logs.py
  - (future) .claude/skills/auth0-stats/scripts/auth0_stats.py
  - (future) .claude/skills/auth0-attack/scripts/auth0_attack.py

Standard error categories (exit codes):
  missing_env (1), auth_failed (2), bad_query (3), rate_limited (4),
  api_error (5), uri_too_large (6).

See docs/decisions/0014-auth0-logs-skill.md for the standing design decision.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Protocol

import requests


# ---------------------------------------------------------------------------
# Structured error envelope
# ---------------------------------------------------------------------------

def error_exit(error_type: str, exit_code: int, detail: str, hint: str) -> None:
    """Print structured error JSON to stderr and exit with a category code."""
    json.dump({"error": error_type, "detail": detail, "hint": hint}, sys.stderr, indent=2)
    sys.stderr.write("\n")
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# .env loader (in-script — removes the need for the caller to source .env)
# ---------------------------------------------------------------------------

def load_dotenv() -> None:
    """Load KEY=VALUE pairs from .env into os.environ if not already set.

    Searches: ./.env, then <repo_root>/.env (repo root inferred from this
    file's location at .claude/skills/auth0-logs/scripts/). Silently no-ops
    if no .env is found. Existing env vars are not overridden — sourced-env
    in the parent shell still wins.
    """
    candidates = [
        Path(".env"),
        Path(__file__).resolve().parent.parent.parent.parent.parent / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            pass
        return


# ---------------------------------------------------------------------------
# Auth Provider seam (swappable per Decision 0014 / Decision 0015 M4)
# ---------------------------------------------------------------------------

class AuthProvider(Protocol):
    """Protocol for obtaining Auth0 Management API tokens."""

    def get_token(self) -> str: ...

    @property
    def domain(self) -> str: ...


class EnvAuthProvider:
    """Standalone mode: reads credentials from environment variables, caches token to file.

    Per Decision 0014, this is the temporary path. When Decision 0015 M4 lands
    and the centralized-platform IdentityBroker is specified in code, a second
    AuthProvider implementation will integrate with it.
    """

    # Security: never include self._client_id, self._client_secret, or token contents
    # in error messages or logs. error_exit calls below MUST NOT echo credentials.

    TOKEN_CACHE_PATH = Path(".auth0-token.json")
    TOKEN_SAFETY_MARGIN = 300  # refresh 5 min before expiry

    def __init__(self) -> None:
        load_dotenv()
        self._domain = os.environ.get("AUTH0_DOMAIN", "")
        self._client_id = os.environ.get("AUTH0_CLIENT_ID", "")
        self._client_secret = os.environ.get("AUTH0_CLIENT_SECRET", "")
        if not all([self._domain, self._client_id, self._client_secret]):
            error_exit(
                "missing_env",
                1,
                "AUTH0_DOMAIN, AUTH0_CLIENT_ID, and AUTH0_CLIENT_SECRET must be set.",
                "Copy .env.example to .env and fill in Auth0 credentials.",
            )

    @property
    def domain(self) -> str:
        return self._domain

    def get_token(self) -> str:
        cached = self._read_cache()
        if cached:
            return cached
        token_data = self._acquire_token()
        self._write_cache(token_data)
        return token_data["access_token"]

    def _read_cache(self) -> str | None:
        if not self.TOKEN_CACHE_PATH.exists():
            return None
        try:
            data = json.loads(self.TOKEN_CACHE_PATH.read_text())
            if data.get("expires_at", 0) > time.time() + self.TOKEN_SAFETY_MARGIN:
                return data["access_token"]
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _acquire_token(self) -> dict:
        url = f"https://{self._domain}/oauth/token"
        # IMPORTANT: Content-Type must be application/x-www-form-urlencoded, NOT JSON.
        # Using `data=` (not `json=`) ensures requests encodes as form data.
        resp = requests.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "audience": f"https://{self._domain}/api/v2/",
            },
            timeout=(5, 30),
        )
        if resp.status_code in (401, 403):
            try:
                detail = resp.json().get("error_description", resp.text[:500])
            except (json.JSONDecodeError, ValueError):
                detail = resp.text[:500]
            error_exit(
                "auth_failed",
                2,
                f"{resp.status_code} from token endpoint: {detail}",
                "Check AUTH0_CLIENT_ID/SECRET; ensure the M2M app has the required scopes.",
            )
        resp.raise_for_status()
        return resp.json()

    def _write_cache(self, token_data: dict) -> None:
        cache = {
            "access_token": token_data["access_token"],
            "expires_at": time.time() + token_data.get("expires_in", 86400),
        }
        tmp = self.TOKEN_CACHE_PATH.with_suffix(".tmp")
        # Use os.open with explicit mode for owner-only permissions on POSIX.
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(cache, f)
            os.replace(str(tmp), str(self.TOKEN_CACHE_PATH))
        except Exception:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            raise


# When Decision 0015 M4 lands and the centralized-platform IdentityBroker is
# specified in code, add a second AuthProvider implementation here that
# integrates with it. The exact shape (sync call, cached token, per-invocation
# exchange) will be decided when the broker interface exists. See
# docs/decisions/0015-centralized-platform-mcp.md.


# ---------------------------------------------------------------------------
# HTTP seam — shared rate-limit back-off and structured error handling
# ---------------------------------------------------------------------------

def make_session(token: str) -> requests.Session:
    """Create a requests.Session pre-configured for Auth0 Management API calls."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    )
    return session


def auth0_get(
    session: requests.Session,
    url: str,
    params: dict,
    timeout: tuple = (5, 30),
) -> requests.Response:
    """GET against an Auth0 Management API endpoint with shared idioms.

    Behavior shared across all auth0-* skills:
      - If X-RateLimit-Remaining < 2, sleep until X-RateLimit-Reset before
        returning (proactive smoothing — keeps subsequent calls off the cliff).
      - On 429, sleep Retry-After then retry once. A second 429 raises
        rate_limited (exit 4).
      - 400 raises bad_query (exit 3).
      - 414 raises uri_too_large (exit 6).
      - 401/403 raises auth_failed (exit 2) with a "delete .auth0-token.json"
        hint (the most common cause is a stale cached token).
      - Any other non-2xx raises api_error (exit 5).
    """
    resp = session.get(url, params=params, timeout=timeout)

    # Proactive rate-limit back-off
    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining is not None:
        try:
            if int(remaining) < 2:
                reset_ts = float(resp.headers.get("X-RateLimit-Reset", time.time() + 1))
                wait = max(0, reset_ts - time.time()) + 0.1
                time.sleep(wait)
        except (TypeError, ValueError):
            pass

    # Reactive rate-limit: 429 — retry once
    if resp.status_code == 429:
        try:
            retry_after = float(resp.headers.get("Retry-After", 1))
        except (TypeError, ValueError):
            retry_after = 1.0
        time.sleep(retry_after)
        resp = session.get(url, params=params, timeout=timeout)
        if resp.status_code == 429:
            error_exit(
                "rate_limited",
                4,
                "Rate limit exceeded after retry.",
                "Wait a moment and retry, or narrow the query.",
            )

    if resp.status_code == 400:
        try:
            detail = resp.json().get("message", resp.text[:500])
        except (json.JSONDecodeError, ValueError):
            detail = resp.text[:500]
        error_exit(
            "bad_query",
            3,
            f"400 Bad Request: {detail}",
            "Check the query syntax — field names, date format, special character escaping.",
        )

    if resp.status_code == 414:
        error_exit(
            "uri_too_large",
            6,
            "414 Request-URI Too Large — query string exceeds server limits.",
            "Simplify the query: fewer filters, shorter date ranges.",
        )

    if resp.status_code in (401, 403):
        try:
            detail = resp.json().get("message", resp.text[:500])
        except (json.JSONDecodeError, ValueError):
            detail = resp.text[:500]
        # Differentiate hints: 403 with "scope" in detail → permission, not freshness.
        if "scope" in detail.lower():
            hint = (
                "The M2M app lacks a required scope. Add it in the Auth0 Dashboard "
                "(Applications → [your app] → APIs → Auth0 Management API), then "
                "delete .auth0-token.json so the next call refreshes the token."
            )
        else:
            hint = "Token may be expired or credentials wrong. Delete .auth0-token.json and retry; if that fails, verify AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET."
        error_exit(
            "auth_failed",
            2,
            f"{resp.status_code}: {detail}",
            hint,
        )

    if not resp.ok:
        detail = resp.text[:500]
        error_exit(
            "api_error",
            5,
            f"{resp.status_code}: {detail}",
            "Unexpected Auth0 API error.",
        )

    return resp
