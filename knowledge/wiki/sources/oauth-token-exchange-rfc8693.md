---
title: "RFC 8693 — OAuth 2.0 Token Exchange"
kind: source
raw_path: "raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md"
url: "https://datatracker.ietf.org/doc/html/rfc8693"
author: "IETF"
fetched_at: 2026-05-04
tags: ["oauth", "rfc", "token-exchange", "delegation", "impersonation", "product:cross-cutting"]
entities:
  - "wiki/entities/oauth-token-exchange.md"
concepts: []
created: 2026-05-04
updated: 2026-05-04
---

## Why this source

Closes the OAuth token exchange gap identified in the Decision 0014 Phase A review. The Platform MCP Server needs a mechanism to allow agents (acting under their own identity) to make downstream API calls on behalf of a user or another service — the on-behalf-of pattern. RFC 8693 is the IETF standard for this.

## What it covers

The OAuth 2.0 Token Exchange extension grant type (`urn:ietf:params:oauth:grant-type:token-exchange`). Covers: request parameters (subject_token, actor_token, requested_token_type, resource, audience, scope), response parameters, impersonation vs. delegation semantic distinction, token type URIs, JWT delegation claims (`act`, `may_act`), normative processing requirements, and error handling.

## Key claims

- Grant type URI: `urn:ietf:params:oauth:grant-type:token-exchange`. Used as `grant_type` in a POST to the token endpoint. [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]
- `subject_token` (REQUIRED): represents the identity of the party on whose behalf the request is made. `subject_token_type` (REQUIRED): URI identifying the token format. [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]
- `actor_token` (OPTIONAL): represents the acting party's identity. If present, `actor_token_type` is REQUIRED; MUST NOT be included otherwise. [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]
- **Impersonation (on-behalf-of)**: only `subject_token` provided; issued token grants all rights the subject has; the client acts indistinguishably as the subject. [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]
- **Delegation**: both `subject_token` and `actor_token` provided; issued composite token shows that actor A acts on behalf of subject B while A retains distinct identity; `act` JWT claim records the delegation chain. [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]
- Response: `access_token` (the issued token — named for historical reasons, need not be an OAuth access token), `issued_token_type` (REQUIRED), `token_type` (`Bearer` or `N_A`), `expires_in` (RECOMMENDED). [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]
- No `refresh_token` is typically issued — token exchange is a one-time event, not linked to the input tokens. [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]
- Standard token type URIs: `urn:ietf:params:oauth:token-type:jwt`, `urn:ietf:params:oauth:token-type:access_token`, `urn:ietf:params:oauth:token-type:id_token`, SAML1, SAML2. [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]
- Scope, resource, and audience are cumulative — requested rights are the Cartesian product across all targets. `invalid_target` error when the AS cannot fulfill a multi-target request. [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]
- Token exchange has no impact on the validity of the subject or actor token (absent one-time-use semantics). Exchange does not create tight linkage between input and output tokens. [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md]

## Entities introduced

- [wiki/entities/oauth-token-exchange.md] — new entity: the RFC 8693 token exchange grant type, impersonation vs. delegation, and delegation chain claims.

## Open questions for LINQ

1. **Auth0 RFC 8693 support.** Does LINQ's Auth0 tenant support the token-exchange grant type? Auth0's standard docs focus on client credentials and authorization code flows. RFC 8693 support may require a custom Action or an enterprise feature.
2. **On-behalf-of for MCP server → product API calls.** The Platform MCP Server acts on behalf of the calling agent (which itself may be acting on behalf of a user). Does LINQ need full delegation chain tracking (`act` claims), or just impersonation?
3. **AWS integration path.** AWS STS `AssumeRoleWithWebIdentity` accepts a JWT (analogous to a `subject_token`) and issues STS credentials. This is related to but distinct from RFC 8693. The bridge between Auth0 JWTs and AWS STS credentials via this pattern is a gap.
4. **Token lifetime.** The spec recommends `expires_in` but does not mandate a specific lifetime. For the Platform MCP Server → product API call chain, what lifetime is appropriate for exchanged tokens?
