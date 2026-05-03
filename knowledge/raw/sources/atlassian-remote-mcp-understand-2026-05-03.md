---
title: "Understand Atlassian Rovo MCP Server (Atlassian admin support docs)"
url: "https://support.atlassian.com/security-and-access-policies/docs/understand-atlassian-rovo-mcp-server/"
fetched_at: 2026-05-03
auth_required: false
license_note: "Atlassian public admin support docs — condensed for agent reference; cite source for verbatim text"
---

## Overview

<escape>
The Atlassian Rovo MCP (Model Context Protocol) server enables AI tools to securely access Jira, Confluence, and Compass data, allowing actions such as "searching for work items, summarizing pages, or bulk-creating new content via natural language commands."
</escape>

Supported products: Jira, Confluence, Compass.

## Authentication methods

1. **OAuth 2.1 (default and recommended).** Users connect AI tools via OAuth 2.1 consent screen. Access is scoped to existing user permissions. Admins control via domain settings and app management controls.
2. **API Tokens (advanced).** Tools connect using an API token instead of per-user OAuth. Described as useful for <escape>"service-style or non-interactive tools."</escape> An organization-level setting controls enablement.

## Atlassian-supported domains

<escape>
"Atlassian-supported domains are a list of Atlassian AI partners" including Anthropic (Claude.ai) and OpenAI (ChatGPT). By default, these domains are automatically allowed. Admins can block all supported domains collectively but cannot block individual domains.
</escape>

## IP allowlisting integration

- IP allowlists are **configured in Atlassian Administration** (not in MCP settings themselves).
- When users access apps through the MCP server, requests are evaluated against the organization's IP policies.
- Blocked IPs receive the error: <escape>"You don't have permission to connect from this IP address."</escape>
- **GOTCHA:** Some AI tools set their own outbound IPs. This can cause MCP calls to be blocked even when the user's corporate network is on the allowlist — because the request originates from the AI tool's infrastructure, not the user's network.

## Related links mentioned on the page

- Monitoring activity
- Controlling settings
- Available domains
- Configuring permissions
- Managing A2A connections
- Third-party MCP agent guidelines

## Documentation gaps explicitly observed

The following topics are **not addressed** on this page:

- Geographic regions or per-region MCP endpoints (US, EU, AP variants)
- Data residency or data processing locations
- Architecture diagrams
- Encryption specifications (TLS version, at-rest standards)
- Compliance certifications (SOC 2, ISO 27001, GDPR, FedRAMP, HIPAA)
- Audit log retention policies
- Data retention for MCP traffic
- Pricing / billing model
- GA vs. beta status (overall)
- Edition / plan requirements
- Admin UI navigation paths

This is not speculation — the page was fetched, read, and these topics were confirmed absent. The documentation-gap signal is itself a load-bearing artifact of this ingest.
