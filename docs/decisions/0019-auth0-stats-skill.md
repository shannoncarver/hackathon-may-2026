---
status: Accepted
date: 2026-05-06
category: skills-management
---

# Decision 0019 — Auth0 stats skill: tenant-wide health dashboard atop the shared auth seam

**Status:** Accepted (2026-05-06).

## Context

[Decision 0014](0014-auth0-logs-skill.md) shipped `/auth0-logs` for raw event queries — a frontline tool for "what happened?" investigations. PR #8's `ha-debug` covers the per-user / per-ticket triage workflow ("what's wrong with user X?"). Neither answers the tenant-wide question that comes up in stakeholder conversations and demo settings: "what does our auth health look like right now?"

Daily login volume, monthly active users, failure rate trends, MFA adoption, and connection-mix breakdowns are all available on the Auth0 Management API today. They live in two endpoints (`/api/v2/stats/daily`, `/api/v2/stats/active-users`) plus aggregations over the existing logs endpoint. None of this requires new infrastructure.

The Decision 0014 design isolated the auth seam intentionally so future skills could plug in without re-implementing token caching, `.env` loading, rate-limit back-off, or structured error envelopes. This decision exercises that seam for the first time.

## Decision

Build a sibling skill at `.claude/skills/auth0-stats/` that imports from `.claude/skills/auth0-logs/scripts/_auth0_common.py` rather than duplicating credential-handling code. The script (`scripts/auth0_stats.py`) calls the two stats endpoints directly and derives three additional metrics (failures, MFA adoption, top connections) from `/api/v2/logs` aggregations. Output is structured JSON; the SKILL.md protocol summarizes in demo style.

Specific binding choices:

- **Same M2M app, additional scope.** The existing `LINQ AI Workflow - Logs Reader` M2M app gets the `read:stats` scope alongside `read:logs`. No new app — adding the skill costs one Auth0 Dashboard click. This is consistent with [Decision 0015](0015-centralized-platform-mcp.md) § 09-auth0-config's "one M2M app per service-identity class — never per handler" rule.
- **Sandbox only.** Same scope restriction as `/auth0-logs`. Production access remains gated on Decision 0015 M4.
- **Three-step flow, no pre-flight.** Stats endpoints are read-only and the windows are short — there is no expensive query to confirm before running. The SKILL.md goes Interpret → Execute → Summarize, dropping the pre-flight step that `/auth0-logs` uses for Lucene-query confirmation.
- **No new agent.** Self-contained skill, mirrors the routing skill pattern and `/auth0-logs` conventions.
- **Five sections, opt-in subset.** The script computes `daily`, `mau`, `failures`, `mfa-adoption`, and `top-connections` by default; `--include` and `--exclude` let the user pick a subset for narrow asks ("just MAU", "skip the connection breakdown").

## Alternatives Considered

### Alternative A — Fold stats into `/auth0-logs` as `--mode stats`

Add a flag to the existing skill that switches the script's output between log queries and stats. Single skill, single command.

**Rejected.** The user-facing prompts diverge sharply. `/auth0-logs` answers question-shaped queries about specific events; `/auth0-stats` answers dashboard-shaped requests about aggregate health. Conflating them in one slash command muddies the trigger phrases ("show me failed logins" vs. "what's our failure rate this week"). Two slash commands with two skills, sharing the auth seam, is the cleaner factoring.

### Alternative B — `/auth0-user` skill before `/auth0-stats`

The original phase plan put per-user drill-down ahead of tenant stats.

**Rejected after PR #8 (ha-debug) showed up.** `ha-debug get-user` and `assemble-login-failure-case` cover the per-user investigation workflow comprehensively. Building `/auth0-user` would duplicate work without adding capability. Tenant-wide stats is the next non-overlapping skill on the priority list.

### Alternative C — Extract `_auth0_common.py` lazily, only when forced to

Keep `auth0_logs.py` self-contained; copy-paste the auth code into `auth0_stats.py`; refactor when a third skill arrives.

**Rejected.** Two consumers of the same auth seam is the right moment to extract — the cost of reading two implementations is higher than the cost of one shared module. The refactor was shipped as a separate no-behavior-change PR (sibling of this decision) so reviewers can verify it doesn't move the line for `/auth0-logs`.

## Consequences

- **Positive:** Demo-friendly tenant view ships behind a single slash command. Stakeholders and judges get an aggregate picture without waiting on a real dashboard build-out.
- **Positive:** Validates the Decision 0014 seam. Any future `auth0-*` skill (auth0-attack, auth0-analytics) imports from `_auth0_common.py` the same way. When Decision 0015 M4 lands, all three skills pick up the broker swap from one module change.
- **Positive:** Cumulative scope on the M2M app remains small and read-only: `read:logs` plus `read:stats`. No widening of blast radius.
- **Negative:** Three of the five sections (`failures`, `mfa-adoption`, `top-connections`) are derived from log queries and inherit the 1,000-result API search ceiling. The summary surfaces `capped: true` when this happens, but very high-volume tenants would need Log Streams (push) for accurate counts at scale. Sandbox scope makes this acceptable today.
- **Negative:** The `mfa-adoption` rate is approximate. Numerator (MFA events) and denominator (successful logins) are individually capped at 1,000, so the ratio drifts on busy windows. The skill protocol surfaces the cap explicitly; users who need the precise number can use `/auth0-logs` to count each side themselves.
- **Operational debt:** Same as Decision 0014 — when Decision 0015 M4 retires `EnvAuthProvider`, this skill comes along automatically because it imports from the same module. No additional retirement step needed beyond what Decision 0014 already tracks.

## Sources

- Auth0 Management API — Get daily stats: https://auth0.com/docs/api/management/v2/stats/get-daily
- Auth0 Management API — Get active users count: https://auth0.com/docs/api/management/v2/stats/get-active-users
- Auth0 Management API — Search log events: https://auth0.com/docs/api/management/v2/logs/get-logs
- [`knowledge/wiki/entities/auth0-m2m.md`](../../knowledge/wiki/entities/auth0-m2m.md) — Auth0 M2M entity in the LINQ wiki
- [Decision 0014](0014-auth0-logs-skill.md) — sibling skill (auth0-logs) with the AuthProvider seam
- [Decision 0015](0015-centralized-platform-mcp.md) — centralized platform MCP (target migration)
