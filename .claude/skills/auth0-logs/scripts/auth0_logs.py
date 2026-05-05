#!/usr/bin/env python3
"""Query Auth0 Management API v2 logs.

Part of the LINQ auth0-logs skill. Three-layer architecture:

  Layer 1 — Auth Provider (swappable)
      EnvAuthProvider  : standalone mode, reads credentials from env vars
      (future) Broker-backed provider: see Decision 0015 M4

  Layer 2 — API Client (stable core)
      Auth0LogsClient  : search and checkpoint pagination against /api/v2/logs

  Layer 3 — CLI & Output
      Structured JSON to stdout, structured errors to stderr.

Usage:
    python auth0_logs.py --query 'type:s AND date:[2024-01-01 TO *]'
    python auth0_logs.py --from-id '90020241001...' --max-pages 3

See .claude/skills/auth0-logs/SKILL.md for full documentation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Protocol

import requests


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _error_exit(error_type: str, exit_code: int, detail: str, hint: str) -> None:
    """Print structured error to stderr and exit."""
    json.dump({"error": error_type, "detail": detail, "hint": hint}, sys.stderr, indent=2)
    sys.stderr.write("\n")
    sys.exit(exit_code)


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from .env into os.environ if not already set.

    Searches: ./.env, then <repo_root>/.env (repo root inferred from this file's
    location). Silently no-ops if no .env is found. Existing env vars are not
    overridden — sourced-env in the parent shell still wins.
    """
    candidates = [
        Path(".env"),
        Path(__file__).resolve().parent.parent.parent.parent / ".env",
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
# Layer 1 — Auth Provider (swappable)
# ---------------------------------------------------------------------------

class AuthProvider(Protocol):
    """Protocol for obtaining Auth0 Management API tokens."""

    def get_token(self) -> str: ...

    @property
    def domain(self) -> str: ...


class EnvAuthProvider:
    """Standalone mode: reads credentials from environment variables, caches token to file."""

    # Security: never include self._client_id, self._client_secret, or token contents
    # in error messages or logs. _error_exit calls below MUST NOT echo credentials.

    TOKEN_CACHE_PATH = Path(".auth0-token.json")
    TOKEN_SAFETY_MARGIN = 300  # refresh 5 min before expiry

    def __init__(self) -> None:
        _load_dotenv()
        self._domain = os.environ.get("AUTH0_DOMAIN", "")
        self._client_id = os.environ.get("AUTH0_CLIENT_ID", "")
        self._client_secret = os.environ.get("AUTH0_CLIENT_SECRET", "")
        if not all([self._domain, self._client_id, self._client_secret]):
            _error_exit(
                "missing_env",
                1,
                "AUTH0_DOMAIN, AUTH0_CLIENT_ID, and AUTH0_CLIENT_SECRET must be set.",
                "Copy .env.example to .env and fill in Auth0 credentials.",
            )

    @property
    def domain(self) -> str:
        return self._domain

    def get_token(self) -> str:
        # 1. Check cache file
        cached = self._read_cache()
        if cached:
            return cached
        # 2. Acquire new token via client_credentials grant
        token_data = self._acquire_token()
        # 3. Cache it
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
            detail = resp.json().get("error_description", resp.text[:500])
            _error_exit(
                "auth_failed",
                2,
                f"{resp.status_code} from token endpoint: {detail}",
                "Check AUTH0_CLIENT_ID/SECRET; ensure M2M app has read:logs scope.",
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
            # Clean up temp file on failure
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
# Layer 2 — API Client (stable core — never changes)
# ---------------------------------------------------------------------------

class Auth0LogsClient:
    """Queries Auth0 Management API v2 logs endpoint."""

    def __init__(self, domain: str, token: str) -> None:
        self.base_url = f"https://{domain}/api/v2/logs"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    # -- Search-based pagination (Lucene query) ----------------------------

    def search(
        self,
        query: str,
        max_pages: int = 5,
        per_page: int = 100,
        sort: str = "date:-1",
        fields: str | None = None,
    ) -> dict:
        """Search-based pagination (Lucene query). Max 1,000 results via API."""
        all_logs: list[dict] = []
        total: int | None = None
        pages_fetched = 0

        for page in range(max_pages):
            params: dict = {
                "q": query,
                "page": page,
                "per_page": min(per_page, 100),
                "sort": sort,
                "include_totals": "true",
            }
            if fields:
                params["fields"] = fields
                params["include_fields"] = "true"

            resp = self._request(params)
            data = resp.json()

            # Auth0 returns either {"logs": [...], "total": N} or just [...]
            if isinstance(data, dict):
                logs = data.get("logs", [])
                if page == 0:
                    total = data.get("total", len(logs))
            else:
                logs = data
                if page == 0:
                    total = len(logs)

            all_logs.extend(logs)
            pages_fetched = page + 1

            # Stop: we have retrieved everything the API reports
            if total is not None and len(all_logs) >= total:
                break

            # Stop: we've hit Auth0's 1,000-result search ceiling
            if len(all_logs) >= 1000:
                break

            # Stop: API returned fewer logs than per_page (no more pages)
            if len(logs) < per_page:
                break

        # Determine capped status after the loop
        capped = False
        reason: str | None = None
        if total is not None and total > 1000 and len(all_logs) >= 1000:
            capped = True
            reason = "api_ceiling_1000"
        elif total is not None and len(all_logs) < total:
            capped = True
            reason = "max_pages_reached"

        return self._result(
            query,
            sort,
            total if total is not None else len(all_logs),
            all_logs,
            pages_fetched,
            capped=capped,
            reason=reason,
        )

    # -- Checkpoint-based pagination (from log ID) -------------------------

    def checkpoint(
        self,
        from_id: str,
        max_pages: int = 5,
        per_page: int = 100,
    ) -> dict:
        """Checkpoint-based pagination (from log ID). No 1,000 result limit."""
        all_logs: list[dict] = []
        current_id = from_id
        pages_fetched = 0

        for i in range(max_pages):
            params = {"from": current_id, "take": min(per_page, 100)}
            resp = self._request(params)
            logs = resp.json()

            if not logs:
                break

            all_logs.extend(logs)
            pages_fetched = i + 1

            # Parse Link header for next checkpoint
            link = resp.headers.get("Link", "")
            if 'rel="next"' not in link:
                break
            match = re.search(r"from=([^&>]+)", link)
            if not match:
                break
            current_id = match.group(1)

        return {
            "from_id": from_id,
            "sort": None,
            "total": len(all_logs),
            "fetched": len(all_logs),
            "pages_fetched": pages_fetched,
            "capped": pages_fetched >= max_pages and len(all_logs) > 0,
            "capped_reason": "max_pages_reached" if pages_fetched >= max_pages and len(all_logs) > 0 else None,
            "logs": all_logs,
        }

    # -- Internal helpers --------------------------------------------------

    def _request(self, params: dict) -> requests.Response:
        """Make a GET request with rate-limit handling and structured errors."""
        resp = self.session.get(self.base_url, params=params, timeout=(5, 30))

        # Proactive rate-limit back-off: pause before we hit the wall
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) < 2:
            reset_ts = float(resp.headers.get("X-RateLimit-Reset", time.time() + 1))
            wait = max(0, reset_ts - time.time()) + 0.1
            time.sleep(wait)

        # Reactive rate-limit: 429 — retry once after the server-specified delay
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 1))
            time.sleep(retry_after)
            resp = self.session.get(self.base_url, params=params, timeout=(5, 30))
            if resp.status_code == 429:
                _error_exit(
                    "rate_limited",
                    4,
                    "Rate limit exceeded after retry.",
                    "Wait a moment and retry, or narrow the query.",
                )

        if resp.status_code == 400:
            detail = resp.json().get("message", resp.text)
            _error_exit(
                "bad_query",
                3,
                f"400 Bad Request: {detail}",
                "Check Lucene query syntax — field names, date format, special character escaping.",
            )

        if resp.status_code == 414:
            _error_exit(
                "uri_too_large",
                6,
                "414 Request-URI Too Large — query string exceeds server limits.",
                "Simplify the query: fewer filters, shorter date ranges.",
            )

        if resp.status_code in (401, 403):
            detail = resp.json().get("message", resp.text[:500])
            _error_exit(
                "auth_failed",
                2,
                f"{resp.status_code}: {detail}",
                "Token may be expired. Delete .auth0-token.json and retry.",
            )

        if not resp.ok:
            detail = resp.text[:500]
            _error_exit(
                "api_error",
                5,
                f"{resp.status_code}: {detail}",
                "Unexpected Auth0 API error.",
            )

        return resp

    @staticmethod
    def _result(
        query: str,
        sort: str,
        total: int,
        logs: list[dict],
        pages: int,
        capped: bool = False,
        reason: str | None = None,
    ) -> dict:
        return {
            "query": query,
            "sort": sort,
            "total": total,
            "fetched": len(logs),
            "pages_fetched": pages,
            "capped": capped,
            "capped_reason": reason,
            "logs": logs,
        }


# ---------------------------------------------------------------------------
# Layer 3 — CLI & Output
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query Auth0 Management API v2 logs.",
        epilog="Part of the LINQ auth0-logs skill. See .claude/skills/auth0-logs/SKILL.md.",
    )
    parser.add_argument(
        "--query", "-q", help="Lucene query string (required unless --from-id)"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Max pages to fetch (default: 5, max: 10)",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=100,
        help="Results per page (default/max: 100)",
    )
    parser.add_argument(
        "--sort",
        default="date:-1",
        help="Sort field:direction (default: date:-1)",
    )
    parser.add_argument(
        "--fields", help="Comma-separated fields to return"
    )
    parser.add_argument(
        "--from-id", help="Log event ID for checkpoint-based pagination"
    )
    args = parser.parse_args()

    # Validate: at least one mode is required
    if not args.query and not args.from_id:
        parser.error("Either --query or --from-id is required.")

    # Clamp to safe maximums
    args.max_pages = min(args.max_pages, 10)
    args.per_page = min(args.per_page, 100)

    # Layer 1: Auth
    auth = EnvAuthProvider()
    token = auth.get_token()

    # Layer 2: API Client
    client = Auth0LogsClient(auth.domain, token)

    if args.from_id:
        result = client.checkpoint(args.from_id, args.max_pages, args.per_page)
    else:
        result = client.search(
            args.query, args.max_pages, args.per_page, args.sort, args.fields
        )

    # Layer 3: Output — structured JSON to stdout
    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
