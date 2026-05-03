---
title: "Available Atlassian Rovo MCP Server Domains (admin support docs)"
url: "https://support.atlassian.com/security-and-access-policies/docs/available-atlassian-rovo-mcp-server-domains/"
fetched_at: 2026-05-03
auth_required: false
license_note: "Atlassian public docs — condensed for agent reference; cite source for verbatim text"
---

## Overview

<escape>
By default, Atlassian automatically allows Atlassian-supported domains to access apps in your organization. Domain rules apply only to tools connecting via OAuth 2.1.
</escape>

This page documents the AI-client / partner domains that an Atlassian org admin pre-allowlists so external AI tools can dial INTO the org's Atlassian MCP server via OAuth 2.1. These are the domains of AI client tools — not the MCP server's own endpoints.

## Atlassian-supported pre-allowlisted domains

### HTTP (dev/test only)

- `127.0.0.1`
- `localhost`

### HTTPS (AI partner / client domains)

- `app.writer.com`
- `chatgpt.com`
- `claude.ai`
- `claude.com`
- `integrations.zoom.us`
- `figma-gov.com`
- `global.consent.azure-apim.net`
- `api.devin.ai`
- `*.apps.dynatrace.com`
- `*.azuredatabricks.net`
- `*.databricks.com`
- `*.resolve.ai`
- `vertexaisearch.cloud.google.com`
- `lovable.dev`
- `mcp.docker.com`
- `callback.mistral.ai`
- `oauth.pstmn.io`
- `token.botframework.com`
- `vscode.dev`
- `us-east-1.quicksight.aws.amazon.com`
- `www.canva.com`

### Protocol-specific (custom URI schemes for desktop/IDE clients)

- `cursor:` protocol (cursor.mcp)
- `raycast:` protocol (oauth)

## Adding custom domains — pattern syntax

Admins can authorize additional domains via four pattern types:

| Pattern type | Example |
|---|---|
| Single domain | `https://aiagent.mydomain.com` |
| Subdomain wildcard | `https://*.example.com/**` |
| Environment braces | `https://{dev,staging,prod}.platform-demo.com/**` |
| Port wildcard | `http://localhost:*/**` |

Pattern requirements (verbatim from source):

<escape>
- "Always include a protocol" (https://, http://, or custom like cursor://)
- http:// valid only for localhost or 127.0.0.1
- "Specify a valid domain or host" (no omitting top-level domain)
- Optional: port (:8080) or wildcard (:**)
- Optional: path wildcard (/**)
</escape>

## Configuration location (Atlassian Administration UI navigation)

Security and access policies → Maintain secure access to apps → Manage Atlassian Rovo MCP server → Control Atlassian Rovo MCP server settings

Related admin pages: Monitor activity, Configure permissions, Manage A2A connections.

## Key constraint

<escape>
"MCP clients can perform actions in Jira, Confluence, and Compass with your existing permissions. Use least privilege, review high-impact changes before confirming, and monitor audit logs."
</escape>

## Doc-namespace observation

This page lives at `support.atlassian.com/security-and-access-policies/docs/...` — a third Atlassian doc namespace, distinct from `/rovo/docs/` (legacy) and `/atlassian-rovo-mcp-server/docs/` (current user docs). The same Rovo MCP topic is split across at least three namespaces.

## Notable absences

- No geographic / regional variants (US, EU, AP) of the MCP server documented on this page.
- No beta or upcoming-deprecation markers on any listed domain.
- The MCP server's own endpoint hostnames are not enumerated on this page (they live on the getting-started page).
