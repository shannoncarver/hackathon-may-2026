---
description: Tenant-wide Auth0 health dashboard for the LINQ sandbox tenant. Daily login volume, MAU, failure rate, MFA adoption, and top connections by natural-language window.
argument-hint: time window or "this week" / "last 24 hours" / "last 30 days" / specific sections
allowed-tools: Read, Glob, Grep, Bash
---

# /auth0-stats — Tenant Auth0 health dashboard

Window: $ARGUMENTS

You are the **Auth0 stats coordinator**. The user invoked `/auth0-stats` with the request above. Your job is to interpret the time window and any section preferences, run the stats script, and summarize the result in demo style. The full operational protocol lives in the [`auth0-stats` skill](.claude/skills/auth0-stats/SKILL.md) — read it before proceeding.

## What to do

1. **Read the skill.** Open `.claude/skills/auth0-stats/SKILL.md` and follow its three-step flow: interpret → execute → summarize.
2. **If `$ARGUMENTS` is empty**, default to `7d` (last 7 days). Tell the user that's what you're using and offer alternatives ("today", "this-week", "30d", etc.) so they can re-run with a different window.
3. **Interpret the window.** Map natural-language phrases to the script's `--window` flag (`today`, `yesterday`, `this-week`, `24h`, `7d`, `14d`, `30d`, `90d`, or `NNd` for arbitrary lengths). If the user names specific sections (e.g., "just MAU", "failure rate only"), pass `--include <sections>`.
4. **Execute.** Run the script anchored to the repo root:
   ```bash
   cd "$(git rev-parse --show-toplevel)" && python .claude/skills/auth0-stats/scripts/auth0_stats.py --window <flag> [--include <sections>]
   ```
   Parse JSON from stdout; surface stderr errors with concrete next steps.
5. **Summarize.** Use the demo output style — **Objective** → **Progress** → **Next Steps**. Cover: daily average + high/low days, MAU, failure rate as a percentage, MFA adoption rate, top 1–3 connections by login. Do not dump raw JSON unless the user asks.

## Constraints

- This skill targets the **sandbox tenant** (`linq-accounts-sandbox.us.auth0.com`) only. Production-tenant queries are out of scope.
- Requires `.env` populated with `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`. The M2M app must have **`read:logs` and `read:stats`** scopes — see `docs/developer/onboarding.md` for setup.
- Trust boundary applies. Stats endpoints return aggregates only (no per-user identifying fields), but the rule still holds: never read or print `.env`, `.auth0-token.json`, or `Authorization` headers.
- Auth0 rate limits apply (the script handles back-off automatically).

## Behavior on common edge cases

- **Missing env vars** (`missing_env` error): point the user to `docs/developer/onboarding.md` § "Auth0 Logs Setup". Do not attempt to acquire credentials yourself.
- **Missing `read:stats` scope** (`auth_failed` with a hint mentioning stats): the M2M app needs the scope. Tell the user to add `read:stats` in the Auth0 Dashboard (Applications → [their M2M app] → APIs → Auth0 Management API → check `read:stats` → Update), then delete `.auth0-token.json` and retry.
- **Empty result** (zero MAU, empty `daily` array): note that sandbox-tenant traffic may be low for the requested window; suggest a longer window.
- **Capped sections** (`capped: true` on `failures`, `mfa-adoption`, or `top-connections`): the count hit Auth0's 1,000-result search ceiling. Note the cap explicitly and suggest narrowing the window for a complete count.
- **Bad window** (`bad_window` error): show the supported set ("today, yesterday, this-week, 24h, 7d, 14d, 30d, 90d, NNd, NNh") and ask the user to pick one.

After this command runs, the user can drill down with `/auth0-logs <natural-language>` for raw events, or `ha-debug get-user --email <user>` for per-user investigation.
