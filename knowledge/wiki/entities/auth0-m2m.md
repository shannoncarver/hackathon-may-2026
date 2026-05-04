---
title: "Auth0 M2M (Machine-to-Machine)"
kind: entity
tags: ["auth0", "oauth", "m2m", "authentication", "jwt", "product:cross-cutting"]
aliases: ["Auth0 client credentials", "Auth0 M2M app", "machine-to-machine authentication"]
sources:
  - "wiki/sources/auth0-client-credentials-flow.md"
related:
  - "wiki/entities/oauth-token-exchange.md"
  - "wiki/entities/mcp-authorization.md"
  - "wiki/entities/sts-assume-role-external-id.md"
created: 2026-05-04
updated: 2026-05-04
---

# Auth0 M2M (Machine-to-Machine)

Auth0 M2M is Auth0's implementation of the OAuth 2.0 Client Credentials Flow (RFC 6749, Section 4.4) for authenticating backend services, daemons, CLIs, and APIs to other APIs — without user involvement. The application presents its `client_id` and `client_secret`; Auth0 issues a JWT access token.

Source: [wiki/sources/auth0-client-credentials-flow.md]

---

## Parties

| Party | Role |
|-------|------|
| **M2M Application** | OAuth client; holds `client_id` and `client_secret` |
| **Auth0 Authorization Server** | Validates credentials; issues access tokens |
| **Protected API** (resource server) | Validates the Bearer token; returns data |

---

## Token Request

**Endpoint:** `POST https://{yourDomain}/oauth/token`
**Content-Type:** `application/x-www-form-urlencoded`

| Parameter | Required | Value |
|-----------|----------|-------|
| `grant_type` | REQUIRED | `client_credentials` |
| `client_id` | REQUIRED | Application's client ID from Auth0 dashboard |
| `client_secret` | REQUIRED | Application's client secret from Auth0 dashboard |
| `audience` | REQUIRED | API Identifier registered in Auth0 (becomes `aud` JWT claim) |
| `scope` | optional | Space-delimited permission list (e.g., `read:messages write:data`) |
| `organization` | optional | Organization name/ID for multi-tenant scenarios |

---

## Token Response

Successful HTTP 200:

```json
{
  "access_token": "eyJz93a...k4laUWw",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

| Field | Description |
|-------|-------------|
| `access_token` | JWT signed by Auth0; contains `aud`, `iss`, `sub`, `exp`, `iat`, and granted scopes |
| `token_type` | Always `"Bearer"` for client credentials flow |
| `expires_in` | Seconds until expiry; default is 86400 (24 hours) |

**No `refresh_token` is issued.** To get a new token after expiry, re-POST with `client_secret`.

---

## Token Lifecycle

- Default lifetime: **86400 seconds (24 hours)**.
- Applications should cache the token and track expiry; re-request before expiry.
- Auth0 recommends validating tokens before saving (e.g., verify signature and claims).
- Re-authentication is via `client_secret` re-POST — not a refresh token.

---

## Audience and Scope Semantics

**Audience (`aud`):**
- Identifies which API the token is for.
- The protected API validates that `aud` matches its own API Identifier.
- A token issued for API A will be rejected by API B (audience mismatch).
- One token per target API is the norm.

**Scope:**
- Optional but recommended for least-privilege access.
- Scopes can be restricted per API and per M2M application in the Auth0 dashboard.
- Example: `read:customers` allows read-only access; `write:customers` allows write.

---

## Security Constraints

- `client_secret` must never be exposed. This flow is for **trusted clients only** — backend services where the secret is protected.
- Do NOT use in browser-based or mobile applications (use Authorization Code + PKCE instead).
- Auth0 Actions can inject custom claims into the token or deny access based on custom logic.

---

## Bearer Token Usage

```
Authorization: Bearer ACCESS_TOKEN
```

Example curl:
```bash
curl --request GET \
  --url https://myapi.com/api \
  --header 'authorization: Bearer ACCESS_TOKEN' \
  --header 'content-type: application/json'
```

---

## Relationship to Platform MCP Server (Decision 0015)

The Platform MCP Server will use Auth0 M2M in two roles:

1. **Inbound authentication**: the MCP server validates Bearer tokens from agent sub-agents (who obtained them via client credentials flow against the Platform MCP Server's Auth0 API registration).
2. **Outbound authentication**: the Platform MCP Server itself authenticates to downstream LINQ product APIs using its own M2M credentials (a separate Auth0 application with its own `client_id` and `client_secret`).

Key design questions (flagged as gaps in the source page):
- Does LINQ have separate Auth0 API registrations per LINQ product, or a single shared API?
- What scope naming convention does LINQ use for product API permissions?
- Is the `organization` parameter needed for multi-tenant LINQ scenarios?

See also:
- [wiki/entities/oauth-token-exchange.md] — for on-behalf-of / delegation patterns when an agent acts for a user.
- [wiki/entities/sts-assume-role-external-id.md] — for the bridge between Auth0 JWTs and AWS STS credentials.
- [wiki/entities/mcp-authorization.md] — for MCP's OAuth 2.1 authorization layer that wraps token issuance.
