# Implementation plan — Tool Search support (ADR 0017)

**Status:** Draft awaiting plan approval. Mission Phase 4 (code) gated on user sign-off.
**Date:** 2026-05-05
**Owner:** Backend / MCP Server Engineer (with Platform Engineer for registry-seed work).
**Lands in:** `linq-platform-mcp` repo (sibling repo). The 23 tasks span ADR 0015's M1 Phase C and M2 milestones; integration tests light up at M4. See [Milestone mapping](#milestone-mapping) below.
**Effort estimate:** ~10–11 hours of focused work across 23 tasks (excluding human-checkpoint pauses).

> **Terminology note.** *Mission Phases 1–4* are the stages of the mission that produced this plan (Research, Design Doc, Implementation Plan, Implementation). *M1–M6* are ADR 0015's implementation milestones for the platform MCP server itself. The two are unrelated; this document uses **mission Phase X** when referring to mission stages and **M1 Phase C** / **M2** / **M4** when referring to ADR 0015 milestones. Each task below is tagged with its ADR 0015 milestone home in square brackets — for example `[M1-C]`.

## Goal and exit criteria

Implement [ADR 0017](../../decisions/0017-tool-search-support.md) across M1 Phase C and M2 of the platform MCP server, with integration tests landing at M4. Exit criteria:

1. `platform.search_tools`, `platform.whoami`, and `platform.list_products` are seeded in the registry, pass `mcp-handler-lint`, and dispatch end-to-end against a real Auth0 M2M token.
2. `routes/tools-search.ts` returns ≤5 `tool_reference[]` blocks for a representative regex query, applying per-`client_id` projection before regex.
3. `tools/list` accepts `cursor` and emits `nextCursor` for forward-compat with MCP `2025-06-18` pagination.
4. Audit records carry the new `tools_loaded_via_search: string[]` field; platform tools emit audit records without `tenant_id`.
5. All seven tests in [ADR 0017 §Phase-2 implementation](../../decisions/0017-tool-search-support.md#phase-2-implementation) pass: functional, RBAC negative, tenant-scope negative, read-only negative, fallback, pagination, audit.
6. Existing ADR 0015 acceptance criteria remain green (especially AC3, AC5, AC7, AC8).
7. Client-side SDK helper at `sdk/client/typescript/src/defer-loading-helper.ts` exists, with one usage example in the README.

## Milestone mapping

ADR 0015's implementation roadmap moves through six milestones (M1–M6). ADR 0017's 23 tasks land in three of them, with no work in M3 or M5–M6:

| ADR 0015 milestone | Status today | Tool Search tasks here | What this milestone delivers |
|---|---|---|---|
| **M1 Phase A** — repo scaffold | ✅ Done (2026-05-04) | none | Empty package layout |
| **M1 Phase B** — bootstrap CFN + GHA OIDC | ✅ Done (2026-05-05) | none | Cross-account OIDC trust round-trip |
| **M1 Phase C** — MCP server code, 10-step pipeline, audit, errors | 🔄 Next | T1, T2, T3, T9, T11, T12, T13, T14, T15, T16, T19, T20, T21, T22 (server-side: types, search route, pagination, platform-tool dispatch, audit field, SDK helper, docs) | Lambda + JSON-RPC dispatcher per [`03-mcp-server.md`](../0015-centralized-platform-mcp/implementation/03-mcp-server.md) |
| **M2** — Registry + auth gates, `tools/list` projection | Not started | T4, T5, T6, T7, T8, T10 (registration-API exemption, three platform seed items, CFN custom-resource wiring, registry search method) | DynamoDB registry + projection + lint per [`04-registry.md`](../0015-centralized-platform-mcp/implementation/04-registry.md) |
| **M3** — IdentityBroker + cross-account dispatch | Not started | **None.** Platform tools are in-process and never cross account boundaries; they explicitly bypass steps 7 (broker), 8 (STS), and 9 (handler dispatch) of the 10-step pipeline. M3's machinery is orthogonal to this ADR. | KMS-signed JWT, STS session cache, cross-account assume-role |
| **M4** — E2E happy path | Not started | T17, T18, T23 (integration / contract tests + final PR) light up here once `erp.checkUserAccess` is dispatchable end-to-end | First E2E `tools/call` against a real product handler |
| **M5/M6** | Not started | none | Negative-test hardening, audit reconciliation, runbooks |

**Why nothing lands in M3.** The three platform tools (`platform.search_tools`, `platform.whoami`, `platform.list_products`) read the registry and the verified principals, then return data. They never invoke a product handler, so they don't need IdentityBroker token exchange, STS assume-role, or cross-account dispatch. ADR 0017 introduces a new `handlerType: "platform-internal"` (T2) precisely so the dispatcher can route these tools without touching M3's seams.

**Why some tasks span M1 Phase C and M2.** A task like T10 (registry search method) modifies code that ships in M1 Phase C (`registry.ts`) but depends on a method that lands in M2 (`listToolsForClient` projection). The convention below is to tag each task by *where the file the task changes lives in the milestone roadmap*, not by what it depends on. Where dependencies cross milestones, the task body calls them out.

**Why integration tests slip to M4.** T17 and T18 hit `tools/call` against `erp.checkUserAccess` and a 100-tool projection respectively. Neither can run end-to-end before M4 lights up the first product handler. Until then, T17/T18 are scaffolded as fixture-driven contract tests in M1 Phase C and promoted to integration tests at M4.

## Dependencies on ADR 0015 milestone scope

The Tool Search work *adds* to ADR 0015's existing scope — it does not replace anything. Tasks below explicitly mark which files are net-new (this work) versus modified (existing milestone scope + this work).

**Coordination touchpoint:** before T1, confirm with M1 Phase C and M2 owners that the additional ~10 hours fits across both milestones, and that branch naming + PR cadence align. Single coordinated PR series spanning M1-C and M2 preferred over rebase merges if both milestones are owned by the same person; two coordinated PR series otherwise (M1-C tasks first, then M2 tasks once the registry is deployed).

---

## Tasks

Each task ≤30 minutes of focused work. Files use absolute repo-relative paths inside `linq-platform-mcp`.

### Phase A — Types and schema

**T1 [M1-C, M2 — coordination] — M1 Phase C and M2 scope coordination (15 min, human checkpoint).**
Confirm with M1 Phase C and M2 owners that ADR 0017 work merges into their respective PR series. Confirm branch strategy, test framework (Jest assumed), and review cadence across both milestones. **No code changes. Output: short Slack/PR comment recording the alignment.**
- Files: none.
- Tests: none.
- AC: M1 Phase C and M2 owners have acknowledged in writing.
- Rollback: N/A — coordination only.
- ⏸ **CHECKPOINT:** human must confirm milestone absorption (both M1-C and M2) before T2.

**T2 [M1-C] — Add `handlerType: "platform-internal"` to registry-types package (20 min).**
- Files: `linq-platform-mcp/sdk/handler/typescript/src/registry-types.ts` (modify) — extend `HandlerType` enum to include `"platform-internal"`.
- Tests: `sdk/handler/typescript/tests/registry-types.test.ts` (new or extend) — type-narrowing case.
- AC: `tsc` passes against the registry-types package; existing handler types remain valid.
- Rollback: revert the enum change; downstream code reverts cleanly because none consumes `"platform-internal"` until T9.

**T3 [M1-C] — Add `tools_loaded_via_search` field to audit-record type (15 min).**
- Files: `linq-platform-mcp/sdk/handler/typescript/src/audit-types.ts` (modify) — add `tools_loaded_via_search?: string[]` to `AuditRecord` type.
- Tests: `audit-types.test.ts` — type-shape assertion.
- AC: type compiles; existing audit-emitting code remains valid (field is optional).
- Rollback: revert the field addition.

### Phase B — Registration API and registry seeds

**T4 [M2] — Allow `platform.*` namespace to skip `tenantSourceClaim` in the registration API (25 min).**
- Files: `linq-platform-mcp/src/registration-api/handler.ts` (modify) — at step 3 of the gate per [04-registry.md §2.4](../0015-centralized-platform-mcp/implementation/04-registry.md), wrap the `TENANT_SOURCE_CLAIM_REQUIRED` check in `const isPlatform = item.toolId.startsWith("platform.");` so platform tools are exempt. Add the same exemption at lint rule `DESC005-schema-parity` (no required input fields ⇒ no parity check) — actually DESC005 already passes if `required: []`, so no lint change needed. Document the exemption inline.
- Tests: `tests/contract/platform-namespace-tenant-exemption.test.ts` — POST a `platform.*` item without `tenantSourceClaim` returns 201; POST a non-platform item without `tenantSourceClaim` still returns 400.
- AC: contract tests pass; existing 0015 ADR R1 tests still pass for non-platform tools.
- Rollback: revert the conditional. Registry items with `tenantSourceClaim: ""` would then fail to register; the three platform seed items in T5–T7 must be deleted before rollback.

**T5 [M2] — Author `platform.whoami` registry seed item (20 min).**
- Files: `linq-platform-mcp/src/registration-api/seed-items/platform-whoami.json` (new).
- Item shape: `{ toolId: "platform.whoami", version: "1.0.0", status: "active", handlerType: "platform-internal", title: "Identity echo", description: "Read-only. Returns the verified user sub, agent client_id, tenant_id, scope set, and permission set for the current request. Use this when an agent needs to confirm its identity context — for example before deciding which product to query. Do NOT use this to look up a different user (see iam.lookupUser).", inputSchemaRef: "s3://platform-mcp-schemas/platform.whoami/1.0.0/input.json", outputSchemaRef: "s3://platform-mcp-schemas/platform.whoami/1.0.0/output.json", sideEffects: "read", idempotent: true, tenantSourceClaim: "", timeoutMs: 1000, requiredScopes: ["platform:identity:read"], requiredPermissions: [], visibility: { agentIdentities: ["*"] }, owner: "platform" }`.
- Schemas: also create `input.json` (`{ "type": "object", "properties": {}, "additionalProperties": false }`) and `output.json` (object with `sub`, `client_id`, `tenant_id`, `scope[]`, `permissions[]`).
- Tests: `tests/fixtures/seed-items/platform-whoami.test.ts` — runs `mcp-handler-lint` against the item, asserts zero errors.
- AC: lint passes (description hits all DESC001–009 rules); JSON Schema validates both input.json and output.json.
- Rollback: delete the seed item file. CFN custom resource removes the registry row.

**T6 [M2] — Author `platform.list_products` registry seed item (20 min).**
- Files: `linq-platform-mcp/src/registration-api/seed-items/platform-list-products.json` (new) + matching schemas.
- Description: starts with `"Read-only. Lists the LINQ product namespaces ..."`. Returns array of `{ namespace, displayName, description, toolCount }`.
- Tests: same pattern as T5.
- AC: lint passes; output schema validates.
- Rollback: delete file; remove registry row.

**T7 [M2] — Author `platform.search_tools` registry seed item (25 min).**
- Files: `linq-platform-mcp/src/registration-api/seed-items/platform-search-tools.json` (new) + schemas.
- Description: starts with `"Read-only. Searches the platform tool registry for handlers matching a Python regex. Returns up to 5 tool references that the API will auto-expand into full definitions."` Input: `{ query: string (max 200), limit?: number (max 5, default 5) }`. Output: array of `{ tool_name: string }` (matches MCP `tool_reference` shape — a content-block fragment, not a result envelope; the route assembles the wire shape).
- Tests: lint pass, schema validation, plus an extra check that the description names `query` (DESC005 schema parity).
- AC: lint passes including DESC005 (since `query` is required and named in the description).
- Rollback: delete file. Removing this seed is the kill-switch per ADR 0017.

**T8 [M2] — Wire the three new seeds into the `04-registry-seed` CFN custom resource (25 min).**
- Files: `linq-platform-mcp/infra/stacks/04-registry-seed.yaml` (modify) — add three CFN custom-resource invocations after the existing `erp.checkUserAccess` seed. Order: `platform.whoami`, `platform.list_products`, `platform.search_tools`.
- Tests: stack synthesis (`sam validate`) passes; deploy to dev account leaves three new rows in `platform-mcp-handler-registry-dev`.
- AC: post-deploy `aws dynamodb get-item` retrieves all three rows; existing ERP item unchanged.
- Rollback: revert the YAML changes; redeploy clears the three rows. (Items are independent — partial rollback per item is also possible by removing one custom-resource invocation.)
- ⏸ **CHECKPOINT:** human review of the deployed registry rows in dev before proceeding to the M1-C server-side tasks (T9 onwards).

### Phase C — `routes/tools-search.ts`

**T9 [M1-C] — Scaffold `routes/tools-search.ts` (30 min).**
- Files: `linq-platform-mcp/src/mcp-server/routes/tools-search.ts` (new).
- Surface: `export async function handleToolsSearch(args: { agent: AgentPrincipal; user: UserPrincipal; query: string; limit?: number; rpcId: unknown; requestId: string }): Promise<APIGatewayProxyResultV2>`. **Not** a JSON-RPC method; this is the in-process implementation that `routes/tools-call.ts` invokes when the tool id is `platform.search_tools`. Returns the wire-shape `tool_reference[]` array embedded in a `content` block per Anthropic's spec.
- Tests: skeleton test file with `describe("handleToolsSearch")` ready for population in T11/T12.
- AC: file exists, exports the function signature, `tsc` passes.
- Rollback: delete file. No callers yet, so isolated.

**T10 [M1-C; depends on M2 `listToolsForClient`] — Add `searchToolsForClient(client_id, scope, regex, limit)` to `registry.ts` (25 min).**
- Files: `linq-platform-mcp/src/mcp-server/registry.ts` (modify) — add a method that (a) calls existing `listToolsForClient(client_id, scope)` (which lands in M2 as part of `tools/list` projection) to apply per-principal projection first, then (b) regex-filters the projected list against tool `name` and `description`, returning the top `limit` (default 5, max 5) matches.
- Tests: unit test in `tests/registry.test.ts` — given a mock projection of 10 tools, regex `^erp\..*` returns the right subset; case-sensitivity holds; `(?i)` flag works; invalid regex throws a typed error `INVALID_PATTERN`.
- AC: tests green; new method does not bypass projection (regression test: caller with no scopes gets empty).
- Rollback: revert registry.ts changes. tools-search.ts will fail to compile until T9 is also reverted (acceptable — they ship together).

**T11 [M1-C] — Implement `handleToolsSearch` body (30 min).**
- Files: `linq-platform-mcp/src/mcp-server/routes/tools-search.ts` (modify).
- Logic: validate query length ≤ 200; call `registry.searchToolsForClient(...)`; map matches to `tool_reference[]` blocks; emit audit record (decision: allow); return the `content[]` envelope. On `INVALID_PATTERN`: emit deny audit, return 400 with rpc error code per `errors.ts`.
- Tests: unit tests covering happy path, empty result, invalid regex, query too long, projection-first ordering.
- AC: all tests green; audit records contain `tool: { id: "platform.search_tools", version: "1.0.0" }` and zero `tenant_id`.
- Rollback: revert function body; the scaffold from T9 remains.

**T12 [M1-C] — Add per-call rate limit on `platform.search_tools` (15 min).**
- Files: `linq-platform-mcp/src/mcp-server/routes/tools-search.ts` (modify) — call `rateAllow(agent.client_id, "platform.search_tools")` at top, return `RATE_LIMITED` if false.
- Tests: rate-limit test fires 11 requests in 1s; the 11th is denied.
- AC: token bucket honored; default 10/s per `(client_id, "platform.search_tools")`.
- Rollback: revert the rate-limit call. Search becomes unlimited but otherwise functional.

### Phase D — Pagination and platform-tool dispatch

**T13 [M1-C] — Add `cursor` parameter to `routes/tools-list.ts` (25 min).**
- Files: `linq-platform-mcp/src/mcp-server/routes/tools-list.ts` (modify per [03-mcp-server.md §2.9](../0015-centralized-platform-mcp/implementation/03-mcp-server.md)).
- Logic: read `params.cursor` (optional, opaque base64-encoded string with the last-seen tool id); if absent, return first page; if present, return tools alphabetically after the cursor. Emit `nextCursor` if more pages exist; omit otherwise.
- Page size: env var `TOOLS_LIST_PAGE_SIZE` default 50.
- Tests: unit test with 100-tool projection — three pages, last `nextCursor` undefined.
- AC: round-trip pagination is loss-less and order-stable; unknown cursor returns empty page (not error).
- Rollback: ignore `params.cursor` in the route and stop emitting `nextCursor`. Behavior reverts to flat list (still spec-compliant since pagination is optional).

**T14 [M1-C] — Wire platform-tool dispatch in `routes/tools-call.ts` (30 min).**
- Files: `linq-platform-mcp/src/mcp-server/routes/tools-call.ts` (modify per [03-mcp-server.md §2.5](../0015-centralized-platform-mcp/implementation/03-mcp-server.md)).
- Logic: at top of `handleToolsCall`, after JWT validation but before registry lookup, branch on `params.name.startsWith("platform.")`. For platform tools, call a new `dispatchPlatformTool(toolId, agent, user, params)` helper. The helper calls into `routes/tools-search.ts` for `platform.search_tools`, into `index.ts`-internal `whoami(agent, user)` and `listProducts(agent)` helpers for the other two. Skip steps 4 (tenant-scope), 7 (broker), 8 (STS), 9 (handler dispatch) because platform tools have no tenant data and no cross-account dispatch. Steps 1–3, 5, 6, and 10 (auth, registry lookup, authz, schema, sideEffects, output validate + audit) still apply.
- Tests: contract test for each of the three platform tools — happy path returns expected shape; insufficient scope returns `AGENT_SCOPE_DENIED`.
- AC: all three platform tools dispatch correctly; non-platform tools take the unchanged 10-step path.
- Rollback: remove the platform-tool branch. Platform tools then fail at step 4 because `tenantSourceClaim` is empty.

**T15 [M1-C] — Implement `whoami` and `listProducts` in-process helpers (20 min).**
- Files: `linq-platform-mcp/src/mcp-server/platform-handlers.ts` (new).
- `whoami(agent, user)`: returns `{ sub, client_id, tenant_id, scope, permissions }` from the verified principals. No registry lookup, no STS.
- `listProducts(agent)`: calls `registry.listProductsForClient(agent.client_id, agent.scope)` (a new registry method that returns distinct namespace prefixes from the projected catalog). Returns `[{ namespace, displayName, description, toolCount }]`.
- Tests: unit tests for both helpers with mock principals.
- AC: outputs validate against the registry's `outputSchema` for each tool.
- Rollback: delete the file. T14's branch falls through to error per the missing case.

### Phase E — Audit and telemetry

**T16 [M1-C] — Wire `tools_loaded_via_search[]` into the audit record (25 min).**
- Files: `linq-platform-mcp/src/mcp-server/audit.ts` (modify per [03-mcp-server.md §2.6](../0015-centralized-platform-mcp/implementation/03-mcp-server.md)) — accept the new optional field on `emitAudit` calls; default empty array.
- `routes/tools-call.ts` (modify): at the start of `handleToolsCall`, look up the request session's recently-emitted `platform.search_tools` audit records (within 5 min via the existing in-process cache) and check whether the tool now being invoked appears in those results. If so, append the tool id to `tools_loaded_via_search` on this call's audit record.
- Tests: integration test — invoke `platform.search_tools`, then invoke a discovered tool; assert the second call's audit record contains the discovered tool id in `tools_loaded_via_search`.
- AC: positive and negative integration tests pass; field defaults to empty when no recent search.
- Rollback: drop the field assignment. Audit records still emit; only the new field is missing.

⏸ **CHECKPOINT (after T16):** human review of an end-to-end happy-path trace (search → tool_call) against the dev account before proceeding to test hardening.

### Phase F — Tests, SDK helper, and docs

**T17 [M4 — scaffolded in M1-C as fixture-driven contract tests] — Negative tests: RBAC, tenant-scope, read-only, fallback (30 min).**
- Files: `linq-platform-mcp/test/contract/tool-search-negative.test.ts` (new).
- Cases:
  1. RBAC: agent without `erp:read` searches `^erp\..*`, gets empty result (never the existence of an unauthorized tool).
  2. Tenant-scope: search-discovered tool invoked with mismatched tenant returns `TENANT_SCOPE_VIOLATION` per [03-mcp-server.md §2.5](../0015-centralized-platform-mcp/implementation/03-mcp-server.md) step 4.
  3. Read-only: registry rejects any seed item with `sideEffects: "write"` (existing test); search never surfaces a write-marked tool because none can be registered.
  4. Fallback: simulate a non-supporting client (raw `tools/list` without invoking `platform.search_tools`); assert flat catalog is returned.
- AC: all four cases pass.
- Rollback: N/A — tests only.

**T18 [M4 — scaffolded in M1-C as fixture-driven contract tests] — Pagination round-trip test (15 min).**
- Files: `linq-platform-mcp/test/contract/tools-list-pagination.test.ts` (new).
- Case: seed 100 mock tools; page through with `pageSize=25`; assert exactly 4 pages, no duplicates, no missing tools, last `nextCursor` undefined.
- AC: passes.
- Rollback: N/A.

**T19 [M1-C] — TypeScript SDK helper for client-side `defer_loading` (25 min).**
- Files: `linq-platform-mcp/sdk/client/typescript/src/defer-loading-helper.ts` (new); `package.json` for the package (new).
- Surface: `export function withDeferLoading(toolsFromMcp: McpTool[]): AnthropicTool[]` — wraps each MCP tool definition into the Messages API tool shape. Tools whose name starts with `platform.` are emitted as-is (always-loaded). All other tools get `defer_loading: true`. Caller is responsible for adding `tool_search_tool_regex_20251119` separately.
- Tests: unit test asserts platform-namespace tools are not deferred, others are.
- AC: helper exported, tested, type-safe.
- Rollback: delete the package. Clients fall back to building tool definitions by hand (existing approach).

**T20 [M1-C] — README example for the SDK helper (15 min).**
- Files: `linq-platform-mcp/sdk/client/typescript/README.md` (new) — short usage example showing the helper consuming `tools/list` output and producing a Messages API request.
- Tests: N/A (docs only).
- AC: example is copy-pasteable and `tsc`-clean against `@anthropic-ai/sdk` types.
- Rollback: delete file.

**T21 [M1-C] — Top-level `linq-platform-mcp/README.md` mention of Tool Search (15 min).**
- Files: `linq-platform-mcp/README.md` (modify) — add a one-paragraph blurb under "Features" pointing at ADR 0017 and the SDK helper.
- Tests: N/A.
- AC: section present; link to ADR resolves.
- Rollback: revert the section.

**T22 [M1-C, M2] — `CHANGELOG.md` entry (10 min).**
- Files: `linq-platform-mcp/CHANGELOG.md` (modify).
- Entry: M1 Phase C row gains "Tool Search server route + cursor pagination + `tools_loaded_via_search` audit field per ADR 0017"; M2 row gains "three `platform.*` registry seed items + registration-API exemption per ADR 0017".
- Tests: N/A.
- AC: entry committed alongside the code.
- Rollback: revert.

### Phase G — Final review and merge

⏸ **CHECKPOINT (T23) [M4]:** human review of the full PR series before merge.
- Files: PR description authored at `gh pr create` time, summarizing token impact (cite Anthropic's 85% claim — no LINQ-side measurement per ADR 0017's Q10 disposition), security analysis (link to ADR 0017's Phase-2 implementation section), and rollback plan (delete `platform.search_tools` seed item).
- AC: PR has approval from one reviewer outside the work; CI green (Jest + sam validate + cfn-lint); ADR 0017 status notes the merged commit hash.
- Rollback (post-merge): revert the PR series. Seed items disappear from the registry on next CFN deploy. SDK helper package is independent — leaving it published does not break callers since it is additive.

---

## Risks and watch-list

- **M1 Phase C / M2 scope creep.** If either milestone absorbs work beyond ADR 0015's scaffold (e.g., schema-validate hardening, ratelimit ElastiCache migration), defer those to a follow-on milestone. ADR 0017's tasks are scoped narrowly to deliver the ADR's exit criteria.
- **Auth0 scope provisioning.** Tasks T5–T7 assume `platform:identity:read` and `platform:catalog:read` exist as Auth0 scopes. Coordinate with security to add them; no blocking dependency since seed-time registration only checks string presence.
- **mcp-handler-lint friction on `platform.*` descriptions.** DESC001–009 were tuned for product handlers. The platform tools' descriptions must satisfy them anyway (tested in T5–T7). If any rule fires unexpectedly, surface to the registry-lint owner; do not bypass the lint.
- **Pagination compat.** Some MCP clients on older SDKs may not handle `nextCursor` correctly. Compatibility falls back to flat list because returning all tools in one page (page size ≥ catalog size) is also valid. Keep `TOOLS_LIST_PAGE_SIZE` ≥ projected per-principal max for V1 (≤ 50).
- **`tools_loaded_via_search` recency window.** T16 ties the field to a 5-minute in-process recency window. If Lambda concurrency makes session affinity weak (separate Lambda instances handle search and follow-up call), the field misses some legitimate matches. Acceptable for V1 — tuning lever lives in the Phase F retro.

## Cross-references

- ADR — [`docs/decisions/0017-tool-search-support.md`](../../decisions/0017-tool-search-support.md)
- Deep-dive — [`deep-dives/mcp-native-progressive-tool-discovery.md`](deep-dives/mcp-native-progressive-tool-discovery.md)
- Parent ADR — [`docs/decisions/0015-centralized-platform-mcp.md`](../../decisions/0015-centralized-platform-mcp.md)
- Server scaffold — [`docs/research/0015-centralized-platform-mcp/implementation/03-mcp-server.md`](../0015-centralized-platform-mcp/implementation/03-mcp-server.md)
- Registry schema — [`docs/research/0015-centralized-platform-mcp/implementation/04-registry.md`](../0015-centralized-platform-mcp/implementation/04-registry.md)
- Mission record — `/Users/scarver/.claude/plans/mission-add-mcp-idempotent-tiger.md` (private, working-tree).
