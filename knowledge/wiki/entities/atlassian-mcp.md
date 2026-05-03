---
title: "Atlassian MCP"
kind: entity
tags: ["mcp", "atlassian", "confluence", "jira", "jira-service-management", "bitbucket", "compass", "rovo", "product:cross-cutting"]
aliases: ["atlassian connector", "atlassian remote mcp server", "atlassian rovo mcp server"]
serves_hosts:
  - "confluence.atlassian.linq.com"
  - "*.atlassian.net"
mcp_server_name: "atlassian"
auth_required: true
auth_tools:
  - "mcp__atlassian__authenticate"
  - "mcp__atlassian__complete_authentication"
sources:
  - "wiki/sources/atlassian-remote-mcp-server.md"
  - "wiki/sources/atlassian-remote-mcp-getting-started.md"
  - "wiki/sources/atlassian-remote-mcp-supported-tools.md"
  - "wiki/sources/atlassian-remote-mcp-available-domains.md"
  - "wiki/sources/atlassian-remote-mcp-understand.md"
related: []
created: 2026-05-03
updated: 2026-05-03
---



## Definition

The Atlassian MCP (branded by Atlassian as the "Atlassian Rovo MCP server") is a secure integration layer hosted at `mcp.atlassian.com` that connects external AI clients — including Claude, IDEs, and agent platforms — to Atlassian products via the Model Context Protocol. It is not an AI model itself; it exposes Atlassian data through OAuth-mediated tool calls scoped to the signed-in user's permissions. "Rovo MCP" is Atlassian's product name for this server; within this repository the entity is called "Atlassian MCP" for brevity.

Source: [`wiki/sources/atlassian-remote-mcp-server.md`](../sources/atlassian-remote-mcp-server.md).

## Supported products

Jira, Confluence, Jira Service Management, Bitbucket Cloud, and Compass are explicitly supported. Two beta cross-product capabilities — Teamwork Graph traversal and natural-language search via Rovo — are also available. Cross-product content linking (fetching documentation linked from Jira issues) is supported.

JSM and Bitbucket Cloud are available via **API token only** and must be **enabled by an organization admin**. Bitbucket Cloud additionally requires a linked Bitbucket workspace. Compass tools are available via **OAuth 2.1 only** (no API token support).

Sources: [`wiki/sources/atlassian-remote-mcp-getting-started.md`](../sources/atlassian-remote-mcp-getting-started.md); [`wiki/sources/atlassian-remote-mcp-supported-tools.md`](../sources/atlassian-remote-mcp-supported-tools.md).

## Server endpoints

| Endpoint | Status |
|---|---|
| `https://mcp.atlassian.com/v1/mcp/authv2` | Current — use this |
| `https://mcp.atlassian.com/v1/sse` | **Deprecated** — legacy SSE endpoint; will not be supported after June 30, 2026 |

Source: [`wiki/sources/atlassian-remote-mcp-getting-started.md`](../sources/atlassian-remote-mcp-getting-started.md).

## Supported clients and IDEs

**External AI clients:** OpenAI ChatGPT, Claude, Docker, GitHub Copilot CLI, Google Gemini, Amazon Quick Suite, and any local MCP-compatible client via the `mcp-remote` proxy.

**IDEs and desktop environments:** Claude Desktop, VS Code, Cursor. IDE setup requires Node.js v18+ to run the `mcp-remote` proxy.

Source: [`wiki/sources/atlassian-remote-mcp-getting-started.md`](../sources/atlassian-remote-mcp-getting-started.md).

## Authentication methods

Two methods are available:

1. **OAuth 2.1 (primary):** Browser-based flow with dynamic client registration support. This is the default method.
2. **API token (optional):** An admin-controlled alternative disabled by default. Enabled only when an admin explicitly configures token authentication in Atlassian Administration.

All tokens are scoped and session-based. Access is limited to data the authenticated user already has permission to view.

Source: [`wiki/sources/atlassian-remote-mcp-getting-started.md`](../sources/atlassian-remote-mcp-getting-started.md).

## Tools exposed

**Authentication tools** (always present, surface before and during OAuth):

- `mcp__atlassian__authenticate` — initiates the OAuth flow
- `mcp__atlassian__complete_authentication` — completes the OAuth callback

**Permission groups and tool counts** (post-auth, organized by product):

Full per-tool listings with required scopes are in [`wiki/sources/atlassian-remote-mcp-supported-tools.md`](../sources/atlassian-remote-mcp-supported-tools.md) and its raw file [`raw/sources/atlassian-remote-mcp-supported-tools-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-supported-tools-2026-05-03.md).

| Permission group | Auth modes | Key scope(s) | Tool count | Notes |
|---|---|---|---|---|
| `read_jira` | OAuth 2.1, API token | `read:jira-work` | 8 | — |
| `write_jira` | OAuth 2.1, API token | `write:jira-work` | 5 | `createJiraIssue` description may be mismatched — see OQ#1 below |
| `search_jira` | OAuth 2.1, API token | `search:jira-work` | 1 | — |
| `read_confluence` | OAuth 2.1, API token | varies per tool | 7 | — |
| `write_confluence` | OAuth 2.1, API token | `write:page:confluence` | 4 | — |
| `search_confluence` | OAuth 2.1, API token | `search:confluence` | 1 | — |
| `read_jsm` | API token only | varies per tool | 3 | Admin-enabled; ops alerts, on-call schedules, ops teams |
| `write_jsm` | API token only | `write:ops-alert:jira-service-management` | 1 | Admin-enabled; alert actions (acknowledge, close, escalate) |
| `read_bitbucket` | API token only | varies per tool | 8 (families) | Admin-enabled; linked workspace required |
| `write_bitbucket` | API token only | varies per tool | 4 (families) | Admin-enabled; PR, branch/commit, pipeline, environment |
| `read_teamwork_graph` | OAuth 2.1, API token | multiple (see raw) | 2 | **BETA** — cross-product entity traversal |
| `search_atlassian` | OAuth 2.1, API token | `search:rovo:mcp` | 2 | **BETA** — natural-language search + ARI fetch |
| `read_compass` | OAuth 2.1 only | `read:component:compass` | 7 | — |
| `write_compass` | OAuth 2.1 only | `write:component:compass` | 3 | — |
| Shared Platform | N/A (always present) | `read:me`, `read:account` | 2 | `atlassianUserInfo`, `getAccessibleAtlassianResources` |

Source: [`wiki/sources/atlassian-remote-mcp-supported-tools.md`](../sources/atlassian-remote-mcp-supported-tools.md).

## When to use

Route a URL to this MCP when its host matches any pattern in `serves_hosts:`:

- Exact match: `confluence.atlassian.linq.com` — LINQ's internal Confluence instance
- Trailing-wildcard: `*.atlassian.net` — all Atlassian cloud tenant hostnames

The [`kb-ingest`](../../.claude/skills/kb-ingest/SKILL.md) skill consults this entity at Step 1 classification time to determine which MCP to invoke. Because `serves_hosts:` is populated here, no edits to the skill or to the static source-classification table are needed to enable routing for these hosts — the entity record is sufficient.

## How LINQ uses this

The Atlassian MCP is wired in `.mcp.json` under the `atlassian` server name and is available to the `40-knowledge-curator` agent via `mcpServers: atlassian`. The knowledge-curator uses it to fetch Confluence pages during the wiki ingest pipeline: auth-required URLs that match `serves_hosts:` receive stub-form treatment in `raw/sources/` (frontmatter only, with `auth_required: true` and `requires_mcp: "atlassian"`) rather than full condensed copies.

## Known issues

**Mac Desktop app — tools do not refresh after mid-session auth.**
On the Claude Mac Desktop app, the list of available MCP tools does not update automatically after OAuth completes mid-session. Workaround: quit the app (Cmd+Q) and reopen it after finishing the OAuth flow. The read tools will surface on the next session startup.

**Remote/SSH sessions — OAuth callback can time out.**
The callback URL listener may time out before the browser redirect completes when running on a remote or SSH-attached machine. Mitigation: copy the full redirect URL from the browser address bar after approving access and pass it directly to `mcp__atlassian__complete_authentication`.

Both issues were observed during the LINQ Hackathon May 2026 kb-ingest session that produced this entry.

## Rate limits

Site-level limits by Atlassian plan (verbatim from [`raw/sources/atlassian-remote-mcp-server-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-server-2026-05-03.md)):

| Plan | Calls per hour |
|---|---|
| Free | 500 |
| Standard | 1,000 |
| Premium | 1,000 base + 20 per user, max 10,000 |
| Enterprise | 1,000 base + 20 per user, max 10,000 |

LINQ's current Atlassian plan tier is "unable to verify" — confirm before estimating throughput for production agent workflows.

## Restrictions

The Atlassian Remote MCP Server does not currently support **FedRAMP** or **HIPAA** requirements. This is an explicit exclusion on the public landing page, not inferred.

Source: [`raw/sources/atlassian-remote-mcp-server-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-server-2026-05-03.md).

## Org admin domain allowlist

**Important distinction:** The `serves_hosts:` field above is the AI-client routing list used by `/kb-ingest` to determine which MCP server to invoke when fetching a URL. The allowlist documented in this section is separate — it is the Atlassian org admin's OAuth allowlist controlling which *external AI tool domains* may connect INTO the org's Atlassian MCP server. The two mechanisms operate at opposite ends of the connection.

Source: [`wiki/sources/atlassian-remote-mcp-available-domains.md`](../sources/atlassian-remote-mcp-available-domains.md).

### Pre-allowlisted domains (Atlassian defaults)

**HTTP (dev/test only):**
- `127.0.0.1`, `localhost`

**HTTPS AI partner / client domains (selected):**
- Claude: `claude.ai`, `claude.com`
- ChatGPT: `chatgpt.com`
- Mistral: `callback.mistral.ai`
- Devin AI: `api.devin.ai`
- VS Code: `vscode.dev`
- Docker: `mcp.docker.com`
- Databricks: `*.azuredatabricks.net`, `*.databricks.com`
- Others: `app.writer.com`, `integrations.zoom.us`, `figma-gov.com`, `www.canva.com`, `lovable.dev`, `vertexaisearch.cloud.google.com`, `us-east-1.quicksight.aws.amazon.com`, `global.consent.azure-apim.net`, `oauth.pstmn.io`, `token.botframework.com`, `*.apps.dynatrace.com`, `*.resolve.ai`

**Protocol-specific (desktop/IDE clients):**
- `cursor:` URI scheme (Cursor MCP)
- `raycast:` URI scheme (Raycast OAuth)

### Custom domain pattern types

Admins can add domains beyond the defaults. Four pattern types are supported:

| Pattern type | Example |
|---|---|
| Single domain | `https://aiagent.mydomain.com` |
| Subdomain wildcard | `https://*.example.com/**` |
| Environment braces | `https://{dev,staging,prod}.platform-demo.com/**` |
| Port wildcard | `http://localhost:*/**` |

`http://` is valid only for `localhost` or `127.0.0.1`. All other custom entries must use `https://` or a custom protocol scheme.

### Admin UI navigation

Security and access policies → Maintain secure access to apps → Manage Atlassian Rovo MCP server → Control Atlassian Rovo MCP server settings.

Related admin pages (same parent): Monitor activity, Configure permissions, Manage A2A connections.

## IP allowlisting integration

IP allowlists for the Atlassian MCP server are configured in **Atlassian Administration** — not within the MCP server settings themselves. When a user accesses Atlassian apps through the MCP server, each request is evaluated against the organization's IP policies.

Blocked IPs receive the verbatim error: <escape>"You don't have permission to connect from this IP address."</escape>

**Gotcha — AI tool outbound IPs.** Some AI tools originate MCP requests from their own infrastructure IPs rather than from the user's corporate network. This can cause MCP calls to fail even when the user's network is in the IP allowlist — because the IP policy is evaluated against the AI tool's egress IP, not the user's. This is a distinct mechanism from the OAuth domain allowlist (see "Org admin domain allowlist" above).

Source: [`wiki/sources/atlassian-remote-mcp-understand.md`](../sources/atlassian-remote-mcp-understand.md).

## Open questions for LINQ

1. **`createJiraIssue` description mismatch.** The Atlassian source gives `createJiraIssue` the description "Create a link between two Jira issues," which appears to match `createJiraIssueLink`. Preserved verbatim. Needs human verification against the live Atlassian docs or the tool at runtime. Source: [`raw/sources/atlassian-remote-mcp-supported-tools-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-supported-tools-2026-05-03.md).
2. **JSM at LINQ.** Does LINQ use Jira Service Management? If so, the `atlassian-mcp` entity's `serves_hosts:` may need a JSM host pattern added, and an org admin must enable the JSM permission groups.
3. **Bitbucket Cloud at LINQ.** Does LINQ use Bitbucket Cloud (as distinct from GitHub or other VCS)? Bitbucket tools require a linked workspace and API token. Needs LINQ IT/admin confirmation before use in agent workflows.

## Sources

- [`wiki/sources/atlassian-remote-mcp-server.md`](../sources/atlassian-remote-mcp-server.md) — summary of the Atlassian public landing page, ingested 2026-05-03
- [`wiki/sources/atlassian-remote-mcp-getting-started.md`](../sources/atlassian-remote-mcp-getting-started.md) — summary of the Atlassian support getting-started guide, ingested 2026-05-03; adds Compass, current endpoint, supported clients, and API-token auth method
- [`wiki/sources/atlassian-remote-mcp-supported-tools.md`](../sources/atlassian-remote-mcp-supported-tools.md) — supported-tools reference, ingested 2026-05-03; closes OQ#1 on specific tool names; adds JSM, Bitbucket, Teamwork Graph, and search_atlassian
- [`wiki/sources/atlassian-remote-mcp-available-domains.md`](../sources/atlassian-remote-mcp-available-domains.md) — org admin domain allowlist, ingested 2026-05-03; documents the AI-client OAuth allowlist and four custom pattern types (distinct from `serves_hosts:` routing)
- [`wiki/sources/atlassian-remote-mcp-understand.md`](../sources/atlassian-remote-mcp-understand.md) — admin "Understand" page, ingested 2026-05-03; adds IP allowlisting integration semantics and the AI-tool outbound IP gotcha; confirms that regional variants, data residency, and compliance certifications are not covered on this page
