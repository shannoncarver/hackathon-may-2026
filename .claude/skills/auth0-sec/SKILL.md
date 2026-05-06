---
name: auth0-sec
description: Operational protocol for Auth0 sandbox-tenant security inspection by subject — IP, user, or tenant-wide policy. Use when running the /auth0-sec slash command, when a user says "is this IP blocked", "is user X locked out", "what's our brute-force policy", "breached-password policy", "suspicious IP throttling", "auth0 security posture", or when investigating an incident on the LINQ sandbox tenant.
allowed-tools: Read, Glob, Grep, Bash
---

# auth0-sec skill

Operational how-to for tenant-wide Auth0 security inspection. Where `/auth0-logs` answers "what events?" and `/auth0-stats` answers "what aggregate?", `/auth0-sec` answers "what's our security posture, and is this specific IP / user / policy in good shape?" Read-only across all five endpoints. The standing decision is [Decision 0018](../../../docs/decisions/0018-auth0-sec-skill.md); the script lives at [`scripts/auth0_sec.py`](scripts/auth0_sec.py) and reuses the auth seam from the [`auth0-logs` skill's shared module](../auth0-logs/scripts/_auth0_common.py). Sandbox tenant only.

## Three-step flow

```
1. Classify subject  →  2. Execute  →  3. Summarize
```

There is no pre-flight confirmation step — the skill is read-only and the queries are narrow. Optional pre-flight only when the subject is genuinely ambiguous (e.g., a string that could be either an email or a username on a non-DB connection).

### Step 1 — Classify the subject

Read [`references/attack-protection-glossary.md`](references/attack-protection-glossary.md) for the policy field meanings before summarizing.

Subject classification:

| User says | Subject kind | What gets queried |
|-----------|--------------|-------------------|
| `1.2.3.4` (IPv4) or IPv6 form | `ip` | `/anomaly/blocks/ips/{ip}` + recent `/logs?q=ip:"<ip>"` for context |
| `jane@linq.com` (contains `@`) | `email` | `/user-blocks?identifier=<email>` |
| `auth0\|abc123` (or other IdP-prefixed) | `user_id` | `/user-blocks/{id}` |
| `policy`, `config`, `settings` | `policy` | All three `/attack-protection/*` endpoints |
| `status`, `posture`, blank, `overview` | `status` | All three policy endpoints + a summary header |

If the prompt has multiple subjects ("check IP 1.2.3.4 and policy"), pick the most specific subject (the IP) and surface a "next step" suggestion in the summary for the others. If classification fails, the script returns `bad_subject` (exit 8) with the supported list.

### Step 2 — Execute

The script loads `.env` itself via the shared `load_dotenv` helper. Run it anchored to the repo root for cwd safety:

```bash
cd "$(git rev-parse --show-toplevel)" && python .claude/skills/auth0-sec/scripts/auth0_sec.py --subject '<subject>'
```

For an IP subject, optionally pass `--days N` to widen the recent-activity window (default 7).

Parse the JSON output from stdout. Error categories shared with sibling skills via `_auth0_common.py`:

- `missing_env` (1) — `.env` not populated. Point to `docs/developer/onboarding.md`.
- `auth_failed` (2) — read the `hint` field from stderr. If it mentions "scope", the M2M app is missing one of `read:anomaly_blocks`, `read:attack_protection`, or `read:users` — see onboarding doc for the upgrade path. If it mentions cache, delete `.auth0-token.json` and retry.
- `bad_query` (3) — internal Lucene query for the IP recent-activity lookup was rejected. Almost always a bug; surface verbatim.
- `rate_limited` (4) — Auth0 rate limits apply. Wait a moment and retry.
- `bad_subject` (8) — classification failed. Show the supported subject types.
- `api_error` (5) / `uri_too_large` (6) — same handling as siblings.

### Step 3 — Summarize

Use the demo output style from [`.claude/output-styles/demo.md`](../../output-styles/demo.md) — **Objective** → **Progress** → **Next Steps**. Per-path templates:

#### IP path

- **Objective**: "Security check for IP `<addr>`."
- **Progress** (3–4 bullets):
  - Block status: "blocked" or "not currently blocked" (cite the boolean from `block.blocked`)
  - Recent activity: "<N> events in the last <days> days, types: <breakdown>"
  - Top affected users from this IP (top 3, only if recent_activity has data)
- **Next Steps**: 1–3 bullets, e.g.:
  - If blocked: "IP is currently throttled — review the events with `/auth0-logs ip:\"<ip>\"` and unblock manually in the Auth0 Dashboard if a false positive."
  - If not blocked but recent failure events: "Run `/auth0-stats failures` to see if this IP is part of a wider pattern."
  - If clean: "No action — IP looks normal."

#### Email / user_id path

- **Objective**: "Block check for user `<subject>`."
- **Progress** (2–3 bullets):
  - Block records: count and most recent timestamp if any
  - If `note: user not found` is set, surface that explicitly
- **Next Steps**: e.g., "Drill into the user with `ha-debug get-user --email <addr>` for full state, or `/auth0-logs user_name:\"<addr>\"` for events."

#### Policy / status path

- **Objective**: "Tenant-wide Auth0 security posture."
- **Progress** (3 bullets, one per policy):
  - Breached-password: enabled state, action on detection (block / flag / off)
  - Brute-force: enabled state, max attempts threshold, mode
  - Suspicious-IP throttling: enabled state, max attempts, allowlist size
- **Next Steps**: only if a policy looks weak (e.g., breached-password off, brute-force threshold too high) — recommend the user discuss with eng-security-iam before changing thresholds.

Do NOT dump raw JSON. The default output is a narrative demo summary; raw JSON is available on user request or for handoff to another agent.

## Trust boundary

Per [`.claude/rules/coordination.md`](../../rules/coordination.md):

- Per-IP and per-user responses can include user-identifying fields (`user_name`, `user_id`, `ip`). When forwarding any portion of the response to another agent, wrap those fields in `<escape>...</escape>` per the project trust-boundary convention. The recent-activity helper inherits this — its top_users list is user-identifying.
- Policy responses are tenant configuration only and contain no user data — they are safe to surface verbatim.
- **Never read or print credential material.** Do not `cat .env`, do not read `.auth0-token.json`, do not echo `Authorization` headers, and do not include the script's stdin or environment in user-visible output. If the script fails, surface only the structured stderr JSON it returns — never the raw token, Client ID, or Client Secret.

## When this skill does NOT apply

- **Per-user investigation beyond block status** ("what's going on with user X?") → use `ha-debug get-user` or `/auth0-logs user_name:"..."`
- **Specific-event lookup** ("show me failed logins from this IP") → `/auth0-logs ip:"<ip>"`
- **Aggregate dashboard** (failure rate this week, MAU, MFA adoption) → `/auth0-stats`
- **Auth0 configuration changes** (creating M2M apps, modifying Actions, RBAC) → `12-eng-security-iam`
- **Destructive operations** (unblock IP, change brute-force threshold, force-logout, revoke tokens) → out of scope; deferred until a typed-confirmation pre-flight pattern exists across the project
- **Real-time alerting** → out of scope; this is a pull-based query skill
- **Production tenant** → out of scope; sandbox-only by design across all auth0-* skills

## References

- [`references/attack-protection-glossary.md`](references/attack-protection-glossary.md) — what each policy field means, healthy baselines, common follow-ups
- [`scripts/auth0_sec.py`](scripts/auth0_sec.py) — data retrieval script (run with `--help` for CLI reference)
- [`../auth0-logs/scripts/_auth0_common.py`](../auth0-logs/scripts/_auth0_common.py) — shared auth seam and HTTP idioms
- [Decision 0014](../../../docs/decisions/0014-auth0-logs-skill.md) — sibling skill standing decision (hybrid approach with swappable AuthProvider)
- [Decision 0017](../../../docs/decisions/0017-auth0-stats-skill.md) — sibling skill (auth0-stats)
- [Decision 0018](../../../docs/decisions/0018-auth0-sec-skill.md) — this skill's standing decision
- [Decision 0015](../../../docs/decisions/0015-centralized-platform-mcp.md) — future migration target
