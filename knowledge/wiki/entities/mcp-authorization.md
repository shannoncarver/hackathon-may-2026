---
title: "MCP Authorization"
kind: entity
tags: ["mcp", "oauth", "authorization", "security", "product:cross-cutting"]
aliases: ["MCP OAuth", "MCP auth spec", "MCP Protected Resource Metadata"]
sources:
  - "wiki/sources/mcp-authorization-spec.md"
related:
  - "wiki/entities/mcp-tool-catalog.md"
  - "wiki/entities/auth0-m2m.md"
  - "wiki/entities/oauth-token-exchange.md"
  - "wiki/entities/atlassian-mcp.md"
created: 2026-05-04
updated: 2026-05-04
---

# MCP Authorization

The MCP authorization layer is an OPTIONAL but RECOMMENDED mechanism for HTTP-based MCP servers to enforce access control using OAuth 2.1. It is governed by the MCP 2025-06-18 specification and implements a selected subset of established OAuth and IANA standards.

Source: [wiki/sources/mcp-authorization-spec.md]

---

## Applicability

| Transport | Authorization spec applies? |
|-----------|---------------------------|
| HTTP / SSE | SHOULD conform to this spec |
| STDIO | SHOULD NOT use this spec — retrieve credentials from environment |
| Other | MUST follow protocol-specific security best practices |

---

## Standards Implemented

| Standard | Role |
|---------|------|
| OAuth 2.1 (draft-ietf-oauth-v2-1-13) | Core authorization framework |
| RFC 9728 — Protected Resource Metadata | Server advertises its authorization server |
| RFC 8414 — Authorization Server Metadata | AS advertises its endpoints |
| RFC 7591 — Dynamic Client Registration | Clients register without user interaction |
| RFC 8707 — Resource Indicators | Tokens bound to specific target resources |

---

## Roles

- **MCP server**: acts as an OAuth 2.1 **resource server**. Validates access tokens; rejects unauthorized requests.
- **MCP client**: acts as an OAuth 2.1 **client**. Discovers authorization servers; acquires and presents tokens.
- **Authorization server**: issues access tokens. May be co-located with the MCP server or a separate service (e.g., Auth0).

---

## Authorization Server Discovery

The discovery flow is metadata-driven — clients do not need hardcoded authorization server URLs:

1. Client sends an MCP request without a token.
2. Server returns **HTTP 401** with `WWW-Authenticate` header containing the Protected Resource Metadata URL.
3. Client fetches `/.well-known/oauth-protected-resource` from the MCP server.
4. Server returns a document with `authorization_servers` array (one or more AS URLs).
5. Client fetches `/.well-known/oauth-authorization-server` from the chosen AS.
6. AS returns its metadata (endpoints, supported grant types, capabilities).

---

## Authorization Code Flow (Full)

1. Client receives HTTP 401; extracts resource metadata URL.
2. Client fetches Protected Resource Metadata.
3. Client fetches AS Metadata.
4. (Optional) Client performs **Dynamic Client Registration**: `POST /register` → receives `client_id` (and credentials if confidential client).
5. Client generates PKCE `code_verifier` + `code_challenge`; includes `resource` parameter.
6. Client opens browser to authorization URL.
7. User authorizes; AS redirects to callback with authorization code.
8. Client exchanges code + `code_verifier` + `resource` for access token.
9. Client presents `Authorization: Bearer <token>` on every MCP request.

---

## Resource Parameter (RFC 8707)

MCP clients MUST include `resource` in both authorization and token requests. The `resource` value is the canonical URI of the MCP server (e.g., `https://mcp.example.com/mcp`). This binds the issued token to that specific server — tokens cannot be reused at other servers.

Valid canonical URIs: include scheme, no fragment. Examples: `https://mcp.example.com`, `https://mcp.example.com:8443`, `https://mcp.example.com/server/mcp`.

---

## PKCE Requirement

MCP clients MUST implement PKCE (Proof Key for Code Exchange). Prevents authorization code interception attacks. The `code_verifier` is a random string; the `code_challenge` is its SHA-256 hash (base64url-encoded). The AS verifies these match at token exchange time.

---

## Token Validation Requirements

| Requirement | Detail |
|-------------|--------|
| Audience validation | MCP servers MUST verify tokens were issued for them specifically |
| Token passthrough | FORBIDDEN — MCP servers MUST NOT forward client tokens to upstream APIs |
| Upstream API calls | Require a separately-issued token from the upstream AS |
| Invalid/expired token response | MUST return HTTP 401 |

---

## HTTP Error Codes

| Code | Meaning |
|------|---------|
| 401 | Authorization required, or token invalid/expired |
| 403 | Valid token but insufficient scope/permissions |
| 400 | Malformed authorization request |

---

## Security Notes

- All AS endpoints MUST be served over HTTPS.
- All redirect URIs MUST be `localhost` or HTTPS.
- AS MUST validate exact redirect URIs against pre-registered values (prevents open redirect attacks).
- AS SHOULD issue short-lived access tokens.
- For public clients, AS MUST rotate refresh tokens.

---

## Relationship to Platform MCP Server (Decision 0015)

For the LINQ centralized Platform MCP Server:

- If using HTTP transport: this entire authorization layer applies.
- Auth0 is a strong candidate as the authorization server — it supports RFC 8414 and RFC 7591. Does it support RFC 9728 (Protected Resource Metadata)? Flagged as a gap.
- **Token passthrough prohibition** is architecturally significant: the Platform MCP Server cannot simply forward agent tokens to downstream LINQ product APIs. It needs its own downstream identity, likely via [wiki/entities/auth0-m2m.md] (client credentials) or [wiki/entities/sts-assume-role-external-id.md] (cross-account IAM role).
- Dynamic Client Registration is key for agent sub-types — each agent type could auto-register as an MCP client without manual Auth0 app setup.
