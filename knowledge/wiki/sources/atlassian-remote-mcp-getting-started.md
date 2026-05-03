---
title: "Atlassian Rovo MCP Server — Getting Started (support docs)"
kind: source
raw_path: "raw/sources/atlassian-remote-mcp-getting-started-2026-05-03.md"
url: "https://support.atlassian.com/rovo/docs/getting-started-with-the-atlassian-remote-mcp-server/"
author: "Atlassian"
fetched_at: 2026-05-03
tags: ["product:cross-cutting", "mcp", "atlassian", "rovo"]
entities: ["wiki/entities/atlassian-mcp.md"]
concepts: []
created: 2026-05-03
updated: 2026-05-03
---

## Why this source

This page partially closes Open Question #1 from [`wiki/sources/atlassian-remote-mcp-server.md`](atlassian-remote-mcp-server.md) — which flagged that the landing page did not enumerate specific tool names or fully describe supported products. The getting-started guide adds Compass as a supported product, confirms the current OAuth 2.1 endpoint (`/v1/mcp/authv2`), documents the legacy endpoint sunset date (June 30, 2026), enumerates supported external clients and IDEs, and describes capabilities by product. It does not enumerate specific MCP tool names — that information lives in the linked "Supported tools" sub-page, which remains an open gap.

This source enriches the [`atlassian-mcp`](../entities/atlassian-mcp.md) entity. No new entities or concepts are introduced.

## What it covers

- Server endpoints: current (`/v1/mcp/authv2`) and legacy (`/v1/sse`) with sunset date
- Supported external AI clients (ChatGPT, Claude, Docker, GitHub Copilot CLI, Gemini, Amazon Quick Suite, and any `mcp-remote`-compatible client)
- Supported IDEs for desktop setup (Claude Desktop, VS Code, Cursor) and the Node.js v18+ prerequisite for `mcp-remote`
- Both authentication methods: OAuth 2.1 (primary) and API token (optional, admin-controlled)
- Capabilities by product: Jira, Confluence, Compass, and cross-product linking
- Permissions model and security posture (TLS 1.2+, user-scoped access, IP allowlisting)
- Admin installation model (just-in-time consent, not a Marketplace app), domain allowlisting, audit logging
- Common admin troubleshooting messages

## Key claims

All claims cite [`raw/sources/atlassian-remote-mcp-getting-started-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-getting-started-2026-05-03.md).

- **Current endpoint.** The authoritative server endpoint is `https://mcp.atlassian.com/v1/mcp/authv2`. The legacy SSE endpoint (`/v1/sse`) is deprecated and will not be supported after June 30, 2026.
- **Compass added.** Compass is explicitly named alongside Jira and Confluence as a supported product. The landing page (`atlassian-remote-mcp-server.md`) only named Jira and Confluence.
- **Supported clients.** Seven external clients are enumerated: ChatGPT, Claude, Docker, GitHub Copilot CLI, Google Gemini, Amazon Quick Suite, and any `mcp-remote`-compatible client.
- **IDE support requires Node.js v18+.** Setting up the MCP in Claude Desktop, VS Code, or Cursor requires the `mcp-remote` proxy and Node.js v18 or later.
- **Two auth methods.** OAuth 2.1 is the primary method (browser-based, dynamic client registration). API token is an optional alternative, disabled by default and gated by admin configuration.
- **Capabilities by product.** Jira: search and create/update issues. Confluence: summarize, create pages, list spaces. Compass: create service components, bulk import, query dependencies. Cross-product: link content and fetch linked documentation.
- **Just-in-time installation.** The Rovo MCP server is not a Marketplace app. It installs on first OAuth consent; no pre-installation step is required.
- **Domain allowlisting.** Org admins control which external tool domains can connect. Misconfigured domains produce the error "Your organization admin must authorize access from a domain."
- **Tool names deferred.** Specific MCP tool names are not enumerated on this page; they live in the linked "Supported tools" sub-page.

## Entities introduced

No new entities. This source updates the existing [`wiki/entities/atlassian-mcp.md`](../entities/atlassian-mcp.md) entity:

- Compass added to the product list
- Current server endpoint (`/v1/mcp/authv2`) and legacy endpoint sunset note added
- Supported clients list added
- API-token auth method documented as optional alongside OAuth 2.1

## Open questions for LINQ

1. ~~**Specific tool names.**~~ **CLOSED** — [`wiki/sources/atlassian-remote-mcp-supported-tools.md`](atlassian-remote-mcp-supported-tools.md) (ingested 2026-05-03) enumerates all permission groups and tool names. Canonical URL confirmed as `https://support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/` (note: the `/rovo/docs/...` path that appeared in prior versions of this source's OQ has since resolved to the `/atlassian-rovo-mcp-server/docs/...` namespace).
2. **Available domains list — re-framed (documentation gap filled, not closed as routing extension).** The "Available Atlassian Rovo MCP Server domains" admin page has been ingested at [`wiki/sources/atlassian-remote-mcp-available-domains.md`](atlassian-remote-mcp-available-domains.md) (2026-05-03). That page documents the AI-client domain allowlist mechanism — the OAuth callback origins of external AI tools connecting into Atlassian — which is distinct from the `/kb-ingest` routing field `serves_hosts:`. The original framing of this OQ ("may reveal additional `serves_hosts:` patterns") was incorrect; `serves_hosts:` tracks Atlassian tenant hostnames for inbound URL routing, not AI-client OAuth domains. The available-domains page does not add new `serves_hosts:` patterns. The documentation gap is now filled, but the routing-extension question was never the right question.
3. **LINQ IDE setup.** The "Setting up IDEs" sub-page documents the Claude Desktop and VS Code configuration workflow. Ingesting it would support LINQ developer onboarding instructions and confirm the Node.js v18+ requirement in a production context.
4. **Compass at LINQ.** Does LINQ use Atlassian Compass? If so, the Compass capabilities (service component creation, bulk import, dependency queries) are available through the same MCP server and may be relevant to engineering workflows.

## Related sources

- [`wiki/sources/atlassian-remote-mcp-server.md`](atlassian-remote-mcp-server.md) — the landing-page source this getting-started guide supplements; OQ#1 and OQ#2 from that source are partially answered here.
