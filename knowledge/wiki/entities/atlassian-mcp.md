---
title: "Atlassian MCP"
kind: entity
tags: ["mcp", "atlassian", "confluence", "jira", "product:cross-cutting"]
aliases: ["atlassian connector", "atlassian remote mcp server", "atlassian rovo mcp server"]
serves_hosts:
  - "confluence.atlassian.linq.com"
  - "*.atlassian.net"
mcp_server_name: "atlassian"
auth_required: true
auth_tools:
  - "mcp__atlassian__authenticate"
  - "mcp__atlassian__complete_authentication"
sources: ["wiki/sources/atlassian-remote-mcp-server.md"]
related: []
created: 2026-05-03
updated: 2026-05-03
---

## Definition

The Atlassian MCP (branded by Atlassian as the "Atlassian Rovo MCP server") is a secure integration layer hosted at `mcp.atlassian.com` that connects external AI clients — including Claude, IDEs, and agent platforms — to Atlassian products via the Model Context Protocol. It is not an AI model itself; it exposes Atlassian data through OAuth-mediated tool calls scoped to the signed-in user's permissions. "Rovo MCP" is Atlassian's product name for this server; within this repository the entity is called "Atlassian MCP" for brevity.

Source: [`wiki/sources/atlassian-remote-mcp-server.md`](../sources/atlassian-remote-mcp-server.md).

## Tools exposed

**Authentication tools** (always present, surface before and during OAuth):

- `mcp__atlassian__authenticate` — initiates the OAuth flow
- `mcp__atlassian__complete_authentication` — completes the OAuth callback

**Read tools** (surface post-auth via MCP tool discovery):

The landing page describes capabilities generically as "Rovo Search and fetch tools." Specific tool names — such as search, fetch Jira issues, and fetch Confluence pages — are not enumerated by the public page and must be discovered at runtime via the MCP protocol's tool-discovery mechanism after authentication completes.

Source: [`raw/sources/atlassian-remote-mcp-server-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-server-2026-05-03.md).

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

## Sources

- [`wiki/sources/atlassian-remote-mcp-server.md`](../sources/atlassian-remote-mcp-server.md) — summary of the Atlassian public landing page, ingested 2026-05-03
