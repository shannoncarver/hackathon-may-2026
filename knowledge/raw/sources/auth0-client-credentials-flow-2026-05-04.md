---
title: "Auth0 — Client Credentials Flow (Machine-to-Machine)"
url: "https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow"
fetched_at: 2026-05-04
auth_required: false
license_note: "Auth0 public documentation — condensed for agent reference; cite source for verbatim text"
sources_also_consulted:
  - "https://auth0.com/docs/get-started/authentication-and-authorization-flow/call-your-api-using-the-client-credentials-flow"
fetch_note: "Primary URL (authentication-and-authorization-flows/client-credentials-flow, with 's') returned HTTP 404. Canonical URL is authentication-and-authorization-flow (without 's'). Content retrieved via the call-your-api sub-page and web search corroboration."
---

# Auth0 — Client Credentials Flow (Machine-to-Machine)

## Purpose

The Client Credentials Flow (OAuth 2.0 RFC 6749, Section 4.4) enables machine-to-machine (M2M) authentication where applications authenticate themselves rather than a human user. Use cases: CLIs, daemon processes, backend services, API-to-API calls.

## Parties

- **Application** (OAuth client): holds client_id and client_secret; requests the token.
- **Auth0 Authorization Server**: validates credentials, issues access tokens.
- **API** (resource server): protected resource that accepts the token.

## Flow Steps

1. Application POSTs its credentials to Auth0's token endpoint.
2. Auth0 validates client_id, client_secret, and audience.
3. Auth0 issues an access token.
4. Application presents the Bearer token in the `Authorization` header when calling the protected API.
5. API validates the token and returns the requested data.

## Token Request

**Endpoint:** `POST https://{yourDomain}/oauth/token`

**Content-Type:** `application/x-www-form-urlencoded`

**Parameters:**

| Parameter | Required | Value |
|-----------|----------|-------|
| `grant_type` | REQUIRED | `client_credentials` |
| `client_id` | REQUIRED | Application's client ID from Auth0 dashboard |
| `client_secret` | REQUIRED | Application's client secret from Auth0 dashboard |
| `audience` | REQUIRED | API Identifier (found in API settings in Auth0 dashboard) |
| `scope` | OPTIONAL | Space-delimited list of permissions (e.g., `read:messages write:data`) |
| `organization` | OPTIONAL | Organization name or ID for M2M requests in multi-tenant scenarios |

## Token Response

Successful HTTP 200 response body:

```json
{
  "access_token": "eyJz93a...k4laUWw",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

- `access_token`: JWT access token.
- `token_type`: Always `"Bearer"` for client credentials flow.
- `expires_in`: Token lifetime in seconds. Default is 86400 (24 hours).
- No `refresh_token` is issued in client credentials flow — applications re-request a token when the current one expires.
- `scope` is returned in the response if the granted scope differs from what was requested (or as confirmation).

## Using the Token

Pass the token as a Bearer credential:

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

## Token Lifecycle and Caching

- Default expiration: 86400 seconds (24 hours).
- Auth0 recommends validating tokens before saving them.
- Applications should cache tokens and re-request only after expiration.
- No refresh_token mechanism exists for client credentials flow — re-authenticate with client_secret.
- Auth0 Actions can customize token claims or deny access based on custom logic.

## Audience and Scope

- **Audience** (`aud` claim in JWT): identifies the API the token is issued for. Must match the API Identifier registered in Auth0. A token issued for audience A will be rejected by API B (audience validation enforced by the resource server).
- **Scope**: specifies requested permissions. Scopes can be enabled on a per-API and per-application basis, allowing granular M2M permission grants.

## Security Requirement

Because the application must always hold the client_secret, this grant is only for **trusted clients** where there is no risk of the secret being exposed. Do not use in browser-based or mobile applications.

## Relationship to RFC 6749

This flow implements OAuth 2.0 RFC 6749 Section 4.4 (Client Credentials Grant). No user interaction or authorization code is involved. The application acts as both the resource owner and the client.
