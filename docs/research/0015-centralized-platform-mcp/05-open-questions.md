# Open questions — stakeholder decision log

Questions surfaced during the five-role review that the available context could not resolve. Each carries the guess the coordinator would make if forced to decide today, the role(s) that surfaced it, and an assessment of whether it blocks moving the ADR from Proposed to Accepted.

## Blocks Accepted status

### Q1. ~~Does Auth0 support RFC 8693 OAuth Token Exchange natively?~~ **RESOLVED 2026-05-04 — non-blocking by design**

- **Resolution.** Auth0 Enterprise is confirmed to support RFC 8693, **but the feature is in early access** as of 2026-05-04. Production-critical paths must not depend on early-access features (no SLA parity, behavior may change, limited support escalation). V1 IdentityBroker uses **Path C — Platform-owned KMS-signed JWT** with an RFC 8693-compatible wire shape, fully decoupled from Auth0's RFC 8693 release timeline.
- **Why this no longer blocks.** Path C uses only AWS KMS (GA since 2014) and standard JOSE primitives (GA since 2015). No early-access dependency. Wire shape is identical to native RFC 8693, so future migration to Auth0's RFC 8693 grant — once GA and operationally proven — is a code change in the IdentityBroker Lambda only; handlers don't change.
- **Implementation reference.** [`deep-dives/identity-broker-implementation.md`](deep-dives/identity-broker-implementation.md) — full design rationale, JWT wire shape, KMS key configuration, JWKS endpoint, comparison with Path A, future migration story.
- **Surfaced by.** Security & IAM, MCP / AI Integration, Architecture review.
- **Owner to ask.** No external dependency remains. The IdentityBroker is fully Platform-owned in V1.

### Q2. What is LINQ's Auth0 enterprise tier and Machine-to-Machine application entitlement?

- **Why it matters.** Auth0 prices M2M applications **per application**, not per token issued. The cost-discipline rule "one M2M app per service identity" is what makes the architecture's cost sub-linear in handler count. The platform contract bans per-handler M2M apps. If LINQ's tier caps M2M apps below ~10, the V1 service-identity slate (`claude-code-internal`, `ops-dashboard`, `internal-dev-tool`, plus break-glass admin = 4) is fine; if the cap is below 4, the slate must compress.
- **Surfaced by.** Cost & Reliability.
- **Forced answer if blocking.** Assume LINQ has an Enterprise plan with ≥ 10 M2M app entitlement, sufficient for V1's 3–5 service identities and 3-year growth to ~10. **`[ASSUMED]` until Finance / IT confirms.**
- **What it does NOT block.** Anything technical — only the budget claim in the ADR's Consequences section.
- **Owner to ask.** LINQ Finance / IT.

### Q3. Are all four V1 product AWS accounts in one AWS Organization, alongside the Platform Services account?

- **Why it matters.** Drives the SCP layer of the cross-account trust model. If all in one Org, `aws:PrincipalOrgID` SCPs layer cleanly on top of External ID. If accounts are in separate Orgs (e.g., legacy product accounts predating consolidation), the SCP guardrail does not apply and External ID becomes the only mechanism.
- **Surfaced by.** Security & IAM, Architecture review.
- **Forced answer if blocking.** Assume all four product accounts and Platform Services share one AWS Organization, given the brief's "shared Platform Services account" framing. **`[ASSUMED]`.**
- **What it does NOT block.** The cross-account default (External ID) is the same either way; the SCP layer is additive defense.
- **Owner to ask.** LINQ CloudOps team.

### Q4. Does Platform Services already operate a centralized logging account, or is one a V1 prerequisite?

- **Why it matters.** The audit log lives in a Platform-Services-account log group with cross-account log shipping (CloudWatch Logs subscription filter → Kinesis Firehose → S3 with Object Lock). If a centralized logging account exists, audit shipping is configuration. If not, standing one up is a parallel ~1-week workstream.
- **Surfaced by.** Cost & Reliability.
- **Forced answer if blocking.** Assume LINQ has a logging-OU account in AWS Organizations; if not, scope it as a V1 prerequisite parallel workstream. **`[ASSUMED]`.**
- **What it does NOT block.** Audit-log shape and content design (covered in [`role-passes/security-iam.md`](role-passes/security-iam.md)) — only the destination account.
- **Owner to ask.** LINQ CloudOps / Security team.

## Does not block Accepted status

### Q5. Does LINQ already run an internal API gateway (Kong, Apigee, custom) at scale?

- **Why it matters.** If yes, [Alternative (b)](02-comparison-matrix.md) becomes more attractive; the platform MCP server should target the gateway rather than direct cross-account invoke, simplifying credential semantics and reusing existing observability.
- **Surfaced by.** Platform.
- **Forced answer if forced today.** Assume no shared internal gateway; design the MCP-server-to-handler dispatcher as the only platform-managed seam. Revisit if LINQ confirms an existing gateway.
- **Owner to ask.** LINQ Platform / engineering leadership.

### Q6. Which MCP SDK version is LINQ standardizing on?

- **Why it matters.** The 2025-06-18 spec adds `outputSchema` and `structuredContent`. Older SDKs silently drop these. Pre-2025-06-18 SDKs cannot emit structured content; clients on older SDKs ignore it.
- **Surfaced by.** MCP / AI Integration.
- **Forced answer if forced today.** Target the latest 2025-06-18-compliant release; reject any agent runtime pinned below that floor. Document in the platform handler SDK and in the registry's CI lint.
- **Owner to ask.** LINQ AI engineering / Claude Code platform owner.

### Q7. Are agent identities long-lived M2M clients (one per agent type) or short-lived (one per session)?

- **Why it matters.** Drives Auth0 client-count cardinality and the agent-side identity lifecycle.
- **Surfaced by.** Security & IAM, MCP / AI Integration, Platform.
- **Forced answer if forced today.** Long-lived M2M clients per agent type (e.g., one for `claude-code-internal`, one for `ops-dashboard`). Per-session clients via Dynamic Client Registration is overkill for an internal-only roster and balloons Auth0 client count without security benefit.
- **Owner to ask.** Resolved in V1 design unless LINQ Identity team objects.

### Q8. Does ADR 0008's per-user OAuth pattern coexist with the broker pattern, or supersede it for any product?

- **Why it matters.** [ADR 0008](../../decisions/0008-mcp-connectors.md) governs Atlassian MCP (per-user OAuth via the Atlassian remote MCP server). The new pattern is M2M + STS for internal LINQ products. The two should coexist, but a future product onboarding decision could choose either.
- **Surfaced by.** MCP / AI Integration, Architecture review.
- **Forced answer if forced today.** **Coexist.** Per-user OAuth is the right pattern when the user's permissions are the authorization boundary (external SaaS, where the SaaS's own RBAC binds the access). Broker-with-STS is the right pattern when the agent identity is the AWS principal and downstream RBAC is enforced inside LINQ. Decision per-product, recorded in each product's onboarding ADR. The Decision 0015 ADR explicitly states 0008 is **not** superseded.
- **Owner to ask.** Resolved.

### Q9. Per-handler `cacheTtlSeconds` declaration — who declares it, and what's the default?

- **Why it matters.** Caching is the highest-leverage cost lever. Handler authors will under-declare TTL (everyone wants fresh data); some handlers can safely cache for hours.
- **Surfaced by.** Cost & Reliability.
- **Forced answer if forced today.** Registry schema requires `cacheTtlSeconds` as a non-null integer; default `0` (no caching). Platform engineering reviews any value > 300 s during onboarding (one of the narrow review gates in [`role-passes/platform.md`](role-passes/platform.md)).
- **Owner to ask.** Resolved in V1 design.

### Q10. What is the agent-side retry policy?

- **Why it matters.** Aggressive retries on read-only operations are fine in principle but amplify a cache-miss storm into a thundering herd.
- **Surfaced by.** Cost & Reliability.
- **Forced answer if forced today.** Mandate exponential backoff with full jitter, max 3 retries, total budget 10 s. Document in the MCP client SDK; enforce in the platform handler SDK.
- **Owner to ask.** Resolved in V1 design.

### Q11. Does LINQ already have a normalized RBAC permission namespace across products, or do products each have their own permission grammar?

- **Why it matters.** Drives the registry's `requiredPermissions[]` shape. A normalized namespace lets handlers reference cross-product permissions cleanly; per-product grammars require product-prefixed strings (`erp:read:user`, `lms:read:enrollment`) until normalization.
- **Surfaced by.** Security & IAM.
- **Forced answer if forced today.** Per-product grammar today; registry's `requiredPermissions[]` carries product-prefixed strings until normalization happens. Normalization is a separate workstream not in V1 scope.
- **Owner to ask.** LINQ Security team if `[ASSUMED]` proves wrong.

### Q12. Is there a long-running batch agent in V1 (no live human user), or is V1 interactive-only?

- **Why it matters.** Long-running batch agents need a separate "delegation grant" pattern with explicit user pre-authorization. Interactive agents (Claude Code session, ops dashboard with a live operator) can use OBO at request time.
- **Surfaced by.** Security & IAM.
- **Forced answer if forced today.** **Interactive only in V1.** Long-running batch is a V2 design with its own ADR.
- **Owner to ask.** Resolved in V1 design unless stakeholder pushes back.

## How to use this log

Open questions move from "blocks Accepted" to "does not block" or to "resolved" only by direct stakeholder confirmation. The coordinator does not silently flip them — flagged guesses stay `[ASSUMED]` until evidence lands.

When an answer is obtained:
1. Update the relevant question above (mark `Resolved (date)` and the answer).
2. If the answer differs from the forced guess, update the ADR's Consequences section and the affected role memo.
3. If the answer surfaces new sub-questions, add them as new entries below the existing list (do not renumber).
