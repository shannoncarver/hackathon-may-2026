---
name: auth0-stats
description: Operational protocol for fetching tenant-wide Auth0 health stats by natural-language window. Use when running the /auth0-stats slash command, when a user says "auth health", "login volume", "MAU", "monthly active users", "failure rate this week", "MFA adoption", "top connections", or when a stakeholder asks for a tenant-level dashboard view of authentication activity on the LINQ sandbox tenant.
allowed-tools: Read, Glob, Grep, Bash
---

# auth0-stats skill

Operational how-to for tenant-wide Auth0 health checks. Where `/auth0-logs` answers "what events happened?" and `ha-debug` answers "what's wrong with this user?", `/auth0-stats` answers "what does our auth look like at the tenant level?" Stakeholder-friendly aggregate, not engineer-on-call triage. The standing decision is [Decision 0017](../../../docs/decisions/0017-auth0-stats-skill.md); the script lives at [`scripts/auth0_stats.py`](scripts/auth0_stats.py) and reuses the auth seam from the [`auth0-logs` skill's shared module](../auth0-logs/scripts/_auth0_common.py). Sandbox tenant only.

## Three-step flow

```
1. Interpret  →  2. Execute  →  3. Summarize
```

There is no pre-flight confirmation step — the skill is read-only and the windows are short. If the user wants to confirm before running (rare), they say so.

### Step 1 — Interpret the request

Read [`references/health-metrics.md`](references/health-metrics.md) for what each section measures and what counts as a healthy baseline.

Map the natural-language window to the script's `--window` flag:

| User says | Window flag |
|-----------|------------|
| "today" | `--window today` |
| "yesterday" | `--window yesterday` |
| "this week" | `--window this-week` |
| "last 24 hours" / "last day" | `--window 24h` |
| "last week" / "past week" / "7 days" | `--window 7d` |
| "last 30 days" / "this month" | `--window 30d` |
| "last 90 days" / "last quarter" | `--window 90d` |

The script understands an `NNd` form (e.g., `--window 14d`) for arbitrary lengths.

Decide which sections to fetch (default: all five):

| Section | When to include |
|---------|----------------|
| `daily` | When the user wants a time series — counts per day |
| `mau` | When the user asks about monthly active users or growth |
| `failures` | When the user asks about failure rate or auth health |
| `mfa-adoption` | When the user asks about MFA adoption or compliance posture |
| `top-connections` | When the user asks which auth providers are being used |

Use `--include` for a subset (e.g., `--include daily,mau`) or `--exclude` to drop specific sections.

### Step 2 — Execute

Source `.env` is unnecessary — the script loads `.env` itself via the shared `load_dotenv` helper. Run the script via Bash, anchored to the repo root for cwd safety:

```bash
cd "$(git rev-parse --show-toplevel)" && python .claude/skills/auth0-stats/scripts/auth0_stats.py \
  --window <window> \
  [--include <sections> | --exclude <sections>]
```

Parse the JSON output from stdout. Error categories shared with `auth0-logs` (per the standard envelope from `_auth0_common.py`):

- `missing_env` (1) — `.env` not populated. Point to `docs/developer/onboarding.md`.
- `auth_failed` (2) — read the `hint` field from stderr. If it mentions the token endpoint, your `AUTH0_CLIENT_ID` or `AUTH0_CLIENT_SECRET` is wrong. If it mentions cache, delete `.auth0-token.json` and retry. If it mentions `read:stats`, the M2M app needs the additional scope — see onboarding doc.
- `bad_query` (3) — Lucene query for a derived metric was rejected. Almost always a bug; surface verbatim.
- `rate_limited` (4) — Auth0 rate limits apply. Wait a moment and retry, or narrow the window.
- `bad_window` (7) — `--window` value not recognized. Show the user the supported set.
- `api_error` (5) / `uri_too_large` (6) — same handling as `auth0-logs`.

### Step 3 — Summarize

Use the demo output style from [`.claude/output-styles/demo.md`](../../output-styles/demo.md) — **Objective** → **Progress** → **Next Steps**.

- **Objective** — one sentence: the window and what was measured. Example: "Tenant auth health for the past 7 days."
- **Progress** — 3–5 bullets covering:
  - Daily volume: average logins per day, with the high and low day named
  - MAU: the integer, with comparison to baseline if available from prior runs
  - Failure rate: failures ÷ (failures + successes) as a percentage; flag if > 5%
  - MFA adoption: rate as a percentage; flag if < 50% on a tenant that should require MFA
  - Top connections: name the top 1–3 by login count
- **Next Steps** — 1–3 actionable bullets, e.g., "Drill into a specific user with `ha-debug get-user`" or "Run `/auth0-logs type:fp` to see wrong-password specifics" or "MFA adoption is low — investigate connections without MFA enforced via `ha-debug get-connection`."

If `capped: true` appears on any section, surface it: "Failure count was capped at the 1,000-result API ceiling — narrow the window or filter by event type via `/auth0-logs` for a complete count."

If `mau` returns 0 or the daily array is empty, the sandbox tenant may have low traffic during the window. Note this rather than implying a problem.

Do NOT dump raw JSON. The default output is a narrative demo summary; raw JSON is available on user request.

## Trust boundary

Per [`.claude/rules/coordination.md`](../../rules/coordination.md):

- Stats endpoints return tenant-level aggregates with no user-identifying fields, so the trust-boundary risk is lower than `/auth0-logs`. The log-derived sections (`failures`, `mfa-adoption`, `top-connections`) compute counts only — they do not pass individual log entries downstream.
- **Never read or print credential material.** Do not `cat .env`, do not read `.auth0-token.json`, do not echo `Authorization` headers, and do not include the script's stdin or environment in user-visible output. If the script fails, surface only the structured stderr JSON it returns — never the raw token, Client ID, or Client Secret.
- The connection names in `top_connections` come from Auth0's tenant configuration (not user input), so they are safe to surface verbatim.

## When this skill does NOT apply

- **Per-user investigation** ("what's going on with user X?") → use `ha-debug get-user` or `/auth0-logs <user>`
- **Specific event lookup** ("show me failed logins from this IP") → use `/auth0-logs`
- **Auth0 configuration changes** (creating M2M apps, modifying Actions, RBAC) → `12-eng-security-iam`
- **Real-time alerting** → out of scope; `/auth0-stats` is pull-based, not stream-based
- **Production tenant** → out of scope; sandbox-only by design across all auth0-* skills
- **Destructive operations** → no DELETE/PATCH/POST endpoints exist in this skill

## References

- [`references/health-metrics.md`](references/health-metrics.md) — what each section measures, healthy baselines, common follow-ups
- [`scripts/auth0_stats.py`](scripts/auth0_stats.py) — data retrieval script (run with `--help` for CLI reference)
- [`../auth0-logs/scripts/_auth0_common.py`](../auth0-logs/scripts/_auth0_common.py) — shared auth seam and HTTP idioms
- [Decision 0014](../../../docs/decisions/0014-auth0-logs-skill.md) — sibling skill standing decision (hybrid approach with swappable AuthProvider)
- [Decision 0015](../../../docs/decisions/0015-centralized-platform-mcp.md) — future migration target
- [Decision 0017](../../../docs/decisions/0017-auth0-stats-skill.md) — this skill's standing decision
