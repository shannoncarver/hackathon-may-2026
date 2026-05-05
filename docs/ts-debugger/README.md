# Harmony-Auth Tech Services Debugger

An internal AI tool that helps LINQ Technical Services engineers find root causes for Harmony-Auth tickets — without filing escalation tickets to engineers who hold the data-source access.

> Hackathon project for "The Forge: Season 2 — Every Minute Matters" (May 2026). Architecture pinned in [Decision 0018](../decisions/0018-ts-debugger-architecture.md).

## Problem

Tech Services lacks direct access to Harmony-Auth's underlying state — CloudWatch Logs across 40+ Lambdas, five DynamoDB tables, OpenSearch, and the Auth0 / Cognito management APIs. Today, every "user can't log in" or "MFA looks misconfigured" ticket means filing an escalation ticket to engineering. Slow, lossy, and not scalable.

The tool lets a Tech Services engineer go from a symptom (an email, a clientId, a timestamp, an error string) to a structured case file — a unified timeline assembled from every relevant signal — without leaving Claude Code.

## Solution

Two components plus a Claude Code skill, one repository:

```
Python ha-debug package (library layer)
              ↓
        [ha-debug CLI (argparse)]
              ↑
        Claude Code via Bash,
        guided by the ts-debug skill
```

| Component | Purpose |
|---|---|
| `ha-debug-core` | Python package. All join logic, queries, and result shaping. Pure functions in, structured records out. |
| `ha-debug` (CLI) | Argv-to-function shim over the core, built with `argparse`. Used by humans, scripts, and Claude Code via Bash. JSON to stdout, errors to stderr. |
| `ts-debug` skill | Markdown skill at `.claude/skills/ts-debug/SKILL.md`. Tells Claude when to invoke `ha-debug` for which symptoms and how to interpret output. |

The skill is what makes the CLI demo-able in Claude Code without the engineer having to remember subcommand syntax. See [Decision 0018 — Why CLI + skill, not MCP](../decisions/0018-ts-debugger-architecture.md) for the rationale and the trade-offs.

## Three-layer architecture

The library follows the three-layer pattern established by `auth0_logs.py` in `feature/auth0-logs-skill`:

1. **AuthProvider** (swappable) — `EnvAuthProvider` reads shared credentials from a local config file for the hackathon. `BrokerAuthProvider` is the production swap-in when the centralized platform MCP broker lands.
2. **API clients** — one per data source (`Auth0LogsClient`, `CognitoClient`, `DynamoDBClient`, `CloudWatchClient`). Each handles HTTP, pagination, rate limiting, and raises `DataSourceError` on failure.
3. **CLI + output** — `argparse` subcommands, JSON stdout, structured error stderr.

## What it does — v1

Two ticket archetypes, chosen to exercise both shapes of the underlying data layer.

### 1. "Login failed for some unknown reason"

A Tech Services engineer reports that a user can't log in. The tool assembles a case file from CloudWatch logs, Auth0 logs, Cognito user state, TokenCache, and LockRepository — covering a configurable time window. Claude reasons over the structured output and proposes a likely root cause.

### 2. "User was not required for MFA and TS doesn't know why"

A Tech Services engineer notices a user wasn't prompted for MFA. The tool assembles a configuration snapshot from MFAEnrollment, Auth0 user factors, Cognito MFA configuration, connection-level policy, and SuperAdminMFA. Claude identifies which configuration short-circuited the MFA requirement.

## Public surface

The CLI exposes only three subcommands. Primitives stay internal — see [Decision 0018 — Public surface](../decisions/0018-ts-debugger-architecture.md) for the rationale.

| Function | CLI subcommand | Use |
|---|---|---|
| `assemble_login_failure_case(email_or_user_id, window)` | `assemble-login-failure-case` | Run on archetype 1. |
| `assemble_mfa_not_enforced_case(email_or_user_id)` | `assemble-mfa-not-enforced-case` | Run on archetype 2. |
| `write_resolved_case(case_file, hypothesis, resolution)` | `write-resolved-case` | Persist a sanitized resolved case to the wiki. |

## Authentication — hackathon scope

The tool ships with shared read-only credentials for a non-production Harmony-Auth environment, stored in a local config file on the presenter's laptop. `EnvAuthProvider` reads from this config. No per-user authentication, no SSO, no proxy. The demo runs as a single baked-in service identity.

> Production deployment will require per-user authentication — likely Microsoft Entra-federated SSO with an Auth0 / Cognito broker — captured in a follow-up ADR once the tool moves toward broader use. Out of hackathon scope per [Decision 0018 — Authentication](../decisions/0018-ts-debugger-architecture.md). When the centralized platform MCP broker (Decision 0015, `feature/auth0-logs-skill`) hits milestone M4, `BrokerAuthProvider` swaps in with no changes to assemblers or CLI.

## Case persistence

After Claude resolves a case, the tool writes a sanitized resolved case to `knowledge/wiki/cases/` via `write_resolved_case`. Subsequent debug sessions retrieve prior resolutions as context — the case corpus compounds value over time.

The case bucket and frontmatter spec are pinned in [Decision 0017](../decisions/0017-case-as-wiki-bucket.md). Product tagging uses the canonical slugs in [Decision 0016](../decisions/0016-product-slug-canonical-list.md).

## Demo arc

```
Tech Services engineer in Claude Code:
  "User john@school.edu can't log in — failing all morning."
                        ↓
Claude (guided by the ts-debug skill) runs:
  ha-debug assemble-login-failure-case --email john@school.edu --window 8h
                        ↓
CLI returns structured case file:
  {
    "identity":  { "auth0_id": "...", "cognito_sub": "...", "status": "FORCE_CHANGE_PASSWORD" },
    "attempts":  [4 entries, all "PasswordResetRequiredException"],
    "tokens":    { "last_success": "2026-04-30T14:22Z", "last_failure": "2026-05-04T09:14Z" },
    "lock":      { "locked": false }
  }
                        ↓
Claude:
  "John's Cognito account is in FORCE_CHANGE_PASSWORD state — his
   password expired April 30 and he hasn't reset it. The 4 failed
   attempts this morning all returned PasswordResetRequiredException.
   Send him a password-reset email via the Harmony-Auth admin tool."
                        ↓
Claude runs:
  ha-debug write-resolved-case --case-file ... --resolution send-password-reset-email
                        ↓
Result: knowledge/wiki/cases/case-2026-05-04-...md
```

## Out of scope (v1)

- Claude Desktop support. CLI-only architecture; an MCP shim is the natural follow-up if Desktop ever becomes in-scope.
- Per-user authentication. Hackathon scope.
- PII redaction in `write_resolved_case`. Deferred to a follow-up ADR.
- Cross-product extension. The architecture is per-product; the second product is a follow-up ADR.
- Reading from the 40+ Harmony-Auth API endpoints directly. v1 reads underlying state from DynamoDB and logs.

## References

- [Decision 0016 — Canonical product-slug list](../decisions/0016-product-slug-canonical-list.md)
- [Decision 0017 — `case` as a fifth wiki bucket](../decisions/0017-case-as-wiki-bucket.md)
- [Decision 0018 — Tech Services debugger architecture](../decisions/0018-ts-debugger-architecture.md)
- [Decision 0013 — Three-layer LLM-wiki pattern](../decisions/0013-karpathy-wiki-pattern.md)
- [Knowledge base SCHEMA](../../knowledge/SCHEMA.md)
