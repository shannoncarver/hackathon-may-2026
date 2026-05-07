#!/usr/bin/env python3
"""Unified CLI for Auth0 Management API queries — logs, stats, sec.

Per Decision 0025, this is the merged successor to the three separate scripts:
auth0_logs.py, auth0_stats.py, auth0_sec.py. The shared auth seam (_auth0_common.py)
is imported as a sibling. CLI flags and JSON output schemas are unchanged from the
predecessors so consumers can rename "python auth0_logs.py X" to "python
auth0_management.py logs X" without other changes.

Three-layer architecture (inherited from each predecessor):

  Layer 1 — Auth Provider (swappable, lives in _auth0_common.py)
      EnvAuthProvider  : standalone mode, reads credentials from env vars
      (future) Broker-backed provider: see Decision 0015 M4

  Layer 2 — API Clients (subcommand-specific)
      Auth0LogsClient   : search and checkpoint pagination against /api/v2/logs
      Auth0StatsClient  : tenant-wide stats endpoints + log-derived metrics
      Auth0SecClient    : security-related endpoints (anomaly, user-blocks,
                          attack-protection) plus per-IP recent activity

  Layer 3 — CLI & Output
      argparse subparsers (logs / stats / sec); structured JSON to stdout,
      structured errors to stderr.

Subcommands:

  logs    — query Auth0 Management API logs by Lucene query or checkpoint ID
  stats   — tenant-wide auth health (daily, MAU, failures, MFA adoption,
            top connections)
  sec     — security inspection by subject (IP, email, user_id, or
            'policy' / 'status')
  clients — list/get Auth0 application (client) configuration; safe-projection
            by default, never returns client_secret
  user    — get a specific Auth0 user record by email or user_id

Usage:
    python auth0_management.py logs --query 'type:f AND date:[2024-01-01 TO *]'
    python auth0_management.py logs --from-id '90020241001...' --max-pages 3
    python auth0_management.py stats --window 7d
    python auth0_management.py stats --window 30d --include daily,mau,failures
    python auth0_management.py sec --subject 1.2.3.4 --days 7
    python auth0_management.py sec --subject jane@linq.com
    python auth0_management.py sec --subject policy
    python auth0_management.py clients --name "ERP V4"
    python auth0_management.py clients --client-id abc123def456
    python auth0_management.py user --email scarver@linq.com
    python auth0_management.py user --user-id 'auth0|abc123'

See .claude/skills/auth0-management/SKILL.md for the operational protocol.
See docs/decisions/0025-* for the merge decision.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta

from _auth0_common import (
    EnvAuthProvider,
    auth0_get,
    error_exit,
    make_session,
)


# ---------------------------------------------------------------------------
# Constants (consolidated from auth0-stats and auth0-sec)
# ---------------------------------------------------------------------------

# stats sections
ALL_SECTIONS = ("daily", "mau", "failures", "mfa-adoption", "top-connections")
LOG_FAILURE_TYPES = ("f", "fp", "fu", "fsa", "fco", "fcoa")
LOG_SUCCESS_TYPES = ("s", "ss", "ssa")
LOG_MFA_TYPES = ("gd_auth_succeed", "gd_auth_failed", "gd_enrollment_complete", "mfar")

# sec subject classification
IPV4_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
IPV6_RE = re.compile(r"^[0-9a-fA-F:]+$")
USER_ID_PREFIXES = (
    "auth0|", "google-oauth2|", "windowslive|", "github|", "facebook|",
    "linkedin|", "twitter|", "samlp|", "oidc|", "email|", "sms|",
    "waad|", "adfs|", "ad|",
)
POLICY_KEYWORDS = {"policy", "config", "settings", "configuration"}
STATUS_KEYWORDS = {"status", "posture", "overview", "summary", "all", ""}

# clients subcommand — safe field projection. client_secret is intentionally absent.
DEFAULT_CLIENT_FIELDS = (
    "client_id,name,description,app_type,is_first_party,oidc_conformant,"
    "grant_types,token_endpoint_auth_method,callbacks,allowed_logout_urls,"
    "web_origins,allowed_origins,initiate_login_uri,jwt_configuration,"
    "refresh_token,sso,cross_origin_authentication,custom_login_page_on,"
    "tenant"
)
# Fields we will refuse to project even if the operator asks. These are credential
# material or PII surfaces. The skill is read-only; a fetch path for a secret has
# no operational use.
FORBIDDEN_CLIENT_FIELDS = frozenset({"client_secret", "signing_keys", "encryption_key"})

# user subcommand — safe field projection. password_hash and reset tokens never appear.
# /api/v2/users-by-email accepts a strict subset of fields; multifactor is NOT in
# that subset (it's only on /api/v2/users/{id}). We pick the intersection so the
# default works for both endpoints. Use --fields to widen for /users/{id}.
DEFAULT_USER_FIELDS = (
    "user_id,email,email_verified,blocked,name,nickname,picture,"
    "identities,last_login,last_ip,logins_count,"
    "created_at,updated_at,app_metadata,user_metadata,"
    "given_name,family_name"
)
FORBIDDEN_USER_FIELDS = frozenset({
    "password_hash", "phone_password_hash", "last_password_reset",
    "guardian_authenticators",
})


# ---------------------------------------------------------------------------
# Helpers — window parsing (stats) and subject classification (sec)
# ---------------------------------------------------------------------------

def parse_window(window: str) -> tuple[date, date]:
    """Parse a relative window string into (start_date, end_date) inclusive.

    Supported: today, yesterday, 24h, 7d, 14d, 30d, 90d, this-week (Mon–today).
    end_date is always today.
    """
    today = date.today()
    window = window.strip().lower()

    if window == "today":
        return today, today
    if window == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    if window == "this-week":
        days_since_monday = today.weekday()  # Monday is 0
        return today - timedelta(days=days_since_monday), today
    if window in ("24h", "1d"):
        return today - timedelta(days=1), today
    # nNd or nNh form
    if window.endswith("d") and window[:-1].isdigit():
        n = int(window[:-1])
        return today - timedelta(days=n), today
    if window.endswith("h") and window[:-1].isdigit():
        n = int(window[:-1])
        # Floor to days for the date-keyed stats endpoint
        return today - timedelta(days=max(1, n // 24)), today
    error_exit(
        "bad_window",
        7,
        f"Unrecognized --window value: {window!r}",
        "Use one of: today, yesterday, this-week, 24h, 7d, 14d, 30d, 90d, or NNd / NNh.",
    )


def yyyymmdd(d: date) -> str:
    return d.strftime("%Y%m%d")


def iso_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def classify_subject(subject: str) -> str:
    """Classify the user's subject into one of: ip, email, user_id, policy, status, unknown."""
    s = subject.strip()
    if IPV4_RE.match(s):
        return "ip"
    # IPv6 sanity check — must contain a colon and only hex/colons
    if ":" in s and IPV6_RE.match(s) and "|" not in s:
        return "ip"
    if "@" in s and "|" not in s:
        return "email"
    if any(s.startswith(p) for p in USER_ID_PREFIXES):
        return "user_id"
    lowered = s.lower()
    if lowered in POLICY_KEYWORDS:
        return "policy"
    if lowered in STATUS_KEYWORDS:
        return "status"
    return "unknown"


# ---------------------------------------------------------------------------
# Layer 2 — Auth0LogsClient (logs subcommand)
# The search and checkpoint pagination semantics are unique to /api/v2/logs.
# ---------------------------------------------------------------------------

class Auth0LogsClient:
    """Queries Auth0 Management API v2 logs endpoint."""

    def __init__(self, domain: str, token: str) -> None:
        self.base_url = f"https://{domain}/api/v2/logs"
        self.session = make_session(token)

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

            resp = auth0_get(self.session, self.base_url, params)
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
            resp = auth0_get(self.session, self.base_url, params)
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
# Layer 2 — Auth0StatsClient (stats subcommand)
# Queries stats endpoints and derives metrics from /logs.
# ---------------------------------------------------------------------------

class Auth0StatsClient:
    """Queries Auth0 Management API stats endpoints and derives metrics from /logs."""

    def __init__(self, domain: str, token: str) -> None:
        self.domain = domain
        self.session = make_session(token)
        self.stats_daily_url = f"https://{domain}/api/v2/stats/daily"
        self.stats_mau_url = f"https://{domain}/api/v2/stats/active-users"
        self.logs_url = f"https://{domain}/api/v2/logs"

    # -- stats/daily ----------------------------------------------------------

    def daily(self, start: date, end: date) -> list[dict]:
        """Daily login/signup/breach counts. Auth0 returns up to ~30 days per call."""
        params = {"from": yyyymmdd(start), "to": yyyymmdd(end)}
        resp = auth0_get(self.session, self.stats_daily_url, params)
        data = resp.json()
        # Normalize: stats/daily can return a list of {date, logins, signups, breached_password_detections}
        if isinstance(data, list):
            return data
        return []

    # -- stats/active-users ---------------------------------------------------

    def mau(self) -> int:
        """30-day MAU as a single integer."""
        resp = auth0_get(self.session, self.stats_mau_url, {})
        try:
            value = resp.json()
            if isinstance(value, int):
                return value
            # Some Auth0 responses wrap in an object
            if isinstance(value, dict) and "active_users" in value:
                return int(value["active_users"])
        except (ValueError, TypeError):
            pass
        return 0

    # -- log-derived metrics --------------------------------------------------

    def _query_logs(self, query: str, max_pages: int = 10, per_page: int = 100) -> list[dict]:
        """Page through /api/v2/logs and return the accumulated entries."""
        out: list[dict] = []
        for page in range(max_pages):
            params = {
                "q": query,
                "page": page,
                "per_page": per_page,
                "sort": "date:-1",
                "include_totals": "true",
            }
            resp = auth0_get(self.session, self.logs_url, params)
            data = resp.json()
            logs = data.get("logs", []) if isinstance(data, dict) else data
            out.extend(logs)
            if len(logs) < per_page:
                break
            if len(out) >= 1000:  # API ceiling
                break
        return out

    def failures(self, start: date, end: date) -> dict:
        """Count failure events of each type within the window."""
        type_clause = " OR ".join(f"type:{t}" for t in LOG_FAILURE_TYPES)
        date_clause = f"date:[{iso_date(start)} TO {iso_date(end)}]"
        query = f"({type_clause}) AND {date_clause}"
        logs = self._query_logs(query)
        by_type = Counter(l.get("type") for l in logs)
        return {
            "total": len(logs),
            "by_type": dict(by_type.most_common()),
            "capped": len(logs) >= 1000,
        }

    def mfa_adoption(self, start: date, end: date) -> dict:
        """Compute (MFA-related events) / (successful logins) within the window."""
        date_clause = f"date:[{iso_date(start)} TO {iso_date(end)}]"

        success_query = f"type:s AND {date_clause}"
        successes = self._query_logs(success_query)

        mfa_query = "(" + " OR ".join(f"type:{t}" for t in LOG_MFA_TYPES) + f") AND {date_clause}"
        mfa_events = self._query_logs(mfa_query)

        # Adoption rate is approximate; capped at 1000 each per API ceiling.
        rate = (len(mfa_events) / len(successes)) if successes else 0.0
        return {
            "successful_logins": len(successes),
            "mfa_events": len(mfa_events),
            "adoption_rate": round(rate, 3),
            "capped": len(successes) >= 1000 or len(mfa_events) >= 1000,
        }

    def top_connections(self, start: date, end: date, limit: int = 5) -> dict:
        """Top connections (auth providers) by successful login count."""
        date_clause = f"date:[{iso_date(start)} TO {iso_date(end)}]"
        query = f"type:s AND {date_clause}"
        logs = self._query_logs(query)
        counts = Counter((l.get("connection") or "<unknown>") for l in logs)
        return {
            "total_successful_logins": len(logs),
            "top": [{"connection": c, "logins": n} for c, n in counts.most_common(limit)],
            "capped": len(logs) >= 1000,
        }


# ---------------------------------------------------------------------------
# Layer 2 — Auth0SecClient (sec subcommand)
# Queries security-related endpoints and derives per-IP recent activity.
# ---------------------------------------------------------------------------

class Auth0SecClient:
    """Queries Auth0 Management API security-related endpoints."""

    def __init__(self, domain: str, token: str) -> None:
        self.domain = domain
        self.session = make_session(token)
        self.anomaly_url = f"https://{domain}/api/v2/anomaly/blocks/ips"
        self.user_blocks_url = f"https://{domain}/api/v2/user-blocks"
        self.attack_protection_base = f"https://{domain}/api/v2/attack-protection"
        self.logs_url = f"https://{domain}/api/v2/logs"

    # -- IP block status -----------------------------------------------------

    def ip_block_status(self, ip: str) -> dict:
        """Check if an IP is currently blocked by suspicious-IP throttling.

        Auth0 returns 200 with a body when blocked; 404 when not blocked.
        We surface either as a structured boolean.
        """
        url = f"{self.anomaly_url}/{ip}"
        # Custom handling: 404 is "not blocked", not an error.
        resp = self.session.get(url, timeout=(5, 30))
        if resp.status_code == 404:
            return {"ip": ip, "blocked": False}
        if resp.status_code in (200, 204):
            try:
                body = resp.json() if resp.content else {}
            except (ValueError, json.JSONDecodeError):
                body = {}
            return {"ip": ip, "blocked": True, "details": body}
        # Any other status — fall back to standard error handling
        # Manually invoke the shared error path by re-issuing through auth0_get
        auth0_get(self.session, url, {})  # raises via error_exit
        return {"ip": ip, "blocked": False}  # unreachable

    # -- User blocks ---------------------------------------------------------

    def user_blocks_by_identifier(self, identifier: str) -> dict:
        """Look up blocks for a user identifier (email or username)."""
        resp = auth0_get(self.session, self.user_blocks_url, {"identifier": identifier})
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError):
            data = {}
        return {"identifier": identifier, "blocks": data}

    def user_blocks_by_id(self, user_id: str) -> dict:
        """Look up blocks for a specific user_id (auth0|... format)."""
        url = f"{self.user_blocks_url}/{user_id}"
        resp = self.session.get(url, timeout=(5, 30))
        # 200 = a blocks object (possibly empty)
        if resp.status_code == 200:
            try:
                data = resp.json()
            except (ValueError, json.JSONDecodeError):
                data = {}
            return {"user_id": user_id, "blocks": data}
        if resp.status_code == 404:
            return {"user_id": user_id, "blocks": {}, "note": "user not found"}
        # Other status — fall through to standard error
        auth0_get(self.session, url, {})
        return {"user_id": user_id, "blocks": {}}  # unreachable

    # -- Attack protection policies -----------------------------------------

    def breached_password_policy(self) -> dict:
        url = f"{self.attack_protection_base}/breached-password-detection"
        resp = auth0_get(self.session, url, {})
        return resp.json() if resp.content else {}

    def brute_force_policy(self) -> dict:
        url = f"{self.attack_protection_base}/brute-force-protection"
        resp = auth0_get(self.session, url, {})
        return resp.json() if resp.content else {}

    def suspicious_ip_policy(self) -> dict:
        url = f"{self.attack_protection_base}/suspicious-ip-throttling"
        resp = auth0_get(self.session, url, {})
        return resp.json() if resp.content else {}

    def all_policies(self) -> dict:
        return {
            "breached_password_detection": self.breached_password_policy(),
            "brute_force_protection": self.brute_force_policy(),
            "suspicious_ip_throttling": self.suspicious_ip_policy(),
        }

    # -- Recent IP activity (uses /logs, no new scope) ----------------------

    def recent_ip_activity(self, ip: str, days: int = 7, max_pages: int = 2) -> dict:
        """Summarize recent log events for a specific IP."""
        end = date.today()
        start = end - timedelta(days=days)
        query = f'ip:"{ip}" AND date:[{start.isoformat()} TO {end.isoformat()}]'

        all_logs: list[dict] = []
        for page in range(max_pages):
            params = {
                "q": query,
                "page": page,
                "per_page": 100,
                "sort": "date:-1",
                "include_totals": "true",
            }
            resp = auth0_get(self.session, self.logs_url, params)
            data = resp.json()
            logs = data.get("logs", []) if isinstance(data, dict) else data
            all_logs.extend(logs)
            if len(logs) < 100:
                break

        by_type = Counter(l.get("type") for l in all_logs)
        by_user = Counter((l.get("user_name") or l.get("user_id") or "<anonymous>") for l in all_logs)
        return {
            "ip": ip,
            "window_days": days,
            "events": len(all_logs),
            "by_type": dict(by_type.most_common()),
            "top_users": [{"user": u, "events": n} for u, n in by_user.most_common(5)],
        }


# ---------------------------------------------------------------------------
# Layer 2 — Auth0ClientsClient (clients subcommand)
# Queries /api/v2/clients for application configuration. Read-only by design.
# ---------------------------------------------------------------------------


def _resolve_client_fields(requested: str | None) -> str:
    """Apply the safe-projection rule and reject forbidden fields.

    The forbidden set covers credential material (client_secret, signing_keys,
    encryption_key). The skill is read-only and these fields have no operational
    use here, so we refuse them even when explicitly asked.
    """
    fields = (requested or DEFAULT_CLIENT_FIELDS).strip()
    requested_set = {f.strip() for f in fields.split(",") if f.strip()}
    forbidden = requested_set & FORBIDDEN_CLIENT_FIELDS
    if forbidden:
        error_exit(
            "bad_query",
            3,
            f"Refused fields: {sorted(forbidden)}",
            (
                "client_secret, signing_keys, and encryption_key are not retrievable "
                "via this skill by design (read-only operational verification). "
                "Use the Auth0 Dashboard if you need credential rotation."
            ),
        )
    return ",".join(sorted(requested_set))


class Auth0ClientsClient:
    """Queries Auth0 Management API v2 clients endpoint (applications).

    Required Auth0 M2M scope: read:clients. The script never requests
    read:client_keys (which would expose client_secret) — that is a deliberate
    boundary, not an oversight.
    """

    def __init__(self, domain: str, token: str) -> None:
        self.domain = domain
        self.session = make_session(token)
        self.base_url = f"https://{domain}/api/v2/clients"

    def list_clients(
        self,
        name_substr: str | None = None,
        app_type: str | None = None,
        is_first_party: bool | None = None,
        fields: str | None = None,
        per_page: int = 50,
        max_pages: int = 5,
    ) -> dict:
        """List clients, optionally filtered. Filters name_substr client-side
        because /api/v2/clients only supports app_type / is_first_party server-side.
        """
        projected = _resolve_client_fields(fields)

        all_clients: list[dict] = []
        for page in range(max_pages):
            params: dict = {
                "page": page,
                "per_page": min(per_page, 100),
                "include_totals": "false",
                "include_fields": "true",
                "fields": projected,
            }
            if app_type:
                params["app_type"] = app_type
            if is_first_party is not None:
                params["is_first_party"] = "true" if is_first_party else "false"
            resp = auth0_get(self.session, self.base_url, params)
            data = resp.json()
            page_clients = data if isinstance(data, list) else data.get("clients", [])
            all_clients.extend(page_clients)
            if len(page_clients) < per_page:
                break

        if name_substr:
            needle = name_substr.lower()
            filtered = [c for c in all_clients if needle in (c.get("name") or "").lower()]
        else:
            filtered = all_clients

        sys.stderr.write(
            f"[clients] endpoint={self.base_url} "
            f"name_filter={name_substr!r} app_type={app_type!r} "
            f"first_party={is_first_party!r} returned={len(filtered)} "
            f"of_total_fetched={len(all_clients)}\n"
        )

        return {
            "filter": {
                "name_substr": name_substr,
                "app_type": app_type,
                "is_first_party": is_first_party,
            },
            "fields": projected,
            "fetched": len(all_clients),
            "matched": len(filtered),
            "clients": filtered,
        }

    def get_client(self, client_id: str, fields: str | None = None) -> dict:
        projected = _resolve_client_fields(fields)
        url = f"{self.base_url}/{client_id}"
        params = {"include_fields": "true", "fields": projected}
        resp = auth0_get(self.session, url, params)
        sys.stderr.write(f"[clients] endpoint={url} fields={projected}\n")
        return {
            "client_id": client_id,
            "fields": projected,
            "client": resp.json() if resp.content else {},
        }


# ---------------------------------------------------------------------------
# Layer 2 — Auth0UsersClient (user subcommand)
# Queries /api/v2/users-by-email and /api/v2/users/{id}. Read-only by design.
# ---------------------------------------------------------------------------


def _resolve_user_fields(requested: str | None) -> str:
    """Apply the safe-projection rule and reject forbidden fields."""
    fields = (requested or DEFAULT_USER_FIELDS).strip()
    requested_set = {f.strip() for f in fields.split(",") if f.strip()}
    forbidden = requested_set & FORBIDDEN_USER_FIELDS
    if forbidden:
        error_exit(
            "bad_query",
            3,
            f"Refused fields: {sorted(forbidden)}",
            (
                "password_hash and credential-related fields are not retrievable via "
                "this skill by design. Use the Auth0 Dashboard for credential audit."
            ),
        )
    return ",".join(sorted(requested_set))


class Auth0UsersClient:
    """Queries Auth0 Management API v2 users endpoint.

    Required Auth0 M2M scope: read:users. read:user_idp_tokens / read:current_user
    are not requested.
    """

    def __init__(self, domain: str, token: str) -> None:
        self.domain = domain
        self.session = make_session(token)
        self.base_url = f"https://{domain}/api/v2/users"
        self.by_email_url = f"https://{domain}/api/v2/users-by-email"

    def by_email(self, email: str, fields: str | None = None) -> dict:
        projected = _resolve_user_fields(fields)
        params = {
            "email": email.strip().lower(),
            "include_fields": "true",
            "fields": projected,
        }
        resp = auth0_get(self.session, self.by_email_url, params)
        data = resp.json()
        users = data if isinstance(data, list) else []
        sys.stderr.write(
            f"[user] endpoint={self.by_email_url} "
            f"email={email!r} matched={len(users)}\n"
        )
        return {
            "lookup": {"email": email.strip().lower()},
            "fields": projected,
            "matched": len(users),
            "users": users,
        }

    def by_id(self, user_id: str, fields: str | None = None) -> dict:
        projected = _resolve_user_fields(fields)
        url = f"{self.base_url}/{user_id}"
        params = {"include_fields": "true", "fields": projected}
        resp = auth0_get(self.session, url, params)
        sys.stderr.write(f"[user] endpoint={url} fields={projected}\n")
        return {
            "lookup": {"user_id": user_id},
            "fields": projected,
            "user": resp.json() if resp.content else {},
        }


# ---------------------------------------------------------------------------
# Layer 3 — CLI dispatch
# ---------------------------------------------------------------------------

def _run_logs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Dispatch the `logs` subcommand — preserves auth0_logs.py behavior exactly."""
    # Validate: at least one mode is required
    if not args.query and not args.from_id:
        parser.error("Either --query or --from-id is required.")

    # Clamp to safe maximums
    args.max_pages = min(args.max_pages, 10)
    args.per_page = min(args.per_page, 100)

    # Layer 1: Auth (from _auth0_common)
    auth = EnvAuthProvider()
    token = auth.get_token()

    # Layer 2: API Client (logs-specific)
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


def _run_stats(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Dispatch the `stats` subcommand — preserves auth0_stats.py behavior exactly."""
    if args.include and args.exclude:
        parser.error("--include and --exclude are mutually exclusive.")

    if args.include:
        sections = tuple(s.strip() for s in args.include.split(",") if s.strip())
        unknown = set(sections) - set(ALL_SECTIONS)
        if unknown:
            parser.error(f"Unknown --include section(s): {sorted(unknown)}. Valid: {ALL_SECTIONS}")
    elif args.exclude:
        excluded = {s.strip() for s in args.exclude.split(",") if s.strip()}
        unknown = excluded - set(ALL_SECTIONS)
        if unknown:
            parser.error(f"Unknown --exclude section(s): {sorted(unknown)}. Valid: {ALL_SECTIONS}")
        sections = tuple(s for s in ALL_SECTIONS if s not in excluded)
    else:
        sections = ALL_SECTIONS

    start, end = parse_window(args.window)

    # Layer 1: Auth (shared)
    auth = EnvAuthProvider()
    token = auth.get_token()

    # Layer 2: stats client
    client = Auth0StatsClient(auth.domain, token)

    result: dict = {
        "window": {
            "label": args.window,
            "start": iso_date(start),
            "end": iso_date(end),
            "days": (end - start).days + 1,
        },
        "sections_fetched": list(sections),
        "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    if "daily" in sections:
        result["daily"] = client.daily(start, end)
    if "mau" in sections:
        result["mau"] = client.mau()
    if "failures" in sections:
        result["failures"] = client.failures(start, end)
    if "mfa-adoption" in sections:
        result["mfa_adoption"] = client.mfa_adoption(start, end)
    if "top-connections" in sections:
        result["top_connections"] = client.top_connections(start, end)

    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _run_sec(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Dispatch the `sec` subcommand — preserves auth0_sec.py behavior exactly."""
    kind = classify_subject(args.subject)
    if kind == "unknown":
        error_exit(
            "bad_subject",
            8,
            f"Could not classify subject: {args.subject!r}",
            "Pass an IP (1.2.3.4), email (x@linq.com), user_id (auth0|...), or 'policy' / 'status'.",
        )

    auth = EnvAuthProvider()
    token = auth.get_token()
    client = Auth0SecClient(auth.domain, token)

    result: dict = {
        "subject": args.subject,
        "subject_kind": kind,
        "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    if kind == "ip":
        result["block"] = client.ip_block_status(args.subject)
        result["recent_activity"] = client.recent_ip_activity(args.subject, days=args.days)
    elif kind == "email":
        result.update(client.user_blocks_by_identifier(args.subject))
    elif kind == "user_id":
        result.update(client.user_blocks_by_id(args.subject))
    elif kind == "policy":
        result["policies"] = client.all_policies()
    elif kind == "status":
        result["policies"] = client.all_policies()
        result["note"] = (
            "No specific subject probed. Pass an IP, email, or user_id "
            "to /auth0-management sec to drill into a single target."
        )

    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _run_clients(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Dispatch the `clients` subcommand."""
    if not args.client_id and not args.name and not args.app_type and args.is_first_party is None:
        # Empty filter is allowed — operator wants the full list. No-op here.
        pass

    auth = EnvAuthProvider()
    token = auth.get_token()
    client = Auth0ClientsClient(auth.domain, token)

    if args.client_id:
        result = client.get_client(args.client_id, fields=args.fields)
    else:
        result = client.list_clients(
            name_substr=args.name,
            app_type=args.app_type,
            is_first_party=args.is_first_party,
            fields=args.fields,
            per_page=args.per_page,
            max_pages=args.max_pages,
        )

    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _run_user(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Dispatch the `user` subcommand."""
    if not args.email and not args.user_id:
        parser.error("Either --email or --user-id is required.")
    if args.email and args.user_id:
        parser.error("--email and --user-id are mutually exclusive.")

    auth = EnvAuthProvider()
    token = auth.get_token()
    client = Auth0UsersClient(auth.domain, token)

    if args.email:
        result = client.by_email(args.email, fields=args.fields)
    else:
        result = client.by_id(args.user_id, fields=args.fields)

    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="auth0_management.py",
        description="Unified CLI for Auth0 Management API queries — logs, stats, sec, clients, user.",
        epilog="Part of the LINQ auth0-management skill. See .claude/skills/auth0-management/SKILL.md.",
    )
    sub = parser.add_subparsers(
        dest="subcommand", required=True, metavar="{logs,stats,sec,clients,user}"
    )

    # -- logs subcommand ----------------------------------------------------
    p_logs = sub.add_parser(
        "logs",
        help="Query Auth0 Management API logs by Lucene query or checkpoint ID.",
        description="Query Auth0 Management API v2 logs.",
    )
    p_logs.add_argument(
        "--query", "-q", help="Lucene query string (required unless --from-id)"
    )
    p_logs.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Max pages to fetch (default: 5, max: 10)",
    )
    p_logs.add_argument(
        "--per-page",
        type=int,
        default=100,
        help="Results per page (default/max: 100)",
    )
    p_logs.add_argument(
        "--sort",
        default="date:-1",
        help="Sort field:direction (default: date:-1)",
    )
    p_logs.add_argument(
        "--fields", help="Comma-separated fields to return"
    )
    p_logs.add_argument(
        "--from-id", help="Log event ID for checkpoint-based pagination"
    )

    # -- stats subcommand ---------------------------------------------------
    p_stats = sub.add_parser(
        "stats",
        help="Tenant-wide auth health (daily, MAU, failures, MFA adoption, top connections).",
        description="Query Auth0 Management API for tenant-wide auth health stats.",
    )
    p_stats.add_argument(
        "--window",
        default="7d",
        help="Time window: today, yesterday, this-week, 24h, 7d, 14d, 30d, 90d, NNd, NNh.",
    )
    p_stats.add_argument(
        "--include",
        help=f"Comma-separated subset of: {','.join(ALL_SECTIONS)} (default: all)",
    )
    p_stats.add_argument(
        "--exclude",
        help="Comma-separated subset to exclude. Mutually exclusive with --include.",
    )

    # -- sec subcommand -----------------------------------------------------
    p_sec = sub.add_parser(
        "sec",
        help="Security inspection by subject (IP, email, user_id, or 'policy' / 'status').",
        description="Query Auth0 Management API for tenant security posture and per-subject inspection.",
    )
    p_sec.add_argument(
        "--subject",
        default="status",
        help="IP, email, user_id (auth0|...), or one of: policy, status. Default: status.",
    )
    p_sec.add_argument(
        "--days",
        type=int,
        default=7,
        help="For IP subject: how far back to look in /logs (default: 7 days).",
    )

    # -- clients subcommand -------------------------------------------------
    p_clients = sub.add_parser(
        "clients",
        help="List/get Auth0 application configuration. Read-only; never returns client_secret.",
        description=(
            "Query Auth0 Management API /api/v2/clients for application config. "
            "Required scope: read:clients. The skill refuses to return client_secret, "
            "signing_keys, or encryption_key by design."
        ),
    )
    p_clients.add_argument(
        "--name",
        help="Case-insensitive substring match on client name (e.g., 'ERP V4').",
    )
    p_clients.add_argument(
        "--client-id",
        help="Fetch a single client by client_id. Mutually exclusive with --name in effect.",
    )
    p_clients.add_argument(
        "--app-type",
        help="Server-side filter: spa, regular_web, native, non_interactive.",
    )
    p_clients.add_argument(
        "--is-first-party",
        type=lambda v: None if v in (None, "") else v.lower() in ("1", "true", "yes"),
        default=None,
        help="Server-side filter: true | false. Omit for no filter.",
    )
    p_clients.add_argument(
        "--fields",
        help=(
            "Comma-separated projection. Defaults to a verification-relevant set. "
            "client_secret/signing_keys/encryption_key are always rejected."
        ),
    )
    p_clients.add_argument("--per-page", type=int, default=50)
    p_clients.add_argument("--max-pages", type=int, default=5)

    # -- user subcommand ----------------------------------------------------
    p_user = sub.add_parser(
        "user",
        help="Get a single Auth0 user record by email or user_id.",
        description=(
            "Query Auth0 Management API /api/v2/users-by-email or /api/v2/users/{id}. "
            "Required scope: read:users. Returns a safe field projection; "
            "password_hash and credential fields are refused."
        ),
    )
    p_user.add_argument(
        "--email",
        help="Email address (case-insensitive). Uses /api/v2/users-by-email.",
    )
    p_user.add_argument(
        "--user-id",
        help="Auth0 user_id (e.g., 'auth0|abc123'). Uses /api/v2/users/{id}.",
    )
    p_user.add_argument(
        "--fields",
        help="Comma-separated projection. Defaults to a verification-relevant set.",
    )

    args = parser.parse_args()

    # Dispatch — pass the appropriate per-subparser parser so .error() prints
    # the subcommand's usage line, matching the predecessor scripts' behavior.
    if args.subcommand == "logs":
        _run_logs(args, p_logs)
    elif args.subcommand == "stats":
        _run_stats(args, p_stats)
    elif args.subcommand == "sec":
        _run_sec(args, p_sec)
    elif args.subcommand == "clients":
        _run_clients(args, p_clients)
    elif args.subcommand == "user":
        _run_user(args, p_user)


if __name__ == "__main__":
    main()
