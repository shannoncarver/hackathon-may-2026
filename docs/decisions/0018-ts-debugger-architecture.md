---
status: Accepted
date: 2026-05-05
category: architecture
---

# Decision 0018 — Tech Services debugger architecture

**Status:** Accepted (2026-05-05)

## Context

LINQ Technical Services engineers debug Harmony-Auth (and other LINQ products) without direct access to the data sources where root-cause evidence lives — CloudWatch Logs across 40+ Lambdas, five DynamoDB tables (`UserEvents`, `TokenCache`, `MFAEnrollment`, `LockRepository`, `SuperAdminMFA`), an OpenSearch index, and the Auth0 / Cognito management APIs. Today, every "user can't log in" or "MFA looks misconfigured" ticket means filing an escalation to engineers who hold the access. Slow, lossy, and not scalable.

The "Forge: Season 2 — Every Minute Matters" hackathon (May 2026) requires AI-leveraged solutions. Audience: Tech Services engineers using Claude Code. Demo target: one user (the project lead) presenting on a personal laptop. Production deployment is explicitly out of hackathon scope.

This decision pins the architecture for the first product surface — the Harmony-Auth debugger — and sets the pattern future product debuggers extend.

**Language:** TypeScript. The Harmony-Auth repo (`/Harmony-Auth`) is a TypeScript application that exports canonical type definitions for every DynamoDB entity the debugger queries: `MultiFactorEnrollment`, `SuperAdminMFA`, `TokenCache`, `Auth0UserEvent`, the `Lock` shape, `Auth0Connection`, and `ProductKey`. All five repository classes contain the exact query patterns (GSI names, key conditions, projection expressions) the debugger needs. Implementing in TypeScript lets `ha-debug-core` import those types directly rather than maintaining a parallel set of Python dataclasses that will drift from the source of truth. See Alternatives for the Python trade-off.

## Decision

Two components plus a Claude Code skill, one repository.

```
TypeScript ha-debug package (library layer)
              ↓
        [ha-debug CLI (commander)]
              ↑
        Claude Code via Bash,
        guided by the ts-debug skill
```

### Components

- **`ha-debug-core`** (TypeScript package) — All join logic, queries, and result shaping. Pure functions in, structured records out. Knows nothing about CLIs, transports, or the calling environment.
- **`ha-debug`** (CLI) — Argv-to-function shim over the core. Invoked by humans, shell scripts, CI jobs, and Claude Code via the Bash tool. Built with `commander`; JSON to stdout, errors to stderr — machine-readable output contract.
- **`ts-debug`** (Claude Code skill) — Markdown skill at `.claude/skills/ts-debug/SKILL.md`. Tells Claude when to invoke `ha-debug` for which ticket symptoms and how to interpret the output. The skill is what makes the CLI demo-able in Claude Code without the engineer having to remember subcommand syntax.

### Three-layer architecture

**Layer 1 — AuthProvider (swappable)**

```typescript
interface AuthProvider {
  getCredentials(service: string): Promise<Credentials>;
}
```

- `EnvAuthProvider` — reads shared read-only credentials from a local config file (`.ha-debug.env` or `ha-debug.json`) and caches tokens with a configurable TTL. Ships with the hackathon build.
- `BrokerAuthProvider` — placeholder. When Decision 0015 (centralized-platform-mcp, from `feature/auth0-logs-skill`) milestone M4 lands and the platform MCP broker ships, this implementation swaps `EnvAuthProvider` out with no changes to calling code.

**Layer 2 — API clients (stable interface)**

One client class per data source. Each client:
- Accepts an `AuthProvider` instance at construction (injected, not global).
- Handles HTTP, pagination, rate limiting, and retries internally.
- Raises `DataSourceError` on any failure — normalized shape across all sources.

Initial clients: `Auth0LogsClient`, `CognitoClient`, `DynamoDBClient` (shared across tables), `CloudWatchClient`.

> **Type reuse:** DynamoDB schema types for all five tables are imported directly from the Harmony-Auth source: `MultiFactorEnrollment` (`src/orm/MultiFactorEnrollment.ts`), `SuperAdminMFA` (`src/def/superAdminMFA.ts`), `TokenCache` (`src/def/auth0-token.ts`), `Auth0UserEvent` (`src/def/auth0/Auth0UserEvent.ts`). The `Lock` shape and GSI/key-condition constants are copied verbatim from `src/repository/LockRepository.ts`. These types are the Harmony-Auth source of truth; TypeScript gives the compiler enforcement that our queries match the actual DynamoDB schema.

**Layer 3 — CLI + output**

`commander`-based CLI. Subcommands map one-to-one to the public assemblers. Output:
- Success → JSON to stdout (Claude reads it).
- Error → structured JSON to stderr with `{"error": "<kind>", "message": "...", "retryable": true|false}`.

### Required core seams

Two seams ship with the core on day one, before any assembler is written. Per the eng-principal review:

- **`resolveSubject(emailOrUserId: string): Promise<CanonicalSubject>`** — the single place that knows Auth0 versus Cognito ID precedence, alias handling, and soft-deleted user behavior. Every assembler's first call. Without this seam, identity-resolution rules duplicate across primitives.
- **`DataSourceError extends Error`** with fields `source: string`, `kind: "missing" | "throttled" | "timeout" | "auth" | "unknown"`, `retryable: boolean`, `raw: unknown` — normalized error type across all data sources. Without normalization, six different error shapes (Auth0 4xx, Cognito throttling, DynamoDB `ProvisionedThroughputExceeded`, CloudWatch query timeouts, etc.) leak into case files as a graveyard of half-failed lookups.

### Public surface — assemblers only

The CLI subcommand list exposes only the *case-file assemblers*. Primitives stay internal (prefixed with `_` by convention and not exported from the package index). Per the eng-principal review: exposing primitives invites the model to compose them ad hoc and produce inconsistent case files. Tools should match user intents (resolve a ticket), not data sources (query a table).

**Public assemblers (v1):**

| Function | CLI subcommand | Inputs | Output |
|---|---|---|---|
| `assembleLoginFailureCase(emailOrUserId, window)` | `assemble-login-failure-case` | identity input + time window | structured timeline of identity, recent login attempts, token issuance state, and account lock state |
| `assembleMfaNotEnforcedCase(emailOrUserId)` | `assemble-mfa-not-enforced-case` | identity input | configuration snapshot of identity, MFA state, and MFA enforcement context |
| `writeResolvedCase(caseFile, hypothesis, resolution)` | `write-resolved-case` | assembled case + Claude's hypothesis + the chosen fix | sanitized markdown written to `knowledge/wiki/cases/` per [Decision 0017](0017-case-as-wiki-bucket.md) |

**Internal primitives (not exported from package index):**

`_getUserIdentity`, `_getRecentLoginAttempts`, `_getTokenIssuanceState`, `_getMfaState`, `_getAccountLockState`, `_getMfaEnforcementContext`. Not importable from `ha-debug-core`'s public namespace.

### Why CLI + skill, not MCP

Claude Code has a Bash tool — a CLI is sufficient. Claude Desktop is explicitly out of scope as the audience (confirmed 2026-05-04). Without Claude Desktop in scope, an MCP server has no audience to serve, and the CLI-plus-skill path wins on:

- Operational simplicity. One artifact (the CLI), one config file. No MCP host registration, no JSON-RPC layer.
- Dev velocity. The CLI runs without Claude in the loop — test the underlying library through a shell, not through an LLM.
- Scriptability. Engineers can pipe CLI output into shell tools or chain it in CI.
- Reversible. If Claude Desktop later becomes in-scope, an MCP server is a thin shim (~100 lines) over the same core library.

### Ticket archetypes (v1)

The two archetypes the public assemblers cover. Chosen to exercise both shapes of the data layer:

- **"Login failed for unknown reason"** — time-windowed failure investigation. Assembler joins CloudWatch logs from the auth handlers, Auth0 user logs, Cognito user state, TokenCache, and LockRepository.
- **"User was not required for MFA and TS doesn't know why"** — configuration-state question. Assembler joins MFAEnrollment, Auth0 user factors, Cognito MFA configuration, connection-level MFA policy, and SuperAdminMFA.

Future archetypes add new assemblers, not new primitives.

### Authentication — hackathon scope

The tool ships with shared read-only credentials for a non-production Harmony-Auth environment, stored in a local config file on the presenter's laptop. `EnvAuthProvider` reads from this config. No per-user authentication, no SSO, no proxy, no Microsoft Entra integration. The demo runs as a single baked-in service identity.

This is deliberately minimal because the hackathon is a single-user demo. **Production deployment will require per-user auth — likely Microsoft Entra-federated SSO with an Auth0 / Cognito broker.** That work is out of hackathon scope and will be captured in a follow-up ADR once the tool moves toward broader use. When the platform MCP broker (Decision 0015 from `feature/auth0-logs-skill`) reaches milestone M4, `BrokerAuthProvider` replaces `EnvAuthProvider` with no changes to assemblers or CLI.

### Read scope

v1 reads from DynamoDB tables (`UserEvents`, `TokenCache`, `MFAEnrollment`, `LockRepository`, `SuperAdminMFA`), CloudWatch log streams from the auth-related Lambdas, and the Auth0 / Cognito management APIs. **v1 does not read from the 40+ Harmony-Auth API endpoints directly** — case files are assembled from underlying state, not API replays.

### Cross-product extension

Other LINQ products live on different AWS accounts and have different data-source patterns. The architecture is intentionally per-product: each product gets its own `<product>-debug-core` TypeScript package, `<product>-debug` CLI, and `<product>` Claude Code skill. Naming convention and shared protocol details are deferred to a follow-up ADR when the second product comes online.

## Consequences

- Pro: Demo-able in Claude Code with a one-line CLI install (`npm install -g .` or `npx`). No MCP host to register, no JSON-RPC layer, no extra Claude Desktop configuration.
- Pro: TypeScript allows direct import of Harmony-Auth's canonical DynamoDB schema types. The compiler enforces that query results match the actual table schema; no parallel Python dataclasses to drift.
- Pro: All five Harmony-Auth repository classes contain the exact GSI names, key conditions, and marshalling options needed — copy-with-confidence rather than reverse-engineering from the DynamoDB console.
- Pro: The three-layer auth pattern (`EnvAuthProvider` → `BrokerAuthProvider`) makes the hackathon auth model a clean swap-out, not a rewrite, when production auth lands.
- Pro: The case-file assembler contract is stable; primitives can evolve internally without changing the public surface.
- Pro: Resolved cases compound. `writeResolvedCase` writes to `knowledge/wiki/cases/` per [Decision 0017](0017-case-as-wiki-bucket.md), so future debug sessions retrieve prior resolutions as context.
- Pro: Reversible. Adding an MCP transport later is a thin shim over the same core library if Claude Desktop or another MCP-only client becomes in-scope.
- Con: Node.js runtime required on the presenter's laptop. The team already works in the Harmony-Auth TypeScript repo, so this is a negligible added dependency.
- Con: Auth model is hackathon-only. Production deployment is a separate effort, not a config flip.
- Con: Cross-product extension story is sketched, not pinned. Mitigation: deferred to a follow-up ADR when needed.
- Con: Claude Desktop is unsupported. Adopting Desktop later requires building the MCP shim that was deferred here.

## Alternatives considered

- **CLI + MCP server, both shipping in v1.** Rejected: with Claude Desktop out of scope (audience confirmed 2026-05-04), the MCP server has no audience to serve. The architectural-discipline argument ("two frontends force a clean library API") doesn't justify the operational and cognitive overhead for a single-user hackathon demo. If Claude Desktop later becomes in-scope, an MCP shim (~100 lines) over the same core library is the natural extension.
- **MCP server only, no CLI.** Rejected: loses the non-LLM debugging surface, the dev-loop ergonomics, and shell scriptability. Without Claude Desktop in scope, MCP gives nothing back.
- **Compose existing AWS MCP servers + a join skill.** Rejected: Auth0 has no first-party MCP server, the join logic *is* the product, and credential handling still has to live somewhere.
- **Hosted / remote MCP server.** Rejected for hackathon scope. A remote server is the right answer if Claude.ai web later becomes in-scope.
- **Expose primitives plus assemblers as CLI subcommands.** Rejected per eng-principal review: nine commands is a wide surface, and primitives are not independently useful to a Tech Services engineer answering a ticket.
- **Per-user authentication via Microsoft Entra in v1.** Rejected for hackathon scope. The demo runs as one user on one laptop; per-user auth is a production concern, captured in a follow-up ADR.
- **Python instead of TypeScript.** Rejected. Initial rationale for Python was reuse of the `feature/auth0-logs-skill` three-layer auth pattern in `auth0_logs.py`. Rejected after inspecting Harmony-Auth: the five DynamoDB repository classes (`MultiFactorEnrollmentRepository`, `LockRepository`, `TokenCacheRepository`, `SuperAdminMFARepository`, `UserEventsRepository`) contain exact TypeScript type definitions for every entity the debugger queries. Importing those types eliminates a category of schema-drift bugs. The `auth0_logs.py` three-layer auth pattern translates cleanly to TypeScript; no capability is lost, and the Auth0 management API is accessible via the official `auth0` npm package with first-class TypeScript types.

## Sources

- [Decision 0006 — Claude Code-native](0006-claude-code-native.md) (target client surface).
- [Decision 0008 — MCP connectors](0008-mcp-connectors.md) (existing MCP integration pattern; deferred for this debugger).
- [Decision 0010 — Reference-quality posture](0010-reference-quality-posture.md) (commits to the thorough branch).
- Decision 0015 — Centralized platform MCP (`feature/auth0-logs-skill` branch; `BrokerAuthProvider` migration target when M4 lands).
- [Decision 0016 — Canonical product-slug list](0016-product-slug-canonical-list.md) (introduces `product:harmony-auth`).
- [Decision 0017 — `case` as a fifth wiki bucket](0017-case-as-wiki-bucket.md) (case persistence target).
- knowledge-curator review (2026-05-04) and eng-principal review (2026-05-04) — both consulted before this decision was committed.
- Anthropic guidance on tool design: https://www.anthropic.com/engineering/writing-tools-for-agents
- claude-code-guide specialist verification (2026-05-04): Claude Desktop has no shell-execution tool; MCP is required to invoke local capabilities. Drove the audience-scope decision.
- Harmony-Auth TypeScript source (`/Users/dainkasprak/Projects/temp-hack/Harmony-Auth`) — five DynamoDB repository classes and canonical schema types confirmed present (2026-05-05). Drove language decision from Python to TypeScript.

## History

- 2026-05-04 (initial) — Three components: core library, CLI, stdio MCP server. Audience: Claude Code + Claude Desktop. Both transports first-class. Language: TypeScript. ADR numbered 0016.
- 2026-05-04 (revised) — MCP server dropped. Audience narrowed to Claude Code. CLI + Claude Code skill is the chosen path. Reversible: MCP shim is the natural extension if Claude Desktop ever becomes in-scope.
- 2026-05-04 (revised) — Language changed to Python to match `feature/auth0-logs-skill` tooling. Three-layer auth pattern (`EnvAuthProvider` / `BrokerAuthProvider`) adopted. `Auth0LogsClient` reuse noted. ADR renumbered from 0016 to 0018 to avoid collision with `feature/auth0-logs-skill` branch (which claims 0014 for auth0-logs-skill and 0015 for centralized-platform-mcp).
- 2026-05-05 (revised) — Language reverted to TypeScript after inspecting the Harmony-Auth repo. All five DynamoDB repositories and their schema types (`MultiFactorEnrollment`, `SuperAdminMFA`, `TokenCache`, `Auth0UserEvent`, `Lock`) confirmed present as TypeScript exports. Direct type import eliminates schema-drift risk. Python alternative considered and rejected in Alternatives.
