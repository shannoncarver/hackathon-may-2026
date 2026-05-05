# Implementation 06 — Cross-account dispatch (AssumeRole + External ID + PrincipalOrgID)

**Status:** Implementation plan (Phase B). Implements [Decision 0015](../../../decisions/0015-centralized-platform-mcp.md).
**Owner:** 12-eng-security-iam (Security & IAM Engineer lens)
**Date:** 2026-05-04
**Effort estimate:** `3 d [ASSUMED]`

## 1. Overview

The Platform MCP Server reaches each product account by calling `sts:AssumeRole` against a per-product `PlatformMcpInvoker` role whose trust policy layers two independent conditions — a per-product External ID and `aws:PrincipalOrgID` — and never substitutes one for the other. External ID closes the Confused Deputy class of attacks across products under registry tampering, tool-ID mis-resolution, or future product spin-out into a separate AWS Organization; `aws:PrincipalOrgID` adds an Organization-scoped guardrail so a leaked Platform principal outside the LINQ Org cannot assume any product role. V1 deliberately uses standard `AssumeRole`, **not** `AssumeRoleWithWebIdentity`, because the MCP Server already holds its own AWS principal in the Platform Services account — WebIdentity buys complexity without buying isolation. The dispatcher caches STS sessions in-process to keep the warm path off the STS call rate, and tags every session with `tenant_id`, `user_sub`, `agent_client_id`, and `request_id` so CloudTrail per-product correlates back to the Platform audit log on `request_id`. This artifact resolves [Open Question Q3](../05-open-questions.md) per cross-cutting decision **CC-5** (all four V1 product accounts share one AWS Organization, `[ASSUMED]`).

## 2. Concrete artifacts

### 2.1 `PlatformMcpInvoker` trust policy — CFN snippet

The trust policy lives in **each product account's** nested stack `07-product-handler-trust`, deployed by the product team via CloudFormation StackSets targeting their own account (StackSet target lives in the Platform Services account; per-account roles are created in-product). The platform team owns the template; the product team applies it. This is the single artifact a product team must accept to onboard.

```yaml
# infrastructure/07-product-handler-trust/template.yaml
# Deployed in the product account. One stack instance per product.
AWSTemplateFormatVersion: "2010-09-09"
Description: PlatformMcpInvoker cross-account role. Trusts the Platform MCP Server only.

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, stage, prod]
  PlatformAccountId:
    Type: String
    Description: AWS account ID of the Platform Services account.
    AllowedPattern: "^[0-9]{12}$"
  PlatformMcpServerRoleName:
    Type: String
    Default: PlatformMcpServer
    Description: IAM role name in the Platform account that the MCP Server Lambda assumes at runtime.
  ExternalId:
    Type: String
    Description: |
      Per-product External ID issued by the Platform team at onboarding (32 chars,
      base32). Identifier, not credential — see §2.2 and R20. Stored in the registry's
      product table; surfaced to the product team for inclusion here.
    AllowedPattern: "^[A-Z2-7]{32}$"
    NoEcho: false  # Per AWS guidance, External ID is not a secret.
  LinqOrgId:
    Type: String
    Description: AWS Organizations ID for the LINQ Org (o-xxxxxxxxxx).
    AllowedPattern: "^o-[a-z0-9]{10,32}$"
  ProductSlug:
    Type: String
    Description: Canonical product slug, e.g. erp, crm, lms. Used in role name + tags.

Resources:

  PlatformMcpInvokerRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub "PlatformMcpInvoker-${ProductSlug}-${Environment}"
      Description: !Sub |
        Cross-account role assumed by the Platform MCP Server to invoke ${ProductSlug}
        handlers. Trust requires both ExternalId AND aws:PrincipalOrgID — layered, not
        substituted.
      MaxSessionDuration: 3600  # 1 hour. STS cache uses ~50 min effective TTL (§2.3).
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Sid: PlatformMcpServerAssume
            Effect: Allow
            Principal:
              # Single named principal in the Platform account. No wildcards.
              # Failure mode prevented: any other Platform-account role (e.g. an admin
              # role compromised in a parallel incident) cannot assume this role.
              AWS: !Sub "arn:aws:iam::${PlatformAccountId}:role/${PlatformMcpServerRoleName}"
            Action:
              - sts:AssumeRole
              - sts:TagSession  # Required to attach session tags (§2.5).
            Condition:
              StringEquals:
                # CONDITION 1 — Per-product External ID.
                # Failure mode prevented: Confused Deputy across products. Even if the
                # Platform principal is correctly identified, a registry tampering or
                # tool-ID mis-resolution that routes a request to product B with product
                # A's External ID fails here. AWS requires the assumer to pass
                # ExternalId in the AssumeRole call; the role only grants the trust if
                # the value matches. See
                # https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user_externalid.html.
                "sts:ExternalId": !Ref ExternalId
                # CONDITION 2 — AWS Organizations boundary.
                # Failure mode prevented: a leaked Platform principal outside the LINQ
                # Organization (e.g. a future spin-out account, a partner integration
                # that briefly held the principal) cannot assume product roles. This is
                # additive defense; it does NOT replace ExternalId. See
                # https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-principalorgid.
                "aws:PrincipalOrgID": !Ref LinqOrgId
              # Defense in depth — pin transport + signing.
              Bool:
                "aws:SecureTransport": "true"
      Tags:
        - Key: linq:product
          Value: !Ref ProductSlug
        - Key: linq:owner
          Value: platform-mcp
        - Key: linq:environment
          Value: !Ref Environment

  # Permissions policy — handler invocation only. Read-only V1.
  # The set of resources is product-specific; this excerpt shows the Lambda
  # adapter case (§2.4). ECS RunTask + SFN StartSyncExecution variants ship in M2.
  PlatformMcpInvokerPolicy:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: invoke-handlers
      Roles: [!Ref PlatformMcpInvokerRole]
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Sid: InvokeProductHandlers
            Effect: Allow
            Action: "lambda:InvokeFunction"
            # Tightened by the product team's handler ARNs. Wildcard is acceptable
            # here only because the product account itself is the trust boundary —
            # AWS Org SCP (§2.6) prevents cross-product invocation paths.
            Resource: !Sub "arn:aws:lambda:*:${AWS::AccountId}:function:${ProductSlug}-*"
            Condition:
              # The session tag injected by sts:TagSession at AssumeRole time
              # (§2.5) is propagated. Handler-side IAM may reference
              # aws:PrincipalTag/tenant_id for an in-IAM tenant guardrail layered
              # under handler-level row checks.
              StringNotEquals:
                "aws:PrincipalTag/tenant_id": ""

Outputs:
  PlatformMcpInvokerRoleArn:
    Value: !GetAtt PlatformMcpInvokerRole.Arn
    Description: ARN registered in the Handler Registry's product table.
    Export:
      Name: !Sub "${AWS::StackName}-RoleArn"
```

The permissions policy stays narrow on purpose. Adding a new handler substrate (ECS RunTask, Step Functions StartSyncExecution) is a policy change reviewed by the platform team — not a trust-policy change reviewed by the product team. The trust policy only changes when the External ID rotates or when a new Platform principal is introduced; both are rare, deliberate events.

### 2.2 External ID generation procedure

External IDs are **identifiers, not credentials** ([AWS guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user_externalid.html); R20). They live in DynamoDB, ship in CloudFormation parameters, and appear in CloudTrail unredacted — which is fine, because their security value comes from being unguessable to an attacker who is not the Platform principal, not from being secret to anyone with read access to the registry.

| Property | Value |
|---|---|
| **Length** | 32 characters |
| **Alphabet** | RFC 4648 base32 (`A–Z`, `2–7`) — no ambiguous glyphs (`0`/`O`, `1`/`I`/`l`), case-insensitive on copy-paste |
| **Entropy** | 160 bits — exceeds AWS's "any random string" guidance and survives quantum-era guessing collapse |
| **Generator** | Node `crypto.randomBytes(20)` → base32-encoded; one-time call inside the registry's `register-product` Lambda |
| **Storage of record** | DynamoDB Handler Registry product item: `pk=PRODUCT#<slug>`, attribute `externalId` |
| **Surfaced to** | Product team via the onboarding PR (CFN parameter `ExternalId`); also the Platform internal runbook `runbooks/onboard-product.md` |
| **Rotation cadence** | None on schedule. Rotated only on compromise of the Platform MCP Server principal, in which case the principal itself is the larger problem (R20). |
| **Inputs to AssumeRole** | Read at request time from the registry's product cache; passed as `ExternalId` in the SDK call |

The platform team is the **sole** issuer. The product team neither generates nor proposes the value; copy-paste error during onboarding is the failure mode this prevents (a product team that picks `"corporate-default-2026"` because it looks like a password reintroduces guessability).

### 2.3 STS session caching — TypeScript skeleton

STS has account-level rate limits on `AssumeRole` ([AWS STS quotas](https://docs.aws.amazon.com/STS/latest/APIReference/welcome.html)); at 5–10× growth and bursty agent concurrency, naïve "AssumeRole per call" hits ceilings (R16). The cache is in-process per Lambda execution environment, keyed on the assumer's view of the target — `(productAccount, externalId)` — and refreshed proactively at ~80% of the session's effective TTL so a request never lands on an expired credential.

The cache is per-execution-environment, not global; the warm-Lambda assumption underwriting the 95% hit-rate target is that the MCP Server Lambda's reserved concurrency holds enough warm environments to amortize the cold AssumeRole. Cross-replica STS reuse via ElastiCache is **out of scope for V1** — STS credentials are bearer tokens, and shipping them to Redis introduces a new credential-store attack surface for marginal cost saving.

```typescript
// src/mcp-server/sts-cache.ts
import {
  STSClient,
  AssumeRoleCommand,
  type AssumeRoleCommandOutput,
} from "@aws-sdk/client-sts";

interface CachedSession {
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken: string;
  expirationMs: number;          // absolute epoch ms
  refreshAfterMs: number;        // ~80% of TTL — proactive refresh threshold
}

interface SessionTags {
  tenant_id: string;
  user_sub: string;
  agent_client_id: string;
  request_id: string;
}

interface AssumeArgs {
  productAccount: string;        // 12-digit account ID
  productSlug: string;           // canonical slug, used in RoleSessionName
  externalId: string;            // base32, 32 chars (§2.2)
  roleName: string;              // e.g. "PlatformMcpInvoker-erp-prod"
  tags: SessionTags;             // session tags (§2.5)
}

const TTL_SECONDS = 3600;        // 1 h — matches role MaxSessionDuration
const REFRESH_FRACTION = 0.8;    // refresh at 80% — leaves 12 min slack on a 60 min token
const SAFETY_MS = 60_000;        // never serve a credential within 1 min of expiry

const sts = new STSClient({});
const cache = new Map<string, CachedSession>();
const inflight = new Map<string, Promise<CachedSession>>();

/**
 * Returns valid STS credentials for the given product, refreshing proactively.
 * Cache key intentionally excludes session tags — tags are embedded in CloudTrail
 * via RoleSessionName + sts:TagSession on every AssumeRole call, but a single
 * cached session is reused across requests with different tags. R10 mitigation:
 * the Platform audit log carries the authoritative principal, CloudTrail is
 * corroborating. Per-tag cache keys would collapse the cache hit rate.
 */
export async function getCredentials(args: AssumeArgs): Promise<CachedSession> {
  const cacheKey = `${args.productAccount}:${args.externalId}`;
  const now = Date.now();
  const cached = cache.get(cacheKey);

  if (cached && cached.refreshAfterMs > now && cached.expirationMs - now > SAFETY_MS) {
    return cached;
  }

  // Single-flight: if another request is already refreshing, await its result.
  const pending = inflight.get(cacheKey);
  if (pending) return pending;

  const promise = assumeAndStore(args, cacheKey).finally(() => inflight.delete(cacheKey));
  inflight.set(cacheKey, promise);
  return promise;
}

async function assumeAndStore(args: AssumeArgs, cacheKey: string): Promise<CachedSession> {
  // RoleSessionName must be unique-ish for CloudTrail correlation. Truncate
  // request_id; AWS limits this to 64 chars matching [\w+=,.@-].
  const sessionName = `mcp-${args.productSlug}-${args.tags.request_id}`.slice(0, 64);

  const out: AssumeRoleCommandOutput = await sts.send(
    new AssumeRoleCommand({
      RoleArn: `arn:aws:iam::${args.productAccount}:role/${args.roleName}`,
      RoleSessionName: sessionName,
      ExternalId: args.externalId,
      DurationSeconds: TTL_SECONDS,
      Tags: [
        { Key: "tenant_id", Value: args.tags.tenant_id },
        { Key: "user_sub", Value: args.tags.user_sub },
        { Key: "agent_client_id", Value: args.tags.agent_client_id },
        { Key: "request_id", Value: args.tags.request_id },
      ],
    }),
  );

  if (!out.Credentials?.AccessKeyId || !out.Credentials.Expiration) {
    throw new Error("AssumeRole returned no credentials");
  }

  const expirationMs = out.Credentials.Expiration.getTime();
  const ttlMs = expirationMs - Date.now();
  const session: CachedSession = {
    accessKeyId: out.Credentials.AccessKeyId,
    secretAccessKey: out.Credentials.SecretAccessKey!,
    sessionToken: out.Credentials.SessionToken!,
    expirationMs,
    refreshAfterMs: Date.now() + Math.floor(ttlMs * REFRESH_FRACTION),
  };
  cache.set(cacheKey, session);
  return session;
}
```

Two points worth pinning. First, the `inflight` map is the cache stampede guard — without it, an under-warmed Lambda environment fires N parallel `AssumeRole` calls on its first request burst, eats N STS quota slots, and fails the cold-path latency budget. Second, `RoleSessionName` carries `request_id` so CloudTrail rows in the product account stitch back to the Platform audit log without needing the session tags (CloudTrail logs `RoleSessionName` as a top-level field; tags appear under `requestParameters.tags` and are slightly less convenient to query).

### 2.4 Lambda dispatcher adapter — TypeScript skeleton

The dispatcher consumes the cached credentials and invokes the product handler in `RequestResponse` mode with the IdentityBroker-signed envelope as payload. The handler-side JWT verification against the Platform JWKS endpoint (07-poc-handler) is what closes the trust loop — the Lambda IAM permission proves the assumer identity, the embedded JWT proves the user/agent identity. **Token passthrough is forbidden by spec and by platform contract** — the dispatcher must never forward the inbound agent or user token; it forwards only the IdentityBroker-issued downstream JWT. ECS RunTask and SFN StartSyncExecution adapters share this signature and ship in M2.

```typescript
// src/mcp-server/dispatcher.ts
import { LambdaClient, InvokeCommand } from "@aws-sdk/client-lambda";
import { getCredentials } from "./sts-cache.js";

interface DispatchArgs {
  productAccount: string;
  productSlug: string;
  externalId: string;
  roleName: string;
  handlerArn: string;
  envelope: SignedInvocationEnvelope;  // IdentityBroker JWT + tool input
  tags: SessionTags;
  timeoutMs: number;                   // from registry, surfaced in MCP description
}

interface SignedInvocationEnvelope {
  identityToken: string;               // ≤5 min KMS-signed JWT (05-identity-broker)
  callId: string;                      // platform request_id; matches identityToken.jti and the tags.request_id session tag — handler uses this for log correlation (R10)
  toolId: string;                      // e.g. "erp.checkUserAccess"
  toolVersion: string;                 // e.g. "1.4.0"
  input: Record<string, unknown>;      // schema-validated tool input
  // tenant_id is NOT in input — it's claimed inside identityToken.
  // The handler reads it from the JWT, never from the envelope (R1).
}

export async function dispatchLambda(args: DispatchArgs): Promise<unknown> {
  const creds = await getCredentials({
    productAccount: args.productAccount,
    productSlug: args.productSlug,
    externalId: args.externalId,
    roleName: args.roleName,
    tags: args.tags,
  });

  // Per-call Lambda client constructed with the temporary credentials. The
  // overhead is negligible (no TLS handshake — the client reuses the AWS SDK's
  // shared HTTP agent), and per-call construction keeps credentials scoped to
  // the request's lifetime.
  const lambda = new LambdaClient({
    region: regionFromArn(args.handlerArn),
    credentials: {
      accessKeyId: creds.accessKeyId,
      secretAccessKey: creds.secretAccessKey,
      sessionToken: creds.sessionToken,
    },
    requestHandler: { requestTimeout: args.timeoutMs },
  });

  const out = await lambda.send(
    new InvokeCommand({
      FunctionName: args.handlerArn,
      InvocationType: "RequestResponse",
      Payload: Buffer.from(JSON.stringify(args.envelope)),
    }),
  );

  if (out.FunctionError) {
    // Map Lambda-side errors to the platform error envelope (see 03-mcp-server).
    throw mapInvocationError(out.FunctionError, out.Payload);
  }

  return JSON.parse(Buffer.from(out.Payload!).toString("utf8"));
}

function regionFromArn(arn: string): string {
  // arn:aws:lambda:<region>:<account>:function:<name>[:<qualifier>]
  return arn.split(":")[3];
}

function mapInvocationError(kind: string, payload?: Uint8Array): Error {
  // Implementation intentionally elided — see 03-mcp-server.md error envelope.
  return new Error(`Handler invocation error: ${kind}`);
}
```

### 2.5 Session-tag strategy

Every `sts:AssumeRole` call carries four session tags via [`sts:TagSession`](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_session-tags.html). The tags are AWS principal tags from the moment the session opens — handler IAM policies may reference `aws:PrincipalTag/<key>`, and CloudTrail records them on every action the session takes.

| Tag key | Source | Why this tag, what it proves |
|---|---|---|
| `tenant_id` | User JWT claim named by the registry's `tenantSourceClaim` field | The agent did not supply tenant; the value the handler IAM sees came from the user's verified token. Closes the in-IAM half of R1. |
| `user_sub` | User JWT `sub` | CloudTrail rows in the product account name the human, not just the role. Closes the audit-principal half of R10 (Platform log is authoritative; this is corroborating). |
| `agent_client_id` | M2M token `azp` / `client_id` | Distinguishes Claude Code from internal dev tools from ops dashboards in product-side audit. |
| `request_id` | UUID v4 minted at the MCP Server's request entry | Stitches CloudTrail rows in the product account to the Platform audit record (R10). Also embedded in `RoleSessionName` for indexed search. |

The trust policy explicitly grants `sts:TagSession` (§2.1). Without that grant, the AssumeRole call fails with `AccessDenied` even when the session itself is permitted — a foot-gun worth pinning in the trust template.

### 2.6 SCP layering — additive defense

[Service Control Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html) layer on top of the trust-policy conditions; they are never the substitute. Two SCPs ship with the Platform Services OU and the Product OU.

```yaml
# infrastructure/00-org-scp/platform-services-ou.yaml
# Attached to: Platform Services OU (Platform Services account is the sole member).
# Failure mode prevented: any Platform-account principal other than the MCP Server
# from assuming a cross-account role into a product account. This is what stops
# a compromised admin role in the Platform account from pivoting through the
# trust topology, even though product-side trust policies already restrict by
# Principal ARN.
Version: "2012-10-17"
Statement:
  - Sid: DenyCrossAccountAssumeFromNonMcpServer
    Effect: Deny
    Action: "sts:AssumeRole"
    Resource: "arn:aws:iam::*:role/PlatformMcpInvoker-*"
    Condition:
      StringNotEquals:
        "aws:PrincipalArn":
          - !Sub "arn:aws:iam::${PlatformAccountId}:role/PlatformMcpServer"
  - Sid: DenyPassRoleFromOutsidePlatformServices
    Effect: Deny
    Action: "iam:PassRole"
    Resource: "arn:aws:iam::*:role/PlatformMcp*"
    Condition:
      StringNotEqualsIfExists:
        "aws:PrincipalOrgPaths":
          - !Sub "${LinqOrgId}/r-root/ou-platform-services"
```

```yaml
# infrastructure/00-org-scp/product-ou.yaml
# Attached to: Product OU (4 product accounts in V1).
# Failure mode prevented: a product team — by accident or under registry
# tampering — adds a non-Platform principal to the PlatformMcpInvoker trust
# policy. The SCP denies the role-modification action when the new principal
# does not belong to the LINQ Org.
Version: "2012-10-17"
Statement:
  - Sid: DenyTrustPolicyEscapeFromOrg
    Effect: Deny
    Action:
      - "iam:UpdateAssumeRolePolicy"
      - "iam:CreateRole"
    Resource: "arn:aws:iam::*:role/PlatformMcpInvoker-*"
    Condition:
      "ForAnyValue:StringNotEqualsIfExists":
        "aws:PrincipalOrgID": !Ref LinqOrgId
```

The SCPs are **additive** — they do not reduce what trust policy or IAM policy already forbid; they catch the human-error and registry-tampering cases that bypass IAM logic entirely.

## 3. Acceptance criteria

Observable signals only. Every criterion is testable from the deployed sandbox.

- **AC-06.1 — `AssumeRole` succeeds with the correct External ID.** Given the registered External ID, the MCP Server's AssumeRole call returns 1 h credentials. Asserted by the integration test in `08-testing.md`.
- **AC-06.2 — `AssumeRole` fails with a mismatched External ID.** Given any string other than the registered External ID, STS returns `AccessDenied` and the MCP Server emits an `AUTH` error envelope. Asserted by chaos test (deliberately wrong External ID).
- **AC-06.3 — `AssumeRole` fails for a principal outside the LINQ Org.** Simulated by a `PolicySimulator` test against the trust policy with a non-Org principal; result must be `explicitDeny`.
- **AC-06.4 — Session tags appear in CloudTrail.** A successful invoke produces a CloudTrail row in the product account whose `userIdentity.sessionContext.attributes` includes `tenant_id`, `user_sub`, `agent_client_id`, and `request_id`. The Platform audit row for the same `request_id` matches.
- **AC-06.5 — STS cache hit rate ≥ 95% in steady state.** Measured via a CloudWatch custom metric `Platform/MCP/StsCacheHitRate` emitted by the dispatcher. Reported daily; `< 95%` for two consecutive days fires the R16 alarm.
- **AC-06.6 — `RoleSessionName` carries `request_id` for correlation.** Asserted by parsing CloudTrail and matching against the Platform audit log; reconciliation runs daily (10-observability-runbooks).
- **AC-06.7 — Trust policy template passes `cfn-nag`.** Zero FAIL findings; all WARN findings carry inline justification.

## 4. Effort estimate

`3 d [ASSUMED]` — one engineer, single-shift. Breakdown:

- 0.5 d — trust-policy template + parameterization
- 0.5 d — External ID generator + registry product-table wiring
- 1.0 d — STS cache + dispatcher adapter (in TypeScript) with unit tests
- 0.5 d — SCP authoring + Org-level review prep
- 0.5 d — integration tests for AC-06.1 through AC-06.4

Critical path dependency: Platform Services account exists with `PlatformMcpServer` role provisioned (01-cloudformation, deployed via 02-github-actions). External ID generation depends on the registry's product table from 04-registry — sequencing handled by CC-3.

## 5. Open questions

**Q3 (resolved per CC-5).** All four V1 product accounts share one AWS Organization, `[ASSUMED]`. The design uses External ID and `aws:PrincipalOrgID` as **layered** conditions regardless — Q3 only affects whether the SCP layer is meaningful. If the assumption proves false (a product spins out of the Org during V1), the External ID layer continues to protect; the SCP layer would need to be re-evaluated and extended to cover the spun-out account separately.

**Out of scope, deliberately deferred.** PrivateLink for the cross-account dispatch path; cross-region session caching; per-tenant External IDs (single per-product External ID is sufficient — per-tenant adds a registry write to every onboarding without a corresponding security gain, since handlers enforce tenant via the JWT claim, not via IAM principal); third-party External ID rotation tooling (V1 manual rotation via the onboarding runbook is sufficient for the 3-year horizon at expected External ID count).

## 6. Cross-references

- ADR — [`docs/decisions/0015-centralized-platform-mcp.md`](../../../decisions/0015-centralized-platform-mcp.md), §"Cross-account invocation"
- Architecture — [`01-architecture.md`](../01-architecture.md), §"Cross-account trust diagram" — defines the `PlatformMcpServer` ↔ `PlatformMcpInvoker` topology this artifact realizes.
- Security role pass — [`role-passes/security-iam.md`](../role-passes/security-iam.md), R2/R7 + "External ID vs. Org trust" + "AssumeRoleWithWebIdentity setup" — the design notes here are the binding source for §2.1 and §2.2.
- Risks register — [`03-risks-register.md`](../03-risks-register.md), R2, R10, R16, R20, R21
- IdentityBroker — [`05-identity-broker.md`](./05-identity-broker.md) — supplies the signed envelope passed through `dispatchLambda` (§2.4).
- POC handler (the verifier) — [`07-poc-handler.md`](./07-poc-handler.md) — handler-side JWT verify against Platform JWKS.
- Open Questions — [`05-open-questions.md`](../05-open-questions.md), Q3
- Wiki entity — [`knowledge/wiki/entities/sts-assume-role-external-id.md`](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)
- AWS docs cited:
  - External ID — https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user_externalid.html
  - `aws:PrincipalOrgID` — https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-principalorgid
  - `sts:TagSession` — https://docs.aws.amazon.com/IAM/latest/UserGuide/id_session-tags.html
  - SCPs — https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html
  - STS quotas — https://docs.aws.amazon.com/STS/latest/APIReference/welcome.html

## 7. Risks protected against

- **R2 — Confused Deputy across products.** Per-product External ID layered with `aws:PrincipalOrgID` on every cross-account trust policy. Even under registry tampering or tool-ID mis-resolution, the trust policy refuses an AssumeRole that does not present the expected External ID; even with the expected External ID, a principal outside the LINQ Org is refused.
- **R10 — STS session caching causes stale principal at audit time.** `RoleSessionName` carries `request_id`; `sts:TagSession` adds `tenant_id`, `user_sub`, `agent_client_id`, `request_id`; CloudTrail rows in each product account correlate to the Platform audit log on `request_id`. The Platform audit log is authoritative, CloudTrail is corroborating.
- **R16 — Cross-account STS quota.** In-process credential cache keyed on `(productAccount, externalId)`, refreshing at ~80% of session TTL with single-flight stampede protection. Steady-state hit rate ≥ 95%, monitored via CloudWatch alarm.
- **R20 — External ID treated as a secret.** Documented as identifier, not credential; stored in DynamoDB without encryption-at-rotation cadence; surfaced in CFN parameters with `NoEcho: false`; rotated only on Platform principal compromise. Procedure pinned in §2.2.
- **R21 — Lambda resource-policy drift.** `AssumeRole` is the platform default for cross-account dispatch; Lambda resource-based policies are documented as a narrow-case alternative for invoke-only handlers, justified per-handler in the registry, and never used to substitute the External ID + `PrincipalOrgID` layering. Mixing the two patterns arbitrarily is what creates bimodal audit and rotation surface; this artifact avoids that by making AssumeRole non-negotiable for V1.
