# Risks register

Severity-rated risks consolidated from the five role memos. Each risk lists the source memo, the failure it protects against, and the mitigation either built into the V1 design or required to be added.

## HIGH

### R1 — Tenant leakage at the handler

- **Source.** [`security-iam.md`](role-passes/security-iam.md) R1.
- **What.** A handler that derives `tenant_id` from anywhere except a verified claim or a signed argument can return another tenant's row.
- **Why.** Four product teams write 40–200 handlers; defaults will drift if the platform does not enforce.
- **Mitigation.** Registry **rejects** any handler entry missing a `tenantSourceClaim` field at registration. Handler input contract requires `tenant_id` as a validated argument. The MCP server reads tenant from the user's verified JWT and injects it as a separate, signed argument; the agent cannot supply tenant directly. This is the single largest correctness lever in V1.

### R2 — Confused Deputy across products

- **Source.** [`security-iam.md`](role-passes/security-iam.md) R2; [`architecture.md`](role-passes/architecture.md) concern 9.
- **What.** A registry lookup error or tampered tool ID could route an agent's request through a role assumption into the wrong product account.
- **Why.** Centralized assumer with broad cross-account reach is the textbook Confused Deputy scenario.
- **Mitigation.** Per-product External ID on every cross-account trust policy, even intra-Org; layered with `aws:PrincipalOrgID` SCP guardrail; AWS Access Analyzer enabled on every product account. The architecture review preferred relying on `aws:PrincipalOrgID` alone; the synthesis adopts both layers.

### R3 — Token passthrough vs. MCP spec prohibition

- **Source.** [`security-iam.md`](role-passes/security-iam.md) R3; [`mcp-integration.md`](role-passes/mcp-integration.md) finding 4.
- **What.** A naïve implementation forwards the agent's Auth0 JWT to product Lambdas, violating the MCP spec and giving the product API the wrong audience.
- **Why.** Convenience: avoiding token re-issuance is tempting.
- **Mitigation.** Forbidden in code review and in the platform handler SDK. The MCP server re-issues a downstream identity (RFC 8693 token-exchange or fallback Auth0 Action) and validates audience server-side. Handlers that observe an inbound token whose `aud` is not their expected audience must reject the request.

### R4 — Context-window leak from full-catalog injection

- **Source.** [`mcp-integration.md`](role-passes/mcp-integration.md) HIGH risk; [`mcp-integration.md`](role-passes/mcp-integration.md) finding 5.
- **What.** Every Claude Code session that connects to the Platform MCP loads all advertised tools into context. At 200 handlers, ~50–100k tokens; at 2000 (10× growth target), exceeds usable context.
- **Why.** The MCP `tools/list` response IS the available tool surface handed to the model.
- **Mitigation.** Server-side `tools/list` projection by authenticated principal (`sub` / `client_id`). Agent A in role "support" gets 20 tools; agent B in role "ops" gets 50; no agent gets the full catalog. Spec-compliant — the server chooses what to advertise. **Required before the second product onboards**, not later.

### R5 — Auth0 RFC 9728 (Protected Resource Metadata) support unconfirmed

- **Source.** [`mcp-integration.md`](role-passes/mcp-integration.md) HIGH risk; Phase A gap #1.
- **What.** The MCP authorization spec requires the MCP server to advertise its authorization server via `/.well-known/oauth-protected-resource`. Whether Auth0 supports RFC 9728 is unconfirmed in the wiki.
- **Why.** RFC 9728 is the newest of the five required RFCs and least likely to be supported out-of-the-box.
- **Mitigation.** **Closed by design.** RFC 9728 is the resource server's metadata, not the authorization server's. The MCP server self-hosts `/.well-known/oauth-protected-resource` regardless of Auth0 support, listing Auth0 in `authorization_servers[]` and pointing at Auth0's RFC 8414 metadata. The MCP server returns `WWW-Authenticate: Bearer resource_metadata="..."` on 401. No Auth0 dependency.

### R6 — Auth0 M2M cost explosion

- **Source.** [`cost-reliability.md`](role-passes/cost-reliability.md) HIGH risk.
- **What.** Auth0 bills per Machine-to-Machine application. Naïve "one M2M per handler" or "one M2M per agent instance" makes cost linear in handler or user count and breaks the sub-linear-cost claim.
- **Why.** Auth0 pricing model is per-app, not per-token.
- **Mitigation.** Platform contract mandates **one M2M app per service-identity class** (3–5 total in V1, ~10 at 3-year scale). Per-handler M2M apps are forbidden. Audit M2M app count quarterly.

### R7 — MCP-server availability is the entire system's availability

- **Source.** [`cost-reliability.md`](role-passes/cost-reliability.md) HIGH risk; [`architecture.md`](role-passes/architecture.md) concern 5.
- **What.** Single broker means MCP-server outage = all agent traffic dies.
- **Why.** Architectural choice — centralization is what gives the design its governance properties.
- **Mitigation.** Multi-AZ behind API Gateway + Lambda in V1 (default). Document the "MCP server unavailable — operate without agent automation" degradation playbook before any non-internal user touches it. Multi-region active-passive triggered by external exposure or 99.9% availability target.

### R8 — Runaway agent saturating downstream

- **Source.** [`cost-reliability.md`](role-passes/cost-reliability.md) HIGH risk.
- **What.** One misbehaving agent fires 1000 req/sec → cascades to product handlers → throttles DynamoDB, Lambda concurrency, CloudWatch ingest.
- **Why.** No native backpressure between agent and broker.
- **Mitigation.** Per-agent + per-tool token bucket at the MCP server. Default 10 req/s per agent identity; per-tenant cap; circuit-break per-handler at 5× baseline. Implemented in the API Gateway throttling layer + per-call check at the dispatcher.

## MEDIUM

### R9 — Auth0 RFC 8693 unsupported, OBO collapses to homemade signing

- **Source.** [`security-iam.md`](role-passes/security-iam.md) R4; Phase A gap #2; Open Question Q1.
- **What.** Forces a custom Auth0 Action or a self-signed JWT bridge with a weaker trust ceiling than a real STS.
- **Why.** Auth0 RFC 8693 native support is unconfirmed.
- **Mitigation.** Build the OBO primitive behind an internal `IdentityBroker.exchange()` interface. V1 implementation is an Auth0 Action that mints a short-lived JWT with `act` claim, signed by a Platform-owned KMS asymmetric key. Wire shape is identical to a real RFC 8693 issuance — swappable to native later without breaking handlers. Document the trust trade-off in the handler SDK so it is explicit, not implicit.

### R10 — STS session caching causes stale principal at audit time

- **Source.** [`security-iam.md`](role-passes/security-iam.md) R5; [`platform.md`](role-passes/platform.md) MED risk.
- **What.** A cached 1-h STS session signs requests whose user-context JWT was issued seconds before — but AWS-side audit (CloudTrail) sees only the role session name.
- **Why.** Caching is required for cost and latency; CloudTrail is per-call.
- **Mitigation.** Embed `agent_sub`, `user_sub`, `request_id` in `RoleSessionName` and STS session tags. Correlate with the Platform audit log on `request_id`. Acceptable trade-off because the platform audit log is the authoritative record; CloudTrail is corroborating.

### R11 — `listChanged` storms during multi-team handler deploys

- **Source.** [`mcp-integration.md`](role-passes/mcp-integration.md) MEDIUM risk; [`platform.md`](role-passes/platform.md) MED risk.
- **What.** Four product teams shipping handlers independently can fire many `notifications/tools/list_changed` per hour; each invalidates every connected agent's catalog cache.
- **Why.** Each notification triggers re-fetch on every connected client.
- **Mitigation.** Server-side debounce, coalesce changes within a 30–60 s window. Track per-agent last-fetched cursor and only notify when their visible catalog actually changed.

### R12 — Handler description quality drives agent behavior more than the design admits

- **Source.** [`mcp-integration.md`](role-passes/mcp-integration.md) MEDIUM risk.
- **What.** Tool `description` strings are the LLM's primary signal for when to invoke a handler. Four product teams writing 200 descriptions independently produces inconsistent quality.
- **Why.** Bad descriptions cause wrong-tool selection and skipped tools — both read as "the AI doesn't work."
- **Mitigation.** Description style guide owned by the platform team. CI lint enforces length, schema-coverage, and example presence. Enforced on PR to the handler registry.

### R13 — Asymmetric latency surfaces as agent timeouts

- **Source.** [`platform.md`](role-passes/platform.md) HIGH risk.
- **What.** A Step-Function-backed tool that takes 5 s looks identical to a 200 ms Lambda from the agent's perspective; the agent's per-request budget gets blown silently.
- **Why.** `handlerType` is intentionally hidden from agents.
- **Mitigation.** Per-handler `timeoutMs` in the registry (tier-based default; per-handler override in registry wins). `expectedLatencyP50Ms` exposed in the MCP `description` field so agents can plan. Hard cap at 30 s end-to-end in V1.

### R14 — `inputSchema` / `outputSchema` drift between registry and handler

- **Source.** [`platform.md`](role-passes/platform.md) HIGH risk.
- **What.** A handler bumps its real I/O without bumping the registry schema, and the dispatcher passes through a payload that fails downstream.
- **Why.** Two artifacts (handler code + registry schema) governing one contract.
- **Mitigation.** Contract tests in the handler's repo that diff against the registry's published schema. Fail CI on drift. The platform handler SDK includes a contract-test rig generated from registry schemas.

### R15 — Cold-start latency violating Claude Code timeouts

- **Source.** [`cost-reliability.md`](role-passes/cost-reliability.md) MED risk.
- **What.** Claude Code tool calls have user-perceived deadlines (~3–10 s); MCP cold + handler cold can stack to 1–2 s.
- **Why.** Both compute layers are Lambda; both pay cold-start.
- **Mitigation.** Provisioned concurrency = 2 on MCP-server Lambda **only if** measured P95 > 1500 ms for 7 consecutive days. Publish per-handler warm-pool budgets so product teams can opt in.

### R16 — Cross-account STS quota

- **Source.** [`platform.md`](role-passes/platform.md) MED risk; [`mcp-integration.md`](role-passes/mcp-integration.md) MED risk.
- **What.** AWS STS has account-level rate limits on `AssumeRole`. At 5–10× growth and high agent concurrency, naïve "AssumeRole per call" hits ceilings.
- **Why.** STS is a global service with shared throughput.
- **Mitigation.** Credential cache in the dispatcher keyed on `(productAccount, externalId)`, refreshing at ~80% of session TTL. Track AssumeRole call rate as a top-line SLO. Monitor `ThrottlingException` rate.

### R17 — Registry cache staleness causing handler-not-found 404s

- **Source.** [`cost-reliability.md`](role-passes/cost-reliability.md) MED risk; [`platform.md`](role-passes/platform.md) MED risk.
- **What.** New handlers added to registry but TTL hasn't expired in the MCP-server cache.
- **Why.** 5-minute in-process cache TTL is the default.
- **Mitigation.** TTL + `tools/list_changed` MCP notification on registry write. Opt-in cache bypass header for ops debugging. Two-tier cache (in-process + ElastiCache) keeps cross-replica consistency tight.

### R18 — Cross-account log shipping fails silently

- **Source.** [`cost-reliability.md`](role-passes/cost-reliability.md) MED risk.
- **What.** Subscription filters break, Firehose throttles → audit gap.
- **Why.** Many moving parts on the audit pipeline.
- **Mitigation.** CloudWatch alarm on log-delivery lag. Daily reconciliation job comparing MCP-server request count to audit-log row count.

### R19 — MCP `aud` mis-binding

- **Source.** [`security-iam.md`](role-passes/security-iam.md) R6.
- **What.** If multiple agents share one Auth0 API audience, scope-based separation alone may not suffice.
- **Why.** Easy to ship if registry enforcement is loose.
- **Mitigation.** One Auth0 API per MCP-server URI. Agents differ by `client_id` and `scope` / `permissions` claim. MCP enforces RFC 8707 `resource` parameter binding.

## LOW

### R20 — External ID treated as a secret

- **Source.** [`security-iam.md`](role-passes/security-iam.md) R7.
- **What.** AWS doc is explicit External ID is **not** a secret. Over-securing it builds brittle infra and wastes vault rotation.
- **Mitigation.** Document External ID as identifier, not credential. Rotate only on compromise of the assumer principal, not on schedule.

### R21 — Lambda resource-policy drift

- **Source.** [`security-iam.md`](role-passes/security-iam.md) R8; [`platform.md`](role-passes/platform.md) finding 3.
- **What.** Mixing AssumeRole and resource-based policies arbitrarily makes audit and rotation bimodal.
- **Mitigation.** AssumeRole is the platform default. Lambda resource policies allowed only for narrow patterns (single function, simple invoke) with explicit ADR-style justification per handler.

### R22 — DynamoDB hot partition on registry under cache-miss storm

- **Source.** [`cost-reliability.md`](role-passes/cost-reliability.md) LOW risk; [`platform.md`](role-passes/platform.md) LOW risk.
- **What.** All MCP-server replicas miss cache simultaneously after deploy.
- **Mitigation.** ON_DEMAND billing in V1 (no provisioned-throughput risk). If PROVISIONED later, add jittered cache warm-up. DAX optional if it ever fires.

### R23 — Auth0 outage

- **Source.** [`cost-reliability.md`](role-passes/cost-reliability.md) LOW risk.
- **What.** Auth0 down → no new tokens issued → MCP server cannot authenticate new agent sessions.
- **Mitigation.** 23-h M2M token cache absorbs short Auth0 outages. Document "operate cached" mode. Bypass for break-glass admin.

### R24 — Outbound IP allowlists from agent hosts

- **Source.** [`mcp-integration.md`](role-passes/mcp-integration.md) LOW risk.
- **What.** Some products may IP-allowlist the MCP server's egress; some agent runtimes may IP-allowlist Auth0 or the MCP server.
- **Mitigation.** Document MCP-server egress IPs early. Coordinate with each product's network team during onboarding. The Atlassian MCP wiki entity flags this exact pattern as a recurring foot-gun ([`atlassian-mcp`](../../../knowledge/wiki/entities/atlassian-mcp.md)).

### R25 — Annotation trust drift in V2

- **Source.** [`mcp-integration.md`](role-passes/mcp-integration.md) LOW risk.
- **What.** MCP spec marks annotations as untrusted. V1 read-only sidesteps this; V2 mutating writes will tempt teams to gate destructive ops on `destructiveHint`.
- **Mitigation.** ADR explicitly states V2 must enforce write/destructive policy at the broker, not via annotations. Untrusted gates are not gates.

## Risk-mitigation summary

| Severity | Count | Mitigations built into V1 design | Mitigations requiring follow-up |
|---|---|---|---|
| HIGH | 8 | All 8 have V1-design mitigations |  |
| MEDIUM | 11 | 11/11 documented; 9 require platform-team operational discipline |  |
| LOW | 6 |  | 6/6 are flag-and-watch |

The HIGH-risk count (8) reflects the breadth of the design surface, not incoherence. Every HIGH risk has a named mitigation that is enforceable architecturally (registry constraint, contract requirement) rather than by convention. The single hardest-to-monitor risk is **R6 (Auth0 M2M cost explosion)** — the platform contract bans per-handler M2M apps, but enforcing the ban requires a quarterly audit because Auth0 itself does not flag the antipattern.
