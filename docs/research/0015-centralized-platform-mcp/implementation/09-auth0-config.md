# Implementation 09 — Auth0 configuration

**Status:** Implementation plan (Phase B). Implements [Decision 0015](../../../decisions/0015-centralized-platform-mcp.md).
**Owner:** 12-eng-security-iam (Security & IAM Engineer lens)
**Date:** 2026-05-04
**Effort estimate:** `2 d [ASSUMED]` — dependent on Identity team availability; flagged.

## 1. Overview

Auth0 is the identity provider for both human SSO into LINQ products and Machine-to-Machine (M2M) identity for internal AI agents — Claude Code, internal dev tools, and ops dashboards — calling the Platform MCP Server. This artifact specifies the Auth0 configuration the V1 POC needs: a single API resource for the MCP server URI, a small set of M2M applications (one per service-identity class — never per handler), an RBAC permission grammar shaped per-product per-action for human users, and the dev-tenant test users the POC exercises against. The configuration does **not** include an Auth0 Action or Hook for OBO token minting — V1 implements OBO via Path C ([Platform-owned KMS-signed IdentityBroker](./05-identity-broker.md)), which means Auth0 has no token-exchange responsibility on the hot path. Coordination with the LINQ Identity team is a **parallel workstream** that must not block the rest of the POC build; M1 proceeds against a dev-tenant configuration even if the production tenant sign-off lands later. This artifact resolves [Open Question Q2](../05-open-questions.md) under cross-cutting decision **CC-5** by **assuming an Auth0 entitlement of ≥ 10 M2M applications [ASSUMED]** — V1 needs 3–5, M2 keeps headroom for ~10.

## 2. Concrete artifacts

### 2.1 Auth0 API resource — Terraform-style configuration block

A single Auth0 API represents the Platform MCP Server. The identifier is the canonical MCP server URI (`https://mcp.linq.platform`); every M2M token issued for that audience is bound to this resource and cannot be replayed against any other Auth0-protected API. RFC 8707 [Resource Indicators](https://www.rfc-editor.org/rfc/rfc8707.html) is enforced — the MCP server validates the `aud` claim against its own canonical URI and rejects any token whose audience does not match exactly. RS256 is the signing algorithm (Auth0 default for new APIs; HS256 is rejected because the MCP server must verify with a public key, not a shared secret).

```hcl
# infrastructure/auth0/api-mcp.tf
# Provider: hashicorp/auth0 (community provider, used for IaC parity with CFN).

resource "auth0_resource_server" "mcp_platform" {
  name        = "LINQ Platform MCP Server"
  identifier  = "https://mcp.linq.platform" # canonical URI; MUST match the `aud` the MCP server validates.
  signing_alg = "RS256"                     # public-key verification only — no shared secrets.

  # Token lifetimes.
  # 24 h is Auth0's M2M default. The MCP server caches the M2M token for ~23 h
  # (knowledge/wiki/entities/auth0-m2m.md). Shortening this here would force
  # re-issue churn without security benefit — Auth0 M2M tokens are not refreshable.
  token_lifetime         = 86400 # 24 h — matches knowledge/wiki/entities/auth0-m2m.md cache plan.
  token_lifetime_for_web = 7200  # 2 h — irrelevant in V1 (no browser clients), set defensively.

  # Per-handler permissions are enabled so M2 can attach scopes here once registry-driven
  # per-product scopes are split out. V1 carries a single `mcp:read` placeholder.
  enforce_policies                                = true
  token_dialect                                   = "access_token_authz"
  skip_consent_for_verifiable_first_party_clients = true
  allow_offline_access                            = false

  # V1 single broad scope. Failure mode this leaves open: any agent with `mcp:read`
  # can call any read-only tool. Mitigation: registry-side `requiredPermissions[]`
  # gating per handler — the MCP server enforces the human user's RBAC permission
  # set, not just the agent scope. Splits to per-product scopes in M2 (§2.6 migration).
  scopes {
    value       = "mcp:read"
    description = "Invoke any read-only tool exposed by the Platform MCP Server (V1 placeholder)."
  }
}
```

The MCP server validates `iss`, `aud`, `exp`, `iat`, signature, and `kid` on every M2M token presentation, per [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html) §3 and [`mcp-authorization`](../../../../knowledge/wiki/entities/mcp-authorization.md) — the Auth0 JWKS endpoint at `https://{auth0_tenant}/.well-known/jwks.json` supplies the public keys. No Auth0 RFC 9728 dependency: the MCP server self-hosts `/.well-known/oauth-protected-resource` ([`03-mcp-server.md`](./03-mcp-server.md)) and points at this API resource via `authorization_servers[]`. This **closes R5 by design** at the protocol level — Auth0's role here is RFC 8414 (AS metadata) and JWKS hosting, both of which Auth0 supports natively.

### 2.2 M2M application — `claude-code-internal` (V1 agent identity)

`claude-code-internal` is the V1 M2M application — the Auth0 client the Claude Code agent runtime presents when calling the Platform MCP Server. Per the **LOCKED** platform contract from [Decision 0015](../../../decisions/0015-centralized-platform-mcp.md) consequences and **R6** in the risks register, **one M2M application per service-identity class** — never per handler, never per agent session. Splitting per handler would make Auth0 cost linear in handler count and break the sub-linear-cost claim ([R6](../03-risks-register.md#r6--auth0-m2m-cost-explosion)).

```hcl
# infrastructure/auth0/client-claude-code-internal.tf

resource "auth0_client" "claude_code_internal" {
  name                       = "claude-code-internal"
  description                = "Internal Claude Code agent — calls Platform MCP Server. One M2M app for this service-identity class."
  app_type                   = "non_interactive" # M2M.
  is_first_party             = true
  oidc_conformant            = true
  cross_origin_authentication = false
  grant_types                = ["client_credentials"] # M2M only — no auth code, no implicit, no password.
  token_endpoint_auth_method = "client_secret_post"

  # Refresh tokens not applicable to M2M client_credentials grant.
  jwt_configuration {
    alg                 = "RS256"
    lifetime_in_seconds = 86400
  }
}

# Grant `mcp:read` on the MCP API resource.
# Failure mode prevented: missing this grant means the agent can authenticate to Auth0
# but its tokens carry no `scope` claim, and the MCP server rejects on scope check.
resource "auth0_client_grant" "claude_code_internal_mcp" {
  client_id = auth0_client.claude_code_internal.id
  audience  = auth0_resource_server.mcp_platform.identifier
  scopes    = ["mcp:read"]
}
```

**Placeholder M2M applications for additional service-identity classes (provisioned alongside `claude-code-internal` so the M2M-app cap is established in V1, not stretched in M2).** Each is one M2M app representing one *class of service*, not one instance, not one handler:

| Client name | Service identity class | V1 status | Rationale |
|---|---|---|---|
| `claude-code-internal` | Interactive developer-agent runtime (Claude Code) | **Active in V1** | The POC's primary agent identity. |
| `internal-dev-tools` | Internal developer-tooling agents (CLI scripts, automation) | Provisioned, dormant | Reserved for the second product onboard (M2). |
| `ops-dashboards` | Read-only ops dashboards calling MCP for telemetry | Provisioned, dormant | Reserved for ops view of audit data, M2. |
| `support-copilot` | Support-team-facing AI copilot | Reserved | Spec only — not provisioned until support team commits. |
| `release-automation` | Release-pipeline agents (e.g., changelog summarizer) | Reserved | Spec only — not provisioned until pipeline owner commits. |

V1 ships with the first three provisioned (3 M2M apps active or dormant); the last two are documented spec only. Total under cap of ≥ 10 entitlement [ASSUMED]. The platform team audits the M2M-app inventory **quarterly** ([`role-passes/cost-reliability.md`](../role-passes/cost-reliability.md)) and rejects any per-handler M2M app at the registry-write CI gate ([`04-registry.md`](./04-registry.md)).

### 2.3 RBAC permissions — per-product per-action grammar

Human users authenticate via Auth0 SSO and carry a `permissions` claim populated by Auth0 RBAC. The grammar is **`<product>:<action>:<resource>`** — three colon-separated segments, all lower-case, no spaces, no wildcards. The product slug matches the canonical LINQ product list ([Decision 0014 / Decision 0013](../../../decisions/0013-karpathy-wiki-pattern.md)). The action is a verb (`read` in V1; `write`, `delete` reserved for later). The resource is a noun representing the data class.

This is the V1 grammar [ASSUMED — Q11 disposition; per-product grammar today, normalization deferred] per [`role-passes/security-iam.md`](../role-passes/security-iam.md) open question #5.

```hcl
# infrastructure/auth0/rbac-permissions.tf

# All permissions hang off the MCP API resource. The MCP server reads the user's
# `permissions[]` claim from their Auth0 token and matches against the registry's
# `requiredPermissions[]` per-handler. Failure mode prevented: a missing permission
# returns a structured 403 with `denial_reason: "missing_permission"` in the audit log.

resource "auth0_resource_server_scope" "erp_read_user" {
  resource_server_identifier = auth0_resource_server.mcp_platform.identifier
  scope                      = "erp:read:user"
  description                = "Read ERP user profile records (handler erp.checkUserAccess)."
}

resource "auth0_resource_server_scope" "erp_read_tenant" {
  resource_server_identifier = auth0_resource_server.mcp_platform.identifier
  scope                      = "erp:read:tenant"
  description                = "Read ERP tenant configuration records."
}

# Future per-product samples (provisioned per product onboarding, not in V1):
#   crm:read:contact   — Read CRM contact records.
#   crm:read:account   — Read CRM account records.
#   lms:read:enrollment — Read LMS enrollment records.
#   lms:read:course    — Read LMS course records.
```

V1 only ships the `erp:*` permissions because the V1 POC handler is `erp.checkUserAccess` ([CC-4](../../../../../../scarver/.claude/plans/implementation-plan-centralized-dapper-stearns.md), per the chosen sample product). Per-product onboarding adds a new permission set per product without touching existing ones — **additive**, not migrative.

**Authorization split** — the MCP server validates that the agent holds the API scope (`mcp:read`) **and** the human user holds the per-handler permission (`erp:read:user`). Both checks must pass. Tenant-scope enforcement at the handler layer rounds this out ([`04-registry.md`](./04-registry.md), [`07-poc-handler.md`](./07-poc-handler.md)) — the MCP server reads tenant from the user's verified token and injects it as a signed argument ([R1](../03-risks-register.md#r1--tenant-leakage-at-the-handler)).

### 2.4 Action / Hook — NOT NEEDED in V1

V1 deliberately **does not** install an Auth0 Action or Hook to mint OBO tokens. Path C ([`05-identity-broker.md`](./05-identity-broker.md)) places token issuance in a Platform-owned IdentityBroker Lambda signed by an AWS KMS asymmetric key; Auth0's only role is issuing the agent's M2M token and the human user's session token. This keeps the Auth0-side configuration small (one API resource, a handful of clients, a permission table) and bounds the Auth0 risk surface to identity issuance — not token-exchange logic.

If LINQ later upgrades to Auth0 RFC 8693 native token-exchange (currently in early access on Auth0 Enterprise as of 2026-05-04 — see [`05-identity-broker.md` §8](./05-identity-broker.md)), the migration is local to the IdentityBroker Lambda. The Auth0 configuration in this artifact does not change; an Action is added only if the migration explicitly requires custom claim post-processing, which the RFC 8693 grant alone does not.

### 2.5 Test users in dev tenant for the POC

The POC operates against an Auth0 **dev tenant** (separate from production); no production identities are needed for M1. Three test users cover the V1 access matrix. All values are anonymized and illustrative; real Auth0 user IDs are provisioned by the Identity team.

| Display name | Auth0 `sub` (illustrative) | Email (anonymized) | RBAC permissions | POC role |
|---|---|---|---|---|
| Alice Engineer | `auth0\|poc-test-alice` | `alice@dev.linq.test` | `erp:read:user`, `erp:read:tenant` | Default happy-path user — full V1 read. |
| Bob Engineer | `auth0\|poc-test-bob`   | `bob@dev.linq.test`   | (none)                                  | Negative-path user — exercises the 403 denial path on missing permission. |
| Carol Engineer | `auth0\|poc-test-carol` | `carol@dev.linq.test` | `erp:read:user` (tenant restricted via custom claim `https://linq/tenant_id = "tenant-9912"`) | Tenant-scope enforcement test (per [R1](../03-risks-register.md#r1--tenant-leakage-at-the-handler)) — agent must not be able to read tenants other than `tenant-9912` on this user's behalf. |

The `tenant_id` claim is a custom Auth0 user metadata claim namespaced as `https://linq/tenant_id`, surfaced in tokens by an Auth0 Action on the **Login** flow (the only Auth0-side Action in V1, and it touches only user-token shape — never agent tokens, never OBO). Snippet:

```js
// auth0/actions/login/add-tenant-claim.js
// Trigger: post-login.
// Purpose: surface user-metadata `tenant_id` as a namespaced claim so the MCP server can
// read it from the verified user JWT and inject it as a signed argument to handlers.
// Failure mode prevented: tenant leakage if a user's tenant binding lives outside the verified token (R1).
exports.onExecutePostLogin = async (event, api) => {
  const tenantId = event.user.app_metadata?.tenant_id;
  if (tenantId) {
    api.idToken.setCustomClaim("https://linq/tenant_id", tenantId);
    api.accessToken.setCustomClaim("https://linq/tenant_id", tenantId);
  }
};
```

This Action is not for OBO and does not mint a downstream JWT. It only reshapes the user's own token at login. Path C remains the OBO seam.

### 2.6 Coordination protocol with the LINQ Identity team — RACI

Auth0 configuration changes touch a tenant the Identity team owns. The platform team cannot ship configuration directly to the production tenant without Identity team review. To keep V1 unblocked, the platform team operates on a **dev tenant** owned by the platform team (or a sandbox project under the Identity team's umbrella) and produces a **production-tenant change request** for Identity to apply at M1 cutover.

| Activity | Platform team (12-eng-security-iam) | Identity team | Hackathon Coordinator |
|---|---|---|---|
| Author `infrastructure/auth0/*.tf` against dev tenant | **R**, **A** | C | I |
| Provision API resource + M2M apps in dev tenant | **R**, **A** | C | I |
| Issue dev-tenant test-user credentials | C | **R**, **A** | I |
| Author production-tenant change request (PR or ticket) | **R**, **A** | C | I |
| Review production-tenant change request | C | **R**, **A** | I |
| Apply production-tenant changes | I | **R**, **A** | I |
| Quarterly M2M app inventory audit | **R**, **A** | C | I |
| Tenant rollback (e.g., revoke a leaked client secret) | C | **R**, **A** | I |

(R = responsible, A = accountable, C = consulted, I = informed.)

**Parallel workstream gate.** M1 cannot block on Identity-team production sign-off; the POC build proceeds on the dev tenant, demos against the dev tenant, and only the production cutover (M2 onward) requires the production tenant. **Failure mode prevented:** an Identity-team scheduling conflict cannot stall the demo if the dev tenant is ready and the change request is in queue.

### 2.7 Migration plan for V2 — split `mcp:read` into per-product scopes

V1 ships the placeholder `mcp:read` scope to keep the Auth0 configuration tractable; per-product scopes split out in M2 once the registry has multiple products. The migration is additive and non-breaking — agents holding `mcp:read` continue to function during the transition.

1. **Add per-product scopes to the API resource.** New `auth0_resource_server_scope` entries: `mcp:read:erp`, `mcp:read:crm`, `mcp:read:lms`, `mcp:read:bsd`, etc. — one per product slug from the canonical list. `mcp:read` remains, marked deprecated in its description.
2. **Update each M2M `auth0_client_grant`.** Add the appropriate per-product scope to each agent's grant. `claude-code-internal` likely holds **all** per-product scopes (cross-product agent); narrower agents (e.g., `support-copilot`) hold only the products they need.
3. **MCP-server scope check changes.** The registry's per-handler `requiredScopes[]` shifts from `["mcp:read"]` to `["mcp:read:<product>"]`. The MCP server's scope validator accepts either the broad scope or the per-product scope during the transition window.
4. **Deprecation window.** Agents migrate their own grants product by product over a documented window (suggest 30 days). After the window closes, the broad `mcp:read` grant is removed from each agent's `auth0_client_grant`. The scope itself stays in the API resource definition until the last grant is gone.
5. **Audit-log assertion.** During the window, the audit log captures both `agent.scope` and the resolved `requiredScopes`; reconciliation queries identify any agent still relying on the broad scope.

The migration is bounded to Auth0 IaC changes and a one-line predicate update on the MCP server. **No handler changes** — handlers do not see the agent's M2M scope; they receive the IdentityBroker JWT, whose `scope` claim is independent of the M2M scope.

## 3. Acceptance criteria

Observable signals — every criterion is testable via either the Auth0 Management API, a token issuance flow, or the audit log.

- **AC-A0-1.** A `client_credentials` POST to Auth0's `/oauth/token` with `client_id=claude-code-internal`, the client secret, and `audience=https://mcp.linq.platform` returns a JWT whose `aud` claim equals `"https://mcp.linq.platform"` exactly, `iss` is the dev tenant's issuer URL, `azp = claude-code-internal`'s client ID, and `scope` includes `mcp:read`. Algorithm in the `alg` header is `RS256`.
- **AC-A0-2.** The MCP server validates that token end-to-end against the dev tenant's JWKS endpoint (`https://{auth0_tenant}/.well-known/jwks.json`) and accepts. A token issued for any other audience (e.g., `https://example.com`) is **rejected** with `WWW-Authenticate: Bearer error="invalid_token"`.
- **AC-A0-3.** Per-handler RBAC enforcement. A request from `claude-code-internal` invoking `erp.checkUserAccess` on behalf of **Alice** (who holds `erp:read:user`) succeeds. The same request on behalf of **Bob** (no permissions) returns 403 with `denial_reason: "missing_permission"` in the audit record.
- **AC-A0-4.** Tenant-scope enforcement via the post-login Action. **Carol's** access token contains `https://linq/tenant_id = "tenant-9912"`. A request invoked on her behalf with `args.tenantId = "tenant-other"` (or any tenant other than `tenant-9912`) is **rejected** at the MCP server before invoking the handler, with `denial_reason: "tenant_scope_violation"`.
- **AC-A0-5.** RFC 8707 enforcement. A token issuance request that omits the `audience` parameter, or supplies an audience the client is not granted, returns an Auth0 `access_denied` error and never reaches the MCP server.
- **AC-A0-6.** M2M-app inventory. The Auth0 Management API `GET /api/v2/clients?app_type=non_interactive` returns no more than **5** M2M applications under the platform-team tag in V1. A quarterly audit fails the build if any per-handler M2M app has been added.
- **AC-A0-7.** Identity-team sign-off captured in the V1 cutover PR. The PR description references the Identity-team review ticket (Jira / change-request system) and the Identity-team approver name. Failure to attach this gates merge to `main`.

## 4. Effort estimate

`2 d [ASSUMED]` — 1 day to author the Terraform and apply against the dev tenant; 1 day to coordinate the production-tenant change request, validate test users, and run AC-A0-1 through AC-A0-6 end-to-end against the dev tenant. **Dependent on Identity team availability — flag.** If the Identity team requires more than one round of review on the production change request, that delay is outside the platform team's critical path and does not block M1 (the dev tenant covers M1 demos).

## 5. Open questions

- **Q2 — Auth0 tier and M2M entitlement.** **V1 disposition: assume ≥ 10 M2M apps available [ASSUMED]** per **CC-5**. V1 needs 3 active + 2 dormant + 2 reserved = 7. If LINQ's Auth0 plan caps M2M apps below 10, the Reserved tier collapses (drop `support-copilot` and `release-automation` from §2.2 until they have committed owners). **Confirm with Identity team during Phase B coordination.** Failure mode if entitlement is materially lower (say, 5): no immediate V1 impact (V1 needs 3 active), but M2 expansion to a fourth service identity is gated on entitlement increase.
- **Q7 — Long-lived M2M client per agent type vs. short-lived per-session client.** **Forced-today guess: long-lived per agent type** (per [`role-passes/security-iam.md`](../role-passes/security-iam.md) open question — the proposed answer is "long-lived" because Dynamic Client Registration is overkill for an internal-only roster, and per-session clients balloon the Auth0 client count with no auth benefit). **V1 disposition:** ship long-lived per-agent-type — a fresh M2M token is issued per Lambda cold start and cached for ~23 h, well below Auth0's 24 h M2M token lifetime ([`auth0-m2m`](../../../../knowledge/wiki/entities/auth0-m2m.md)). Re-evaluate at M2 if any agent surfaces multi-tenant or cross-trust concerns.
- **Q11 — RBAC permission grammar normalization across products.** **Forced-today guess: per-product grammar today** (`erp:read:user`, `lms:read:enrollment`) per [`role-passes/security-iam.md`](../role-passes/security-iam.md) open question #5. Normalization across products (e.g., a unified `linq:read:user` regardless of source product) is deferred until Identity governance is in place. **V1 disposition:** product-prefixed strings as defined in §2.3.

## 6. Cross-references

- [`role-passes/security-iam.md`](../role-passes/security-iam.md) — original Auth0 patterns, MCP `aud` enforcement, audit-log schema with `agent.client_id` and `user.permissions`.
- [`role-passes/mcp-integration.md`](../role-passes/mcp-integration.md) — RFC 8707 `resource` parameter enforcement, token-passthrough prohibition, M2M-vs-per-user OAuth distinction from ADR 0008.
- [`05-identity-broker.md`](./05-identity-broker.md) — Path C IdentityBroker; consumer of the M2M token issued by this Auth0 configuration.
- [`03-mcp-server.md`](./03-mcp-server.md) — JWT validation pipeline that consumes the Auth0 JWKS and enforces `aud` / `iss` / `kid`.
- [`04-registry.md`](./04-registry.md) — registry's `requiredScopes[]` and `requiredPermissions[]` fields validated against this Auth0 config.
- [`03-risks-register.md`](../03-risks-register.md) — R6 (M2M cost), R19 (`aud` mis-binding) mitigations.
- [`05-open-questions.md`](../05-open-questions.md) — Q2 (M2M entitlement), Q7 (long-lived M2M), Q11 (RBAC grammar).
- [Decision 0015](../../../decisions/0015-centralized-platform-mcp.md) — binding ADR.
- [Decision 0008](../../../decisions/0008-mcp-connectors.md) — per-user OAuth pattern (Atlassian) that coexists with this M2M-broker pattern.
- [`auth0-m2m`](../../../../knowledge/wiki/entities/auth0-m2m.md) — Client Credentials grant, 24 h token lifetime, no refresh, cache plan.
- [`mcp-authorization`](../../../../knowledge/wiki/entities/mcp-authorization.md) — MCP 2025-06-18 authorization spec, RFC 9728 / 8414 / 8707 obligations.
- [Auth0 Client Credentials Flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow) — vendor docs.
- [Auth0 RBAC](https://auth0.com/docs/manage-users/access-control/rbac) — vendor docs.
- [Auth0 APIs (Resource Servers)](https://auth0.com/docs/get-started/apis) — vendor docs.
- [Auth0 Actions — Login flow](https://auth0.com/docs/customize/actions/flows-and-triggers/login-flow) — vendor docs.
- [RFC 8707 — Resource Indicators for OAuth 2.0](https://www.rfc-editor.org/rfc/rfc8707.html).
- [RFC 8725 — JSON Web Token Best Current Practices](https://www.rfc-editor.org/rfc/rfc8725.html).
- [RFC 8414 — OAuth 2.0 Authorization Server Metadata](https://www.rfc-editor.org/rfc/rfc8414.html).

## 7. Risks protected against

- **R6 — Auth0 M2M cost explosion.** Mitigated by the **one M2M app per service-identity class** rule encoded in §2.2: V1 ships 3 active + 2 dormant under a ≥ 10 entitlement [ASSUMED]; per-handler M2M apps are forbidden by platform contract and rejected at the registry-write CI gate ([`04-registry.md`](./04-registry.md)). The quarterly inventory audit (AC-A0-6) keeps the cap from drifting.
- **R19 — MCP `aud` mis-binding.** Mitigated by the **single Auth0 API per MCP URI** rule in §2.1: the API identifier is `https://mcp.linq.platform`; agents differ by `client_id` and `scope`/`permissions` claim, never by audience; the MCP server enforces RFC 8707 `resource` parameter binding on every token (AC-A0-2, AC-A0-5). A token issued for any audience other than `https://mcp.linq.platform` is rejected before any handler dispatch.
