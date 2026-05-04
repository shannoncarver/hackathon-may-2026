# Harmony-Auth Tech Services Debugger

An internal AI tool that helps LINQ Technical Services engineers find root causes for Harmony-Auth tickets — without filing escalation tickets to engineers who hold the data-source access.

> Hackathon project for "The Forge: Season 2 — Every Minute Matters" (May 2026). Architecture pinned in [Decision 0016](../decisions/0016-ts-debugger-architecture.md).

## Problem

Tech Services lacks direct access to Harmony-Auth's underlying state — CloudWatch Logs across 40+ Lambdas, five DynamoDB tables, OpenSearch, and the Auth0 / Cognito management APIs. Today, every "user can't log in" or "MFA looks misconfigured" ticket means filing an escalation ticket to engineering. Slow, lossy, and not scalable.

The tool lets a Tech Services engineer go from a symptom (an email, a clientId, a timestamp, an error string) to a structured case file — a unified timeline assembled from every relevant signal — without leaving Claude Code or Claude Desktop.

## Solution

Three components, one repository:

```
TypeScript core library (ha-debug-core)
        ↓                          ↓
    [CLI binary]              [stdio MCP server]
   ha-debug ...               mcp__ha-debug__assemble_login_failure_case
        ↑                          ↑
   Claude Code via Bash       Claude Desktop (and Claude Code if preferred)
```

| Component | Purpose |
|---|---|
| `ha-debug-core` | TypeScript library. All join logic, queries, and result shaping. Pure functions in, structured records out. |
| `ha-debug` (CLI) | Argv-to-function shim over the core. Used by humans, scripts, and Claude Code via Bash. |
| `ha-debug-mcp-server` (stdio MCP) | Same functions registered as MCP tools. Required for Claude Desktop; optional in Claude Code. |

Both transports share the core library — the marginal cost of shipping both surfaces is small, and the audience reach is doubled. See [Decision 0016 — Why both surfaces](../decisions/0016-ts-debugger-architecture.md) for the full rationale.

## What it does — v1

Two ticket archetypes, chosen to exercise both shapes of the underlying data layer.

### 1. "Login failed for some unknown reason"

A Tech Services engineer reports that a user can't log in. The tool assembles a case file from CloudWatch logs, Auth0 logs, Cognito user state, TokenCache, and LockRepository — covering a configurable time window. Claude reasons over the structured output and proposes a likely root cause.

### 2. "User was not required for MFA and TS doesn't know why"

A Tech Services engineer notices a user wasn't prompted for MFA. The tool assembles a configuration snapshot from MFAEnrollment, Auth0 user factors, Cognito MFA configuration, connection-level policy, and SuperAdminMFA. Claude identifies which configuration short-circuited the MFA requirement.

## Public surface

The CLI subcommand list and MCP tool registry expose only three functions. Primitives stay internal — see [Decision 0016 — Public surface](../decisions/0016-ts-debugger-architecture.md) for the rationale.

| Function | Use |
|---|---|
| `assembleLoginFailureCase(emailOrUserId, window)` | Run on archetype 1. |
| `assembleMFANotEnforcedCase(emailOrUserId)` | Run on archetype 2. |
| `writeResolvedCase(caseFile, hypothesis, resolution)` | Persist a sanitized resolved case to the wiki. |

## Authentication — hackathon scope

The tool ships with shared read-only credentials for a non-production Harmony-Auth environment, stored in a local config file on the presenter's laptop. Both CLI and MCP server read from the same config. No per-user authentication, no SSO, no proxy. The demo runs as a single baked-in service identity.

> Production deployment will require per-user authentication — likely Microsoft Entra-federated SSO with an Auth0 / Cognito broker — captured in a follow-up ADR once the tool moves toward broader use. Out of hackathon scope per [Decision 0016 — Authentication](../decisions/0016-ts-debugger-architecture.md).

## Case persistence

After Claude resolves a case, the tool writes a sanitized resolved case to `knowledge/wiki/cases/` via the `writeResolvedCase` function. Subsequent debug sessions retrieve prior resolutions as context — the case corpus compounds value over time.

The case bucket and frontmatter spec are pinned in [Decision 0015](../decisions/0015-case-as-wiki-bucket.md). Product tagging uses the canonical slugs in [Decision 0014](../decisions/0014-product-slug-canonical-list.md).

## Demo arc

```
Tech Services engineer:
  "User john@school.edu can't log in — failing all morning."
                        ↓
Claude calls:
  assembleLoginFailureCase("john@school.edu", "8h")
                        ↓
Tool returns structured case file:
  {
    identity:  { auth0_id, cognito_sub, status: "FORCE_CHANGE_PASSWORD", ... },
    attempts:  [4 entries, all "PasswordResetRequiredException"],
    tokens:    { last_success: "2026-04-30 14:22", last_failure: "2026-05-04 09:14" },
    lock:      { locked: false }
  }
                        ↓
Claude:
  "John's Cognito account is in FORCE_CHANGE_PASSWORD state — his
   password expired April 30 and he hasn't reset it. The 4 failed
   attempts this morning all returned PasswordResetRequiredException.
   Send him a password-reset email via the Harmony-Auth admin tool."
                        ↓
Claude:
  writeResolvedCase(...) → wiki/cases/case-2026-05-04-...
```

## Out of scope (v1)

- Per-user authentication. Hackathon scope.
- PII redaction in `writeResolvedCase`. Deferred to a follow-up ADR.
- Cross-product extension. The architecture is per-product; the second product is a follow-up ADR.
- Reading from the 40+ Harmony-Auth API endpoints directly. v1 reads underlying state from DynamoDB and logs.

## References

- [Decision 0014 — Canonical product-slug list](../decisions/0014-product-slug-canonical-list.md)
- [Decision 0015 — `case` as a fifth wiki bucket](../decisions/0015-case-as-wiki-bucket.md)
- [Decision 0016 — Tech Services debugger architecture](../decisions/0016-ts-debugger-architecture.md)
- [Decision 0013 — Three-layer LLM-wiki pattern](../decisions/0013-karpathy-wiki-pattern.md)
- [Knowledge base SCHEMA](../../knowledge/SCHEMA.md)
