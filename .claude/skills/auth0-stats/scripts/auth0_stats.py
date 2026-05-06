#!/usr/bin/env python3
"""Query Auth0 Management API for tenant-wide auth health stats.

Part of the LINQ auth0-stats skill. Reuses the auth seam and HTTP idioms
from .claude/skills/auth0-logs/scripts/_auth0_common.py — when Decision
0015 M4 lands and the centralized platform's IdentityBroker exists,
swapping AuthProvider in _auth0_common.py upgrades this skill too.

Sections (the script can fetch any subset via --include / --exclude):

  daily          — /api/v2/stats/daily (logins, signups, breach detections per day)
  mau            — /api/v2/stats/active-users (rolling 30-day MAU)
  failures       — derived from /api/v2/logs (count of type:f|fp|fu in window)
  mfa-adoption   — derived from /api/v2/logs (gd_* events / successful logins)
  top-connections — derived from /api/v2/logs (top connections by login count)

Usage:
    python auth0_stats.py --window 7d
    python auth0_stats.py --window 30d --include daily,mau,failures
    python auth0_stats.py --window today --exclude top-connections

Output: structured JSON to stdout, errors to stderr.
See .claude/skills/auth0-stats/SKILL.md for full documentation.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# _auth0_common lives next to auth0_logs.py in the auth0-logs skill folder.
# When a 3rd auth0-* skill arrives we'll promote the module to .claude/skills/_shared/auth0/.
_THIS_DIR = Path(__file__).resolve().parent
_COMMON_DIR = _THIS_DIR.parent.parent / "auth0-logs" / "scripts"
sys.path.insert(0, str(_COMMON_DIR))

from _auth0_common import (  # noqa: E402  — sys.path manipulation is intentional
    EnvAuthProvider,
    auth0_get,
    error_exit,
    make_session,
)


ALL_SECTIONS = ("daily", "mau", "failures", "mfa-adoption", "top-connections")
LOG_FAILURE_TYPES = ("f", "fp", "fu", "fsa", "fco", "fcoa")
LOG_SUCCESS_TYPES = ("s", "ss", "ssa")
LOG_MFA_TYPES = ("gd_auth_succeed", "gd_auth_failed", "gd_enrollment_complete", "mfar")


# ---------------------------------------------------------------------------
# Window parsing
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


# ---------------------------------------------------------------------------
# Layer 2 — API client (stats + log-derived)
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
# Layer 3 — CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query Auth0 Management API for tenant-wide auth health stats.",
        epilog="Part of the LINQ auth0-stats skill. See .claude/skills/auth0-stats/SKILL.md.",
    )
    parser.add_argument(
        "--window",
        default="7d",
        help="Time window: today, yesterday, this-week, 24h, 7d, 14d, 30d, 90d, NNd, NNh.",
    )
    parser.add_argument(
        "--include",
        help=f"Comma-separated subset of: {','.join(ALL_SECTIONS)} (default: all)",
    )
    parser.add_argument(
        "--exclude",
        help=f"Comma-separated subset to exclude. Mutually exclusive with --include.",
    )
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
