---
title: "Available Atlassian Rovo MCP Server Domains (admin support docs)"
kind: source
raw_path: "raw/sources/atlassian-remote-mcp-available-domains-2026-05-03.md"
url: "https://support.atlassian.com/security-and-access-policies/docs/available-atlassian-rovo-mcp-server-domains/"
author: "Atlassian"
fetched_at: 2026-05-03
tags: ["product:cross-cutting", "mcp", "atlassian", "rovo", "admin"]
entities: ["wiki/entities/atlassian-mcp.md"]
concepts: []
created: 2026-05-03
updated: 2026-05-03
---

## Why this source

This page was initially expected to extend the `serves_hosts:` field on the [`atlassian-mcp`](../entities/atlassian-mcp.md) entity — closing OQ#2 from [`wiki/sources/atlassian-remote-mcp-getting-started.md`](atlassian-remote-mcp-getting-started.md). That expectation is incorrect and has been corrected.

**Framing correction:** `serves_hosts:` on the atlassian-mcp entity tracks Atlassian tenant hostnames — the URLs that `/kb-ingest` should route to the Atlassian MCP (e.g., `*.atlassian.net`, `confluence.atlassian.linq.com`). This page, by contrast, lists AI-client / partner domains — the domains of external AI tools that an Atlassian org admin pre-allowlists so those tools can connect INTO the org's Atlassian MCP via OAuth 2.1 (e.g., `claude.ai`, `chatgpt.com`). These are different concepts: one is inbound routing for the kb-ingest skill; the other is the org admin's OAuth allowlist.

Consequently, this source enriches the [`atlassian-mcp`](../entities/atlassian-mcp.md) entity with an "Org admin domain allowlist" section and does not modify `serves_hosts:`.

OQ#2 on the getting-started source has been re-framed (not closed in the routing-extension sense) — see that page for the updated open question.

## What it covers

- The pre-allowlisted AI-client / partner domains Atlassian automatically permits by default (HTTP dev/test, HTTPS AI partners, and protocol-specific desktop/IDE clients)
- The four pattern types admins can use to authorize additional custom domains
- The Atlassian Administration UI navigation path to reach the domain-allowlist settings
- The least-privilege security guidance for MCP client access
- A doc-namespace observation: this page lives under `/security-and-access-policies/docs/...`, a third Atlassian namespace distinct from `/rovo/docs/` and `/atlassian-rovo-mcp-server/docs/`

## Key claims

All claims cite [`raw/sources/atlassian-remote-mcp-available-domains-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-available-domains-2026-05-03.md).

- **These are AI-client domains, not MCP server endpoints.** The listed domains are the OAuth callback/redirect origins of AI tools connecting to Atlassian — not the hostnames of the MCP server itself.
- **Pre-allowlisted HTTPS AI partners include:** `claude.ai`, `claude.com`, `chatgpt.com`, `callback.mistral.ai`, `api.devin.ai`, `vscode.dev`, `mcp.docker.com`, `app.writer.com`, `integrations.zoom.us`, `figma-gov.com`, `www.canva.com`, `lovable.dev`, `vertexaisearch.cloud.google.com`, `us-east-1.quicksight.aws.amazon.com`, `global.consent.azure-apim.net`, `oauth.pstmn.io`, `token.botframework.com`, and wildcard patterns for Databricks, Dynatrace, and Resolve AI.
- **Pre-allowlisted HTTP (dev/test only):** `127.0.0.1` and `localhost`.
- **Pre-allowlisted protocol-specific clients:** `cursor:` and `raycast:` URI schemes for Cursor and Raycast desktop clients.
- **Four custom-domain pattern types:** single domain, subdomain wildcard (`https://*.example.com/**`), environment braces (`https://{dev,staging,prod}.platform-demo.com/**`), and port wildcard (`http://localhost:*/**`).
- **HTTP is restricted to localhost.** `http://` is valid only for `localhost` or `127.0.0.1`; all other custom domains must use `https://` or a custom protocol.
- **Admin UI navigation:** Security and access policies → Maintain secure access to apps → Manage Atlassian Rovo MCP server → Control Atlassian Rovo MCP server settings.
- **Least-privilege guidance:** <escape>"MCP clients can perform actions in Jira, Confluence, and Compass with your existing permissions. Use least privilege, review high-impact changes before confirming, and monitor audit logs."</escape>
- **Third doc namespace confirmed.** This page lives at `support.atlassian.com/security-and-access-policies/docs/...`, confirming that Atlassian Rovo MCP documentation is split across at least three namespaces.

## Entities introduced

No new entities. This source updates the existing [`wiki/entities/atlassian-mcp.md`](../entities/atlassian-mcp.md) entity:

- New section "Org admin domain allowlist" added documenting the pre-allowlisted AI-client domains, the four custom pattern types, and the admin UI navigation path.

## Open questions for LINQ

1. **Which AI client domains has LINQ's org admin actually allowlisted?** The defaults cover Claude, ChatGPT, and others; LINQ may have added or removed domains. Needs human verification via the Atlassian Administration UI.
2. **Regional MCP variants — gap remains open.** This page does not document geographic / regional variants of the MCP server (US, EU, AP). The "Understand Atlassian Rovo MCP server" admin page (ingested 2026-05-03 as [`atlassian-remote-mcp-understand`](atlassian-remote-mcp-understand.md)) was the candidate source for closing this gap. It does **not** address regional variants — the gap is still open. A different source is needed: Atlassian Trust Center (`https://www.atlassian.com/trust`) or a vendor/support inquiry.
3. **Doc-namespace fragmentation.** Atlassian Rovo MCP content now confirmed across three namespaces: `/rovo/docs/...` (legacy), `/atlassian-rovo-mcp-server/docs/...` (current user docs), and `/security-and-access-policies/docs/...` (admin policies). The `/kb-ingest` skill and wiki URL hygiene conventions have not yet adopted a canonical namespace preference. See `gaps[]` in this ingest dispatch.

## Related sources

- [`wiki/sources/atlassian-remote-mcp-getting-started.md`](atlassian-remote-mcp-getting-started.md) — the getting-started guide that originally surfaced this page as OQ#2; OQ#2 has been re-framed (not closed) per the framing correction above.
- [`wiki/sources/atlassian-remote-mcp-server.md`](atlassian-remote-mcp-server.md) — the landing-page source covering auth model, rate limits, and restrictions.
