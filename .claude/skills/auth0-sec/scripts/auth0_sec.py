#!/usr/bin/env python3
"""Query Auth0 Management API for tenant security posture and per-subject inspection.

Part of the LINQ auth0-sec skill. Reuses the auth seam and HTTP idioms from
.claude/skills/auth0-logs/scripts/_auth0_common.py — when Decision 0015 M4
lands and the centralized platform's IdentityBroker exists, swapping
AuthProvider in _auth0_common.py upgrades this skill too.

Subject types (the script auto-classifies, the SKILL.md protocol pre-classifies):

  IP (e.g., "1.2.3.4")        — block status + recent /logs activity for that IP
  email (e.g., "x@linq.com")  — user-blocks lookup by identifier
  user_id ("auth0|abc...")    — user-blocks lookup by ID
  policy / config / settings  — all three /attack-protection/* configs
  status / posture / blank    — policy configs + summary header

Usage:
    python auth0_sec.py --subject 1.2.3.4
    python auth0_sec.py --subject jane@linq.com
    python auth0_sec.py --subject 'auth0|507f...'
    python auth0_sec.py --subject policy
    python auth0_sec.py --subject status

Output: structured JSON to stdout, errors to stderr.
See .claude/skills/auth0-sec/SKILL.md for full documentation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# _auth0_common lives next to auth0_logs.py in the auth0-logs skill folder.
_THIS_DIR = Path(__file__).resolve().parent
_COMMON_DIR = _THIS_DIR.parent.parent / "auth0-logs" / "scripts"
sys.path.insert(0, str(_COMMON_DIR))

from _auth0_common import (  # noqa: E402  — sys.path manipulation is intentional
    EnvAuthProvider,
    auth0_get,
    error_exit,
    make_session,
)


IPV4_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
IPV6_RE = re.compile(r"^[0-9a-fA-F:]+$")
USER_ID_PREFIXES = (
    "auth0|", "google-oauth2|", "windowslive|", "github|", "facebook|",
    "linkedin|", "twitter|", "samlp|", "oidc|", "email|", "sms|",
    "waad|", "adfs|", "ad|",
)
POLICY_KEYWORDS = {"policy", "config", "settings", "configuration"}
STATUS_KEYWORDS = {"status", "posture", "overview", "summary", "all", ""}


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
# Layer 2 — API Client
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
        from collections import Counter

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
# Layer 3 — CLI / dispatch
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query Auth0 Management API for tenant security posture and per-subject inspection.",
        epilog="Part of the LINQ auth0-sec skill. See .claude/skills/auth0-sec/SKILL.md.",
    )
    parser.add_argument(
        "--subject",
        default="status",
        help="IP, email, user_id (auth0|...), or one of: policy, status. Default: status.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="For IP subject: how far back to look in /logs (default: 7 days).",
    )
    args = parser.parse_args()

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
            "to /auth0-sec to drill into a single target."
        )

    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
