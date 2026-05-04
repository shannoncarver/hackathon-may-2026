# Role-pass memo: Security & IAM Engineer

**Reviewer:** general-purpose (Security & IAM lens)
**For:** Decision 0015 — Centralized Platform MCP Server
**Date:** 2026-05-04

## Findings

1. **Agent identity is well-modeled by Auth0 M2M, but the MCP server must enforce its own audience.** The Client Credentials grant produces a JWT with `iss`, `aud`, `sub`, `exp`, `iat`, and a `scope`/`permissions` claim ([wiki/entities/auth0-m2m.md](../../../../knowledge/wiki/entities/auth0-m2m.md)). The MCP server is a distinct OAuth 2.1 resource server and MUST validate `aud` matches its own canonical URI; the spec also forbids passing the agent's token through to downstream APIs ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)).
2. **MCP HTTP transports require RFC 9728 Protected Resource Metadata.** The MCP authorization spec mandates that an HTTP MCP server expose `/.well-known/oauth-protected-resource` and emit `WWW-Authenticate` on 401 ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)). Whether Auth0 itself supports RFC 9728 is unconfirmed in the wiki ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)) — but RFC 9728 is a property of the *resource server* (the MCP server), not of the AS, so LINQ can implement it in MCP regardless. RFC 8414 metadata at the AS is what would require Auth0.
3. **OBO has a canonical primitive (RFC 8693) and Auth0 support is not confirmed.** Token Exchange supports both impersonation (`subject_token` only) and delegation (`subject_token` + `actor_token`, with an `act` claim chain) ([wiki/entities/oauth-token-exchange.md](../../../../knowledge/wiki/entities/oauth-token-exchange.md)). The wiki explicitly flags Auth0 RFC 8693 support as unconfirmed and "may require a custom Action or enterprise feature" ([wiki/entities/oauth-token-exchange.md](../../../../knowledge/wiki/entities/oauth-token-exchange.md), [wiki/sources/oauth-token-exchange-rfc8693.md](../../../../knowledge/wiki/sources/oauth-token-exchange-rfc8693.md)).
4. **Token passthrough is forbidden by the MCP spec.** "MCP servers MUST NOT forward client tokens to upstream APIs … Upstream API calls require a separately-issued token from the upstream AS" ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)). This forces a re-issuance step at the MCP boundary; we cannot simply hand the agent's JWT to the product handler.
5. **Cross-account invocation has two viable shapes.** `sts:AssumeRole` with External ID is the multi-account pattern and protects against the Confused Deputy ([wiki/entities/sts-assume-role-external-id.md](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)). For invoke-only access to specific Lambdas, a Lambda resource-based policy is simpler and avoids the AssumeRole hop ([wiki/entities/lambda-resource-policy.md](../../../../knowledge/wiki/entities/lambda-resource-policy.md)).
6. **External ID semantics depend on whether product accounts are inside or outside the LINQ AWS Organization.** External ID is "**required**" for true third-party multi-tenant access and "optional" for intra-org cross-account ([wiki/entities/sts-assume-role-external-id.md](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)). Whether all LINQ product accounts share one AWS Organization is **[ASSUMED]** — unable to verify from the brief, though the brief's phrasing ("dedicated AWS account" per product) is consistent with one Org.
7. **STS sessions are temporary by design.** AssumeRole returns `AccessKeyId`/`SecretAccessKey`/`SessionToken`/`Expiration` ([wiki/entities/sts-assume-role-external-id.md](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)); default is 1h, max 12h. Caching strategy must respect `Expiration` and avoid clock-skew pinning.
8. **Auth0 issues 24h M2M tokens by default and there is no refresh token.** The MCP server itself must cache and re-fetch on expiry ([wiki/entities/auth0-m2m.md](../../../../knowledge/wiki/entities/auth0-m2m.md)).

## Risks

| # | Sev | Risk | Why | Mitigation |
|---|-----|------|-----|-----------|
| R1 | HIGH | **Tenant leakage at the handler.** A handler that derives `tenant_id` from anywhere except a verified claim/argument can return another tenant's row. | Handlers are written by 4+ product teams; defaults will drift. | Registry rejects handler entries lacking `tenantSourceClaim`; handler input contract makes `tenant_id` a required, validated argument; MCP injects it from the verified user JWT, not from agent-supplied input. |
| R2 | HIGH | **Confused Deputy across products.** A registry lookup error or tampered tool ID could route an agent's request through a role assumption into the wrong product account. | Centralized assumer with broad cross-account reach is the textbook Confused Deputy scenario ([wiki/entities/sts-assume-role-external-id.md](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)). | Per-product External ID on every cross-account trust policy, even intra-Org; pair with `aws:PrincipalOrgID` SCP guardrail; Access Analyzer enabled on every product account. |
| R3 | HIGH | **Token passthrough.** A naïve implementation forwards the agent's Auth0 JWT to product Lambdas, violating MCP spec and giving the product API the wrong audience. | Convenience: avoiding re-issuance is tempting. | Forbid in code review; MCP server re-issues a downstream identity (signed assertion or RFC 8693 exchange) and validates audience server-side ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)). |
| R4 | MED | **Auth0 RFC 8693 unsupported, OBO collapses to homemade signing.** Forces a custom Auth0 Action or a self-signed JWT bridge with weaker trust ceiling than a real STS. | Wiki flags Auth0 RFC 8693 as unconfirmed ([wiki/entities/oauth-token-exchange.md](../../../../knowledge/wiki/entities/oauth-token-exchange.md)). | Build the OBO primitive behind an internal interface (`IdentityBroker.exchange()`); v1 implementation can be Auth0 Action that mints a short-lived JWT with `act` claim, swappable to native RFC 8693 later. |
| R5 | MED | **STS session caching causes stale principal at audit time.** A cached 12h STS session signs a request whose Auth0 user-context JWT was issued seconds before — but auditing on AWS side sees only the role session name. | Caching is required for cost/latency; CloudTrail is per-call. | Embed `agent_sub`, `user_sub`, `request_id` in `RoleSessionName` and STS session tags; correlate with platform audit log on `request_id`. |
| R6 | MED | **MCP `aud` mis-binding.** If multiple agents share one Auth0 API audience, scope-based separation alone may not suffice. | Easy to ship if registry enforcement is loose. | One Auth0 API per MCP server URI; agents differ by `client_id` and `scope`/`permissions` claim ([wiki/entities/auth0-m2m.md](../../../../knowledge/wiki/entities/auth0-m2m.md)); MCP enforces RFC 8707 `resource` parameter binding ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)). |
| R7 | LOW | **External ID treated as a secret.** AWS doc is explicit it is *not* a secret ([wiki/entities/sts-assume-role-external-id.md](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)); over-securing it builds brittle infra and wastes vault rotation. | Common antipattern. | Document External ID as identifier, not credential; rotate only on compromise of the assumer principal, not on schedule. |
| R8 | LOW | **Lambda resource policy drift.** If we mix AssumeRole and resource-based policies arbitrarily, audit & rotation get bimodal. | Two patterns harder than one. | Default to AssumeRole; allow resource-based policy only for narrow patterns (single function, simple invoke) with explicit ADR-style justification ([wiki/entities/lambda-resource-policy.md](../../../../knowledge/wiki/entities/lambda-resource-policy.md)). |

## Recommendation

**Identity propagation: pick (a) RFC 8693 token exchange as the *contract*, with a v1 fallback implementation if Auth0 lacks native support.** The MCP server validates the agent's M2M JWT (issuer, audience, signature, `kid` pinning, scope/permissions), then exchanges it — together with the human user's verified token (forwarded by the agent in a separate header, audience-bound to the MCP server, **never** passed through downstream) — for a downstream identity token via an internal `IdentityBroker`. The broker's contract matches RFC 8693: `subject_token = user JWT`, `actor_token = agent JWT`, output is a short-lived (≤5 min) JWT with `sub = user_sub`, `act.sub = agent_client_id`, and `aud = <product-handler>`. If Auth0 supports RFC 8693, the broker is a thin proxy. If it does not — the wiki's flagged gap ([wiki/entities/oauth-token-exchange.md](../../../../knowledge/wiki/entities/oauth-token-exchange.md)) — the v1 broker is an Auth0 Action or in-process signer issuing a JWT with the same `act`-claim shape, signed by a Platform-owned key in AWS KMS. The on-the-wire contract is identical to a real RFC 8693 issue, so swapping the implementation is a code change, not a protocol change. I reject (b) raw signed assertion (lower trust ceiling, no upgrade path) and (c) forwarding the user's original Auth0 token (violates the MCP token-passthrough prohibition — [wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)).

**Authorization split: coarse-grained at MCP, fine-grained at handler.** The MCP server resolves `(agent_client_id, user_sub, tool_id)` against the registry and enforces: agent has `requiredScopes[]` in its M2M token; user has `requiredPermissions[]` in the Auth0 RBAC `permissions` claim; tool exists and is enabled. Handlers receive a downstream token plus an explicit, validated `tenant_id` argument and enforce row-level checks. The registry MUST require a `tenantSourceClaim` on every handler entry — a string naming the JWT claim from which tenant comes (`https://linq/tenant_id`, `org_id`, etc.). Registration without this field is rejected at submission time. The MCP server reads that claim from the user's verified token and injects it as a separate, signed argument; the agent cannot supply tenant directly. This is the schema-level lever that makes tenant leakage hard.

**Cross-account default: `sts:AssumeRole` with per-product External ID, plus AWS Org-scoped SCP guardrails.** Use AssumeRole as the default ([wiki/entities/sts-assume-role-external-id.md](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)) — it generalizes to non-Lambda resources (DynamoDB read, S3 read, Step Functions Describe) which v1 will need beyond the headline Lambda invocation. External IDs are mandatory even though product accounts are likely intra-Org **[ASSUMED]**; the cost is one DynamoDB column per product, the protection is full Confused Deputy coverage if a product later spins out into a separate Org or partner account. Layer `aws:PrincipalOrgID` in the trust policies and an SCP that prevents non-platform principals from being added to the trust policy. Drop to a Lambda resource-based policy ([wiki/entities/lambda-resource-policy.md](../../../../knowledge/wiki/entities/lambda-resource-policy.md)) only for narrowly-scoped invoke-only handlers, documented case by case. Cache STS sessions at session-name granularity (`{tool_id}/{user_sub}` truncated, or `{product}/{handler_family}` for shared sessions) for 50 min on a 1h session, refreshing 10 min before expiry; embed `request_id`, `user_sub`, `agent_client_id` in session tags so CloudTrail correlates to the platform audit record. Same-region invocation only in v1; PrivateLink and per-handler VPC are deferred — handlers run in product VPCs, MCP server reaches them over public AWS endpoints with TLS and IAM SigV4, which is sufficient for read-only internal traffic. v2 mutating handlers should re-evaluate PrivateLink.

## Open questions for Lead Architect

- **Are all 4 v1 product AWS accounts in one AWS Organization?** Guess if forced today: **yes**, given LINQ's "shared Platform Services account" framing — but the design uses per-product External IDs regardless, so this only affects the SCP layer.
- **Does Auth0 support RFC 9728 Protected Resource Metadata at the resource-server side, or do we self-host the `/.well-known/oauth-protected-resource` endpoint on the MCP server?** Guess if forced today: **MCP server hosts it**, AS metadata stays on Auth0 via RFC 8414. RFC 9728 is naturally a resource-server concern.
- **Does Auth0 support RFC 8693 natively (Enterprise feature) or only via a custom Action?** Guess if forced today: **Action-based v1**, swappable to native if/when LINQ upgrades. The wiki flags this as unconfirmed ([wiki/entities/oauth-token-exchange.md](../../../../knowledge/wiki/entities/oauth-token-exchange.md)).
- **Is the human user always present at the time of the agent call (interactive Claude Code), or does v1 also include long-running batch agents with no live user?** Guess if forced today: **interactive only in v1** — long-running batch needs a separate "delegation grant" pattern with explicit user pre-authorization, and we should defer it.
- **Does LINQ already have a normalized RBAC permission namespace across products, or do products each have their own permission grammar?** Guess if forced today: **per-product grammar today**, and the registry's `requiredPermissions[]` carries product-prefixed strings (`erp:read:user`, `lms:read:enrollment`) until normalization happens. Unable to verify from the brief.
- **Where does the agent obtain the human user's token?** The MCP spec forbids passthrough to *downstream*, but the agent presenting both its own and the user's token to the MCP server (as `subject_token`) is the standard OBO seam. Guess if forced today: **agent calls Auth0 with the user's session and gets a token audience-scoped to the MCP server**, then presents it alongside its M2M token in a `X-User-Token` header.

## Forced calls (from Phase A gaps)

- **Auth0 RFC 9728 support.**
  - *If supported at the AS:* still self-host the resource metadata document on the MCP server — RFC 9728 is the *resource server's* metadata, not the AS's. Auth0's role here is RFC 8414 (AS metadata) and RFC 7591 (DCR), both of which it supports per the wiki ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)).
  - *If unsupported at the AS for any reason:* MCP server publishes `/.well-known/oauth-protected-resource` listing Auth0 in `authorization_servers[]`, points clients at Auth0's existing `/.well-known/oauth-authorization-server`, and returns `WWW-Authenticate: Bearer resource_metadata="https://mcp.linq.../.well-known/oauth-protected-resource"` on 401. **We do not block on Auth0 RFC 9728 support — we own this endpoint.**

- **Auth0 RFC 8693 support.**
  - *If supported:* call `POST {auth0_domain}/oauth/token` with `grant_type=urn:ietf:params:oauth:grant-type:token-exchange`, `subject_token={user_jwt}`, `subject_token_type=urn:ietf:params:oauth:token-type:jwt`, `actor_token={agent_jwt}`, `audience={product_handler_audience}`, `scope={resolved_scopes}`. Cache the issued token for its full `expires_in`.
  - *If unsupported:* implement the broker as an **Auth0 Action triggered by client credentials with a custom flag** (or a small Platform-owned signer Lambda fronted by the MCP server using a KMS asymmetric key). Output is a JWT with `iss=https://identity.linq.platform`, `aud=<product_handler>`, `sub=<user_sub>`, `act.sub=<agent_client_id>`, `scope`, `permissions`, `tenant_id`, `exp` ≤ 5 min. The fallback's trust trade-off: the issued JWT's signing authority is Platform-owned, not Auth0; downstream handlers must trust the Platform signer's JWKS endpoint as well as Auth0's. Document this in the handler runtime SDK so it is explicit, not implicit.

- **AssumeRoleWithWebIdentity setup (concrete trust-policy sketch).** Register Auth0 as an OIDC provider in each product account (`https://{auth0_tenant}.auth0.com/`), thumbprint pinned. The MCP server exchanges the broker-issued JWT (or, if not using AssumeRoleWithWebIdentity, the agent JWT directly via standard AssumeRole) for STS credentials. Trust policy on the product-account role:

  ```json
  {
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "Federated": "arn:aws:iam::PRODUCT_ACCT:oidc-provider/AUTH0_DOMAIN" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "AUTH0_DOMAIN:aud":  "https://mcp.linq.platform",
          "AUTH0_DOMAIN:azp":  "<platform_mcp_client_id>"
        },
        "StringLike": {
          "AUTH0_DOMAIN:sub":  "platform-mcp-server@clients"
        }
      }
    }]
  }
  ```

  Session tag strategy: `sts:TagSession` on the AssumeRole call carries `tenant_id`, `user_sub`, `agent_client_id`, `request_id`. Tags are attribute-bound — handler IAM policies can reference `aws:PrincipalTag/tenant_id`, giving an in-IAM tenant guardrail layered under handler-level enforcement. **Recommendation: in v1, use the simpler `AssumeRole` with External ID rather than `AssumeRoleWithWebIdentity`** — the MCP server has its own AWS identity (IAM role in Platform Services account), so it does not need WebIdentity; reserve WebIdentity for later, if v2 wants to skip the MCP-server-as-AWS-principal hop.

- **External ID vs. Org trust: per-product External ID, layered with `aws:PrincipalOrgID` SCP.** Pick **External ID** as the primary mechanism. Failure mode it protects against: Confused Deputy across products if registry data is tampered, if a tool ID is mis-resolved, or if a product later moves out of the LINQ AWS Org ([wiki/entities/sts-assume-role-external-id.md](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)). Failure mode `aws:PrincipalOrgID` adds: prevents an attacker who somehow gets credentials to the Platform MCP role but is outside the Org from assuming product roles. IAM Identity Center is **not** the right tool here — it targets human SSO into AWS consoles, not service-to-service role assumption. External ID generation: the Platform MCP Server generates a per-product 32-char random string at onboarding, stores it in the DynamoDB Handler Registry's product table, and surfaces it to the product team for inclusion in their trust policy. Document explicitly that External IDs are identifiers, not secrets ([wiki/entities/sts-assume-role-external-id.md](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)).

## Audit log schema

Single per-request record, written from the MCP server to a Platform-Services-account log group with object-lock-equivalent retention (e.g., CloudWatch Logs → Kinesis Firehose → S3 with Object Lock, 7-year retention recommended by SOC 2 norms; 1-year acceptable for v1 with a documented upgrade path).

```json
{
  "request_id":         "uuid-v4",
  "ts":                 "2026-05-04T18:23:11.482Z",
  "agent": {
    "client_id":        "auth0-client-id",
    "scope":            ["erp:read"],
    "token_jti":        "auth0-jti"
  },
  "user": {
    "sub":              "auth0|abc123",
    "email":            "engineer@linq.com",
    "permissions":      ["erp:read:user"],
    "token_jti":        "auth0-jti-user"
  },
  "tool": {
    "id":               "erp.checkUserAccess",
    "version":          "1.4.0"
  },
  "handler": {
    "product":          "erp",
    "arn":              "arn:aws:lambda:us-east-1:...:function:erp-checkUserAccess:prod",
    "assume_role_arn":  "arn:aws:iam::...:role/PlatformMCPInvoke",
    "session_name":     "req-uuid-trunc"
  },
  "tenant_id":          "tenant-9912",
  "decision":           "allow",
  "denial_reason":      null,
  "downstream_status":  200,
  "latency_ms": {
    "auth0_validate":   8,
    "registry_lookup":  4,
    "sts_assume":       42,
    "handler_invoke":   118,
    "total":            172
  },
  "error":              null
}
```

Single record covers: agent → user → tool → handler → tenant → outcome → latency. Immutable retention via S3 Object Lock. CloudTrail in each product account independently records the AssumeRole and Lambda invoke, correlated by `request_id` embedded in `RoleSessionName`/session tags.

## Forward-compat for v2 writes and compliance

Two decisions, if made wrong now, will block later:

1. **OBO primitive shape — make the `IdentityBroker` interface RFC 8693-shaped from day one, even if v1 implements it via Auth0 Action.** If v1 ships with raw signed assertions or token passthrough, v2 mutating handlers will need write authorization and non-repudiation, which require a real `act`-claim chain and a token-issuance audit trail. Retrofitting that across 40–200 handlers and product teams is the change that doesn't happen.
2. **Tenant binding at the registry, not the handler — make `tenantSourceClaim` a registration-time required field.** SOC 2 CC6.1 (logical access) and HIPAA's minimum-necessary principle both turn on demonstrable per-tenant access control. If handlers self-derive tenant in v1, the platform cannot prove tenant isolation; v2 compliance scope expands to auditing every handler implementation. Registry-enforced `tenantSourceClaim` keeps the proof at the platform layer where the audit can land.

A third honorable mention: **default to AssumeRole, not Lambda resource-based policies.** Resource-based policies don't support External ID and don't generalize beyond Lambda ([wiki/entities/lambda-resource-policy.md](../../../../knowledge/wiki/entities/lambda-resource-policy.md)); v2 Step Functions, EventBridge, and DynamoDB-direct handlers will need AssumeRole anyway, and a mixed pattern doubles audit surface.
