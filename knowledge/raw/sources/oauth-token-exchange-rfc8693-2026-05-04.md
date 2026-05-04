---
title: "RFC 8693 — OAuth 2.0 Token Exchange"
url: "https://datatracker.ietf.org/doc/html/rfc8693"
fetched_at: 2026-05-04
auth_required: false
license_note: "IETF RFC — public domain; cite RFC number and URL for verbatim text"
---

# RFC 8693 — OAuth 2.0 Token Exchange

## Purpose

RFC 8693 defines the token-exchange extension grant type for OAuth 2.0, enabling clients to request security tokens from an authorization server acting as a Security Token Service (STS). It standardizes:

- Delegation (acting on behalf of another principal while retaining distinct identity)
- Impersonation (acting indistinguishably as another principal)

## Grant Type

The token-exchange grant type URI: `urn:ietf:params:oauth:grant-type:token-exchange`

Used as `grant_type` in a POST to the token endpoint.

## Request Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `grant_type` | REQUIRED | `urn:ietf:params:oauth:grant-type:token-exchange` |
| `subject_token` | REQUIRED | Security token representing the identity of the party on behalf of whom the request is being made |
| `subject_token_type` | REQUIRED | URI identifying the token type (e.g., `urn:ietf:params:oauth:token-type:jwt`) |
| `actor_token` | OPTIONAL | Token representing the identity of the acting party |
| `actor_token_type` | REQUIRED if actor_token present | Token type URI for the actor token; MUST NOT be included if actor_token is absent |
| `requested_token_type` | OPTIONAL | Desired output token type; if unspecified, at the authorization server's discretion |
| `resource` | OPTIONAL | Absolute URI of the target service or resource. Multiple values permitted. |
| `audience` | OPTIONAL | Logical name for the target service (e.g., OAuth client identifier, SAML entity ID). Multiple values permitted. |
| `scope` | OPTIONAL | Space-delimited list of desired scopes for the issued token |

## Response Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `access_token` | REQUIRED | The issued security token. Named `access_token` for historical reasons; need not be an OAuth access token. |
| `issued_token_type` | REQUIRED | URI identifying the type of the issued token (e.g., `urn:ietf:params:oauth:token-type:jwt`) |
| `token_type` | REQUIRED | How to utilize the token. Bearer tokens use `Bearer`; non-access-tokens use `N_A`. |
| `expires_in` | RECOMMENDED | Token validity in seconds. |
| `scope` | OPTIONAL | Required if issued scope differs from requested. |
| `refresh_token` | OPTIONAL | Typically NOT issued for token exchange (one temporary credential for another). |

## Impersonation vs. Delegation

### Impersonation (On-Behalf-Of Pattern)

Only `subject_token` is provided (no `actor_token`). The issued token grants the client all rights that the subject has — the client acts indistinguishably as the subject principal.

> "When principal A impersonates principal B, A is given all the rights that B has within some defined rights context."

Use case: service A needs to act as user B for downstream calls.

### Delegation Pattern

Both `subject_token` and `actor_token` are provided. The issued token is a "composite token" expressing that principal A (the actor) acts on behalf of B (the subject) while A retains its own identity.

The issued JWT includes an `act` (Actor) claim identifying the current actor. Nested `act` claims represent delegation chains.

> "Principal A still has its own identity separate from B" while representing B's interests.

Use case: service A delegates authority from user B to service C (chained delegation).

## Token Type Identifiers (URIs)

RFC 8693 defines these standard URIs:

| URI | Token type |
|-----|-----------|
| `urn:ietf:params:oauth:token-type:access_token` | OAuth 2.0 access token |
| `urn:ietf:params:oauth:token-type:refresh_token` | OAuth 2.0 refresh token |
| `urn:ietf:params:oauth:token-type:id_token` | OpenID Connect ID token |
| `urn:ietf:params:oauth:token-type:saml1` | SAML 1.1 assertion (base64url-encoded) |
| `urn:ietf:params:oauth:token-type:saml2` | SAML 2.0 assertion (base64url-encoded) |
| `urn:ietf:params:oauth:token-type:jwt` | JWT |

## Scope and Target Resource Handling

The `resource`, `audience`, and `scope` parameters are cumulative: "the requested access rights of the token are the Cartesian product of all the scopes at all the target services."

Clients should exercise discretion with broad multi-target requests. The `invalid_target` error code signals that the authorization server cannot fulfill a multi-target request.

## JWT-Specific Claims for Delegation

- **`act` (Actor)**: JSON object identifying the current actor in delegation chains; nested `act` claims show delegation history.
- **`may_act` (Authorized Actor)**: Indicates which party can assume the actor role.
- **`scope`**: Space-separated list of scopes granted.
- **`client_id`**: OAuth 2.0 client identifier that requested the token.

## Normative Processing Requirements

1. The authorization server MUST perform appropriate validation for the indicated token type for both subject and actor tokens.
2. Token exchange has "no impact on the validity of the subject token or actor token" absent one-time-use semantics.
3. The exchange is "a one-time event and does not create a tight linkage between the input and output tokens."
4. Client authentication uses standard OAuth 2.0 mechanisms (password, JWT bearer, etc.).

## Error Handling

- Invalid request or tokens: `invalid_request` error.
- Unable to issue tokens for specified targets: `invalid_target` error code SHOULD be used.

## Relationship to Other Specs

- Extends OAuth 2.0 (RFC 6749) with a new grant type.
- Interoperates with SAML tokens, JWT tokens, and OpenID Connect ID tokens as subject/actor token types.
- Foundational for cross-service delegation patterns in microservice architectures.
- In AWS STS terms: analogous to `AssumeRoleWithWebIdentity` (present a JWT, get STS credentials). RFC 8693 standardizes the pure-OAuth version of this pattern.
