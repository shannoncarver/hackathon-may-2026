# Wiki index

Master catalog for the LINQ Hackathon knowledge base. Every wiki page is listed here under its bucket with a one-line summary and tag set. The knowledge-curator updates this file on every ingest. Conventions: [`knowledge/SCHEMA.md`](../SCHEMA.md).

## Entities

| Page | Tags | Summary |
|---|---|---|
| [atlassian-mcp](entities/atlassian-mcp.md) | `mcp`, `atlassian`, `confluence`, `jira`, `jira-service-management`, `bitbucket`, `compass`, `rovo`, `product:cross-cutting` | Atlassian Remote MCP Server — OAuth-mediated integration layer connecting AI clients to Jira, Confluence, JSM, Bitbucket Cloud, Compass, and beta cross-product search. 15 permission groups; ~60 tools. |
| [auth0-m2m](entities/auth0-m2m.md) | `auth0`, `oauth`, `m2m`, `authentication`, `jwt`, `product:cross-cutting` | Auth0 Machine-to-Machine (client credentials flow) — token issuance, audience/scope semantics, token lifecycle, and security constraints for backend service authentication. |
| [forge-linq-hackathon-program](entities/forge-linq-hackathon-program.md) | `product:cross-cutting`, `hackathon`, `forge`, `confluence` | LINQ's internal quarterly hackathon program — two formats (Race and Project), 2026 season schedule, recognition structure, and business-cycle rationale. |
| [forge-season-2-every-minute-matters](entities/forge-season-2-every-minute-matters.md) | `product:cross-cutting`, `hackathon`, `forge`, `confluence`, `season-2` | The Forge Season 2 (Q2 2026) — "Every Minute Matters" — May 4–8, five-criterion judging rubric, AI-required Project Format event. |
| [lambda-resource-policy](entities/lambda-resource-policy.md) | `aws`, `lambda`, `iam`, `cross-account`, `resource-policy`, `product:cross-cutting` | AWS Lambda resource-based policy for cross-account invoke — structure, add-permission CLI, alias-locking, SourceAccount/SourceArn conditions, and comparison with AssumeRole-based access. |
| [mcp-authorization](entities/mcp-authorization.md) | `mcp`, `oauth`, `authorization`, `security`, `product:cross-cutting` | MCP OAuth 2.1 authorization layer for HTTP transports — Protected Resource Metadata discovery, Dynamic Client Registration, PKCE, resource parameter (RFC 8707), token passthrough prohibition, and audience validation. |
| [mcp-tool-catalog](entities/mcp-tool-catalog.md) | `mcp`, `protocol`, `tools`, `discovery`, `product:cross-cutting` | MCP tool catalog shape (name, description, inputSchema, outputSchema, annotations), tools/list discovery, listChanged notifications, and invocation protocol. |
| [oauth-token-exchange](entities/oauth-token-exchange.md) | `oauth`, `rfc`, `token-exchange`, `delegation`, `impersonation`, `product:cross-cutting` | RFC 8693 OAuth 2.0 Token Exchange — grant type, impersonation vs. delegation patterns, subject_token/actor_token, act JWT claim, and delegation chain semantics. |
| [sts-assume-role-external-id](entities/sts-assume-role-external-id.md) | `aws`, `iam`, `sts`, `security`, `cross-account`, `product:cross-cutting` | AWS STS AssumeRole with External ID — Confused Deputy prevention, trust policy configuration, multi-tenant cross-account access pattern, and external ID format constraints. |
| [sub-agent](entities/sub-agent.md) | `product:cross-cutting`, `anthropic`, `claude-code` | Specialized Claude Code AI assistant with its own context window, system prompt, and tools. |

## Concepts

| Page | Tags | Summary |
|---|---|---|
| [project-format](concepts/project-format.md) | `hackathon`, `forge`, `product:cross-cutting` | Four-day cross-functional hackathon event format — self-formed teams, working prototype submission, judging on impact, creativity, feasibility, and theme alignment. |
| [race-format](concepts/race-format.md) | `hackathon`, `forge`, `product:cross-cutting` | Biweekly hackathon challenge series — four races per quarter, PR-label-based scoring, cumulative season leaderboard, used in lower-capacity quarters. |

## Sources

| Page | Tags | Summary |
|---|---|---|
| [Understand Atlassian Rovo MCP Server](sources/atlassian-remote-mcp-understand.md) | `mcp`, `atlassian`, `rovo`, `admin`, `product:cross-cutting` | Atlassian admin support page — IP allowlisting integration with MCP requests, AI-tool outbound IP gotcha, auth method overview. Thin page; primary value is confirming that regional variants, data residency, and compliance certifications are absent from this source. |
| [Available Atlassian Rovo MCP Server Domains](sources/atlassian-remote-mcp-available-domains.md) | `mcp`, `atlassian`, `rovo`, `admin`, `product:cross-cutting` | Atlassian admin support page — pre-allowlisted AI-client / partner domains (OAuth allowlist), four custom domain pattern types, admin UI navigation path. Distinct from kb-ingest `serves_hosts:` routing. |
| [Atlassian Rovo MCP Server: Supported Tools](sources/atlassian-remote-mcp-supported-tools.md) | `mcp`, `atlassian`, `rovo`, `product:cross-cutting` | Atlassian supported-tools reference — all 15 permission groups, ~60 tools, required scopes, and auth-mode constraints across Jira, Confluence, JSM, Bitbucket Cloud, Teamwork Graph, search_atlassian, and Compass. Closes OQ#1 on specific tool names. |
| [Atlassian Rovo MCP Server — Getting Started](sources/atlassian-remote-mcp-getting-started.md) | `mcp`, `atlassian`, `rovo`, `product:cross-cutting` | Atlassian support getting-started guide — current endpoint, supported clients and IDEs, capabilities by product (Jira, Confluence, Compass), auth methods, admin model. |
| [Atlassian Remote MCP Server](sources/atlassian-remote-mcp-server.md) | `mcp`, `atlassian`, `product:cross-cutting` | Atlassian public landing page for the Rovo MCP server — auth model, rate limits, restrictions, and runtime endpoints. |
| [Anthropic — Create custom subagents](sources/anthropic-sub-agents.md) | `anthropic`, `claude-code`, `product:cross-cutting` | Canonical Anthropic documentation for the Claude Code sub-agent primitive. |
| [Auth0 — Client Credentials Flow (Machine-to-Machine)](sources/auth0-client-credentials-flow.md) | `auth0`, `oauth`, `m2m`, `authentication`, `jwt`, `product:cross-cutting` | Auth0 client credentials flow — M2M token issuance, request/response parameters, audience/scope semantics, token lifecycle (86400s default), no refresh token, Bearer token usage. |
| [AWS IAM — AssumeRole with External ID](sources/aws-sts-assume-role-external-id.md) | `aws`, `iam`, `sts`, `security`, `cross-account`, `product:cross-cutting` | AWS IAM guide — Confused Deputy problem, external ID trust policy condition, AssumeRole API call with ExternalId, format constraints, multi-tenant setup process. |
| [AWS Lambda — Resource-Based Policies and Cross-Account Invoke](sources/aws-lambda-resource-based-policies.md) | `aws`, `lambda`, `iam`, `cross-account`, `resource-policy`, `product:cross-cutting` | AWS Lambda docs — resource-based policy structure, add-permission CLI, cross-account invoke patterns, alias-locked invocation, SourceAccount/SourceArn conditions, vs. AssumeRole comparison. |
| [MCP Specification 2025-06-18 — Authorization](sources/mcp-authorization-spec.md) | `mcp`, `oauth`, `authorization`, `security`, `product:cross-cutting` | MCP authorization spec — OAuth 2.1 on HTTP transports, Protected Resource Metadata (RFC 9728), Dynamic Client Registration (RFC 7591), PKCE requirement, resource parameter (RFC 8707), token passthrough prohibition, audience validation. |
| [MCP Specification 2025-06-18 — Tools, Resources, and Prompts](sources/mcp-tool-resource-prompt-primitives.md) | `mcp`, `protocol`, `tools`, `resources`, `prompts`, `product:cross-cutting` | MCP tools/resources/prompts spec — tool catalog shape (name, inputSchema, outputSchema, annotations), tools/list pagination, listChanged notifications, resource templates (RFC 6570), subscriptions, prompt arguments. |
| [RFC 8693 — OAuth 2.0 Token Exchange](sources/oauth-token-exchange-rfc8693.md) | `oauth`, `rfc`, `token-exchange`, `delegation`, `impersonation`, `product:cross-cutting` | IETF RFC 8693 — token-exchange grant type, subject_token/actor_token, impersonation vs. delegation, act JWT claim, token type URIs, scope/resource Cartesian product semantics. |
| [The Forge — LINQ Hackathon Program](sources/forge-linq-hackathon-program.md) | `product:cross-cutting`, `hackathon`, `forge`, `confluence` | Confluence program page (auth-required stub) — The Forge purpose, Race Format, Project Format, 2026 season schedule, and recognition structure. |
| [The Forge — Season 2: Every Minute Matters](sources/forge-season-2-every-minute-matters.md) | `product:cross-cutting`, `hackathon`, `forge`, `confluence`, `season-2` | Confluence Season 2 event page (auth-required stub) — dates, theme, team rules, AI requirement, five-criterion judging rubric, tracking app, and Slack channel. |

## Synthesis

| Page | Tags | Summary |
|---|---|---|
| [centralized-mcp-broker](synthesis/centralized-mcp-broker.md) | `mcp`, `auth0`, `aws`, `iam`, `oauth`, `architecture`, `product:cross-cutting` | LINQ-specific composition of MCP authorization, Auth0 M2M, RFC 8693 token exchange, STS + External ID, and Lambda resource policies into the "Auth0-fronted MCP broker with cross-account credential exchange" pattern adopted in [Decision 0015](../../docs/decisions/0015-centralized-platform-mcp.md). Coexists with [Decision 0008](../../docs/decisions/0008-mcp-connectors.md). |

## Cases

_None yet._ See [Decision 0017](../../docs/decisions/0017-case-as-wiki-bucket.md). Cases are written by the Tech Services debugger's `write-resolved-case` subcommand rather than the knowledge-curator.
