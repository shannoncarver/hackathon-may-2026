---
description: Auth0 Management API queries on the LINQ sandbox tenant — events, health stats, and security inspection. Pass a natural-language description of what to look for.
argument-hint: <natural language description of what to query for>
allowed-tools: Read, Glob, Grep, Bash
---

# /auth0-management — Auth0 Management API queries

Request: $ARGUMENTS

You are the **Auth0 Management coordinator**. The user invoked `/auth0-management` with the request above. Your job is to classify which subcommand applies, run the unified CLI, and summarize the result in demo style. The full operational protocol lives in the [`auth0-management` skill](.claude/skills/auth0-management/SKILL.md) — read it before proceeding.

## What to do

1. **Read the skill.** Open `.claude/skills/auth0-management/SKILL.md` and follow its three-step flow: classify → execute → summarize.
2. **If `$ARGUMENTS` is empty**, ask the user what they want to query (events / health / security inspection) and stop. Do not invent.
3. **Classify the subcommand** (logs / stats / sec) per the table in the SKILL.md.
4. **Build flags** based on subcommand using the relevant reference file.
5. **Execute** the unified CLI:
   ```bash
   cd "$(git rev-parse --show-toplevel)" && python .claude/skills/auth0-management/scripts/auth0_management.py <subcommand> [flags]
   ```
6. **Summarize** using the demo output style — Objective → Progress → Next Steps. Per-subcommand templates live in the SKILL.md.

## Constraints

- This skill targets the **sandbox tenant** (`linq-accounts-sandbox.us.auth0.com`) only.
- Requires `.env` populated. The M2M app must have **`read:logs`, `read:stats`, `read:anomaly_blocks`, `read:attack_protection`, `read:users`** scopes — see `docs/developer/onboarding.md`.
- Trust boundary applies. Wrap user-identifiable fields (user_name, user_id, ip, description, details, user_agent) in `<escape>...</escape>` per `.claude/rules/coordination.md` before forwarding to another agent.
- All endpoints are read-only `GET`. Destructive operations are out of scope until a typed-confirmation pattern exists.

## Behavior on common edge cases

- **Missing env vars** (`missing_env`): point the user to `docs/developer/onboarding.md` § "Auth0 Skills Setup".
- **Missing scope** (`auth_failed` mentioning "scope"): the M2M app needs the named scope. Tell the user to add it in the Auth0 Dashboard, then delete `.auth0-token.json`.
- **Bad subject / window / query**: surface the structured error and ask the user to refine.
- **Capped results**: surface the reason (`max_pages_reached` / `api_ceiling_1000`) and suggest narrowing.

After this command runs, the user can chain to `/ha-debug` for per-user investigation across Cognito/DynamoDB, or `verify-user-authorization` for ERP authorization checks.
