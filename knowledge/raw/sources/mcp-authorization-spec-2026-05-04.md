---
title: "MCP Specification 2025-06-18 — Authorization"
url: "https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization"
fetched_at: 2026-05-04
auth_required: false
license_note: "Model Context Protocol public documentation — condensed for agent reference; cite source for verbatim text"
---

# MCP Specification 2025-06-18 — Authorization

## Purpose and Scope

The MCP authorization spec defines authorization capabilities at the transport level, enabling MCP clients to make requests to restricted MCP servers on behalf of resource owners. This spec applies to HTTP-based transports.

Authorization is **OPTIONAL** for MCP implementations.

- HTTP-based transports: SHOULD conform to this specification.
- STDIO transports: SHOULD NOT follow this spec — retrieve credentials from the environment instead.
- Other transports: MUST follow established security best practices for their protocol.

## Standards Basis

Implements a selected subset of:
- OAuth 2.1 IETF DRAFT (draft-ietf-oauth-v2-1-13)
- OAuth 2.0 Authorization Server Metadata (RFC 8414)
- OAuth 2.0 Dynamic Client Registration Protocol (RFC 7591)
- OAuth 2.0 Protected Resource Metadata (RFC 9728)
- Resource Indicators for OAuth 2.0 (RFC 8707)

## Roles

- **MCP server** acts as an OAuth 2.1 resource server.
- **MCP client** acts as an OAuth 2.1 client, making requests on behalf of a resource owner.
- **Authorization server** issues access tokens. It may be co-located with the MCP server or separate.

## Core Requirements

1. Authorization servers MUST implement OAuth 2.1 with appropriate security measures for both confidential and public clients.
2. Authorization servers and MCP clients SHOULD support Dynamic Client Registration (RFC 7591).
3. MCP servers MUST implement OAuth 2.0 Protected Resource Metadata (RFC 9728).
4. MCP clients MUST use OAuth 2.0 Protected Resource Metadata for authorization server discovery.
5. Authorization servers MUST provide OAuth 2.0 Authorization Server Metadata (RFC 8414).
6. MCP clients MUST use the OAuth 2.0 Authorization Server Metadata.

## Authorization Server Discovery

### Discovery Mechanism

1. Client makes an MCP request without a token.
2. Server returns HTTP 401 Unauthorized with `WWW-Authenticate` header pointing to the Protected Resource Metadata URL.
3. Client fetches `/.well-known/oauth-protected-resource` from the MCP server.
4. Server returns resource metadata document containing `authorization_servers` field with at least one authorization server URL.
5. Client fetches `/.well-known/oauth-authorization-server` from the authorization server.
6. Authorization server returns its metadata (endpoints, capabilities, supported grant types).

MCP servers MUST return `WWW-Authenticate` on HTTP 401, indicating the resource server metadata URL per RFC 9728 Section 5.1.

MCP clients MUST parse `WWW-Authenticate` headers and respond appropriately to HTTP 401 responses.

### Protected Resource Metadata Document

Required field: `authorization_servers` — array of authorization server URLs. Multiple authorization servers can be listed; MCP client selects which to use per RFC 9728 Section 7.6.

## Dynamic Client Registration (RFC 7591)

MCP clients and authorization servers SHOULD support Dynamic Client Registration. This enables MCP clients to obtain OAuth client IDs without user interaction, which is crucial because:
- Clients may not know all possible MCP servers and their authorization servers in advance.
- Manual registration creates friction.
- It enables seamless connection to new MCP servers.

For authorization servers that do NOT support Dynamic Client Registration:
- Option 1: MCP client hardcodes a client ID (and credentials if applicable).
- Option 2: MCP client presents UI for users to enter credentials after manual OAuth client registration.

## Authorization Flow Steps (Authorization Code Flow)

1. Client sends MCP request without token.
2. Server responds HTTP 401 with `WWW-Authenticate` header.
3. Client extracts resource metadata URL from `WWW-Authenticate`.
4. Client fetches Protected Resource Metadata from MCP server.
5. Client parses metadata, extracts authorization server(s), determines which AS to use.
6. Client fetches `/.well-known/oauth-authorization-server` from chosen AS.
7. (Optional) Client performs Dynamic Client Registration: POST `/register` → receives client credentials.
8. Client generates PKCE parameters (code_verifier, code_challenge). Includes `resource` parameter.
9. Client opens browser with authorization URL + code_challenge + resource parameter.
10. User authorizes in browser.
11. Authorization server redirects to callback with authorization code.
12. Client exchanges authorization code + code_verifier + resource for access token.
13. Authorization server returns access token (and optional refresh token).
14. Client makes MCP request with `Authorization: Bearer <access-token>`.
15. MCP communication continues with valid token.

## Resource Parameter (RFC 8707)

MCP clients MUST implement Resource Indicators for OAuth 2.0 (RFC 8707).

The `resource` parameter:
- MUST be included in both authorization requests and token requests.
- MUST identify the MCP server that the client intends to use the token with.
- MUST use the canonical URI of the MCP server.
- MUST be sent even if authorization servers don't support it.

Valid canonical URI examples:
- `https://mcp.example.com/mcp`
- `https://mcp.example.com`
- `https://mcp.example.com:8443`

Invalid: missing scheme (`mcp.example.com`), containing fragment (`...#fragment`).

## Access Token Usage

- MUST use `Authorization: Bearer <access-token>` header on every HTTP request from client to server.
- Access tokens MUST NOT be included in the URI query string.
- MCP servers MUST validate access tokens were issued specifically for them as the intended audience (per RFC 8707 Section 2).
- Invalid or expired tokens MUST receive HTTP 401.

## PKCE Requirement

MCP clients MUST implement PKCE (Proof Key for Code Exchange) per OAuth 2.1 Section 7.5.2. Prevents authorization code interception and injection attacks.

## HTTP Error Codes

| Status | Description | Usage |
|--------|-------------|-------|
| 401 | Unauthorized | Authorization required or token invalid |
| 403 | Forbidden | Invalid scopes or insufficient permissions |
| 400 | Bad Request | Malformed authorization request |

## Security Considerations

### Token Passthrough Prohibition

MCP servers MUST NOT pass through the access token they received from the MCP client to upstream APIs. If the MCP server makes requests to upstream APIs, it acts as an OAuth client to them and obtains a separate token from the upstream authorization server.

### Token Audience Validation

MCP servers MUST only accept tokens specifically intended for themselves. MUST reject tokens that do not include them in the audience claim. This prevents confused deputy attacks where tokens issued for one service are misused at another.

### Redirect URI Validation

- All authorization server endpoints MUST be served over HTTPS.
- All redirect URIs MUST be either `localhost` or use HTTPS.
- Authorization servers MUST validate exact redirect URIs against pre-registered values.
- MCP clients MUST have redirect URIs registered with the authorization server.
- MCP clients SHOULD use and verify state parameters in the authorization code flow.

### Confused Deputy Problem

MCP proxy servers using static client IDs MUST obtain user consent for each dynamically registered client before forwarding to third-party authorization servers.

### Token Theft Mitigation

Authorization servers SHOULD issue short-lived access tokens. For public clients, authorization servers MUST rotate refresh tokens (OAuth 2.1 Section 4.3.1).
