---
status: Accepted
date: 2026-05-04
category: architecture
---

# Decision 0016 — Tech Services debugger architecture

**Status:** Accepted (2026-05-04)

## Context

LINQ Technical Services engineers debug Harmony-Auth (and other LINQ products) without direct access to the data sources where root-cause evidence lives — CloudWatch Logs across 40+ Lambdas, five DynamoDB tables (`UserEvents`, `TokenCache`, `MFAEnrollment`, `LockRepository`, `SuperAdminMFA`), an OpenSearch index, and the Auth0 / Cognito management APIs. Today, every "user can't log in" or "MFA looks misconfigured" ticket means filing an escalation to engineers who hold the access. Slow, lossy, and not scalable.

The "Forge: Season 2 — Every Minute Matters" hackathon (May 2026) requires AI-leveraged solutions. Audience: Tech Services engineers using Claude Code. Demo target: one user (the project lead) presenting on a personal laptop. Production deployment is explicitly out of hackathon scope.

This decision pins the architecture for the first product surface — the Harmony-Auth debugger — and sets the pattern future product debuggers extend.

## Decision

Two components plus a Claude Code skill, one repository.

```
TypeScript core library (ha-debug-core)
              ↓
        [CLI binary (ha-debug)]
              ↑
        Claude Code via Bash,
        guided by the ts-debug skill
```

### Components

- **`ha-debug-core`** — TypeScript library. All join logic, queries, and result shaping. Pure functions in, structured records out. Knows nothing about CLIs, transports, or the calling environment.
- **`ha-debug` (CLI)** — Argv-to-function shim over the core. Invoked by humans, shell scripts, CI jobs, and Claude Code via the Bash tool.
- **`ts-debug` (Claude Code skill)** — Markdown skill at `.claude/skills/ts-debug/SKILL.md`. Tells Claude when to invoke `ha-debug` for which ticket symptoms and how to interpret the output. The skill is what makes the CLI demo-able in Claude Code without the engineer having to remember subcommand syntax.

### Why CLI + skill, not MCP

Claude Code has a Bash tool — a CLI is sufficient. Claude Desktop is explicitly out of scope as the audience (confirmed 2026-05-04). Without Claude Desktop in scope, an MCP server has no audience to serve, and the CLI-plus-skill path wins on:

- Operational simplicity. One artifact (the CLI), one config file. No MCP host registration, no `claude_desktop_config.json` dance, no JSON-RPC layer.
- Dev velocity. The CLI runs without Claude in the loop — test the underlying library through a shell, not through an LLM.
- Scriptability. Engineers can pipe CLI output into shell tools or chain it in CI.
- Reversible. If Claude Desktop later becomes in-scope, an MCP server is a thin shim (~100 lines) over the same core library.

### Public surface — assemblers only

The CLI subcommand list exposes only the *case-file assemblers*. Primitives stay internal (marked `@internal`). Per the eng-principal review (2026-05-04): exposing primitives invites the model to compose them ad hoc and produce inconsistent case files. Tools should match user intents (resolve a ticket), not data sources (query a table).

**Public assemblers (v1):**

| Function | Inputs | Output |
|---|---|---|
| `assembleLoginFailureCase(emailOrUserId, window)` | identity input + time window | structured timeline of identity, recent login attempts, token issuance state, and account lock state |
| `assembleMFANotEnforcedCase(emailOrUserId)` | identity input | configuration snapshot of identity, MFA state, and MFA enforcement context |
| `writeResolvedCase(caseFile, hypothesis, resolution)` | assembled case + Claude's hypothesis + the chosen fix | sanitized markdown written to `knowledge/wiki/cases/` per [Decision 0015](0015-case-as-wiki-bucket.md) |

**Internal primitives (not exposed):**

`getUserIdentity`, `getRecentLoginAttempts`, `getTokenIssuanceState`, `getMFAState`, `getAccountLockState`, `getMFAEnforcementContext`. Marked `@internal` in the library.

### Required core seams

Two seams ship with the core on day one, before any assembler is written. Per the eng-principal review:

- **`resolveSubject(emailOrUserId) -> CanonicalSubject`** — the single place that knows Auth0 versus Cognito ID precedence, alias handling, and soft-deleted user behavior. Every assembler's first call. Without this seam, identity-resolution rules duplicate across primitives.
- **`DataSourceError { source, kind: "missing"|"throttled"|"timeout"|"auth"|"unknown", retryable, raw }`** — normalized error type across all six data sources. Without normalization, six error shapes (Auth0 4xx, Cognito throttling, DynamoDB `ProvisionedThroughputExceeded`, CloudWatch query timeouts, etc.) leak into case files as a graveyard of half-failed lookups.

### Ticket archetypes (v1)

The two archetypes the public assemblers cover. Chosen to exercise both shapes of the data layer:

- **"Login failed for unknown reason"** — time-windowed failure investigation. Assembler joins CloudWatch logs from the auth handlers, Auth0 user logs, Cognito user state, TokenCache, and LockRepository.
- **"User was not required for MFA and TS doesn't know why"** — configuration-state question. Assembler joins MFAEnrollment, Auth0 user factors, Cognito MFA configuration, connection-level MFA policy, and SuperAdminMFA.

Future archetypes add new assemblers, not new primitives.

### Authentication — hackathon scope

The tool ships with shared read-only credentials for a non-production Harmony-Auth environment, stored in a local config file on the presenter's laptop. The CLI reads from this config. No per-user authentication, no SSO, no proxy, no Microsoft Entra integration. The demo runs as a single baked-in service identity.

This is deliberately minimal because the hackathon is a single-user demo. **Production deployment will require per-user auth — likely Microsoft Entra-federated SSO with an Auth0 / Cognito broker.** That work is out of hackathon scope and will be captured in a follow-up ADR once the tool moves toward broader use.

### Read scope

v1 reads from DynamoDB tables (`UserEvents`, `TokenCache`, `MFAEnrollment`, `LockRepository`, `SuperAdminMFA`), CloudWatch log streams from the auth-related Lambdas, and the Auth0 / Cognito management APIs. **v1 does not read from the 40+ Harmony-Auth API endpoints directly** — case files are assembled from underlying state, not API replays.

### Cross-product extension

Other LINQ products live on different AWS accounts and have different data-source patterns. The architecture is intentionally per-product: each product gets its own `<product>-debug-core`, `<product>-debug` CLI, and `<product>` Claude Code skill. Naming convention and shared protocol details are deferred to a follow-up ADR when the second product comes online.

## Consequences

- Pro: Demo-able in Claude Code with a one-line CLI install. No MCP host to register, no JSON-RPC layer, no extra Claude Desktop configuration.
- Pro: The case-file assembler contract is stable; primitives can evolve internally without changing the public surface.
- Pro: Resolved cases compound. `writeResolvedCase` writes to `knowledge/wiki/cases/` per [Decision 0015](0015-case-as-wiki-bucket.md), so future debug sessions retrieve prior resolutions as context.
- Pro: Reversible. Adding an MCP transport later is a thin shim over the same core library if Claude Desktop or another MCP-only client becomes in-scope.
- Con: Claude Desktop is unsupported. Adopting Desktop later requires building the MCP shim that was deferred here.
- Con: Auth model is hackathon-only. Production deployment is a separate effort, not a config flip.
- Con: Cross-product extension story is sketched, not pinned. Mitigation: deferred to a follow-up ADR when needed.

## Alternatives considered

- **CLI + MCP server, both shipping in v1.** Rejected: with Claude Desktop out of scope (audience confirmed 2026-05-04), the MCP server has no audience to serve. The architectural-discipline argument ("two frontends force a clean library API") doesn't justify the operational and cognitive overhead for a single-user hackathon demo. If Claude Desktop later becomes in-scope, an MCP shim (~100 lines) over the same core library is the natural extension.
- **MCP server only, no CLI.** Rejected: loses the non-LLM debugging surface, the dev-loop ergonomics, and shell scriptability. Without Claude Desktop in scope, MCP gives nothing back.
- **Compose existing AWS MCP servers + a join skill.** Rejected: Auth0 has no first-party MCP server, the join logic *is* the product, and credential handling still has to live somewhere.
- **Hosted / remote MCP server.** Rejected for hackathon scope. A remote server is the right answer if Claude.ai web later becomes in-scope.
- **Expose primitives plus assemblers as CLI subcommands.** Rejected per eng-principal review: nine commands is a wide surface, and primitives are not independently useful to a Tech Services engineer answering a ticket.
- **Per-user authentication via Microsoft Entra in v1.** Rejected for hackathon scope. The demo runs as one user on one laptop; per-user auth is a production concern, captured in a follow-up ADR.

## Sources

- [Decision 0006 — Claude Code-native](0006-claude-code-native.md) (target client surface).
- [Decision 0008 — MCP connectors](0008-mcp-connectors.md) (existing MCP integration pattern; deferred for this debugger).
- [Decision 0010 — Reference-quality posture](0010-reference-quality-posture.md) (commits to the thorough branch).
- [Decision 0014 — Canonical product-slug list](0014-product-slug-canonical-list.md) (introduces `product:harmony-auth`).
- [Decision 0015 — `case` as a fifth wiki bucket](0015-case-as-wiki-bucket.md) (case persistence target).
- knowledge-curator review (2026-05-04) and eng-principal review (2026-05-04) — both consulted before this decision was committed.
- Anthropic guidance on tool design: https://www.anthropic.com/engineering/writing-tools-for-agents
- claude-code-guide specialist verification (2026-05-04): Claude Desktop has no shell-execution tool; MCP is required to invoke local capabilities. Drove the audience-scope decision.

## History

- 2026-05-04 (initial) — Three components: core library, CLI, stdio MCP server. Audience: Claude Code + Claude Desktop. Both transports first-class.
- 2026-05-04 (revised) — MCP server dropped. Audience narrowed to Claude Code. CLI + Claude Code skill is the chosen path. Reversible: MCP shim is the natural extension if Claude Desktop ever becomes in-scope.
