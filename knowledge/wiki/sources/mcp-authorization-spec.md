---
title: "MCP Specification 2025-06-18 — Authorization"
kind: source
raw_path: "raw/sources/mcp-authorization-spec-2026-05-04.md"
url: "https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization"
author: "Model Context Protocol authors"
fetched_at: 2026-05-04
tags: ["mcp", "oauth", "authorization", "security", "product:cross-cutting"]
entities:
  - "wiki/entities/mcp-authorization.md"
concepts: []
created: 2026-05-04
updated: 2026-05-04
---

## Why this source

Closes the MCP authorization spec gap identified in the Decision 0014 Phase A review. The Platform MCP Server design requires understanding which OAuth flows MCP servers must support, how dynamic client registration works, and how protected resource metadata drives authorization server discovery.

## What it covers

The MCP 2025-06-18 authorization specification for HTTP-based transports. Covers: OAuth 2.1 compliance, Protected Resource Metadata (RFC 9728), Dynamic Client Registration (RFC 7591), Authorization Server Metadata (RFC 8414), PKCE requirement, the `resource` parameter (RFC 8707), token audience validation, and token passthrough prohibition.

## Key claims

- Authorization is **OPTIONAL** for MCP implementations. HTTP-based transports SHOULD conform; STDIO transports SHOULD NOT (use environment credentials instead). [raw/sources/mcp-authorization-spec-2026-05-04.md]
- Standards basis: OAuth 2.1 (draft-ietf-oauth-v2-1-13), RFC 8414 (AS Metadata), RFC 7591 (Dynamic Client Registration), RFC 9728 (Protected Resource Metadata), RFC 8707 (Resource Indicators). [raw/sources/mcp-authorization-spec-2026-05-04.md]
- MCP servers act as OAuth 2.1 **resource servers**. MCP clients act as OAuth 2.1 **clients**. The authorization server may be co-located or separate. [raw/sources/mcp-authorization-spec-2026-05-04.md]
- MCP servers MUST implement RFC 9728 Protected Resource Metadata. When returning HTTP 401, servers MUST include a `WWW-Authenticate` header pointing to the resource server metadata URL. [raw/sources/mcp-authorization-spec-2026-05-04.md]
- Authorization server discovery: client fetches `/.well-known/oauth-protected-resource` from the MCP server, gets the `authorization_servers` array, then fetches `/.well-known/oauth-authorization-server` from the chosen AS. [raw/sources/mcp-authorization-spec-2026-05-04.md]
- Dynamic Client Registration (RFC 7591) SHOULD be supported by both authorization servers and MCP clients. Without it: either hardcode a client ID or present UI for manual registration. [raw/sources/mcp-authorization-spec-2026-05-04.md]
- MCP clients MUST implement PKCE (Proof Key for Code Exchange). Authorization servers MUST validate exact redirect URIs. [raw/sources/mcp-authorization-spec-2026-05-04.md]
- MCP clients MUST include the `resource` parameter (RFC 8707) in both authorization requests and token requests, identifying the MCP server's canonical URI. MUST send even if the AS doesn't support it. [raw/sources/mcp-authorization-spec-2026-05-04.md]
- **Token passthrough is forbidden.** MCP servers MUST NOT pass through the access token they received from the MCP client to upstream APIs. Upstream API calls require a separately-issued token from the upstream authorization server. [raw/sources/mcp-authorization-spec-2026-05-04.md]
- MCP servers MUST validate that access tokens were issued specifically for them (audience validation). MUST reject tokens not intended for them. Invalid or expired tokens MUST receive HTTP 401. [raw/sources/mcp-authorization-spec-2026-05-04.md]
- Authorization servers SHOULD issue short-lived access tokens. For public clients, MUST rotate refresh tokens. [raw/sources/mcp-authorization-spec-2026-05-04.md]
- The spec supports the confused deputy problem: MCP proxy servers using static client IDs MUST obtain user consent for each dynamically registered client before forwarding to third-party authorization servers. [raw/sources/mcp-authorization-spec-2026-05-04.md]

## Entities introduced

- [wiki/entities/mcp-authorization.md] — new entity: MCP OAuth 2.1 authorization flow, discovery mechanisms, and security requirements.

## Open questions for LINQ

1. **Auth0 as MCP authorization server.** The spec requires Protected Resource Metadata (RFC 9728) support at the MCP server level. Does Auth0 serve as the authorization server for the Platform MCP Server? Auth0 supports RFC 8414 (AS Metadata) and RFC 7591 (Dynamic Client Registration). Does LINQ's Auth0 tenant need RFC 9728 configuration?
2. **STDIO vs. HTTP transport.** The authorization spec applies to HTTP-based MCP transports. The Platform MCP Server's transport choice (STDIO or HTTP/SSE) determines whether this entire authorization layer applies. Which transport does the centralized Platform MCP Server use?
3. **Token passthrough and upstream APIs.** The Platform MCP Server exposes handlers for 4 products. Each product API likely has its own authorization server. The token-passthrough prohibition means the MCP server must independently authenticate to each downstream product API — is Auth0 the shared upstream AS for all 4, or do each have separate authorization?
4. **Dynamic client registration at LINQ scale.** The spec recommends Dynamic Client Registration. LINQ's Agent SDK agents (sub-agents) would each be an MCP client. Does LINQ's Auth0 configuration support RFC 7591 dynamic registration, or will each agent sub-type need a pre-registered client ID?
