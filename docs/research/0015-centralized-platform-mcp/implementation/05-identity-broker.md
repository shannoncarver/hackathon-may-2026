# Implementation 05 — IdentityBroker (Path C, KMS-signed JWT)

**Status:** Implementation plan (Phase B). Implements [Decision 0015](../../../decisions/0015-centralized-platform-mcp.md).
**Owner:** 12-eng-security-iam (Security & IAM Engineer lens)
**Date:** 2026-05-04
**Effort estimate:** `3 d [ASSUMED]`

## 1. Overview

The IdentityBroker is the on-behalf-of (OBO) issuance seam for the Platform MCP Server. It accepts a verified user identity plus an agent client identity from the MCP server, validates inputs against a registry-driven audience allowlist, asks AWS KMS to sign a short-lived JWT carrying an RFC 8693-shaped `act` claim chain, and returns the signed token to the caller. V1 implements **Path C — Platform-owned KMS-signed JWT** because Auth0's native RFC 8693 token-exchange grant remains in early access on Auth0 Enterprise as of 2026-05-04 and is therefore inadmissible for production-critical paths (no SLA, behavior may change, limited observability, best-effort vendor support). The on-the-wire shape is bit-for-bit RFC 8693-compatible, which means handler-side verification is portable; a future migration to Auth0's native grant is a code change inside this Lambda only ([RFC 8693](https://www.rfc-editor.org/rfc/rfc8693.html); [`identity-broker-implementation.md`](../deep-dives/identity-broker-implementation.md)). The Lambda runs on **Node 20 + TypeScript** per cross-cutting decision **CC-1**, and resolves [Open Question Q1](../05-open-questions.md) per **CC-5**.

## 2. Concrete artifacts

### 2.1 KMS asymmetric signing key — CFN excerpt

The key lives in the Platform Services account inside nested stack `05-identity-broker`. ECDSA P-256 is chosen over RSASSA-PSS-SHA-256 for three reasons: smaller signature size (~64 bytes vs. ~256 bytes), faster `kms:Sign` latency (~3–5 ms warm vs. ~10–15 ms), and standard `ES256` JOSE support across every JWT-validating library handlers might use. The key policy grants `kms:Sign` to **only** the IdentityBroker Lambda execution role; key administrators get visibility (`kms:Describe*`, `kms:GetPublicKey`) and rotation actions but cannot mint tokens.

```yaml
# infrastructure/05-identity-broker/template.yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: IdentityBroker KMS asymmetric signing key + Lambda. Path C V1.

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, stage, prod]
  IdentityBrokerRoleArn:
    Type: String
    Description: ARN of the IdentityBroker Lambda execution role (created in this stack).
  KeyAdminRoleArn:
    Type: String
    Description: ARN of the platform key-admin role; rotation and inspection only — never sign.

Resources:

  IdentityBrokerSigningKey:
    Type: AWS::KMS::Key
    DeletionPolicy: Retain
    UpdateReplacePolicy: Retain
    Properties:
      Description: !Sub "Platform IdentityBroker JWT signing key (${Environment}). ECDSA P-256."
      KeyUsage: SIGN_VERIFY
      KeySpec: ECC_NIST_P256
      # Annual rotation is performed manually via the procedure in §2.5.
      # Asymmetric KMS keys do not support automatic rotation as of 2026-05-04.
      EnableKeyRotation: false
      MultiRegion: false
      PendingWindowInDays: 30
      KeyPolicy:
        Version: "2012-10-17"
        Id: identity-broker-key-policy
        Statement:
          # Root account guardrail (AWS-recommended; without it, the key becomes unmanageable).
          - Sid: EnableRootPermissions
            Effect: Allow
            Principal:
              AWS: !Sub "arn:aws:iam::${AWS::AccountId}:root"
            Action: "kms:*"
            Resource: "*"
          # IdentityBroker Lambda — only principal allowed to sign.
          # Failure mode prevented: a compromised platform admin role cannot mint downstream JWTs.
          - Sid: IdentityBrokerSign
            Effect: Allow
            Principal:
              AWS: !Ref IdentityBrokerRoleArn
            Action:
              - kms:Sign
              - kms:GetPublicKey
              - kms:DescribeKey
            Resource: "*"
            Condition:
              StringEquals:
                # Bind to the ES256 algorithm so a downgrade attack cannot request HMAC.
                "kms:SigningAlgorithm": "ECDSA_SHA_256"
          # Key admins — inspection and rotation only. No sign.
          # Failure mode prevented: a rogue admin cannot issue arbitrary OBO tokens.
          - Sid: KeyAdminInspectAndRotate
            Effect: Allow
            Principal:
              AWS: !Ref KeyAdminRoleArn
            Action:
              - kms:DescribeKey
              - kms:GetPublicKey
              - kms:GetKeyPolicy
              - kms:GetKeyRotationStatus
              - kms:ScheduleKeyDeletion
              - kms:CancelKeyDeletion
              - kms:DisableKey
              - kms:EnableKey
              - kms:TagResource
              - kms:UntagResource
            Resource: "*"
      Tags:
        - { Key: Component, Value: identity-broker }
        - { Key: Environment, Value: !Ref Environment }
        - { Key: Rotation, Value: annual-manual }

  IdentityBrokerSigningKeyAlias:
    Type: AWS::KMS::Alias
    Properties:
      # Alias is the stable handle; the underlying key id rotates.
      AliasName: !Sub "alias/platform/identity-broker/jwt-signing-${Environment}"
      TargetKeyId: !Ref IdentityBrokerSigningKey

Outputs:
  IdentityBrokerSigningKeyArn:
    Value: !GetAtt IdentityBrokerSigningKey.Arn
    Export:
      Name: !Sub "${AWS::StackName}-IdentityBrokerSigningKeyArn"
  IdentityBrokerSigningKeyAlias:
    Value: !Ref IdentityBrokerSigningKeyAlias
    Export:
      Name: !Sub "${AWS::StackName}-IdentityBrokerSigningKeyAlias"
```

CFN scaffolding for the Lambda function, role, and packaging is owned by 11-eng-cloudops in `02-secrets.md` / cross-stack glue — this artifact specifies only the security-relevant primitives (key spec, policy, signing-algorithm pin).

### 2.2 IdentityBroker Lambda — TypeScript skeleton

The Lambda is stateless; its only job is input validation, JWT assembly, and KMS signing. Cold-start work is limited to importing the AWS SDK v3 KMS client. The audience allowlist is read from the registry's product table at handler resolution time on the MCP server side and passed in as `audience`; the Lambda re-checks it against an in-process allowlist refreshed every 60 s to defend against MCP-server compromise.

```ts
// src/identity-broker/index.ts
import {
  KMSClient,
  SignCommand,
  type SignCommandOutput,
} from "@aws-sdk/client-kms";
import { randomUUID } from "node:crypto";
import { validateInputs, type BrokerInput } from "./validation.js";
import { buildHeader, buildPayload, base64UrlJson } from "./jwt.js";
import { derEcdsaToJoseRaw } from "./signer.js";
import { brokerError } from "./errors.js";

const kms = new KMSClient({}); // Region picked up from Lambda env.
const KEY_ID = process.env.IDENTITY_BROKER_KEY_ALIAS!; // e.g. alias/platform/identity-broker/jwt-signing-prod
const ISSUER = process.env.PLATFORM_ISSUER!;           // e.g. https://mcp.linq.platform
const TTL_SECONDS = 300;                                // exp <= 5 min — non-negotiable
const ALG = "ES256";

export async function handler(input: BrokerInput): Promise<{ jwt: string }> {
  // 1. Input validation — reject before signing. Failure modes:
  //    - audience not in allowlist → defends against confused-deputy via tampered registry (R2).
  //    - empty permissions[]      → defends against accidental privilege grant.
  //    - missing tenant_id        → defends against tenant leakage at handler (R1).
  //    - malformed user_sub       → defends against caller-supplied sub forgery.
  const validated = await validateInputs(input);

  // 2. Header. `kid` is the current KMS key id; rotation is handled by the JWKS endpoint
  //    serving both old and new public keys (see §2.4).
  const header = buildHeader({ alg: ALG, kid: validated.kid });

  // 3. Payload. RFC 8693-shaped: sub = user, act.sub = agent_client_id, aud = handler audience.
  //    exp <= 5 min — bounded so a leaked token's blast radius is small.
  const now = Math.floor(Date.now() / 1000);
  const payload = buildPayload({
    iss: ISSUER,
    sub: validated.user_sub,
    act: { sub: validated.agent_client_id },
    aud: validated.audience,
    exp: now + TTL_SECONDS,
    iat: now,
    jti: validated.request_id ?? randomUUID(),
    scope: validated.scope,
    permissions: validated.permissions,
    tenant_id: validated.tenant_id,
  });

  // 4. Compute the signing input: base64url(header) + "." + base64url(payload).
  const signingInput = `${base64UrlJson(header)}.${base64UrlJson(payload)}`;

  // 5. KMS Sign. MessageType=RAW lets KMS hash; we could pre-hash with DIGEST for
  //    larger payloads, but JWTs are small so RAW is simplest and equally secure.
  let signResult: SignCommandOutput;
  try {
    signResult = await kms.send(
      new SignCommand({
        KeyId: KEY_ID,
        Message: Buffer.from(signingInput, "utf8"),
        MessageType: "RAW",
        SigningAlgorithm: "ECDSA_SHA_256",
      }),
    );
  } catch (e) {
    // Fail closed — never return an unsigned token.
    throw brokerError("KMS_SIGN_FAILED", (e as Error).message);
  }

  if (!signResult.Signature) {
    throw brokerError("KMS_SIGN_EMPTY", "KMS returned no signature");
  }

  // 6. KMS returns a DER-encoded ECDSA signature. JOSE expects raw r||s of fixed length.
  //    Conversion is mandatory — handlers will reject DER-shaped signatures.
  const joseSig = derEcdsaToJoseRaw(Buffer.from(signResult.Signature));
  const signatureB64 = joseSig.toString("base64url");

  return { jwt: `${signingInput}.${signatureB64}` };
}
```

```ts
// src/identity-broker/validation.ts
import { brokerError } from "./errors.js";

export interface BrokerInput {
  user_sub: string;
  agent_client_id: string;
  permissions: string[];
  tenant_id: string;
  audience: string;
  scope?: string;
  request_id?: string;
}

export interface ValidatedInput extends Required<Omit<BrokerInput, "scope" | "request_id">> {
  scope: string;
  request_id?: string;
  kid: string;
}

const AUTH0_SUB_RE = /^[a-z0-9-]+\|[A-Za-z0-9._-]+$/;

let allowlistCache: { audiences: Set<string>; fetchedAt: number } | null = null;
const ALLOWLIST_TTL_MS = 60_000;

export async function validateInputs(input: BrokerInput): Promise<ValidatedInput> {
  if (!input.user_sub || !AUTH0_SUB_RE.test(input.user_sub)) {
    throw brokerError("INVALID_USER_SUB", "user_sub does not match Auth0 sub format");
  }
  if (!input.agent_client_id) {
    throw brokerError("MISSING_AGENT_CLIENT_ID", "agent_client_id is required");
  }
  if (!Array.isArray(input.permissions) || input.permissions.length === 0) {
    throw brokerError("EMPTY_PERMISSIONS", "permissions must be a non-empty array");
  }
  if (!input.tenant_id || !input.tenant_id.trim()) {
    // Closes R1 from the broker side: a missing tenant_id never produces a signed token.
    throw brokerError("MISSING_TENANT_ID", "tenant_id is required");
  }
  if (!input.audience) {
    throw brokerError("MISSING_AUDIENCE", "audience is required");
  }

  const allowlist = await getAudienceAllowlist();
  if (!allowlist.has(input.audience)) {
    // Defense in depth — the MCP server already resolved the audience from the registry.
    // This re-check defends against an MCP-server compromise issuing arbitrary audiences.
    throw brokerError("AUDIENCE_NOT_ALLOWED", `audience ${input.audience} not registered`);
  }

  return {
    user_sub: input.user_sub,
    agent_client_id: input.agent_client_id,
    permissions: input.permissions,
    tenant_id: input.tenant_id,
    audience: input.audience,
    scope: input.scope ?? "",
    request_id: input.request_id,
    kid: process.env.IDENTITY_BROKER_KID!, // populated at deploy time from KMS key id
  };
}

async function getAudienceAllowlist(): Promise<Set<string>> {
  const now = Date.now();
  if (allowlistCache && now - allowlistCache.fetchedAt < ALLOWLIST_TTL_MS) {
    return allowlistCache.audiences;
  }
  // Reads from the registry product table; helper omitted for brevity.
  const audiences = await loadAudiencesFromRegistry();
  allowlistCache = { audiences: new Set(audiences), fetchedAt: now };
  return allowlistCache.audiences;
}

declare function loadAudiencesFromRegistry(): Promise<string[]>;
```

```ts
// src/identity-broker/signer.ts — DER ECDSA → JOSE raw r||s.
// Failure mode prevented: handlers using the JOSE library reject DER signatures with
// "invalid signature length", causing every downstream call to 401.
export function derEcdsaToJoseRaw(der: Buffer): Buffer {
  // Standard ASN.1 SEQUENCE { r INTEGER, s INTEGER } parser, normalized to 32 bytes each
  // for ES256 (P-256). Implementation omitted for brevity; reference: jose@5 utility.
  // Both r and s are left-padded to exactly 32 bytes; output is exactly 64 bytes.
  return parseEcdsaDerAndPad(der, 32);
}

declare function parseEcdsaDerAndPad(der: Buffer, byteLength: number): Buffer;
```

The MCP server invokes the IdentityBroker Lambda **in parallel with `sts:AssumeRole`** — both depend only on registry-resolved metadata (audience, productAccount, externalId, scopes), neither depends on the other's output. This parallelism cuts ~50 ms off the cold path ([`identity-broker-implementation.md` §Latency](../deep-dives/identity-broker-implementation.md)).

### 2.3 JWT wire shape (verbatim)

Reproduced from [`identity-broker-implementation.md` §JWT wire shape](../deep-dives/identity-broker-implementation.md). Bit-for-bit identical to what an [RFC 8693](https://www.rfc-editor.org/rfc/rfc8693.html) token-exchange grant would emit; handlers verify with any standard JOSE library against the platform JWKS. Sample values are illustrative.

```text
Header (base64url-encoded JSON):
  {
    "alg": "ES256",
    "typ": "JWT",
    "kid": "kms-key-id-2026-q2"
  }

Payload (base64url-encoded JSON):
  {
    "iss": "https://mcp.linq.platform",
    "sub": "auth0|alice",
    "act": {
      "sub": "claude-desktop-client-id-uuid"
    },
    "aud": "https://erp-handler.linq.platform",
    "exp": 1714839847,
    "iat": 1714839547,
    "jti": "req-<uuid>",
    "scope": "erp:read",
    "permissions": ["erp:read:user"],
    "tenant_id": "acme"
  }

Signature: ECDSA P-256 signature of header || "." || payload, base64url-encoded (raw r||s, 64 bytes).
```

Failure modes prevented by the cryptographic choices:

- **`alg: ES256` (not `none`, not HMAC).** Prevents algorithm-confusion attacks where a forged token sets `alg: none` or substitutes a symmetric algorithm using the public key as the secret.
- **`kid` pinned to the current KMS key id.** Lets the JWKS endpoint serve the old and new keys simultaneously during rotation without breaking in-flight tokens.
- **`aud` bound to a single handler URI.** Prevents token replay across resource servers; a token issued for `erp-handler` cannot be redeemed at `lms-handler`.
- **`exp - iat = 300` (≤ 5 min).** Bounds blast radius of token leak; coordinates with the rotation drain window.
- **`act.sub` carrying agent identity, `sub` carrying user identity.** RFC 8693-canonical OBO record; handlers log both for non-repudiation. Prevents impersonation attacks where the agent claim is missing.
- **`iss = https://mcp.linq.platform`.** Pins the issuer the handler verifies against the JWKS endpoint. Prevents accepting tokens issued by any other principal that happens to know the public key URL.

### 2.4 JWKS endpoint hosted by the Platform MCP Server

The MCP server self-hosts `/.well-known/jwks.json` for two reasons. First, RFC 9728 places resource-metadata responsibilities on the resource server, and the JWKS endpoint is the natural companion ([RFC 9728](https://www.rfc-editor.org/rfc/rfc9728.html)). Second, hosting it on the platform side **closes R5 by design** — no Auth0-side dependency on JWKS hosting; LINQ controls availability, caching, and rotation behavior end-to-end.

The public key is fetched once at MCP server cold start via `kms:GetPublicKey` and cached in process for the lifetime of the Lambda container. Handlers cache JWKS responses for 1 h via the standard `Cache-Control` header.

```ts
// src/mcp-server/routes/jwks.ts
import {
  KMSClient,
  GetPublicKeyCommand,
} from "@aws-sdk/client-kms";
import type { APIGatewayProxyResultV2 } from "aws-lambda";

const kms = new KMSClient({});
const KEY_ALIAS = process.env.IDENTITY_BROKER_KEY_ALIAS!;
const ROTATION_OVERLAP_KEY_ARN = process.env.IDENTITY_BROKER_PREVIOUS_KEY_ARN; // optional during rotation window

interface CachedJwks {
  body: string;
  fetchedAt: number;
}

let cache: CachedJwks | null = null;
const COLD_START_REFRESH_MS = 60 * 60 * 1000; // 1 h — matches Cache-Control: max-age=3600

export async function handleJwks(): Promise<APIGatewayProxyResultV2> {
  const now = Date.now();
  if (!cache || now - cache.fetchedAt > COLD_START_REFRESH_MS) {
    const keys = await Promise.all(
      [KEY_ALIAS, ROTATION_OVERLAP_KEY_ARN]
        .filter((id): id is string => Boolean(id))
        .map(fetchPublicKeyAsJwk),
    );
    cache = {
      body: JSON.stringify({ keys }),
      fetchedAt: now,
    };
  }

  return {
    statusCode: 200,
    headers: {
      "content-type": "application/json",
      // Public, cacheable: handlers SHOULD cache aggressively. Rotation handled by serving
      // both keys during the overlap window (§2.5), so a 1 h cache is safe.
      "cache-control": "public, max-age=3600",
    },
    body: cache.body,
  };
}

async function fetchPublicKeyAsJwk(keyId: string) {
  const out = await kms.send(new GetPublicKeyCommand({ KeyId: keyId }));
  if (!out.PublicKey || !out.KeyId) {
    throw new Error(`KMS returned no public key for ${keyId}`);
  }
  // KMS returns DER-encoded SubjectPublicKeyInfo; convert to JWK form.
  // For ECC_NIST_P256 the output JWK has kty=EC, crv=P-256, x, y.
  const jwk = derSpkiToEcJwk(Buffer.from(out.PublicKey));
  return {
    kty: "EC",
    crv: "P-256",
    use: "sig",
    alg: "ES256",
    kid: deriveKidFromKeyArn(out.KeyId),
    x: jwk.x,
    y: jwk.y,
  };
}

declare function derSpkiToEcJwk(der: Buffer): { x: string; y: string };
declare function deriveKidFromKeyArn(arn: string): string;
```

The `kid` is derived deterministically from the KMS key ARN so handlers always select the matching JWK when verifying signatures. During the rotation overlap window the endpoint serves both `kid`s ([RFC 7517](https://www.rfc-editor.org/rfc/rfc7517.html) §4.5).

### 2.5 Annual rotation procedure

KMS asymmetric keys do not support automatic rotation as of 2026-05-04, so rotation is manual. Cadence is **annual** under steady state and **immediate** on suspected key compromise. Steps run during a low-traffic window:

1. **Platform on-call engineer** — opens the rotation runbook, files a CAB ticket if production, and confirms the `EnableKey` / `DisableKey` IAM permissions are in place on the key-admin role.
2. **CloudOps engineer (`11-eng-cloudops`)** — provisions a new KMS key (`IdentityBrokerSigningKeyV2`) via the same CFN template parameters, exporting its ARN. Old key is unchanged.
3. **Security engineer (`12-eng-security-iam`)** — updates the IdentityBroker Lambda environment variable `IDENTITY_BROKER_KEY_ALIAS` to point at the new key alias (or the alias is repointed to the new key id; alias-repoint is the simpler path). Also updates `IDENTITY_BROKER_KID` to the new kid. Deploys.
4. **Platform on-call engineer** — sets `IDENTITY_BROKER_PREVIOUS_KEY_ARN` on the MCP server Lambda to the **old** key ARN. The JWKS endpoint now serves both keys. Forces a cold start to flush the cache.
5. **Platform on-call engineer** — waits **at least 5 minutes** (the JWT TTL ceiling) so all in-flight tokens signed by the old key drain. Confirms via CloudTrail that `kms:Sign` traffic on the old key has gone to zero.
6. **Security engineer** — disables the old key via `kms:DisableKey`. Tokens signed by it stop verifying once the JWKS overlap is removed.
7. **Platform on-call engineer** — removes `IDENTITY_BROKER_PREVIOUS_KEY_ARN` from the MCP server Lambda after handlers have refreshed their JWKS cache (1 h max). Forces a cold start.
8. **Security engineer** — schedules the old key for deletion with a 30-day pending window via `kms:ScheduleKeyDeletion`. The 30-day window provides a recovery escape hatch if a delayed verification path surfaces.
9. **Hackathon Coordinator / Platform owner** — files the rotation completion record into the audit log group and updates the rotation calendar.

On suspected compromise, steps 1–6 collapse into a single accelerated run: skip the CAB delay, push the new key, force the JWKS overlap, and disable the old key after the 5-minute drain. Tokens currently in flight expire on their own ≤ 5 min later.

Every `kms:Sign` call lands in CloudTrail with the IdentityBroker Lambda's role as the principal. Rotation does not break that audit trail — old-key Sign calls remain queryable indefinitely.

## 3. Acceptance criteria

Observable signals:

- **AC-IB-1.** `kms:GetKeyPolicy` on the IdentityBroker key returns a policy whose only `kms:Sign` principal is the IdentityBroker Lambda execution role and whose `Condition` pins `kms:SigningAlgorithm = ECDSA_SHA_256`. Verified by a CFN-guard rule and a periodic IAM Access Analyzer run.
- **AC-IB-2.** A request to `GET /.well-known/jwks.json` returns HTTP 200 with `Cache-Control: public, max-age=3600`, `Content-Type: application/json`, and at least one JWK with `kty=EC`, `crv=P-256`, `use=sig`, `alg=ES256`. The `kid` matches the IdentityBroker Lambda's environment.
- **AC-IB-3.** A signed JWT issued by the IdentityBroker verifies cleanly against the JWKS endpoint using `jose@5` or any standard JOSE library, with `iss`, `aud`, `exp`, `sub`, `act.sub`, `tenant_id`, `permissions`, and `jti` claims present.
- **AC-IB-4.** A request with `audience` not in the registry allowlist returns a structured error envelope with code `AUDIENCE_NOT_ALLOWED` and produces no `kms:Sign` CloudTrail entry.
- **AC-IB-5.** A request with empty `permissions[]`, missing `tenant_id`, or malformed `user_sub` returns the corresponding structured error and does not invoke KMS.
- **AC-IB-6.** Issued JWT `exp - iat ≤ 300`. Asserted in unit tests and in the integration test suite (`08-testing.md`).
- **AC-IB-7.** The MCP server's per-request audit record (per [`role-passes/security-iam.md` §Audit log schema](../role-passes/security-iam.md)) shows `latency_ms.identity_broker` and `latency_ms.sts_assume` overlapping — the broker invocation runs in parallel with `AssumeRole`.
- **AC-IB-8.** Rotation procedure completes end-to-end in a sandbox without any handler-side configuration change. Verified annually as a CloudOps drill.

## 4. Effort estimate

`3 d [ASSUMED]` — 1 d for KMS key + Lambda CFN and policy review; 1 d for the Lambda code (validation, signer, DER→JOSE conversion, error envelope, tests); 1 d for the JWKS endpoint integration on the MCP server side, including the rotation-overlap behavior and unit tests for `kid` selection.

## 5. Open questions

None blocking. **Q1 is closed by Path C** per cross-cutting decision **CC-5**.

Non-blocking watch item:

- **Auth0 RFC 8693 native grant — GA timing.** Auth0 promoted token-exchange to early access on Auth0 Enterprise sometime before 2026-05-04. When (or whether) it reaches GA on LINQ's Auth0 plan determines the trigger condition for the future-migration story in §8. **Tracked outside the V1 scope; reviewed quarterly by Identity team and Security.** Unable to verify a GA date from public Auth0 product communications.

## 6. Cross-references

- [`deep-dives/identity-broker-implementation.md`](../deep-dives/identity-broker-implementation.md) — full rationale for Path C, latency analysis, comparison with Path A, and the migration story summarized in §8.
- [`role-passes/security-iam.md`](../role-passes/security-iam.md) — original security-lens findings, audit-log schema, and the IdentityBroker contract sketched at the role-pass stage.
- [`03-mcp-server.md`](./03-mcp-server.md) — Lambda that invokes the broker as part of the 10-step `tools/call` pipeline; also hosts the `/.well-known/jwks.json` endpoint.
- [`04-registry.md`](./04-registry.md) — source of the audience allowlist consulted by `validation.ts`.
- [`06-cross-account.md`](./06-cross-account.md) — the parallel `sts:AssumeRole` step that runs alongside the broker invocation.
- [`03-risks-register.md`](../03-risks-register.md) — R5, R9, R20 mitigations.
- [`05-open-questions.md`](../05-open-questions.md) — Q1 (closed by Path C).
- [`0015-centralized-platform-mcp.md`](../../../decisions/0015-centralized-platform-mcp.md) — the binding ADR.
- [RFC 8693 — OAuth 2.0 Token Exchange](https://www.rfc-editor.org/rfc/rfc8693.html) — wire-shape spec.
- [RFC 9728 — OAuth 2.0 Protected Resource Metadata](https://www.rfc-editor.org/rfc/rfc9728.html) — JWKS hosting context.
- [RFC 8707 — Resource Indicators for OAuth 2.0](https://www.rfc-editor.org/rfc/rfc8707.html) — audience-binding parameter, enforced upstream by the MCP server.
- [RFC 7517 — JSON Web Key (JWK)](https://www.rfc-editor.org/rfc/rfc7517.html) — JWK / JWKS structure.

## 7. Risks protected against

- **R5 — Auth0 RFC 9728 (Protected Resource Metadata) support unconfirmed.** Closes by design. The JWKS endpoint at `/.well-known/jwks.json` is hosted by the Platform MCP Server itself, fed by `kms:GetPublicKey`. No Auth0-side hosting dependency.
- **R9 — Auth0 RFC 8693 unsupported, OBO collapses to homemade signing.** Path C **is** the mitigation. The IdentityBroker issues an RFC 8693-shaped JWT signed by a Platform-owned KMS asymmetric key; future migration to Auth0 native RFC 8693 is a code change in this Lambda only — handlers do not change.
- **R20 — External ID treated as a secret.** This artifact does not propagate External IDs into JWT claims and does not encrypt or vault them. The broker's input contract treats `audience` (which is registry-bound) as the only sensitive routing input; External ID stays where it belongs — in the `06-cross-account` STS trust-policy condition — as an identifier, not a credential ([wiki/entities/sts-assume-role-external-id.md](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)).

## 8. Future considerations

**Path A migration story — single-Lambda swap.** If Auth0 promotes RFC 8693 to GA on LINQ's plan and a concrete operational win materializes (e.g., centralized Auth0 logging that platform-side audit doesn't replicate), migration is bounded to the IdentityBroker Lambda. Steps:

1. **Replace `kms:Sign` with an Auth0 token-exchange POST.** The Lambda body becomes `POST {auth0_domain}/oauth/token` with `grant_type=urn:ietf:params:oauth:grant-type:token-exchange`, `subject_token={user_jwt}`, `actor_token={agent_jwt}`, `audience={validated.audience}`, `scope={resolved_scopes}`. Roughly 50 lines of code change.
2. **Handlers unchanged.** Handler-side JWKS becomes a multi-issuer set (Auth0's signing keys plus, transitionally, the platform's) until the cutover completes. The wire shape is identical, so the verification logic doesn't change.
3. **Cutover plan.** Dual-issue (both platform and Auth0) for one TTL window (≤ 5 min) so any in-flight tokens drain. Then cut platform issuance off and serve only Auth0 keys from JWKS.
4. **KMS key.** Disable, then schedule for deletion with a 30-day pending window. Audit trail in CloudTrail remains queryable.

The migration is a code change, not a protocol change. **No coordinated handler-team upgrade required.**

Other future considerations, deferred from V1:

- **Multi-hop `act` chains.** RFC 8693 allows nested `act` claims for delegation chains (`act: { sub: "agent-B", act: { sub: "agent-A" } }`). V1's `validation.ts` and `jwt.ts` accept a single `act` level; extending to nested chains is additive and does not change the wire shape downstream handlers verify.
- **Revocation list.** A DynamoDB table of revoked `user_sub` values, consulted by `validation.ts` before signing. Not needed for V1 (token TTL ≤ 5 min already bounds the blast radius), but a clean extension point if a downstream compliance regime requires explicit revocation.
- **Multi-region key replication.** The V1 key is single-region. If LINQ targets cross-region active-active for the MCP server, KMS multi-region keys provide the simplest replication path; the JWKS endpoint and Lambda code do not change.
