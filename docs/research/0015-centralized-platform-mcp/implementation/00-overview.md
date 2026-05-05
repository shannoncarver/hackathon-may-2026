# Implementation 00 — Overview

**Decision:** [`0015-centralized-platform-mcp`](../../../decisions/0015-centralized-platform-mcp.md) — Phase B implementation index.
**Owner:** Lead Implementation Architect (`10-eng-principal`).
**Status:** Phase C synthesis (2026-05-04). Drafted from 11 Phase B artifacts.

## TL;DR

This folder is the Monday-morning task list for the Phase-1 POC of the LINQ Platform MCP Server. It contains 11 substantive implementation artifacts (CloudFormation, GitHub Actions, MCP server code, registry, IdentityBroker, cross-account dispatch, sample handler, testing, Auth0, observability, repo layout) plus this overview and a folder README. Audience: the engineers who build M1 through M6. Locked: runtime (Node 20 + TypeScript), single-platform-repo + per-product-handler-repo layout, deploy ordering, sample product (ERP), Q1–Q4 forced-today defaults. Deferred: M2–M6 detail, multi-region, mutating writes, customer-facing exposure, compliance certification.

## ADR-status transition gate (CC-6)

**ADR 0015 is currently `Proposed` (see [`docs/decisions/0015-centralized-platform-mcp.md`](../../../decisions/0015-centralized-platform-mcp.md) frontmatter, dated 2026-05-04). M1 build cannot start until the ADR is promoted to `Accepted`.** This gate is non-negotiable per the implementation plan's Phase 0 entry condition. The promotion is a single-line frontmatter change plus a CHANGELOG entry; the work to support it (5-role architecture review, 25 risks, 4 blocking + 7 non-blocking open questions, 3 deep-dives, milestone-sequenced POC) is already complete and lives at [`docs/research/0015-centralized-platform-mcp/`](../). Lead owner files the promotion PR; CTO or delegate approves; M1 kickoff follows the same week.

If the ADR remains `Proposed` past 2026-05-15, escalate to the Hackathon Coordinator. Do not begin sandbox CFN deploys against the proposed-but-unaccepted design — that order has bitten LINQ before per Decision 0010 reference-quality posture.

## Milestone calendar

The full milestone sequence is in [`../04-phase-1-poc.md`](../04-phase-1-poc.md). M1 is detailed below; M2–M6 are sketched at sequencing depth.

### M1 — Platform Services scaffold (detailed)

**Purpose.** Stand up the MCP server skeleton with auth termination, well-known endpoint, and observability — no registry, no cross-account dispatch yet. Proves the Auth0 + RFC 9728 + RFC 8707 layer end-to-end against `claude-code-internal`.

**Deliverables.**

- API Gateway HTTP API + Lambda for the MCP server (single region, multi-AZ via Lambda VPC subnet selection across two AZs). Owned by `11-eng-cloudops`; specified in [`01-cloudformation.md`](01-cloudformation.md) §2.3 and [`03-mcp-server.md`](03-mcp-server.md) §2.1–2.10.
- `/.well-known/oauth-protected-resource` endpoint returning the RFC 9728 metadata document. Owned by Backend (`17-eng-ai`); specified in [`03-mcp-server.md`](03-mcp-server.md) §2.8.
- Auth0 M2M client `claude-code-internal` registered against the API resource `https://mcp.linq.platform`. JWKS validation in the Lambda with 1 h cache. Owned by `12-eng-security-iam`; specified in [`09-auth0-config.md`](09-auth0-config.md) §2.1–2.2 and [`03-mcp-server.md`](03-mcp-server.md) §2.3–2.4.
- Platform Services CloudWatch Logs group with retention configured; `/aws/apigw/platform-mcp-<env>` access log group with 400-day retention. Owned by `11-eng-cloudops`; specified in [`01-cloudformation.md`](01-cloudformation.md) §2.3 and [`10-observability-runbooks.md`](10-observability-runbooks.md) §2.1.
- GitHub Actions `pr.yml` + `deploy-main.yml` wired with OIDC federation; cfn-lint, cfn-nag, actionlint, unit, contract, schema-validate gates green on `main`. Owned by `11-eng-cloudops`; specified in [`02-github-actions.md`](02-github-actions.md) §2.2–2.5.

**Owners by step.** CFN scaffolding → `11-eng-cloudops`. Lambda code (`index.ts`, `auth.ts`, `jwks.ts`, `routes/well-known.ts`, `errors.ts`) → `17-eng-ai` (Backend lens). Auth0 dev-tenant configuration → `12-eng-security-iam`. CI gates → `11-eng-cloudops`. Smoke procedure → `15-eng-qa`.

**Exit criterion.** A signed M2M JWT from `claude-code-internal` reaches the MCP server and is validated; an unsigned or expired JWT is rejected with the correct `WWW-Authenticate: Bearer resource_metadata="..."` header. The full criterion text is in [`../04-phase-1-poc.md`](../04-phase-1-poc.md) §M1.

**ACs M1 contributes to.** AC9 (`/.well-known` self-host), AC2 (audit emission scaffold — full chain ships in M4), AC6 (cold-path latency baseline measurement starts here).

### M2 — Registry + auth gates (sketch)

DynamoDB Handler Registry, registration API with the four reject classes, server-side `tools/list` projection by `client_id`. Sequenced after M1 because the projection lever needs the auth-validated principal. Owners: `17-eng-ai` (registry + API) and `11-eng-cloudops` (table CFN). Detail: [`04-registry.md`](04-registry.md). Exit criterion: AC4 sub-cases all reject; AC7 projection returns empty list for an unauthorized `client_id`.

### M3 — IdentityBroker + cross-account (sketch)

KMS-signed JWT broker (Path C), per-product External ID generated and stored, `PlatformMcpInvoker` trust policy in the ERP product account with External ID + `aws:PrincipalOrgID` layered, STS session caching. Sequenced after M2 because the broker needs registry-resolved audience allowlist. Owner: `12-eng-security-iam`. Detail: [`05-identity-broker.md`](05-identity-broker.md), [`06-cross-account.md`](06-cross-account.md). Exit criterion: AssumeRole succeeds with correct External ID and fails with mismatch; CloudTrail confirms session tags.

### M4 — End-to-end happy path (sketch)

POC handler `erp.checkUserAccess` deployed in the ERP product account using `@linq/mcp-handler-sdk`; full 10-step pipeline executes. Sequenced after M3. Owner: `18-eng-product-handler` (handler) + `17-eng-ai` (dispatcher). Detail: [`07-poc-handler.md`](07-poc-handler.md). Exit criterion: AC1, AC2, AC5, AC6 all green for a real test request.

### M5 — Negative tests + cache + projection (sketch)

The four negative paths — tenant-scope violation, token passthrough refusal, cache hit, `tools/list` projection — wired into the CI E2E suite. Sequenced after M4 because the negatives test the deployed happy path. Owner: `15-eng-qa`. Detail: [`08-testing.md`](08-testing.md). Exit criterion: AC3, AC5, AC7, AC8 green and pinned in CI.

### M6 — Audit reconciliation + runbooks (sketch)

Cross-account log shipping (CWL → Firehose → S3 with Object Lock); daily audit-reconciliation Lambda; the three runbooks. Sequenced last because reconciliation needs steady traffic to detect drift. Owner: `11-eng-cloudops`. Detail: [`10-observability-runbooks.md`](10-observability-runbooks.md). Exit criterion: AC10 (runbooks present and reviewed); audit lag SLO green for 7 consecutive days.

## Repo layout summary

The 11 Phase B artifacts live in this hackathon repo as reference material. The actual code stand-up happens in a new Platform Services repo `linq-platform-mcp` containing `infra/` (master + 7 nested CFN stacks plus bootstrap), `src/` (`mcp-server`, `identity-broker`, `registration-api` Lambdas), `sdk/handler/{typescript,python}` (the `@linq/mcp-handler-sdk` SDK, lockstep-released), `test/`, `runbooks/`, and `.github/workflows/`. Product handler code lives in per-product repos (e.g., `linq-erp-mcp-handlers`), depends on the SDK, and registers via the platform's registration API on merge to `main`. CODEOWNERS, branch protection (2 reviewers, signed commits, force-push off), and SemVer 2.0.0 SDK policy are pinned in [`11-repo-layout.md`](11-repo-layout.md).

## Role roster

Seven implementation roles across five existing agents and four new Phase-0 specialists.

**Existing agents (5):**
- `10-eng-principal` (this agent) — Lead Implementation Architect; owns this overview and the README, runs Phase C synthesis and Phase E link audit.
- `17-eng-ai` — Backend / MCP Server Engineer (artifact 03) **and** Platform Engineer (artifact 04) under separate invocation contexts.
- `30-docs-generator` — Documentation polish (Phase D brand-voice pass).

**Phase-0 new specialists (4):**
- `11-eng-cloudops` — CloudOps Engineer; owns artifacts 01, 02, 10, 11.
- `12-eng-security-iam` — Security & IAM Engineer; owns artifacts 05, 06, 09.
- `15-eng-qa` — QA / Test Engineer; owns artifact 08.
- `18-eng-product-handler` — Product Handler Owner (proxies for the ERP team); owns artifact 07.

## Reading order by role

The recommended sequence depends on what an engineer is building.

- **CloudOps engineer (M1, M2, M6):** [11-repo-layout](11-repo-layout.md) → [01-cloudformation](01-cloudformation.md) → [02-github-actions](02-github-actions.md) → [10-observability-runbooks](10-observability-runbooks.md).
- **Backend engineer (MCP server):** [03-mcp-server](03-mcp-server.md) → [04-registry](04-registry.md) → [08-testing](08-testing.md).
- **Security & IAM engineer:** [05-identity-broker](05-identity-broker.md) → [06-cross-account](06-cross-account.md) → [09-auth0-config](09-auth0-config.md).
- **QA engineer:** [08-testing](08-testing.md), then skim 03 and 07 for the modules under test.
- **Product handler engineer (ERP team or proxy):** [07-poc-handler](07-poc-handler.md) → 03 §2.5 (10-step pipeline) → 04 §2.2 (registry item shape).
- **Lead / reviewer:** this overview → 04-phase-1-poc → spot-check each artifact's §3 acceptance criteria and §7 risks-protected-against.

## Cross-cutting decisions (reconciled)

| ID | Decision | Reflected in |
|---|---|---|
| **CC-1** | Runtime: Node 20 + TypeScript [ASSUMED, Q-IMPL.1]. AWS SDK v3, `jose@5`, AJV 2020. | 03 §2.2, 05 §2.2, 07 §2.3, 08 §2.1, 11 §2.1 |
| **CC-2** | Single platform repo (`linq-platform-mcp`) plus per-product handler repos (e.g., `linq-erp-mcp-handlers`); Phase B artifacts are reference material in this hackathon repo. | 11 §2.1 |
| **CC-3** | Deploy order: `01-network → 02-secrets → 04-registry → 03-mcp-server → 05-identity-broker → 06-audit → 04-registry-seed → 07-product-handler-trust`. Master template `DependsOn` is the source of truth; GHA mirrors it linearly. | 01 §2.1, 02 §2.3 |
| **CC-4** | Sample handler product: ERP `[ASSUMED]`. Synthetic-product fallback if ERP team is unavailable; tool ID `erp.checkUserAccess` v1.0.0. | 07 §1, 06 §2.1, 09 §2.3 |
| **CC-5 / Q1** | Closed by Path C — Platform-owned KMS-signed JWT (ECDSA P-256). Auth0 RFC 8693 native grant not used in V1. | 05 §1, 09 §2.4 |
| **CC-5 / Q2** | Auth0 entitlement ≥ 10 M2M apps `[ASSUMED]`; V1 uses 3 active + 2 dormant. | 09 §2.2 |
| **CC-5 / Q3** | All four V1 product accounts share one AWS Organization `[ASSUMED]`. External ID + `aws:PrincipalOrgID` layered (not substituted). | 06 §2.1, 01 §2.4 |
| **CC-5 / Q4** | Centralized logging-OU account exists `[ASSUMED]`. Firehose lands records in the logging account; S3 Object Lock at 365-day retention V1 with documented 7-year upgrade path. | 10 §2.4, 06 cross-ref |
| **CC-6** | ADR 0015 status transition: `Proposed` → `Accepted` is the M1-kickoff gate. See "ADR-status transition gate" above. | this overview, all 11 artifacts via ADR cross-reference |

## AC coverage map

Every V1 acceptance criterion from [`../04-phase-1-poc.md`](../04-phase-1-poc.md) maps to a primary owning artifact and at least one secondary.

| AC | Title | Primary | Secondary |
|---|---|---|---|
| AC1 | End-to-end success | [08-testing](08-testing.md) | 03, 04, 05, 06, 07 |
| AC2 | Audit record completeness | [03-mcp-server](03-mcp-server.md) (emission) | 10 (delivery), 08 (assertion) |
| AC3 | Tenant-scope enforcement | [03-mcp-server](03-mcp-server.md) | 04 (registry rule), 08 (test) |
| AC4 | Registry write enforcement | [04-registry](04-registry.md) | 08 (test) |
| AC5 | Cache effectiveness | [03-mcp-server](03-mcp-server.md) (in-process) | 06 (STS cache), 08 (timing assertions) |
| AC6 | Cold-path latency P95 ≤ 1500 ms | [03-mcp-server](03-mcp-server.md) | 10 (alarm), 08 (timing) |
| AC7 | `tools/list` projection | [03-mcp-server](03-mcp-server.md) | 08 (test) |
| AC8 | Token passthrough refusal | [03-mcp-server](03-mcp-server.md) | 07 (handler-side defense), 08 (test) |
| AC9 | `/.well-known/oauth-protected-resource` self-host | [03-mcp-server](03-mcp-server.md) | 08 (curl smoke) |
| AC10 | Documentation parity | [10-observability-runbooks](10-observability-runbooks.md) | this overview (links to runbooks) |

Phase E gate: every AC has at least one automated assertion in `08-testing.md`.

## Risk coverage map

Every R-number from [`../03-risks-register.md`](../03-risks-register.md) is cited by at least one artifact under "Risks protected against."

| Risk | Severity | Cited by |
|---|---|---|
| R1 — tenant leakage | HIGH | 03, 04, 07 |
| R2 — Confused Deputy | HIGH | 06, 01 |
| R3 — token passthrough | HIGH | 03, 04, 07, 08 |
| R4 — catalog leak | HIGH | 03, 08 |
| R5 — RFC 9728 self-host | HIGH | 03, 05, 08 |
| R6 — Auth0 M2M cost | HIGH | 02, 04, 09, 11 |
| R7 — availability | HIGH | 01, 10 |
| R8 — runaway agent | HIGH | 03, 08 |
| R9 — RFC 8693 unsupported | MED | 05 |
| R10 — audit principal correlation | MED | 03, 06, 08 |
| R11 — `listChanged` storms | MED | 03, 04, 10 |
| R12 — description quality | MED | 04 |
| R13 — handler timeout discipline | MED | 03, 04 |
| R14 — schema drift | MED | 04, 07, 08 |
| R15 — cold-start | MED | 03, 10 |
| R16 — STS quota | MED | 06, 03, 10 |
| R17 — registry cache staleness | MED | 03, 04 |
| R18 — cross-account log shipping silent failure | MED | 01, 10, 08 |
| R19 — `aud` mis-binding | MED | 03, 09 |
| R20 — External ID treated as a secret | LOW | 06, 05, 01 |
| R21 — Lambda resource-policy drift | LOW | 06 |
| R22 — DynamoDB hot partition | LOW | 01, 04 |
| R23 — Auth0 outage | LOW | 04, 09, 10 |
| R24 — outbound IP allowlists | LOW | 11 |
| R25 — annotation trust V2 | LOW | 04 (V2 note) |

Phase E gate: every R-number has at least one artifact citing it under "Risks protected against."
