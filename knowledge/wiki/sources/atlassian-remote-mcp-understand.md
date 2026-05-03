---
title: "Understand Atlassian Rovo MCP Server (Atlassian admin support docs)"
kind: source
raw_path: "raw/sources/atlassian-remote-mcp-understand-2026-05-03.md"
url: "https://support.atlassian.com/security-and-access-policies/docs/understand-atlassian-rovo-mcp-server/"
author: "Atlassian"
fetched_at: 2026-05-03
tags: ["product:cross-cutting", "mcp", "atlassian", "rovo", "admin"]
entities: ["wiki/entities/atlassian-mcp.md"]
concepts: []
created: 2026-05-03
updated: 2026-05-03
---

## Why this source

This page was expected to address regional MCP server variants (US/EU/AP), data residency, and compliance certifications — the outstanding documentation gaps from prior ingests. **It does not.** The most valuable artifact from this ingest is the documentation-gap signal itself: a confirmation that the admin "Understand" page does not cover these topics, and that a different source (Atlassian Trust Center or a vendor inquiry) is required to close those gaps.

What the page does add is modest but concrete: IP allowlisting integration semantics and a specific runtime gotcha for AI tools operating behind corporate IP policies.

This page lives in the `/security-and-access-policies/docs/...` namespace on `support.atlassian.com` — the same third Atlassian namespace confirmed by the prior [`atlassian-remote-mcp-available-domains`](atlassian-remote-mcp-available-domains.md) ingest.

## What it covers

This page is thin. It covers:

- A high-level description of what the Rovo MCP server does and which products it supports (Jira, Confluence, Compass)
- Authentication method overview: OAuth 2.1 (default) and API Tokens (advanced/service-style)
- Atlassian-supported domains — defined as a list of Atlassian AI partners allowlisted by default; admins can block all but cannot block individual domains
- **IP allowlisting integration:** how IP allowlists interact with MCP server requests (the page's primary incremental contribution)
- Related admin link references (monitoring, controlling settings, available domains, permissions, A2A connections, third-party MCP guidelines)

## Key claims

All claims cite [`raw/sources/atlassian-remote-mcp-understand-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-understand-2026-05-03.md).

- **Supported products:** Jira, Confluence, and Compass. JSM and Bitbucket Cloud are not mentioned on this page (they are documented elsewhere).
- **OAuth 2.1 is the default and recommended auth method.** Access is scoped to the user's existing Atlassian permissions. Admins control authorization via domain settings and app management controls.
- **API Tokens are an advanced option** described as useful for <escape>"service-style or non-interactive tools."</escape> Enablement is controlled by an organization-level setting.
- **Atlassian-supported domains** are described as <escape>"a list of Atlassian AI partners"</escape> automatically allowed by default; Anthropic (Claude.ai) and OpenAI (ChatGPT) are cited as examples. Admins may block the entire set but cannot block individual partner domains.
- **IP allowlists are configured in Atlassian Administration** (not within MCP settings). MCP requests are evaluated against the org's IP policies. Blocked IPs receive the verbatim error: <escape>"You don't have permission to connect from this IP address."</escape>
- **AI-tool outbound IP gotcha:** Some AI tools originate MCP calls from their own infrastructure IPs rather than the user's corporate network. This can cause MCP calls to fail even when the user's network is in the IP allowlist. This is a runtime administration consideration distinct from domain allowlisting.

## Entities introduced

No new entities. This source enriches the existing [`wiki/entities/atlassian-mcp.md`](../entities/atlassian-mcp.md) entity with an IP allowlisting integration subsection.

## Open questions for LINQ

1. **Regional MCP variants — gap remains open.** This page does not address geographic / regional variants of the MCP server (US, EU, AP endpoints or data residency). The prior [`atlassian-remote-mcp-available-domains`](atlassian-remote-mcp-available-domains.md) source flagged this as an open gap pointing to this "Understand" page as a candidate source. That candidate is now confirmed closed without resolving the gap. A different source is needed: Atlassian Trust Center (`https://www.atlassian.com/trust`) or a vendor/support inquiry.
2. **Data residency and compliance certifications — gap remains open.** SOC 2, ISO 27001, GDPR, FedRAMP, HIPAA, and MCP-specific data-residency commitments are not on this page. Same suggested source: Atlassian Trust Center or vendor inquiry.
3. **IP allowlist configuration at LINQ.** Does LINQ's Atlassian org have IP allowlists configured? If so, which AI tool infrastructure IPs are allow-listed? This determines whether the AI-tool outbound IP gotcha is a live risk for LINQ agent workflows. Needs human verification via the Atlassian Administration UI.
4. **GA vs. beta status — gap remains open.** Overall GA/beta status and edition/plan gating for the MCP server are not stated on this page. Suggested source: Atlassian product release notes or changelog.

## Related sources

- [`wiki/sources/atlassian-remote-mcp-available-domains.md`](atlassian-remote-mcp-available-domains.md) — prior source in the same `/security-and-access-policies/docs/...` namespace; documents the AI-client OAuth allowlist (distinct from IP allowlists). The regional-variant gap first surfaced there and pointed to this page as a candidate — that candidate is now confirmed non-resolving.
- [`wiki/sources/atlassian-remote-mcp-server.md`](atlassian-remote-mcp-server.md) — the Atlassian public landing page covering auth model, rate limits, and restrictions (FedRAMP/HIPAA exclusions).
- [`wiki/sources/atlassian-remote-mcp-getting-started.md`](atlassian-remote-mcp-getting-started.md) — getting-started guide; authentication method overview partially overlaps this page.
