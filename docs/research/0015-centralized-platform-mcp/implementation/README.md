# Implementation — Decision 0015 Phase B artifacts

This folder is the implementation index for [Decision 0015 — Centralized Platform MCP Server with cross-account dispatch](../../../decisions/0015-centralized-platform-mcp.md). It contains the 11 substantive artifacts produced by Phase B (CloudFormation, GitHub Actions, MCP server, registry, IdentityBroker, cross-account dispatch, sample handler, testing, Auth0, observability, repo layout) plus an overview that fronts them. Audience: engineers implementing the Phase-1 POC milestones M1 through M6. Locked: runtime (Node 20 + TypeScript), deploy ordering, sample product (ERP), Q1–Q4 forced-today defaults. **Build kickoff is gated on ADR 0015 promoting from `Proposed` to `Accepted`** — see [`00-overview.md`](00-overview.md).

## Folder index

| File | Owner | One-line summary |
|---|---|---|
| [`00-overview.md`](00-overview.md) | `10-eng-principal` (Lead) | Entry-point doc — TL;DR, M1 detail + M2–M6 sketches, role roster, reading order, cross-cutting decisions, AC + risk coverage maps. |
| [`01-cloudformation.md`](01-cloudformation.md) | `11-eng-cloudops` | Master template + 7 nested stacks; deploy ordering; cross-stack import contract; daily drift detection; stuck-stack recovery. |
| [`02-github-actions.md`](02-github-actions.md) | `11-eng-cloudops` | PR / main / release workflows; OIDC federation; reusable `stack-deploy.yml`; CC-3 deploy ordering mirrored linearly. |
| [`03-mcp-server.md`](03-mcp-server.md) | `17-eng-ai` (Backend) | MCP server Lambda (TypeScript): JSON-RPC dispatcher, JWT verify, JWKS cache, 10-step `tools/call` pipeline, RFC 9728 self-host. |
| [`04-registry.md`](04-registry.md) | `17-eng-ai` (Platform) | DynamoDB Handler Registry table + GSIs + Streams; registration API with 4 reject classes; `mcp-handler-lint` rule pack; ERP seed item. |
| [`05-identity-broker.md`](05-identity-broker.md) | `12-eng-security-iam` | Path C IdentityBroker — KMS asymmetric ECDSA P-256 signing, RFC 8693 wire shape, 5 min TTL, JWKS overlap during rotation. |
| [`06-cross-account.md`](06-cross-account.md) | `12-eng-security-iam` | `PlatformMcpInvoker` trust policy with External ID + `aws:PrincipalOrgID` layered; STS session cache; session-tag strategy; SCP layering. |
| [`07-poc-handler.md`](07-poc-handler.md) | `18-eng-product-handler` | Sample `erp.checkUserAccess` handler with `@linq/mcp-handler-sdk`; seed table; minimal exec role; handler-side JWT verify; contract test rig. |
| [`08-testing.md`](08-testing.md) | `15-eng-qa` | Four-layer pyramid; 10 ACs paired with 10 negatives; JWT validation matrix; localstack + SAM-local dev; MCP Inspector smoke. |
| [`09-auth0-config.md`](09-auth0-config.md) | `12-eng-security-iam` | Auth0 API resource (`https://mcp.linq.platform`); M2M apps per service-identity class; per-product RBAC grammar; dev-tenant test users; Identity-team RACI. |
| [`10-observability-runbooks.md`](10-observability-runbooks.md) | `11-eng-cloudops` | Custom EMF metrics; templated dashboard with `Handler` dimension; alarm matrix; Firehose → S3 Object Lock; 3 runbooks in full. |
| [`11-repo-layout.md`](11-repo-layout.md) | `11-eng-cloudops` | `linq-platform-mcp` directory tree, CODEOWNERS, branch protection, contributing guide outline, SemVer SDK policy, Decision-0008 coexistence note. |

## Reading order

For the full picture, read in this order:

1. [`00-overview.md`](00-overview.md) — start here; everything else is referenced from here.
2. [`../04-phase-1-poc.md`](../04-phase-1-poc.md) — the 10 V1 acceptance criteria the implementation chases.
3. [`11-repo-layout.md`](11-repo-layout.md) — where this code lives (new repo, not this one).
4. [`01-cloudformation.md`](01-cloudformation.md) → [`02-github-actions.md`](02-github-actions.md) — the deploy substrate.
5. [`03-mcp-server.md`](03-mcp-server.md) → [`04-registry.md`](04-registry.md) — the hot path.
6. [`05-identity-broker.md`](05-identity-broker.md) → [`06-cross-account.md`](06-cross-account.md) → [`09-auth0-config.md`](09-auth0-config.md) — the identity layer.
7. [`07-poc-handler.md`](07-poc-handler.md) — what the broker dispatches into.
8. [`08-testing.md`](08-testing.md) → [`10-observability-runbooks.md`](10-observability-runbooks.md) — verifying and operating.

## Where to start by role

- **CloudOps engineer:** [`11-repo-layout.md`](11-repo-layout.md), [`01-cloudformation.md`](01-cloudformation.md), [`02-github-actions.md`](02-github-actions.md), [`10-observability-runbooks.md`](10-observability-runbooks.md).
- **Backend engineer:** [`03-mcp-server.md`](03-mcp-server.md), [`04-registry.md`](04-registry.md).
- **Security & IAM engineer:** [`05-identity-broker.md`](05-identity-broker.md), [`06-cross-account.md`](06-cross-account.md), [`09-auth0-config.md`](09-auth0-config.md).
- **QA engineer:** [`08-testing.md`](08-testing.md), then skim [`03-mcp-server.md`](03-mcp-server.md) and [`07-poc-handler.md`](07-poc-handler.md) for the modules under test.
- **Product handler engineer:** [`07-poc-handler.md`](07-poc-handler.md), then [`03-mcp-server.md`](03-mcp-server.md) §2.5 (10-step pipeline) and [`04-registry.md`](04-registry.md) §2.2 (registry item shape).
- **Lead / reviewer:** [`00-overview.md`](00-overview.md), then spot-check each artifact's §3 acceptance criteria and §7 risks-protected-against.

## Related references

- ADR — [`docs/decisions/0015-centralized-platform-mcp.md`](../../../decisions/0015-centralized-platform-mcp.md) — currently `Proposed`; M1 build is gated on `Accepted`.
- Research index — [`../00-overview.md`](../00-overview.md) — 5 role-pass memos, 25 risks, 11 open questions, 3 deep dives, comparison matrix.
- POC scope — [`../04-phase-1-poc.md`](../04-phase-1-poc.md) — milestones M1 through M6 and the 10 acceptance criteria.
- Implementation plan — `~/.claude/plans/implementation-plan-centralized-dapper-stearns.md` (out-of-tree author plan; cited for traceability only).
- Decision 0008 coexistence — [`docs/decisions/0008-mcp-connectors.md`](../../../decisions/0008-mcp-connectors.md) — per-user OAuth pattern (Atlassian) coexists with this broker pattern; boundary documented in [`11-repo-layout.md`](11-repo-layout.md) §2.6.
