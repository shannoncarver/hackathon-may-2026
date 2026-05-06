#!/usr/bin/env python3
"""Query Auth0 Management API v2 logs.

Part of the LINQ auth0-logs skill. Three-layer architecture:

  Layer 1 — Auth Provider (swappable, lives in _auth0_common.py)
      EnvAuthProvider  : standalone mode, reads credentials from env vars
      (future) Broker-backed provider: see Decision 0015 M4

  Layer 2 — API Client (logs-specific)
      Auth0LogsClient  : search and checkpoint pagination against /api/v2/logs

  Layer 3 — CLI & Output
      Structured JSON to stdout, structured errors to stderr.

The auth seam, .env loading, and shared HTTP idioms (rate-limit back-off,
structured error envelopes) live in _auth0_common.py — sibling auth0-* skills
import from the same module.

Usage:
    python auth0_logs.py --query 'type:s AND date:[2024-01-01 TO *]'
    python auth0_logs.py --from-id '90020241001...' --max-pages 3

See .claude/skills/auth0-logs/SKILL.md for full documentation.
See docs/decisions/0014-auth0-logs-skill.md for the standing design decision.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from _auth0_common import (
    EnvAuthProvider,
    auth0_get,
    make_session,
)


# ---------------------------------------------------------------------------
# Layer 2 — API Client (logs-specific — the search and checkpoint pagination
# semantics are unique to /api/v2/logs)
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


if __name__ == "__main__":
    main()
