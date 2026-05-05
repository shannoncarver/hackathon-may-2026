# Architecture — components, trust diagrams, reference flows

## Component view

```mermaid
flowchart LR
    subgraph PSA["Platform Services AWS account"]
        APIGW["API Gateway HTTP API"]
        MCP["MCP Server<br/>(Lambda + reserved concurrency)"]
        IB["IdentityBroker<br/>(RFC 8693 contract)"]
        REG[("DynamoDB<br/>Handler Registry")]
        CACHE[("ElastiCache<br/>Redis (15 min)")]
        S3SCH[("S3<br/>Schemas")]
        AUDIT[("CloudWatch Logs<br/>→ Firehose → S3 (Object Lock)")]
    end

    subgraph AUTH0["Auth0 (LINQ tenant)"]
        AUTHM2M["M2M client credentials"]
        AUTHRBAC["User RBAC permissions"]
    end

    subgraph PRODA["Product A AWS account"]
        ROLEA["Cross-account role<br/>External ID + aws:PrincipalOrgID"]
        HANDLA["Handler<br/>(Lambda / ECS / SFN)"]
    end

    subgraph PRODB["Product B AWS account (one per product)"]
        ROLEB["Cross-account role"]
        HANDLB["Handler"]
    end

    AGENT["AI agent<br/>(Claude Code / dev tool / ops dashboard)"]

    AGENT -->|"HTTP/SSE<br/>+ M2M JWT<br/>+ X-User-Token"| APIGW
    APIGW --> MCP
    MCP -->|"validate JWT"| AUTHM2M
    MCP -->|"resolve permissions"| AUTHRBAC
    MCP -->|"GetItem TOOL#"| CACHE
    CACHE -.->|"miss"| REG
    REG --> S3SCH
    MCP -->|"exchange tokens"| IB
    IB -.->|"native if supported"| AUTH0
    MCP -->|"sts:AssumeRole<br/>+ External ID + session tags"| ROLEA
    ROLEA --> HANDLA
    MCP -.->|"alt product"| ROLEB
    ROLEB -.-> HANDLB
    MCP -->|"per-request audit record"| AUDIT
    HANDLA -.->|"correlate via request_id"| AUDIT
```

## Cross-account trust diagram

```mermaid
flowchart LR
    subgraph PSA["Platform Services account (Org member)"]
        MCPROLE["MCP Server IAM role<br/>arn:aws:iam::PLATFORM:role/PlatformMcpServer"]
    end

    subgraph PA["Product A account (Org member)"]
        TPA["Trust policy<br/>Principal: PlatformMcpServer<br/>Condition: ExternalId=ext-a + PrincipalOrgID"]
        RA["PlatformMcpInvoker role<br/>arn:aws:iam::PRODA:role/PlatformMcpInvoker"]
        FA["Handler permissions<br/>(invoke Lambda / RunTask ECS / StartSync SFN)"]
    end

    subgraph PB["Product B account (Org member)"]
        TPB["Trust policy<br/>Principal: PlatformMcpServer<br/>Condition: ExternalId=ext-b + PrincipalOrgID"]
        RB["PlatformMcpInvoker role"]
        FB["Handler permissions"]
    end

    MCPROLE -->|"AssumeRole + ExternalId=ext-a<br/>+ TagSession(tenant_id, user_sub, request_id)"| TPA
    TPA --> RA
    RA --> FA

    MCPROLE -.->|"AssumeRole + ExternalId=ext-b"| TPB
    TPB -.-> RB
    RB -.-> FB

    SCP[/"AWS Organizations SCP<br/>aws:PrincipalOrgID = LINQ-Org<br/>denies non-Platform principals from being added"/]
    SCP --> TPA
    SCP --> TPB
```

**Key elements.**
- One `PlatformMcpServer` IAM role in Platform Services. Trusts no external principal.
- One `PlatformMcpInvoker` role per product account, scoped to that product's handlers.
- Per-product External ID (32-char identifier, registered at onboarding, stored in the registry's product table). Identifier, not credential. Failure mode it protects: Confused Deputy across products under registry tampering or future product spinout.
- `aws:PrincipalOrgID` SCP layered on top — additional defense, prevents non-Org principals from ever being added to a trust policy. Not a substitute for External ID.
- `sts:TagSession` on every AssumeRole carries `tenant_id`, `user_sub`, `agent_client_id`, `request_id`. Tags are attribute-bound — handler IAM policies may reference `aws:PrincipalTag/tenant_id` for an in-IAM tenant guardrail layered under handler-level row checks.

## Reference flow 1 — warm path (cache hits)

```mermaid
sequenceDiagram
    autonumber
    participant Agent as AI agent
    participant MCP as MCP server
    participant Cache as Registry cache
    participant IB as IdentityBroker
    participant STS as STS
    participant Handler as Product handler
    participant Audit as Audit log

    Agent->>MCP: tools/call erp.checkUserAccess<br/>(M2M JWT + X-User-Token)
    MCP->>MCP: validate JWTs (in-process, JWKS cached)
    MCP->>Cache: GetItem TOOL#erp.checkUserAccess
    Cache-->>MCP: handler metadata (in-process hit, ~5ms)
    MCP->>IB: token exchange (subject_token=user, actor_token=agent)
    IB-->>MCP: downstream JWT (act claim, ≤5min TTL)
    MCP->>STS: cached AssumeRole creds (no STS call)
    MCP->>Handler: invoke (Lambda RequestResponse, signed envelope)
    Handler-->>MCP: result + outcome envelope
    MCP->>Audit: per-request record (agent → user → tool → handler → tenant → outcome → latency)
    MCP-->>Agent: tools/call response (structured)
```

Expected latency budget on the warm path: `~200ms P50` end-to-end. STS AssumeRole is not on the path (cached). Registry GetItem is in-process map. Handler P50 is `~100ms`.

## Reference flow 2 — cold path (all caches miss)

```mermaid
sequenceDiagram
    autonumber
    participant Agent as AI agent
    participant MCP as MCP server
    participant Cache as Registry cache
    participant Reg as DynamoDB Registry
    participant S3 as S3 schemas
    participant Auth0
    participant IB as IdentityBroker
    participant STS as STS
    participant Handler as Product handler
    participant Audit as Audit log

    Agent->>MCP: tools/call erp.checkUserAccess
    MCP->>Auth0: validate JWT (cache miss, fetch JWKS)
    Auth0-->>MCP: JWKS
    MCP->>Cache: GetItem TOOL# (miss)
    Cache->>Reg: GetItem
    Reg-->>Cache: handler metadata + schema refs
    Cache->>S3: fetch input/output schemas
    S3-->>Cache: schemas
    Cache-->>MCP: full handler descriptor
    MCP->>IB: token exchange
    IB-->>MCP: downstream JWT
    MCP->>STS: AssumeRole + ExternalId + TagSession
    STS-->>MCP: temporary credentials (1h TTL, cache)
    MCP->>Handler: invoke
    Handler-->>MCP: result
    MCP->>Audit: per-request record
    MCP-->>Agent: tools/call response
```

Expected latency budget on the cold path: `~1500ms P95` end-to-end. STS AssumeRole adds 100–300ms. Registry + S3 schema fetch adds another 50–100ms. JWKS fetch adds 50–100ms. Subsequent calls within the cache windows hit the warm path.

## Reference flow 3 — error: tenant-scope violation

```mermaid
sequenceDiagram
    autonumber
    participant Agent as AI agent
    participant MCP as MCP server
    participant IB as IdentityBroker
    participant Handler as Product handler
    participant Audit as Audit log

    Agent->>MCP: tools/call erp.checkUserAccess (tenant=acme)
    MCP->>MCP: validate JWTs
    MCP->>MCP: resolve user permissions (Auth0 RBAC)
    MCP->>MCP: registry says tenantSourceClaim = user.tenant_id
    MCP->>MCP: read tenant_id from user JWT = "globex" (mismatch)
    MCP-->>Agent: error envelope (class=AUTH, code=TENANT_SCOPE_VIOLATION, retryable=false)
    MCP->>Audit: per-request record (decision=deny, denial_reason=tenant_scope)
```

The MCP server **never** trusts the agent-supplied tenant argument. Tenant is read from the user's verified JWT and injected as a separate, signed handler argument. Mismatch fails before any STS call.

## On-call boundary matrix

| Failure stage | Symptom | Owner | Escalation if not resolved |
|---|---|---|---|
| MCP-server JWT validation | 401 from MCP | Platform | Identity team if Auth0 config issue |
| Registry GetItem | `tools/list` empty or `tools/call` returns NOT_FOUND | Platform | Stop the bus — registry is V1 hot path |
| IdentityBroker / token exchange | 502 with `class=AUTH` | Platform | Identity team if Auth0 RFC 8693 changes |
| STS AssumeRole | 502 with `class=AUTH`, AccessDenied trace | Platform until product IAM trust policy is proven mis-set, then product | Joint debug; trust-policy ownership lives with product |
| Handler invoke (Lambda 5xx) | 502 with `class=UPSTREAM_ERROR` | Owning product team | Stop incidents at handler boundary |
| Handler timeout | 504 with `class=UPSTREAM_TIMEOUT` | Owning product team | Negotiate `timeoutMs` increase via registry update |
| Audit log shipping lag | Audit-delivery alarm | Platform | CloudOps if cross-account log shipping breaks |
| Auth0 outage | Cascading auth failures | Identity team | Platform bypasses with cached tokens within 23h |
| Agent-side timeout | Agent reports MCP timeout | Agent owner first; escalate to Platform if MCP server is responsive | If MCP returned a result and agent timed out, agent owner |

The intent: every failure has exactly one named first-responder. STS AssumeRole is the only joint-owned seam, and ownership flips once the trace points to a product-side trust-policy issue.

## Pillar mapping

This work primarily addresses **Pillar 6 — MCP connector inventory** (architecture for how internal LINQ products surface to AI agents). It also touches Pillar 4 (agent definitions, via the M2M service-identity model). It does not modify Pillar 1 (knowledge base) — but the review's Phase A added wiki entries that future agents will reuse.
