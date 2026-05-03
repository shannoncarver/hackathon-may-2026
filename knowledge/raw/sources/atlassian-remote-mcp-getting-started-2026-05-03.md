---
title: "Atlassian Rovo MCP Server — Getting Started (support docs)"
url: "https://support.atlassian.com/rovo/docs/getting-started-with-the-atlassian-remote-mcp-server/"
fetched_at: 2026-05-03
auth_required: false
license_note: "Atlassian public docs — condensed for agent reference; cite source for verbatim text"
---

## Overview

The Atlassian Rovo MCP Server is a cloud bridge enabling external tools to interact with Jira, Compass, and Confluence data via secure OAuth 2.1 authorization. It powers summarization, search, issue/page creation, and task automation.

## Server endpoints

- **Current endpoint:** `https://mcp.atlassian.com/v1/mcp/authv2`
- **Legacy endpoint (deprecated):** `https://mcp.atlassian.com/v1/sse` — will not be supported after June 30, 2026.

## Supported clients and IDEs

Supported AI clients:
- OpenAI ChatGPT
- Claude
- Docker
- GitHub Copilot CLI
- Google Gemini
- Amazon Quick Suite
- Any local MCP-compatible client via `mcp-remote` proxy

Supported IDEs and desktop environments:
- Claude Desktop
- VS Code
- Cursor

## Prerequisites

**For supported clients:**
- Atlassian Cloud site with Jira, Compass, and/or Confluence
- Modern browser for OAuth 2.1 authorization flow
- API token (if admin enabled token authentication)

**For IDEs and desktop setup:**
- Supported IDE (Claude Desktop, VS Code, Cursor)
- Node.js v18+ to run `mcp-remote` proxy
- Modern browser for OAuth 2.1
- API token (if admin enabled)

## Authentication methods

1. **OAuth 2.1 (primary):** Secure browser-based flow with dynamic client registration support.
2. **API Token (optional):** Admin-controlled alternative; disabled by default.

Tokens are scoped and session-based. All actions respect existing Jira, Confluence, and Compass user permissions.

## Security and data protection

- All traffic encrypted via HTTPS using TLS 1.2 or later
- Data access respects Jira, Compass, and Confluence user permissions
- IP allowlisting rules honored if configured
- OAuth tokens and API tokens are scoped and session-based

## Capabilities by product

- **Jira:** Search, create/update issues, bulk creation
- **Confluence:** Summarize, create pages, list accessible spaces
- **Compass:** Create service components, bulk import, query dependencies
- **Combined:** Link content across products, fetch linked documentation

## Permissions model

Access is limited to data the authenticated user already has permission to view. All actions respect existing project or space-level roles. If IP allowlisting is enabled, MCP requests must originate from an allowed IP address for each relevant product.

## Admin installation and access control

- Not a Marketplace app; installed just-in-time on first OAuth consent
- First user must have access to requested apps (Jira, Confluence, etc.)
- Admins manage via Atlassian Administration's "Rovo MCP server" settings page
- Domain allowlisting controls which external tools can connect
- Users can revoke access via personal profile settings
- Audit logging captures key actions for compliance

## Common admin troubleshooting

- "Your site admin must authorize this app" — site admin must complete OAuth 2.1 consent flow first
- "Your organization admin must authorize access from a domain" — org admin must add the domain in Rovo MCP server settings
- "You don't have permission to connect from this IP address" — IP allowlisting enabled; ask admin to add relevant network/VPN ranges
- App not appearing in Connected apps — verify correct Atlassian account, site, and Jira/Confluence/Compass permissions

## Linked sub-pages (candidate sources for follow-up ingest)

- Authentication and authorization
- Configuring OAuth 2.1
- Configuring authentication via API token
- Supported tools — enumerates specific tool names; closes the gap flagged in `atlassian-remote-mcp-server.md` OQ#1
- Setting up clients
- Setting up IDEs (desktop clients)
- Using with other supported MCP clients
- Using Rovo search and fetch in the Atlassian Rovo MCP Server
- Troubleshooting and verifying your setup
- Connect Rovo to Gemini via Google Cloud Marketplace
- Understand Atlassian Rovo MCP Server (admin)
- Control Atlassian Rovo MCP Server settings (admin)
- Monitor Atlassian Rovo MCP Server activity (admin)
- Available Atlassian Rovo MCP Server domains (admin) — canonical MCP host list; relevant to /kb-ingest routing
