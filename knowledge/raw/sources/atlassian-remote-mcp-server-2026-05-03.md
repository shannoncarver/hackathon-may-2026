---
title: "Atlassian Remote MCP Server"
url: "https://www.atlassian.com/platform/remote-mcp-server"
fetched_at: 2026-05-03
auth_required: false
license_note: "Atlassian public docs — condensed for agent reference; cite source for verbatim text"
tags: ["mcp", "atlassian", "product:cross-cutting"]
---

## Definition

The Atlassian Rovo MCP server is a secure integration layer — not an AI model itself — that connects external AI clients (such as Claude, IDEs, or agent platforms) to Atlassian products. It exposes search and data-fetching capabilities via the Model Context Protocol so AI clients can query Atlassian data within the bounds of the signed-in user's permissions.

## Products covered

The public landing page explicitly names **Jira** and **Confluence** as the products covered. Additional products (Compass, Rovo apps) are likely served by the same MCP server but are not enumerated on this page.

## Tools exposed

The landing page describes the capability generically as "Rovo Search and fetch tools." Specific tool names are not published on this page; they surface to AI clients post-authentication via the MCP protocol's standard tool-discovery mechanism.

## Auth model

Authentication is OAuth-based. The server operates within the permissions of the signed-in Atlassian user. Granular permission controls are available. The landing page does not document specific OAuth scopes or the detailed token-exchange flow.

## Rate limits

The following call-per-hour limits apply at the site level, by plan (verbatim from the source):

| Plan | Calls per hour |
|---|---|
| Free | 500 |
| Standard | 1,000 |
| Premium | 1,000 base + 20 per user, max 10,000 |
| Enterprise | 1,000 base + 20 per user, max 10,000 |

## Restrictions

The Atlassian Remote MCP Server does not currently support **FedRAMP** or **HIPAA** requirements.

## Setup

To connect: choose a supported AI client and add the Atlassian Rovo MCP server from that client's connector gallery. Atlassian's own getting-started guide is at:
https://support.atlassian.com/rovo/docs/getting-started-with-the-atlassian-remote-mcp-server/

## Server endpoints

The public landing page does not specify a server URL. Endpoints observed at runtime during the LINQ Hackathon May 2026 kb-ingest session:

- SSE transport: `https://mcp.atlassian.com/v1/sse`
- OAuth authorization: `https://mcp.atlassian.com/v1/authorize`

These are live observations, not published specs; treat as informational until confirmed by Atlassian support docs.

## Source

- Landing page: https://www.atlassian.com/platform/remote-mcp-server
- Getting-started guide (not yet ingested): https://support.atlassian.com/rovo/docs/getting-started-with-the-atlassian-remote-mcp-server/
