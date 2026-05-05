---
title: "OAuth 2.0 Token Exchange (RFC 8693)"
kind: entity
tags: ["oauth", "rfc", "token-exchange", "delegation", "impersonation", "product:cross-cutting"]
aliases: ["RFC 8693", "token exchange", "on-behalf-of", "OBO", "delegation token"]
sources:
  - "wiki/sources/oauth-token-exchange-rfc8693.md"
related:
  - "wiki/entities/auth0-m2m.md"
  - "wiki/entities/mcp-authorization.md"
  - "wiki/entities/sts-assume-role-external-id.md"
created: 2026-05-04
updated: 2026-05-04
---

# OAuth 2.0 Token Exchange (RFC 8693)

RFC 8693 defines the `urn:ietf:params:oauth:grant-type:token-exchange` extension grant type, enabling OAuth 2.0 authorization servers to act as Security Token Services (STS). It standardizes two patterns: **impersonation** (on-behalf-of) and **delegation**. The grant allows one security token to be exchanged for another, optionally of a different type, issued by a different authority.

Source: [wiki/sources/oauth-token-exchange-rfc8693.md]

---

## Grant Type

`grant_type: urn:ietf:params:oauth:grant-type:token-exchange`

Posted to the standard OAuth 2.0 token endpoint.

---

## Request Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `subject_token` | REQUIRED | The input token representing the party on whose behalf the request is made |
| `subject_token_type` | REQUIRED | URI identifying the subject token format |
| `actor_token` | optional | Token representing the identity of the acting party |
| `actor_token_type` | REQUIRED if actor_token present | Format URI for the actor token |
| `requested_token_type` | optional | Desired output token type |
| `resource` | optional | Absolute URI of the target service (multiple allowed) |
| `audience` | optional | Logical name of target service (multiple allowed) |
| `scope` | optional | Space-delimited desired scopes for the issued token |

---

## Response Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `access_token` | REQUIRED | The issued security token (name is historical; need not be an OAuth access token) |
| `issued_token_type` | REQUIRED | URI identifying the issued token's format |
| `token_type` | REQUIRED | `Bearer` for access tokens; `N_A` for non-access tokens |
| `expires_in` | RECOMMENDED | Validity in seconds |
| `scope` | conditional | Required if issued scope differs from requested |
| `refresh_token` | optional | Typically NOT issued for token exchange |

---

## Impersonation vs. Delegation

### Impersonation (On-Behalf-Of)

Only `subject_token` is provided (no `actor_token`).

> "When principal A impersonates principal B, A is given all the rights that B has within some defined rights context."

The issued token grants the caller **all rights** the subject has. The caller acts indistinguishably as the subject. The downstream system sees only the subject's identity.

**Use case**: Service A needs to make API calls as User B, where the downstream API should see User B's identity and apply B's permissions.

### Delegation

Both `subject_token` and `actor_token` are provided.

The issued token is a composite — principal A (actor) acts on behalf of B (subject) while **A retains its distinct identity**. The JWT `act` claim records the delegation chain:

```json
{
  "sub": "user-B-id",
  "act": { "sub": "service-A-id" }
}
```

Nested `act` claims record multi-hop delegation chains (e.g., A delegated to C on behalf of B).

**Use case**: Service A is authorized by User B to take actions; downstream systems can see both that Service A is acting AND that it's authorized by User B.

---

## Token Type Identifiers

| URI | Token type |
|-----|-----------|
| `urn:ietf:params:oauth:token-type:jwt` | JWT |
| `urn:ietf:params:oauth:token-type:access_token` | OAuth 2.0 access token |
| `urn:ietf:params:oauth:token-type:refresh_token` | OAuth 2.0 refresh token |
| `urn:ietf:params:oauth:token-type:id_token` | OpenID Connect ID token |
| `urn:ietf:params:oauth:token-type:saml1` | SAML 1.1 (base64url-encoded) |
| `urn:ietf:params:oauth:token-type:saml2` | SAML 2.0 (base64url-encoded) |

---

## JWT Delegation Claims

| Claim | Purpose |
|-------|---------|
| `act` | Current actor in delegation chain; nested `act` shows delegation history |
| `may_act` | Which party is authorized to assume the actor role |
| `scope` | Space-separated granted scopes |
| `client_id` | OAuth 2.0 client that requested the token |

---

## Scope and Target Handling

- `resource`, `audience`, and `scope` are cumulative — requested rights are the Cartesian product of all scopes at all target services.
- `invalid_target` error: AS cannot fulfill the multi-target request.
- Token exchange does not invalidate the input tokens (absent one-time-use semantics).
- Exchange is a one-time event — no tight linkage between input and output tokens.

---

## Error Codes

| Code | Trigger |
|------|---------|
| `invalid_request` | Invalid request parameters or tokens |
| `invalid_target` | Cannot issue tokens for specified targets |

---

## Relationship to Platform MCP Server (Decision 0015)

RFC 8693 is the pure-OAuth answer to multi-hop service delegation. For the Platform MCP Server:

- **Inbound agent → MCP server → product API**: the MCP server receives a token from an agent sub-agent and must call a LINQ product API. If the product API needs to know "on whose behalf" the call is made, RFC 8693 impersonation or delegation is the mechanism.
- **Auth0 support**: Auth0's built-in grant types are authorization code and client credentials. RFC 8693 support in Auth0 is not confirmed — may require a custom Action or enterprise feature. This is a confirmed gap.
- **AWS STS `AssumeRoleWithWebIdentity`**: analogous but distinct — accepts a JWT (functionally similar to a `subject_token`) and issues STS temporary credentials. Not an RFC 8693 exchange, but conceptually related. See [wiki/entities/sts-assume-role-external-id.md].
- **Delegation chain visibility**: if audit trails need to show "Agent X acted on behalf of User Y", RFC 8693 delegation with `act` claims provides this at the token level.
