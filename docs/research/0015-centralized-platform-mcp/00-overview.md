# Decision 0015 — Centralized Platform MCP Server: research overview

**Status:** Architecture review complete; ADR drafted as Proposed.
**Date:** 2026-05-04
**Owners (review):** coordinator (Lead Solutions Architect) + 5 specialist roles (see roster below).
**Owners (next phase):** platform team (registry + dispatcher), security team (Auth0 + IAM), each product team (handlers).

## What this folder contains

| File | Purpose |
|---|---|
| [`00-overview.md`](00-overview.md) | This file — TL;DR, reading order, role roster |
| [`01-architecture.md`](01-architecture.md) | Component diagram, cross-account trust diagram, three reference flows |
| [`02-comparison-matrix.md`](02-comparison-matrix.md) | Proposed design scored against three alternatives |
| [`03-risks-register.md`](03-risks-register.md) | Severity-rated risks consolidated from all five role memos |
| [`04-phase-1-poc.md`](04-phase-1-poc.md) | One-product / one-handler / one-agent POC scope with acceptance criteria |
| [`05-open-questions.md`](05-open-questions.md) | Stakeholder decision log; each question lists the guess we'd make if forced |
| [`role-passes/`](role-passes/) | Five raw specialist memos (audit trail; do not edit) |
| [`deep-dives/`](deep-dives/) | Educational / further-reading docs that expand on specific design concerns. Not part of the formal review record. |

The ADR itself lives at [`docs/decisions/0015-centralized-platform-mcp.md`](../../decisions/0015-centralized-platform-mcp.md).

## TL;DR — recommendation

**Adopt the centralized platform MCP server design with the refinements below.** The proposed centralized broker is structurally sound for V1 governance goals (read-only, internal, 4 products, 40–200 handlers). It is the correct V1 posture and the correct stepping stone to a future hybrid pattern, but it requires explicit refinements before merge.

The non-optional refinements:

1. **Tooling and protocol fit.** HTTP/SSE transport pinned to MCP spec 2025-06-18. Per-product prefixes (`erp.*`, `crm.*`) from day one. Server-side `tools/list` projection by authenticated principal so no agent loads the full catalog. Without this third change, the architecture fails on its second product onboard, not its tenth.
2. **Authorization split.** MCP server enforces `(agent_scope, user_permission, tool_id)` from the registry. Handlers enforce tenant + record. Registry **rejects** any handler entry missing a `tenantSourceClaim` field. The MCP server reads tenant from the user's verified token and injects it as a separate, signed argument; the agent cannot supply tenant directly.
3. **End-user identity propagation.** RFC 8693 token exchange as the contract. If Auth0 supports RFC 8693 natively, the broker is a thin proxy; if not, the V1 broker is an Auth0 Action or a Platform-owned signer with the same wire shape. The MCP server self-hosts `/.well-known/oauth-protected-resource` regardless of Auth0 RFC 9728 support.
4. **Cross-account default.** `sts:AssumeRole` with **per-product External ID** layered with `aws:PrincipalOrgID` SCP guardrails. Lambda resource-based policies are documented narrow-case alternatives, never the default. External IDs are identifiers, not credentials.
5. **Read-only enforceability.** Every registered tool declares `sideEffects`. The MCP server refuses to register `sideEffects: "write"` in V1. A separate URL prefix is reserved for mutating tools when V2 lands.
6. **Forward-compat reservations.** `idempotencyKey` reserved in the input envelope today. Mutation error classes (`IDEMPOTENCY_CONFLICT`, `PRECONDITION_FAILED`, `PARTIAL_SUCCESS`) reserved in the error envelope enum today. Each is a one-line addition now and a breaking change later.
7. **Federation escape hatch.** `handlerType: "remote-mcp"` reserved in the registry today. Activated when handler count exceeds 800 OR ≥ 2 product teams are review-bottlenecked at the platform write path. Cheapest possible insurance against centralization-bottleneck risk.
8. **Cost discipline.** One Auth0 M2M application per service-identity class (3–5 total in V1). Shared per-product IAM roles with handler-name-conditioned policies. Templated dashboards with handler as a CloudWatch dimension. These three rules are what make the cost profile sub-linear in handler count.

The pattern name — to keep it distinct from [Decision 0008](../../decisions/0008-mcp-connectors.md) per-user OAuth — is **"Auth0-fronted MCP broker with cross-account credential exchange."**

## Role roster

The review used five lenses. Two mapped to existing LINQ specialists; three were filled by general-purpose agents briefed with focused context (LINQ has no dedicated security/platform/cost specialist agent yet).

| Role | Agent | Memo |
|---|---|---|
| Lead Solutions Architect | coordinator (synthesis owner per [`.claude/rules/coordination.md`](../../../.claude/rules/coordination.md)) | This folder — overview, ADR |
| Architecture review | [`eng-principal`](../../../.claude/agents/10-eng-principal.md) | [`role-passes/architecture.md`](role-passes/architecture.md) |
| MCP / AI Integration | [`eng-ai`](../../../.claude/agents/17-eng-ai.md) | [`role-passes/mcp-integration.md`](role-passes/mcp-integration.md) |
| Security & IAM | general-purpose (briefed) | [`role-passes/security-iam.md`](role-passes/security-iam.md) |
| Platform | general-purpose (briefed) | [`role-passes/platform.md`](role-passes/platform.md) |
| Cost & Reliability | general-purpose (briefed) | [`role-passes/cost-reliability.md`](role-passes/cost-reliability.md) |

## Disagreements surfaced and resolved

The review surfaced one substantive role-level disagreement; it is recorded here rather than smoothed over.

- **External ID inside one AWS Organization.** Architecture review argued External ID is optional intra-Org and recommended `aws:PrincipalOrgID`-conditioned trust policies as substitute. Security & IAM treated External ID as **mandatory** belt-and-braces, citing forward-compat to product spinout / partner accounts and the textbook Confused Deputy framing. Coordinator resolved in Security's favor — External ID is a 32-char identifier per product, not a rotated secret, and the protection is real if a product ever moves out of the Org. Both controls layer (`aws:PrincipalOrgID` is added on top, not in place of External ID). Documented in the ADR's Decision section.

## Reading order

If you have 5 minutes:
1. [ADR](../../decisions/0015-centralized-platform-mcp.md) — Decision section only.

If you have 20 minutes:
1. ADR (full).
2. [`02-comparison-matrix.md`](02-comparison-matrix.md) — confirms why the proposed design wins for V1.
3. [`03-risks-register.md`](03-risks-register.md) — top three HIGH risks and their mitigations.

If you are about to scope the POC:
1. ADR.
2. [`01-architecture.md`](01-architecture.md) — diagrams and reference flows.
3. [`04-phase-1-poc.md`](04-phase-1-poc.md) — milestone-level acceptance criteria.
4. [`05-open-questions.md`](05-open-questions.md) — what blocks Accepted status.

If you are doing the implementation:
1. All five [`role-passes/`](role-passes/) memos. They are the raw working notes; the ADR distills them.

## What "Proposed" means here

The ADR is **Proposed**, not Accepted. It moves to Accepted when the four blocking open questions in [`05-open-questions.md`](05-open-questions.md) close — Auth0 RFC 8693 native support, LINQ Auth0 enterprise tier, AWS Org topology, and centralized logging account existence.

Until then, the design path is committed and the V1 implementation can begin work that is independent of those four answers (registry schema, dispatcher abstraction, MCP server scaffolding, audit-log shape, POC handler) without re-litigation.
