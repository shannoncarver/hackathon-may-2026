---
status: Accepted
date: 2026-05-06
category: skills-management
---

# Decision 0021 — `ha-debug` credential migration + setup preflight

**Status:** Accepted (2026-05-06).

## Context

The `ha-debug` CLI and skill landed before [Decision 0016](0016-aws-multi-account-skill-credentials.md) crystallized the AWS-skill credential convention. Today's state:

- **AWS auth uses the legacy env-var paste.** `ha-debug/.env.example` declares `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`. boto3 / aws-sdk-js read these from process env. This violates Rule 1 of Decision 0016 (no shell-global key paste; use named profiles). The legacy pattern is fragile across two-skill prompts (only one set of creds can live in env at a time) and locks every operator into hand-pasting from the SSO console per session.
- **No setup prompting.** When `.env` is missing, the CLI returns `error: auth` and the skill points at `docs/developer/onboarding.md`. Engineers without local setup hit a wall instead of a guided path.
- **No environment toggle.** The CLI runs against whatever account the pasted keys point at. There is no `--environment dev|prod` flag, no prod acknowledgment, no audit banner.
- **Auth0 M2M creds are per-environment** but `.env.example` exposes a single set of `AUTH0_DOMAIN` / `AUTH0_CLIENT_ID` / `AUTH0_CLIENT_SECRET` keys, forcing engineers to swap `.env` content when switching environments.

The skill is the second AWS-touching surface in the repo (after `verify-user-authorization`) and is on track to be one of the most-used in the demo. The longer the legacy pattern stays, the more skills get authored against it as a template, and the more painful the eventual migration.

## Decision

Three coordinated changes, landed together:

### 1. Migrate `ha-debug` AWS auth to the Decision 0016 convention

- **Profile naming.** `linq-platform-services-dev` and `linq-platform-services-prod`. The Harmony-Auth backing resources (DynamoDB, Cognito, CloudWatch) live in the LINQ platform-services AWS accounts; `linq-platform-services-{env}` is the canonical name pattern. If an operator's `~/.aws/config` uses a different name, they pass `--aws-profile <name>` or set `LINQ_PLATFORM_SERVICES_AWS_PROFILE`. The skill's preflight prompts the operator to inspect their own `~/.aws/config` if no canonical profile resolves.
- **Profile resolution order** mirrors Decision 0016 Rule 3 verbatim: `--aws-profile` flag → `LINQ_PLATFORM_SERVICES_AWS_PROFILE` env var → `LINQ_AWS_USE_AMBIENT_CHAIN=1` → derived from `--environment` → empty-string headless fallback.
- **`--environment dev|prod`** drives both the AWS profile name and the per-environment resource names (DynamoDB tables, Cognito user pool, CloudWatch log group, Auth0 tenant + M2M client). Per Rule 4, a single user-facing toggle prevents dev creds from pointing at prod data.
- **`--i-understand-this-is-prod`** required for any prod run. Mirrors Rule 5; the flag has no shorter alias.
- **STS audit banner** prints `env` / `profile` (or `<ambient>`) / `account` / `arn` / target resource names to stderr before any DynamoDB / Cognito / CloudWatch / Auth0 call. Doubles as a per-invocation audit log and credential fail-fast.
- **Three-phase error rule** per Rule 6: `ProfileNotFound` (name the literal `[profile <name>]` block to add), `NoCredentialsError` from `sts:GetCallerIdentity` (the literal `aws sso login --sso-session linq` command), downstream errors (existing messages, distinct from credential errors). The CLI MUST NOT shell out to `aws sso login` — that breaks headless callers.

### 2. Add a `ha-debug doctor` subcommand

- **Read-only setup health check.** Returns structured JSON:

  ```json
  {
    "environment": "dev",
    "checks": [
      { "name": "aws-sso", "ok": true, "profile": "linq-platform-services-dev", "account": "...", "arn": "..." },
      { "name": "dynamodb-accounts", "ok": true, "table": "..." },
      { "name": "dynamodb-super-admin-mfa", "ok": false, "table": "...", "fix": "..." },
      { "name": "dynamodb-app-clients", "ok": true, "table": "..." },
      { "name": "cognito-user-pool", "ok": true, "userPoolId": "..." },
      { "name": "cloudwatch-log-group", "ok": true, "logGroupName": "..." },
      { "name": "auth0-token", "ok": true, "domain": "...", "tokenExpiresInSec": 86400 }
    ],
    "ok": false,
    "checkedAt": "2026-05-06T..."
  }
  ```

- **Each check is independent and isolated.** A failed check sets `ok: false` and includes a `fix` string, but does not abort the rest. Operators see every problem at once, not whichever failure surfaced first.
- **No writes, no mutations.** `doctor` is the single canonical seam for "is my environment ready"; the skill calls it first and walks the operator through every `ok: false` row.

### 3. Add a Step 0 — Preflight to the skill

- **0a. CLI dependency check.** Before `doctor` can run at all, `ha-debug/node_modules/` must exist (the CLI uses `commander`, `dotenv`, `tsx`, the AWS SDK, the Auth0 SDK). The skill's first preflight action is a dep-presence check; if missing, it asks the operator for permission to run `npm install --prefix ha-debug` once.
- **0b. The skill runs `doctor` after the dep check.** If `ok: true`, proceed to Step 1 (Triage). If any row is `ok: false`, the skill walks the operator through each fix in plain language: missing SSO → "run `aws sso login --sso-session linq`"; profile not found → "open `~/.aws/config` and tell me which profile to use, or add this stanza: …"; missing Auth0 creds → "open `https://manage.auth0.com/` for the LINQ {env} tenant, find the existing M2M application, and copy domain / client ID / client secret into `ha-debug/.env` under `AUTH0_*_{ENV}`".
- **The slash command preflights too.** `/ha-debug` runs the dep check and `doctor` before parsing `$ARGUMENTS`. If setup is broken, the user gets the prompt walk-through; if setup is healthy, the slash command continues directly to the triage flow.

### Per-environment env vars (replacing the single-tenant `.env`)

`.env.example` becomes:

```
# AWS profile resolution — see Decision 0016. Override only when needed.
# LINQ_PLATFORM_SERVICES_AWS_PROFILE=
# LINQ_AWS_USE_AMBIENT_CHAIN=

AWS_REGION=us-east-1

# DynamoDB tables — per environment
ACCOUNTS_TABLE_NAME_DEV=
ACCOUNTS_TABLE_NAME_PROD=
SUPER_ADMIN_MFA_TABLE_NAME_DEV=
SUPER_ADMIN_MFA_TABLE_NAME_PROD=
APP_CLIENTS_TABLE_NAME_DEV=
APP_CLIENTS_TABLE_NAME_PROD=

# Cognito user pool — per environment
COGNITO_USER_POOL_ID_DEV=
COGNITO_USER_POOL_ID_PROD=

# CloudWatch log group — per environment
CW_LOG_GROUP_NAME_DEV=/aws/lambda/harmony-auth-dev
CW_LOG_GROUP_NAME_PROD=/aws/lambda/harmony-auth-prod

# Auth0 Management API — per environment, separate M2M apps
AUTH0_DOMAIN_DEV=
AUTH0_CLIENT_ID_DEV=
AUTH0_CLIENT_SECRET_DEV=
AUTH0_DOMAIN_PROD=
AUTH0_CLIENT_ID_PROD=
AUTH0_CLIENT_SECRET_PROD=

# Output — relative to cwd
# WIKI_CASES_DIR=knowledge/wiki/cases
```

Engineers populate the dev block on first run; the prod block stays empty unless they need prod investigation. The doctor / preflight only validates the active environment's keys.

## Alternatives Considered

### Alternative A — Skill-only preflight against the legacy `.env`

Add Step 0 prompting to the skill, leave `.env.example` and `auth.ts` on the env-var paste pattern.

**Rejected.** The user's mental model is "be logged into AWS SSO" — that's literally the named-profile pattern. Layering prompting on top of the legacy paste pattern would lock in the wrong shape and create a second migration later.

### Alternative B — Migrate AWS only; defer doctor + skill preflight

Just align the AWS auth with Decision 0016, leave the prompting unchanged.

**Rejected.** The presenting user complaint is the lack of setup prompting. Migrating auth without the doctor + preflight fixes nothing the operator sees.

### Alternative C — Generate `.env` from a `setup` subcommand

A `ha-debug setup` subcommand that interactively prompts for Auth0 creds and writes `.env`. Simpler than `doctor` for first-run.

**Rejected for now.** Mixes two responsibilities (interactive bootstrap vs. health check). `doctor` is read-only and machine-checkable, which is what the skill prompt needs to drive a guided walk-through. A future `setup` subcommand can build on top of `doctor` if first-run friction warrants it.

### Alternative D — Migrate every other AWS-touching skill in the same PR

Apply the same migration to `auth0-logs`, `auth0-stats`, `auth0-sec` simultaneously.

**Rejected.** Those skills don't currently touch AWS — they hit the Auth0 Management API. They have a related setup-prompting gap (Auth0 M2M creds) but no AWS migration to do. Worth a follow-up decision if their setup UX becomes a friction point in the demo.

## Consequences

- Every AWS-touching skill in the repo now follows Decision 0016 (after this PR: `verify-user-authorization` + `ha-debug`). Future skills should mirror the same shape.
- `ha-debug/.env` files in existing developer setups will need to be updated. The migration breaks any operator who already populated `.env` with the legacy keys; the skill's preflight will detect missing per-env keys and walk them through repopulation.
- The `doctor` JSON shape becomes a minor surface contract — additive changes are safe; renames or removals require a follow-up Decision.
- When the centralized platform MCP server's IdentityBroker reaches GA ([Decision 0015](0015-centralized-platform-mcp.md) M4+), evaluate retiring named-profile resolution from `ha-debug` in favor of broker-issued tokens. The `boto3.Session(profile_name=...)` and `fromIni({ profile })` seams are designed to make that swap a single-block change per client.

## References

- [Decision 0016](0016-aws-multi-account-skill-credentials.md) — AWS multi-account skill credential convention. The standing rule.
- [Decision 0018](0018-ts-debugger-architecture.md) — `ha-debug` architecture.
- [`.claude/rules/aws-skill-credentials.md`](../../.claude/rules/aws-skill-credentials.md) — auto-loaded rule that mirrors Decision 0016.
- [`skills/verify-user-authorization/SKILL.md`](../../skills/verify-user-authorization/SKILL.md) — reference implementation for the credential and audit-banner pattern.
- [`.claude/skills/ha-debug/SKILL.md`](../../.claude/skills/ha-debug/SKILL.md) — skill being migrated.
