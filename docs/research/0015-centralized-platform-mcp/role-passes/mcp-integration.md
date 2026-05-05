# Role-pass memo: MCP / AI Integration Specialist

**Reviewer:** eng-ai
**For:** Decision 0015 — Centralized Platform MCP Server
**Date:** 2026-05-04

## Findings

1. **Transport choice is the load-bearing decision.** STDIO MCP servers SHOULD NOT use the OAuth 2.1 authorization layer; HTTP/SSE servers SHOULD ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)). A centralized platform server brokering 4 products for internal Claude Code, dev tools, and ops dashboards is multi-tenant by definition, which means HTTP — STDIO is per-process and cannot serve multiple concurrent agents over the network. Recommend HTTP transport, conforming to the 2025-06-18 authorization spec.

2. **MCP SDK version pinning matters because `outputSchema` and `structuredContent` are 2025-06-18 additions.** ([wiki/entities/mcp-tool-catalog.md](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)). Pre-2025-06-18 SDKs cannot emit structured content; clients on older SDKs will ignore it. LINQ's current SDK target is `[ASSUMED]` unconfirmed. Recommend pinning server and reference-client SDKs to a release that implements 2025-06-18 (latest spec), and gating any handler that depends on `structuredContent` until the floor is enforced. Failure mode if older: handlers that return typed payloads degrade to text-only `content[]`, agent-side parsing breaks silently.

3. **Flat namespace will hold at 200 handlers; will not at 2000.** A single `tools/list` page typically returns the entire catalog with no pagination triggered ([wiki/entities/mcp-tool-catalog.md](../../../../knowledge/wiki/entities/mcp-tool-catalog.md) — pagination via `nextCursor` exists but is optional). At 200 handlers, a flat `<product>.<verb><Noun>` convention (e.g. `erp.checkUserAccess`) is fine. At 2000 (10× growth `[CONFIRMED-by-brief]`), a flat list dumps ~2000 tool descriptions into every agent's context — see Finding 5. Recommend per-product prefixes from day one (cheap rename insurance) and route catalog scoping at the discovery layer, not the namespace layer.

4. **Token-passthrough prohibition forces the broker pattern.** MCP servers MUST NOT forward client tokens to upstream APIs; upstream calls require a separately-issued token ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)). The proposed STS AssumeRole into the product account is consistent with this — the MCP server uses its own downstream identity. This is architecturally correct and aligns the design with the spec.

5. **Naive catalog injection will leak ~50–100k tokens at 200 handlers, ~500k–1M at 2000.** Each tool definition carries `name`, `description`, and `inputSchema` ([wiki/entities/mcp-tool-catalog.md](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)). A conservative 250–500 tokens per handler × 200 ≈ 50k–100k tokens; at 2000 handlers that exceeds Claude's context window. Mitigation in Finding 9 below.

6. **`listChanged` works for hot-reload, but agent-side cost is non-trivial.** When a handler is added or versioned, the server emits `notifications/tools/list_changed`; clients SHOULD re-fetch ([wiki/entities/mcp-tool-catalog.md](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)). Each re-fetch invalidates whatever catalog snapshot the agent had. With 4 product teams pushing handlers independently, churn could be hourly during business days, and every agent session that's listening pays the re-injection cost. Recommend the server debounce `list_changed` and emit at most every N seconds, and that clients cache by ETag/version cursor.

7. **For v1's read-only scope, default to `tools` not `resources`.** Tools are model-controlled; Resources are application-driven and URI-addressable ([wiki/sources/mcp-tool-resource-prompt-primitives.md](../../../../knowledge/wiki/sources/mcp-tool-resource-prompt-primitives.md)). Read handlers like `erp.checkUserAccess(userId)` are parameter-driven RPCs — Tools fit. Deviate to Resources only when the read is genuinely URI-addressable and benefits from subscription semantics (e.g. live dashboard streams via `notifications/resources/updated`). For v1's 40–200 handlers, default Tools; reserve Resources for an explicit second-pass review in v1.5.

8. **Annotations are untrusted by spec — server-asserted `readOnlyHint` cannot be the authorization mechanism.** ([wiki/entities/mcp-tool-catalog.md](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)). v1 is read-only `[CONFIRMED-by-brief]` so this is mostly moot now, but flagging for v2: do not let agents (or downstream code) decide write-vs-read by annotation alone. The platform's authz layer must be the source of truth.

9. **Catalog scoping pattern (recommended).** Add a non-spec'd `?capability=<scope>` or `?role=<agent-id>` query parameter on the MCP server's HTTP endpoint. The server filters `tools/list` by the agent's identity (from the OAuth token's `sub` or M2M `client_id`). Agent A in role "support" gets ~20 handlers; agent B in role "ops" gets ~50; no agent gets the full 200. This is invisible to the MCP protocol — it's a server-side projection of the catalog, keyed off the authenticated principal. Spec-compliant because `tools/list` returns only the tools the server chooses to advertise to that client. Cost: 5–10× context savings.

10. **Atlassian MCP is not a precedent for this design.** Atlassian MCP is per-user OAuth 2.1 with Dynamic Client Registration, scoped to one tenant's data, and the user's permissions are the authorization boundary ([wiki/entities/atlassian-mcp.md](../../../../knowledge/wiki/entities/atlassian-mcp.md)). The proposed Platform MCP Server is M2M (Auth0 client credentials) for the agent identity plus token-exchange or STS for downstream impersonation across 4 product accounts. Different pattern. See Finding 13 on naming.

11. **No widely-cited multi-tenant or multi-account MCP reference implementation exists yet.** No clear source — common-practice claim based on the field's current maturity. The spec is 2025-06-18 (under one year old). Atlassian MCP ([wiki/entities/atlassian-mcp.md](../../../../knowledge/wiki/entities/atlassian-mcp.md)) is the closest production multi-tenant reference and uses a different auth model. This is signal: LINQ will be ahead of public reference patterns and should expect to contribute back, not copy.

12. **Latency target: P95 ≤ 800ms for read handlers; STS AssumeRole is the most expensive hop.** No clear source — common-practice claim. STS AssumeRole adds 100–300ms when uncached; Lambda cold start adds 200–1000ms. Mitigations: (a) cache STS credentials per role for the credential lifetime (typically 1h), reusing across agent calls — this collapses the AssumeRole cost from per-call to per-hour; (b) provisioned concurrency on hot Lambdas, or move handlers off Lambda for top-decile traffic; (c) connection-pool the cross-account HTTP path. With these, P95 ≤ 800ms is realistic; without STS caching, P95 will sit at 1.5–2s and MCP client default timeouts (often 30–60s) will mask but not solve user-perceived latency.

13. **Pattern name (if different from ADR 0008).** "Auth0-fronted MCP broker with cross-account credential exchange." Captures: agent identity = Auth0 M2M, downstream identity = STS-assumed product role, broker = single MCP server. Distinguish from ADR 0008's "per-user OAuth 2.1 with downstream user-bound tokens" pattern. Both are spec-compliant; they solve different problems (per-user data scoping vs. service-to-service brokering).

## Risks

**HIGH — Context-window leak from full-catalog injection.**
What: Every Claude Code session that connects to the Platform MCP loads all advertised tools into context. At 200 handlers ≈ 50–100k tokens; at 2000, exceeds usable context.
Why: The MCP `tools/list` response is what gets handed to the model as the available tool surface ([wiki/entities/mcp-tool-catalog.md](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)).
Mitigation: Implement role-/capability-scoped `tools/list` projection (Finding 9) before any second product onboards. Validate with a token-budget eval that captures `tools_payload_tokens` per agent type.

**HIGH — Auth0 RFC 9728 (Protected Resource Metadata) support is unconfirmed.**
What: The MCP authorization spec requires the MCP server to advertise its authorization server via `/.well-known/oauth-protected-resource` ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)). RFC 9728 is the newest of the five required RFCs and least likely to be supported out-of-the-box.
Why: If Auth0 doesn't support RFC 9728 directly, LINQ must serve the metadata document from the MCP server itself, pointing at Auth0's RFC 8414 metadata. This is doable but adds an implementation requirement that's easy to miss.
Mitigation: Spike RFC 9728 support in the Auth0 tenant before lock-in. If unsupported, document the MCP-server-hosted metadata document pattern explicitly in the ADR.

**HIGH — Token-passthrough prohibition vs. STS AssumeRole cross-account hop.**
What: The spec prohibits forwarding the client's token to upstream APIs ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)). Proposal uses STS AssumeRole to obtain its own downstream identity — compliant — but the audit trail must still reflect the originating agent identity, or every product team's logs see the platform IAM role and lose attribution.
Why: Without per-call attribution, debugging and abuse-detection are blind.
Mitigation: Pass the agent's `sub` (or M2M `client_id`) as a session tag on `AssumeRoleWithWebIdentity` (or in the request payload to the Lambda). Require all 4 product handlers to log this tag.

**MEDIUM — `listChanged` storms during multi-team handler deploys.**
What: 4 product teams shipping handlers independently can fire many `notifications/tools/list_changed` per hour.
Why: Each notification triggers re-fetch on every connected client ([wiki/entities/mcp-tool-catalog.md](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)).
Mitigation: Server-side debounce (coalesce changes within a 30-60s window) and emit a single notification per window.

**MEDIUM — Handler description quality drives agent behavior more than the design admits.**
What: Tool `description` strings are the LLM's primary signal for when to invoke a handler ([wiki/entities/mcp-tool-catalog.md](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)). 4 product teams writing 200 descriptions independently produces inconsistent quality.
Why: Bad descriptions cause wrong-tool selection and skipped tools — both read as "the AI doesn't work."
Mitigation: Description style guide + a CI lint that validates length, schema-coverage, and example presence. Owned by the platform team, enforced on PR to the handler registry.

**MEDIUM — STS AssumeRole on the hot path.**
What: Per-call AssumeRole adds 100–300ms (no clear source — common-practice claim) and AWS rate-limits AssumeRole.
Why: At 5–10× growth and high agent concurrency, AssumeRole quota becomes a bottleneck.
Mitigation: Per-role credential caching (Finding 12). Track AssumeRole call rate as a top-line SLO.

**LOW — Outbound IP allowlists from agent hosts.**
What: Some products may IP-allowlist the MCP server's egress; some agent runtimes may IP-allowlist Auth0 or the MCP server. The Atlassian MCP entity flags this exact pattern as an outbound-IP gotcha ([wiki/entities/atlassian-mcp.md](../../../../knowledge/wiki/entities/atlassian-mcp.md)).
Why: An invisible foot-gun at production cutover.
Mitigation: Document MCP-server egress IPs early; coordinate with each product's network team during onboarding.

**LOW — Annotation trust drift in v2.**
What: Spec says annotations are untrusted ([wiki/entities/mcp-tool-catalog.md](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)). v1 read-only sidesteps this; v2 mutating writes will tempt teams to gate destructive ops on `destructiveHint`.
Why: Untrusted gates aren't gates.
Mitigation: Note in the ADR that v2 must enforce write/destructive policy at the broker, not via annotations.

## Recommendation

Adopt the design with three non-optional changes. First, transport: HTTP/SSE, not STDIO — STDIO can't serve a multi-agent platform, and the proposal's authorization story only works on HTTP per spec ([wiki/entities/mcp-authorization.md](../../../../knowledge/wiki/entities/mcp-authorization.md)). Second, ship role-/capability-scoped `tools/list` projection in v1 — without it, the 10× growth path slams the context window and the design fails on its second product onboard, not its tenth. Third, cache STS credentials per assumed role and propagate the agent identity as a session tag — this addresses both the latency floor and the audit-attribution gap that token-passthrough prohibition opens.

V1 should pin to the 2025-06-18 MCP spec, default to `tools` (not `resources`) for the read-only handler set, use per-product prefix namespacing (`erp.*`, `crm.*`), and not emit `outputSchema`/`structuredContent` until the platform team commits to a typed-output style guide. Name the pattern explicitly — "Auth0-fronted MCP broker with cross-account credential exchange" — to distinguish it from ADR 0008's per-user OAuth pattern; both belong in LINQ's MCP catalog and they are not substitutes.

## Open questions for Lead Architect

- **Does Auth0 (LINQ tenant) support RFC 9728 Protected Resource Metadata directly?** If forced to decide today: assume no, and have the MCP server host `/.well-known/oauth-protected-resource` itself, pointing at Auth0's RFC 8414 metadata.
- **Which MCP SDK version is LINQ standardizing on?** If forced to decide today: target the latest 2025-06-18-compliant release; reject any agent runtime pinned below that floor.
- **Is the v1 catalog scoped per-agent at the platform layer, or does each agent runtime filter client-side?** If forced to decide today: server-side projection keyed off OAuth `sub` / M2M `client_id` — client-side filtering still pays the context cost.
- **What's the SLO target for AssumeRole call rate against the 4 product accounts?** If forced to decide today: 50 req/s per role with credential caching enabled, validated against AWS account-level AssumeRole quotas.
- **Are agent identities long-lived M2M clients (one per agent type) or short-lived (one per session)?** If forced to decide today: long-lived per agent type — Dynamic Client Registration is overkill for an internal-only roster, and per-session clients balloon the M2M client count in Auth0 with no auth benefit.
- **Does ADR 0008's "per-user OAuth" pattern coexist with this broker pattern, or supersede it for any product?** If forced to decide today: coexist — Atlassian MCP-style per-user is right for products where the user's permissions are the authorization boundary; broker-with-STS is right for service-to-service reads. Decision per-product, documented in each product's onboarding ADR.
