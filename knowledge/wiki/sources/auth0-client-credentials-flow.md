---
title: "Auth0 — Client Credentials Flow (Machine-to-Machine)"
kind: source
raw_path: "raw/sources/auth0-client-credentials-flow-2026-05-04.md"
url: "https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow"
author: "Auth0 (Okta)"
fetched_at: 2026-05-04
tags: ["auth0", "oauth", "m2m", "authentication", "jwt", "product:cross-cutting"]
entities:
  - "wiki/entities/auth0-m2m.md"
concepts: []
created: 2026-05-04
updated: 2026-05-04
---

## Why this source

Closes the Auth0/M2M gap identified in the Decision 0014 Phase A review. The Platform MCP Server design requires understanding how backend services (agents, connectors) authenticate to LINQ APIs without user involvement, including token issuance, audience/scope semantics, and token lifecycle.

## What it covers

Auth0's implementation of the OAuth 2.0 Client Credentials Flow (RFC 6749, Section 4.4) for machine-to-machine authentication. Covers: parties, flow steps, token request parameters, response format, Bearer token usage, token lifecycle, audience/scope semantics, and security constraints.

Fetch note: the primary URL path variant (`authentication-and-authorization-flows`, with trailing `s`) returned HTTP 404. Content retrieved from the canonical path (`authentication-and-authorization-flow`, without `s`) and the `call-your-api` sub-page.

## Key claims

- The Client Credentials Flow authenticates **applications** (not human users). Use cases: CLIs, daemon processes, backend services, API-to-API calls. [raw/sources/auth0-client-credentials-flow-2026-05-04.md]
- Token endpoint: `POST https://{yourDomain}/oauth/token` with `Content-Type: application/x-www-form-urlencoded`. [raw/sources/auth0-client-credentials-flow-2026-05-04.md]
- Required request parameters: `grant_type=client_credentials`, `client_id`, `client_secret`, `audience` (the API Identifier registered in Auth0). Optional: `scope`, `organization`. [raw/sources/auth0-client-credentials-flow-2026-05-04.md]
- Successful response: `{"access_token": "...", "token_type": "Bearer", "expires_in": 86400}`. Default token lifetime is 86400 seconds (24 hours). [raw/sources/auth0-client-credentials-flow-2026-05-04.md]
- **No refresh_token** is issued. Applications must re-request a token when the current one expires by re-authenticating with client_secret. [raw/sources/auth0-client-credentials-flow-2026-05-04.md]
- `audience` maps to the `aud` claim in the JWT. A token issued for audience A will be rejected by API B — the resource server enforces audience validation. [raw/sources/auth0-client-credentials-flow-2026-05-04.md]
- `scope` enables granular per-API, per-application permission grants. Scopes can be restricted on a per-API and per-M2M-application basis in Auth0. [raw/sources/auth0-client-credentials-flow-2026-05-04.md]
- Token is used as `Authorization: Bearer ACCESS_TOKEN` in API requests. [raw/sources/auth0-client-credentials-flow-2026-05-04.md]
- Security constraint: client_secret must never be exposed (not for browser-based or mobile apps). This flow is **trusted-client only**. [raw/sources/auth0-client-credentials-flow-2026-05-04.md]
- Auth0 Actions can customize token claims or deny access based on custom logic. [raw/sources/auth0-client-credentials-flow-2026-05-04.md]

## Entities introduced

- [wiki/entities/auth0-m2m.md] — new entity: Auth0 M2M client credentials, token shape, lifecycle, and audience/scope semantics.

## Open questions for LINQ

1. **Auth0 tenant configuration.** Does LINQ's Auth0 tenant have APIs registered with identifiers matching the Platform MCP Server's audience value? What is the canonical audience URI for each LINQ product API?
2. **Token expiry and caching strategy.** The default is 86400 seconds (24 hours). For agents that make many API calls, what is the recommended caching approach? Auth0 recommends validating tokens before saving, but doesn't specify a caching pattern in this doc.
3. **Scope granularity per product.** The Platform MCP Server exposes 4 products. Should each product have a separate Auth0 API registration with product-specific scopes, or a single API with all scopes?
4. **Organization parameter.** Auth0 supports an optional `organization` parameter for multi-tenant M2M. Is LINQ's Auth0 setup single-tenant or multi-tenant? Does this affect Platform MCP Server design?
5. **Auth0 → AWS bridge.** The Platform MCP Server needs Auth0 tokens for its own identity layer and AWS STS credentials for multi-account AWS calls. The bridge between these two (Auth0 JWT → AssumeRoleWithWebIdentity, or Auth0 → RFC 8693 token exchange) is not covered by this source. Flagged as a gap.
