---
title: "Atlassian Remote MCP Server (public landing page)"
kind: source
raw_path: "raw/sources/atlassian-remote-mcp-server-2026-05-03.md"
url: "https://www.atlassian.com/platform/remote-mcp-server"
author: "Atlassian"
fetched_at: 2026-05-03
tags: ["mcp", "atlassian", "product:cross-cutting"]
entities: ["wiki/entities/atlassian-mcp.md"]
concepts: []
created: 2026-05-03
updated: 2026-05-03
---

## Why this source

The kb-ingest skill authenticated against the Atlassian MCP during the LINQ Hackathon May 2026 session. This page establishes the canonical public definition of the Atlassian Remote MCP Server — its purpose, OAuth model, rate limits, and restrictions — and anchors the [`atlassian-mcp`](../entities/atlassian-mcp.md) entity page. It is the first external MCP connector documented in this knowledge base.

## What it covers

- What the Atlassian Rovo MCP server is (integration layer, not an AI model)
- Which Atlassian products it surfaces (Jira and Confluence explicitly named; others likely but not enumerated)
- The OAuth-based auth model and permission scoping
- Site-level rate limits broken out by Atlassian plan tier
- FedRAMP and HIPAA exclusions
- Setup path (connector gallery in a supported AI client)
- Runtime-observed server endpoints (SSE transport URL, OAuth authorize URL)

## Key claims

All claims cite [`raw/sources/atlassian-remote-mcp-server-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-server-2026-05-03.md).

- **Integration layer, not a model.** The MCP server connects external AI clients to Atlassian products; it is not an AI model itself.
- **Explicit products.** Jira and Confluence are explicitly named on the landing page.
- **Generic tool description.** The landing page describes capabilities as "Rovo Search and fetch tools" without enumerating specific tool names; discovery happens post-auth via the MCP tool-discovery mechanism.
- **OAuth auth, user-scoped.** Authentication is OAuth-based; the server operates within the signed-in user's permission set.
- **Rate limits by plan.** Free: 500 calls/hr. Standard: 1,000 calls/hr. Premium and Enterprise: 1,000 base + 20 per user, max 10,000 calls/hr.
- **No FedRAMP or HIPAA.** Explicitly excluded on the landing page.
- **Runtime endpoints (informational).** SSE transport at `https://mcp.atlassian.com/v1/sse`; OAuth flow at `https://mcp.atlassian.com/v1/authorize`. These are live observations, not published specs.

## Entities introduced

- [`wiki/entities/atlassian-mcp.md`](../entities/atlassian-mcp.md) — the Atlassian Remote MCP Server as a first-class entity in this knowledge base, with `serves_hosts:` populated to extend `/kb-ingest` routing automatically.

## Open questions for LINQ

1. **Specific tool names.** The landing page does not enumerate the read tools exposed post-auth (e.g., search, fetch Jira issues, fetch Confluence pages). A deeper ingest of the getting-started guide (`https://support.atlassian.com/rovo/docs/getting-started-with-the-atlassian-remote-mcp-server/`) would surface these.
2. **Additional products.** Are Compass, Rovo apps, or other Atlassian products reachable through the same MCP server? The landing page is silent on this.
3. **Server endpoint spec.** The endpoints observed at runtime (`mcp.atlassian.com/v1/sse`, `mcp.atlassian.com/v1/authorize`) are not documented on this page. Atlassian support docs or the getting-started guide may confirm them officially.
4. **Enterprise auth flow.** Does LINQ's self-hosted Confluence instance at `confluence.atlassian.linq.com` route through the same `mcp.atlassian.com` endpoints, or does it need a separate MCP configuration? Needs confirmation before production use.
