---
title: "Centralized MCP broker pattern for LINQ"
kind: synthesis
tags: ["mcp", "auth0", "aws", "iam", "oauth", "architecture", "product:cross-cutting"]
sources:
  - "wiki/sources/mcp-authorization-spec.md"
  - "wiki/sources/mcp-tool-resource-prompt-primitives.md"
  - "wiki/sources/auth0-client-credentials-flow.md"
  - "wiki/sources/oauth-token-exchange-rfc8693.md"
  - "wiki/sources/aws-sts-assume-role-external-id.md"
  - "wiki/sources/aws-lambda-resource-based-policies.md"
entities:
  - "wiki/entities/mcp-authorization.md"
  - "wiki/entities/mcp-tool-catalog.md"
  - "wiki/entities/auth0-m2m.md"
  - "wiki/entities/oauth-token-exchange.md"
  - "wiki/entities/sts-assume-role-external-id.md"
  - "wiki/entities/lambda-resource-policy.md"
  - "wiki/entities/atlassian-mcp.md"
  - "wiki/entities/sub-agent.md"
concepts:
  - "wiki/concepts/aws-skill-credential-pattern.md"
created: 2026-05-04
updated: 2026-05-05
---

# Centralized MCP broker pattern for LINQ

A LINQ-specific synthesis of the MCP authorization spec, Auth0 M2M client credentials, RFC 8693 token exchange, AWS STS AssumeRole + External ID, and AWS Lambda resource-based policies. The pattern composes these primitives into a single architectural shape — **"Auth0-fronted MCP broker with cross-account credential exchange"** — that brokers all internal AI-agent access to LINQ product data and capabilities through one platform-owned MCP server. Recorded as [Decision 0015](../../../docs/decisions/0015-centralized-platform-mcp.md); architecture review at [`docs/research/0015-centralized-platform-mcp/`](../../../docs/research/0015-centralized-platform-mcp/00-overview.md).

## What the pattern is

A single MCP server hosted in LINQ's Platform Services AWS account. Each LINQ product runs in its own AWS account; the MCP server is the only entry point for internal AI agents (Claude Code, internal dev tools, ops dashboards) into product data. The broker resolves a tool ID via a versioned handler registry, validates the agent's identity, exchanges tokens to carry the human user's identity downstream, and performs cross-account invocation into the product account.

```
agent → MCP server → registry lookup → token exchange (OBO) → AssumeRole into product account → handler
```

## How the primitives compose

- **MCP authorization** ([`mcp-authorization`](../entities/mcp-authorization.md)) sets the agent → broker boundary. HTTP transport. OAuth 2.1 + RFC 9728 + RFC 8707 + PKCE. Token passthrough is forbidden — the broker re-issues a downstream identity at every cross-account hop.
- **MCP tool catalog** ([`mcp-tool-catalog`](../entities/mcp-tool-catalog.md)) governs the agent-facing surface. The broker exposes per-product-prefixed tool IDs (`erp.checkUserAccess`) and projects `tools/list` server-side by the authenticated principal so no agent receives the full catalog.
- **Auth0 M2M** ([`auth0-m2m`](../entities/auth0-m2m.md)) is the agent's identity. Client credentials grant. One M2M application per service-identity class — `claude-code-internal`, `ops-dashboard`, `internal-dev-tool`, plus break-glass admin. Per-handler M2M apps are forbidden by platform contract; per-handler M2M is the cost-explosion antipattern.
- **OAuth token exchange (RFC 8693)** ([`oauth-token-exchange`](../entities/oauth-token-exchange.md)) is the on-behalf-of contract. Subject token is the user JWT; actor token is the agent JWT; output JWT carries `sub = user_sub`, `act.sub = agent_client_id`, audience-bound to the product handler, TTL ≤ 5 min. If Auth0 supports RFC 8693 natively, the IdentityBroker is a thin proxy. If not — Phase A could not verify — the V1 broker is an Auth0 Action or a Platform-owned KMS-signed JWT with the same wire shape.
- **STS AssumeRole + External ID** ([`sts-assume-role-external-id`](../entities/sts-assume-role-external-id.md)) is the cross-account credential acquisition. Per-product External ID + `aws:PrincipalOrgID`-conditioned trust policy. External IDs are 32-char identifiers, not credentials. Failure mode this protects: Confused Deputy across products under registry tampering, tool-ID mis-resolution, or future product spinout into a separate AWS Org.
- **Lambda resource-based policies** ([`lambda-resource-policy`](../entities/lambda-resource-policy.md)) are the documented narrow-case alternative for invoke-only Lambdas. They are not the default — `sts:AssumeRole` is, because three handler substrates (Lambda, ECS, Step Functions) share one credential-acquisition pattern.

## How this differs from the Atlassian MCP pattern

LINQ already operates under [Decision 0008](../../../docs/decisions/0008-mcp-connectors.md), which uses the [Atlassian Remote MCP Server](../entities/atlassian-mcp.md) with **per-user OAuth 2.1**. The Atlassian pattern and the centralized broker pattern coexist; neither supersedes the other. They solve different problems:

| Aspect | [Atlassian MCP (per-user OAuth)](../entities/atlassian-mcp.md) | Centralized broker (this synthesis) |
|---|---|---|
| **Scope** | External SaaS (Confluence, Jira, JSM, Bitbucket, Compass) | Internal LINQ product data |
| **Identity** | Per-user OAuth 2.1; user's Atlassian permissions are the authorization boundary | Auth0 M2M for agent + RFC 8693 OBO for end-user |
| **Authorization** | Atlassian's own RBAC | LINQ-defined registry scopes + Auth0 RBAC permissions + handler-enforced tenant + record |
| **Credentials downstream** | User's OAuth token (audience = Atlassian) | Re-issued downstream JWT (audience = product handler) |
| **Catalog** | One MCP per SaaS, OAuth scopes gate tool visibility | One MCP for all products, server-side projection by `client_id` |
| **Hosting** | SaaS-hosted (Atlassian) | Self-hosted (LINQ Platform Services account) |

A future product onboarding ADR records which pattern applies per-product. The two patterns are not in tension.

## Where the pattern is decided in LINQ

- [Decision 0015](../../../docs/decisions/0015-centralized-platform-mcp.md) — the ADR, status Proposed.
- [`docs/research/0015-centralized-platform-mcp/`](../../../docs/research/0015-centralized-platform-mcp/00-overview.md) — five role-pass memos plus the synthesis artifacts (overview, architecture, comparison, risks, POC, open questions).
- [Pillar 6 — MCP connector inventory](../../../docs/pillars/6-mcp-connectors.md) — links to both ADR 0008 and ADR 0015.

## Open dependencies on Auth0 capabilities

Three Auth0 capabilities affect the V1 implementation but **none block** moving the ADR from Proposed to Accepted, because each has a documented fallback:

- **RFC 9728 (Protected Resource Metadata).** The MCP server self-hosts the metadata document regardless of Auth0 support — RFC 9728 is the resource server's metadata, not the AS's. No dependency.
- **RFC 8693 (Token Exchange).** If Auth0 supports it natively, the IdentityBroker is a thin proxy. If not, V1 ships an Auth0 Action or KMS-signed JWT with identical wire shape. Swappable later.
- **AssumeRoleWithWebIdentity.** V1 uses standard `AssumeRole` with the MCP server's own AWS principal in Platform Services account. WebIdentity is reserved for V2 if it removes a hop.

The status of these is tracked in [`05-open-questions.md`](../../../docs/research/0015-centralized-platform-mcp/05-open-questions.md).

## Naming

Use **"Auth0-fronted MCP broker with cross-account credential exchange"** to refer to the pattern in agent prompts and design discussion. The Atlassian pattern is **"per-user OAuth via vendor-hosted MCP."** Naming both makes their coexistence explicit and prevents confusion when a new product onboards.

## Citations

Every claim above is supported by either a wiki entity (linked inline) or by Decision 0015 / its research folder. Where Decision 0015 introduces a LINQ-specific commitment (e.g., "one M2M app per service identity"), this synthesis cites Decision 0015 as the authoritative source rather than restating LINQ-specific assumptions here.
