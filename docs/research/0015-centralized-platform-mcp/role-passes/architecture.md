# Role-pass memo: Architecture review (eng-principal)

**Reviewer:** [`eng-principal`](.claude/agents/10-eng-principal.md)
**For:** Decision 0015 — Centralized Platform MCP Server
**Date:** 2026-05-04
**Verdict:** `approve-with-changes`

## Summary

The centralized Platform MCP Server is sound for v1 governance goals (read-only, internal, 4 products, 40–200 handlers) but has architectural smells that will compound at v2 (writes, customer-facing, compliance). Approve-with-changes: tighten the registry to a single responsibility, name the v1/v2 seam explicitly, and pre-decide the federation escape hatch before locking the platform-team-as-bottleneck pattern.

## Findings (concerns)

### 1. Duplicated responsibility — registry table conflates four concerns (HIGH)

The proposed registry record carries `handlerType`, `arn`, `assumeRoleArn`, `requiredScopes`, `inputSchema`, `outputSchema`, `version`, and `owner`. That conflates four orthogonal concerns: (1) tool catalog metadata (input/output schemas, version) — already governed by MCP `tools/list` per [`wiki/entities/mcp-tool-catalog.md`](../../../knowledge/wiki/entities/mcp-tool-catalog.md), (2) authorization policy (`requiredScopes`), (3) infrastructure binding (`handlerType`, `arn`, `assumeRoleArn`), and (4) ownership/governance metadata (`owner`). When any one of these changes — e.g., a product team rotates an `assumeRoleArn` — every reader of the registry is invalidated by definition.

**Recommendation:** Split the registry into three tables with distinct change cadences:
- (a) **Tool catalog** — `name`, `title`, `description`, `inputSchema`, `outputSchema`, `version`, `owner`. Read by `tools/list` responses.
- (b) **Handler binding** — `toolName → {handlerType, arn, assumeRoleArn}`. Operational; may change without a version bump.
- (c) **Authorization policy** — `toolName → requiredScopes, allowedAgentTypes`. Security-team-owned.

The MCP server composes them at call time. This makes blast radius explicit and supports independent ownership.

### 2. Missing seam — v1 read-only → v2 write enforceability (HIGH)

The brief locks v1 to read-only but the proposed flow gives the platform server write capability the moment an IAM policy changes. There is no architectural seam that makes "this is a read-only server" enforceable: no separate write-path planning doc, no annotation discipline (MCP's `readOnlyHint` per [`wiki/entities/mcp-tool-catalog.md`](../../../knowledge/wiki/entities/mcp-tool-catalog.md) is an *untrusted* hint), no proposal for human-in-the-loop on mutations. When v2 adds writes, you will retrofit confirmation/idempotency/audit onto a server already in production, with no test surface to prove read-only-ness held.

**Recommendation:** Make read-only enforceable architecturally:
1. Require every registered tool to declare `side_effects: 'read' | 'write'` in the catalog and have the MCP server **refuse** to register write tools in v1.
2. Reserve a separate URL prefix or a separate MCP server endpoint for mutating tools when v2 lands, so audit, rate-limiting, and idempotency middleware can attach there without touching read paths.
3. Record this seam explicitly in the ADR's Consequences section so v2 is forced to revisit it.

### 3. Missing seam — end-user identity propagation (OBO) (HIGH)

The reference flow describes "authenticate the calling agent (via Auth0)." Per [`wiki/entities/mcp-authorization.md`](../../../knowledge/wiki/entities/mcp-authorization.md), MCP forbids token passthrough — so the central server uses its own M2M identity (per [`wiki/entities/auth0-m2m.md`](../../../knowledge/wiki/entities/auth0-m2m.md)) to call downstream. That works for agent-only operations but loses the human user behind the agent. Phase A gap #2 (RFC 8693 unconfirmed in Auth0, per [`wiki/entities/oauth-token-exchange.md`](../../../knowledge/wiki/entities/oauth-token-exchange.md)) means there is currently no design for "agent X is acting on behalf of user Y" — yet downstream product RBAC almost certainly cares.

**Recommendation:** Pick one of these BEFORE v1 ships, even if the implementation is deferred:
- (a) Propagate user identity as a signed claim inside the MCP request envelope (extension field), and document that handlers MUST treat it as the authorization principal.
- (b) Commit to RFC 8693 delegation tokens once Auth0 support is confirmed, with the `act` claim recorded for audit.
- (c) Explicitly accept that v1 is "agent-as-a-whole" authorization with no user-level RBAC and document the consequence: any user who can invoke an agent gets the union of that agent's permissions.

Option (c) is fine for v1 but only if it is named.

### 4. Leaky abstraction — `handlerType` crossing the agent/platform seam (MEDIUM)

`handlerType` in `{Lambda, ECS, StepFunctions}` is a deployment-substrate detail. If it appears anywhere agent-visible (logs, errors, latency telemetry), agents and their authors will start coupling to it. It also leaks into the platform server's own dispatcher: today a switch over three values; tomorrow when a product wants to add Fargate or an external HTTPS handler, the dispatcher is a closed enum.

**Recommendation:** Hide `handlerType` behind a uniform handler-invocation abstraction. The MCP server calls a single internal `invoke(arn, scopes, input) → output` interface; behind it, an adapter layer dispatches per substrate. Agents see only the MCP tool name. Adding a new substrate is a new adapter, not a new switch case.

### 5. Premature centralization — no federation escape hatch (MEDIUM)

The 4-products × 50-handlers scale (40–200 tools) is well within what a single MCP server can serve. But "single server is the ONLY entry point" is load-bearing for blast radius (one outage stops all agents), platform-team velocity (every product handler change touches a registry the platform team owns), and onboarding cost (every product team must learn the platform's deployment pipeline). The brief's 5–10× growth target (200–2000 handlers, presumably 8–15 products in 3 years) is exactly the scale where federation typically wins.

**Recommendation:** Don't reverse the decision — centralized v1 is right for governance — but pre-design the escape hatch. The handler registry should support `handlerType: 'remote-mcp'` (a handler that itself is an MCP server URL the platform proxies to). Costs ~1 week of design effort now, costs nothing if never used, and converts a future migration into a feature flag. Document this as an explicit Phase B gate condition: when N>X handlers OR Y product teams are bottlenecked on platform-team review, flip a product to remote-mcp mode.

### 6. Missing trade-off — on-call boundary (MEDIUM)

The brief does not specify on-call when a tool fails. Failure modes: (a) registry lookup miss → platform; (b) STS AssumeRole fails → platform OR product (depends on whose IAM is wrong); (c) Lambda 5xx → product; (d) agent-side timeout → ambiguous.

**Recommendation:** Add a one-page on-call matrix to the ADR, keyed by failure stage (auth, registry, dispatch, handler, response). Platform owns auth + registry + dispatch + transport; product owns handler logic + IAM trust policy + downstream resources. The shared seam (STS AssumeRole) is owned by platform but a product-owned IAM misconfiguration is product's escalation. This needs to be in the ADR Consequences section, not invented in incident #1.

### 7. Convention — relationship to ADR 0008 (LOW)

ADR 0008 establishes per-user OAuth via the Atlassian MCP for Confluence/Jira. The new platform MCP design uses Auth0 M2M for all access. This is not a contradiction — they cover different surfaces (external SaaS vs. internal LINQ products) — but the ADR for 0015 should explicitly disambiguate.

**Recommendation:** Add a "Relationship to ADR 0008" subsection: external SaaS = per-user OAuth (0008); internal LINQ products = M2M + STS (0015). State 0008 is **not** superseded.

### 8. Scope — MCP transport choice not documented (LOW; closes Phase A gap #4)

Per [`wiki/entities/mcp-authorization.md`](../../../knowledge/wiki/entities/mcp-authorization.md), the entire OAuth 2.1 / RFC 9728 / RFC 8707 stack only applies to HTTP transport. The proposal implicitly assumes HTTP. Internal-agents-only with all-Claude-Code clients could plausibly use STDIO + a local agent that handles M2M token exchange.

**Recommendation:** Document the transport decision explicitly with rationale, even if HTTP is the right answer (it likely is, for ops dashboards and non-Claude-Code clients).

### 9. Trade-off — External ID inside one AWS Org (LOW; closes Phase A gap #5)

Per [`wiki/entities/sts-assume-role-external-id.md`](../../../knowledge/wiki/entities/sts-assume-role-external-id.md), external IDs are "required" for true multi-tenant third-party scenarios but "optional" for intra-organization cross-account. Using external IDs adds rotation/storage burden for negligible security gain inside one Org, where `aws:PrincipalOrgID` conditions plus IAM Access Analyzer cover the same threat.

**Recommendation:** Default to `aws:PrincipalOrgID`-conditioned trust policies for intra-LINQ cross-account. Keep external IDs as the documented pattern only for any future genuinely-third-party integration.

> **Coordinator note (disagreement to resolve in synthesis):** the Security & IAM lens disagrees and treats External ID as mandatory even intra-Org as a Confused Deputy belt-and-braces. See [`security-iam.md`](security-iam.md). The synthesis must pick.

## Alternatives scored

| Approach | Verdict |
|---|---|
| (a) Federated MCP servers per product with a shared identity broker | rejected — 4× duplicated infra; quality variance; weak governance |
| (b) API Gateway / EventBridge with MCP as a thin adapter | viable — strong if LINQ already has mature API Gateway; forces MCP semantics into request/response shape |
| (c) **Hybrid: thin platform MCP delegating to product-owned MCP servers** | **preferred long-term** — best of both; the proposed design + `handlerType: 'remote-mcp'` reaches this incrementally |
| (proposed) Centralized platform MCP with handler registry + STS dispatch | viable for v1 IF concerns 1–5 are addressed |

## Next steps for the Lead Architect (coordinator)

1. **Update the ADR draft** to: (a) split the registry into catalog / binding / authz tables; (b) name the v1→v2 read-write seam explicitly with an enforceability mechanism; (c) pre-decide the user-identity propagation strategy (commit, defer with named consequence, or punt to extension field); (d) add "Relationship to ADR 0008" partitioning external-SaaS vs. internal-product surfaces.
2. **Add a Phase B gate** to the ADR: `handlerType: 'remote-mcp'` is reserved now, activated when handler count or team count crosses a stated threshold.
3. **Close Phase A gaps in the ADR** — the three "unable to verify" Auth0 dependencies (RFC 9728, RFC 8693, AssumeRoleWithWebIdentity for LINQ topology) must each have a stated fallback recorded in Consequences.

## References

- [`wiki/entities/mcp-tool-catalog.md`](../../../knowledge/wiki/entities/mcp-tool-catalog.md), [`wiki/entities/mcp-authorization.md`](../../../knowledge/wiki/entities/mcp-authorization.md)
- [`wiki/entities/auth0-m2m.md`](../../../knowledge/wiki/entities/auth0-m2m.md), [`wiki/entities/oauth-token-exchange.md`](../../../knowledge/wiki/entities/oauth-token-exchange.md)
- [`wiki/entities/sts-assume-role-external-id.md`](../../../knowledge/wiki/entities/sts-assume-role-external-id.md), [`wiki/entities/lambda-resource-policy.md`](../../../knowledge/wiki/entities/lambda-resource-policy.md)
- [`docs/decisions/0008-mcp-connectors.md`](../../decisions/0008-mcp-connectors.md), [`docs/decisions/0013-karpathy-wiki-pattern.md`](../../decisions/0013-karpathy-wiki-pattern.md)
- Anthropic — [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) — informs the federation-via-broker preference.
- IETF — [RFC 8693 OAuth Token Exchange](https://datatracker.ietf.org/doc/html/rfc8693)
- AWS — [External ID guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user_externalid.html)
