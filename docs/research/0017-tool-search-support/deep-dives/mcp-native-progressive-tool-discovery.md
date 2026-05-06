# Deep dive — MCP-native progressive tool discovery

**Status:** Educational / further reading. Captures the design-space survey behind ADR 0017's choice to ship the Anthropic-API-side Tool Search Tool pattern rather than wait for an MCP-spec-native equivalent. Not part of any formal review record.
**For:** [Decision 0017 — Tool Search support for the platform MCP server](../../../decisions/0017-tool-search-support.md). Backed by [Decision 0015 — Centralized Platform MCP Server](../../../decisions/0015-centralized-platform-mcp.md).
**Date:** 2026-05-05

---

## What this deep-dive answers

When LINQ asked "how should the platform MCP server support progressive tool discovery so agents don't load 200 tool definitions on connect?", the natural follow-up is: *is there an MCP-protocol-native answer, or are we stuck with vendor-specific tooling?*

This document surveys the full design space — five distinct mechanisms across two layers (the Anthropic Messages API and the MCP protocol) — explains where each one sits today, and locks in the rationale for ADR 0017's chosen path. Operators reading this in 2027 should be able to re-evaluate without re-doing the research.

---

## Problem framing

### Why progressive discovery matters

The MCP tool catalog is sent in full to the model on every request, prefixed into the system prompt. Each tool definition costs roughly 400–500 tokens once name, description, and JSON Schema are serialized. At small scale this is invisible; at production scale it becomes the dominant cost in two ways:

- **Context bloat.** Anthropic's [Tool Search Tool announcement](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) cites a representative multi-server setup (GitHub, Slack, Sentry, Grafana, Splunk) at ~55 000 tokens of tool definitions before any work begins, and reports that on-demand search reduces this to ~5 000 — roughly 85 percent.
- **Tool selection accuracy.** Anthropic also reports that "Claude's ability to correctly pick the right tool degrades significantly once you exceed 30–50 available tools." This is not a token-count problem; it's a discrimination problem. The model has to attend across the full catalog every time.

LINQ's planned scale — V1 target 40–200 handlers across ERP, CRM, DWH, and Support, growing to 200–2000 over three years per [ADR 0015](../../../decisions/0015-centralized-platform-mcp.md) — sits firmly inside both failure modes. We will hit the 30–50-tool accuracy cliff before we hit the token-cost cliff, but both arrive on the V1 timeline.

### Two layers, two design centers

The catalog travels from MCP server to agent to Anthropic API in three hops, and each hop is a candidate pivot:

```
[Platform MCP server] --tools/list--> [Agent] --tools[]--> [Anthropic Messages API] --> [Model]
```

A discovery optimization can live at:

- **The MCP-server-to-agent seam** — the server returns less, or returns it on demand. This is the MCP protocol's domain.
- **The agent-to-API seam** — the agent sends the full catalog to the API, but marks parts deferred so the API only materializes them when the model asks. This is Anthropic's API domain.

The two designs are complementary, not exclusive. Where they sit today is the actual subject of this doc.

---

## The five paths

### Path 1 — Anthropic API Tool Search Tool (production-shippable)

**What it is.** A first-party Messages API feature released 2025-11-19 (the date is encoded in the type name `tool_search_tool_regex_20251119`). The agent declares one of two variants in its `tools[]` array — `tool_search_tool_regex_20251119` (Python regex) or `tool_search_tool_bm25_20251119` (BM25 natural language) — alongside other tools marked `defer_loading: true`. Deferred tools are kept out of the system-prompt prefix; when the model needs one, it calls the search tool, gets back 3–5 `tool_reference` blocks, and the API auto-expands the references into full definitions inline.

**Verbatim spec quote (Anthropic):**
> "When you enable the tool search tool: 1. You include a tool search tool ... in your tools list. 2. You provide all tool definitions with `defer_loading: true` for tools that shouldn't be loaded immediately. 3. Claude sees only the tool search tool and any non-deferred tools initially. 4. When Claude needs additional tools, it searches using a tool search tool. 5. The API returns 3-5 most relevant `tool_reference` blocks. 6. These references are automatically expanded into full tool definitions. 7. Claude selects from the discovered tools and invokes them."
> — [Tool Search Tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)

**Where it executes.** Anthropic API server-side. The MCP server is downstream of the deferral decision — it just exposes `tools/list`, and the agent decides what to mark deferred when packaging that list into a Messages API call.

**Limits.**
- Up to 10 000 tools in the catalog.
- At least one tool must be non-deferred (the search tool itself, by convention).
- Regex queries cap at 200 characters using Python `re.search()` semantics.
- Supported on Sonnet 4.0+, Opus 4.0+, Haiku 4.5+, and Mythos Preview. No fallback on older Anthropic models. Non-Anthropic clients ignore `defer_loading` and load everything.
- Not compatible with the `tool_use_examples` API parameter.

**What it does well.** Production-grade today. Preserves prompt caching (deferred tools don't enter the prefix). Anthropic-side regex/BM25 matching is centralized and improvable without LINQ-side changes. No protocol changes required at the MCP layer — works against any MCP server's `tools/list` output.

**What it doesn't do.** Vendor-locked to Anthropic models. Doesn't help any other LLM provider. Treats the catalog as opaque text — semantic relationships between tools (versions, namespaces, deprecations) aren't visible to the search.

**When to revisit.** When LINQ adopts a non-Anthropic model alongside Claude, or when the regex/BM25 search misses too many of the queries we care about and we need a smarter ranker.

### Path 2 — MCP `tools/list` cursor pagination (in current spec, production-shippable)

**What it is.** The MCP `2025-06-18` spec defines `tools/list` with optional `cursor` request parameter and `nextCursor` response field. Clients page through the catalog rather than receiving it all at once.

**Verbatim spec quote (MCP):**
> "To discover available tools, clients send a `tools/list` request. This operation supports pagination."
> — [MCP `2025-06-18` Tools section](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": { "cursor": "optional-cursor-value" }
}
```

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [ /* page */ ],
    "nextCursor": "next-page-cursor"
  }
}
```

**Where it executes.** MCP server.

**What it does well.** Universal. Every MCP-spec-compliant client can paginate without negotiating capabilities. Works at every catalog size.

**What it doesn't do.** No filtering, no scoring, no relevance ranking — the full catalog still gets transferred eventually, just split across many round trips. If an agent paginates the whole catalog up front (which most do), pagination doesn't reduce the model's context cost; it just makes the wire protocol incremental.

**When to revisit.** Pagination is cheap forward-compat. Adding `cursor` support to LINQ's `tools/list` implementation is a Phase C task with no design tax and is included in ADR 0017's plan even though our V1 catalog (per-principal projection caps at ~40 tools per agent) doesn't strictly need it yet.

### Path 3 — Per-principal `tools/list` projection (LINQ already does this)

**What it is.** Server-side filtering of `tools/list` output by the authenticated principal's identity (`client_id` or `sub`). Each agent sees only the tools its identity is authorized to invoke. Not a spec feature — an implementation pattern.

**Where it lives in LINQ.** [ADR 0015 R4](../../../decisions/0015-centralized-platform-mcp.md), implemented in [`docs/research/0015-centralized-platform-mcp/implementation/03-mcp-server.md`](../../0015-centralized-platform-mcp/implementation/03-mcp-server.md) §2.9 (`routes/tools-list.ts`). The registry's `visibility.agentIdentities[]` field per [04-registry.md](../../0015-centralized-platform-mcp/implementation/04-registry.md) drives the filter.

**What it does well.** Catalog presented to any one agent is a small, relevant slice — the design has it as the primary catalog-size control for V1. Does not require client cooperation. Survives the addition of new agents and new products without code changes (declarative registry data).

**What it doesn't do.** Doesn't compose with deferral on the client side directly — the client still sees its full slice up front. For a single-purpose agent that only ever calls 2–3 ERP handlers, projection alone might be enough. For a generalist agent (e.g., Claude Code internal) that *could* touch any product, projection alone leaves a long tail.

**Spec status.** The pattern is being formalized as **SEP-1881** below. LINQ's design pre-dates the SEP and matches it in spirit.

### Path 4 — SEP-1821: Dynamic Tool Discovery (Draft)

**What it is.** A draft MCP Specification Enhancement Proposal authored by Egor Orlov on 2025-11-17, currently seeking a sponsor. Adds an optional `query: string` parameter to `tools/list` and a new `ServerCapabilities.tools.filtering: boolean` capability flag for negotiation.

**Verbatim quote (SEP):**
> "Search string. Server interprets as simple text (category, tag, semantic description, or use case scenario). NOT for complex JSON or structured queries."

> "Present: Server supports and will process the `query` parameter. Absent: Server returns all tools (`query` parameter ignored)."

> "Fully backward compatible: All parameters are optional. Servers ignore unknown parameters. Clients without filtering support work unchanged."
> — [SEP-1821](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1821)

**Search semantics.** The SEP is intentionally non-prescriptive: *"Server implements simple search strategies optimized for LLM/agent usage (substring matching, semantic search, tag matching, category filtering)."*

**Where it executes.** MCP server.

**Status.** Draft, no sponsor, no PR merged into the spec. Authoring activity began 2025-11-17. No visible review comments from MCP maintainers in the proposal as of Phase 1 research (2026-05-05).

**What it would do well.** Universal protocol-level search. Any compliant client can negotiate it. Does not duplicate logic that already exists at the API layer (each MCP server provides its own search; clients don't have to know per-server algorithms).

**What it doesn't do (yet).** It's a Draft. Building production code against it bets on the proposal landing without breaking changes — speculative for any V1 path.

**When to revisit.** When the SEP lands and the MCP TypeScript / Python SDKs ship support, evaluate whether to add a native `query` parameter alongside the `platform.search_tools` MCP tool ADR 0017 introduces. The two can coexist — the SEP would be a second seam useful to non-Anthropic clients.

### Path 5 — SEP-1888: Progressive Disclosure for Typed Library Discovery (Draft)

**What it is.** A draft SEP authored by Harshal Patil on 2025-11-24, currently seeking a sponsor. Proposes a per-library meta-tool naming convention: `<library>.searchTools(resourceType, action, scope, riskLevel, mode)` with `mode: "operations"` (default) returning matching API methods or `mode: "types"` returning type definitions.

**Verbatim quote (SEP):**
> "Instead of registering hundreds of narrowly-scoped tools (e.g., `listPods`, `createDeployment`, `getRepository`), servers implementing this capability expose a single standardized meta-tool with two modes."

> "Uses existing `tools/list` and `tools/call` mechanisms."
> — [SEP-1888](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1888)

**Where it executes.** MCP server, dispatched by the MCP server's normal `tools/call` pipeline.

**Why this matters for LINQ.** The wire shape is **structurally identical** to the "Custom tool search implementation" hook in Anthropic's Tool Search Tool spec. Both designs have a server expose a tool that returns references-to-other-tools. If LINQ implements `platform.search_tools` per ADR 0017 today, the migration to SEP-1888 (if accepted) is cosmetic: rename to `linq.searchTools` and add a `mode` parameter. No re-architecture.

**Status.** Draft, no sponsor. Reference implementation by the author exists for Kubernetes ([ProDisco](https://github.com/harche/ProDisco)) but the spec hasn't been merged.

**What it would do well.** Standardizes a naming convention so every progressive-disclosure-capable MCP server is recognizable to clients. Forward-compatible with type-introspection scenarios (the `types` mode).

**What it doesn't do.** Solves the same problem as Path 1 with a different sticker. The actual on-the-wire behavior — search tool returns references, model invokes target tool — is already achievable today with Path 1's custom-search hook.

**When to revisit.** If the SEP is accepted, rename `platform.search_tools` to align. The cost is a one-line registry change.

### Path 6 (related, lower-priority) — SEP-1881: Scope-Filtered Tool Discovery (Draft)

**What it is.** A draft SEP authored by Kevin Gao on 2025-11-23 that formalizes per-scope filtering of `tools/list`. Servers MAY return only tools whose authorization requirements the current access token satisfies. The SEP also requires that "servers MUST NOT expose metadata about filtered-out tools" — an explicit information-leakage rule.

**Verbatim quote (SEP):**
> "A server is operating in Scope-Filtered Tool Discovery Mode if: `tools/list` returns **only** tools for which the current access token satisfies the tool's authorization requirements."

> "Filtering is applied based on: `tool.authorization.scopes` (from SEP-1880), _if present_."
> — [SEP-1881](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1881)

**Where it lives in LINQ.** ADR 0015 R4 already implements this pattern via `client_id` projection (Path 3 above). The SEP would standardize the capability negotiation; LINQ's behavior already matches.

**Status.** Draft, depends on SEP-1880 (`tool.authorization.scopes`) which is also Draft. Two-deep proposal stack — long lead time.

### Path 7 (mentioned for completeness) — Hierarchical Tool Management (open Discussion)

**What it is.** [Discussion #532](https://github.com/orgs/modelcontextprotocol/discussions/532), open since 2025-08-18 with no consensus. Proposes a larger surface change — categories + four new RPC methods (`tools/categories`, `tools/discover`, `tools/load`, `tools/unload`).

**Status.** No SEP, no sponsor, no movement since August 2025. Treat as evidence the community is thinking about the problem, not as a path forward.

---

## Comparison matrix

| Path | Production-shippable today? | Where it executes | Catalog-size limit | Search semantics | Couples to | Forward-compat with MCP spec |
|---|---|---|---|---|---|---|
| 1. Anthropic API Tool Search Tool | ✅ Yes (2025-11-19 GA on Sonnet 4+ / Opus 4+ / Haiku 4.5+) | Anthropic API server-side | 10 000 | Regex (`re.search`) or BM25 | Anthropic clients only; non-Anthropic clients ignore `defer_loading` | Independent of MCP spec |
| 2. MCP cursor pagination | ✅ Yes | MCP server | None stated | None — page-by-page | Any MCP-spec-compliant client | ✅ In current spec |
| 3. Per-principal projection | ✅ Yes (ADR 0015 R4) | MCP server, by `client_id` | Per-client cap | Server-defined filter | Any MCP-spec-compliant client | Will become SEP-1881 if accepted |
| 4. SEP-1821 native query param | ❌ No (Draft, no sponsor) | MCP server, server-defined search | None stated | Server's choice (substring / semantic / tag) | Any future MCP client supporting filtering capability | Currently a draft proposal |
| 5. SEP-1888 `<library>.searchTools` | ❌ Spec is Draft, but the pattern works today via Path 1's custom-search hook | MCP server, via `tools/call` | None stated | Server's choice | Any client that supports tools | ✅ Works inside today's spec; SEP standardizes naming |
| 6. SEP-1881 scope-filtered discovery | ❌ No (Draft, depends on SEP-1880) | MCP server | N/A | N/A — pure filtering | Any future MCP client | LINQ already aligns with the spirit |
| 7. Discussion #532 hierarchical | ❌ No (no SEP, dormant) | Would add 4 new RPC methods | N/A | Categories + lazy-load | Future protocol | Speculative |

---

## Where LINQ already sits relative to the spec

ADR 0015's per-`client_id` `tools/list` projection (R4) **is already SEP-1881 in spirit, ahead of the spec.** When SEP-1881 lands (if it does), LINQ likely just adds a capability advertisement — the behavior is already there.

The pattern enforced by `mcp-handler-lint` per [04-registry.md](../../0015-centralized-platform-mcp/implementation/04-registry.md) §2.3 also pre-bakes search-friendliness: the description-quality rules (read-only prefix, length bounds, returns clause, no substrate leakage) are exactly the "consistent namespacing and semantic keywords" Anthropic's docs recommend for Tool Search Tool optimization. LINQ writes high-signal descriptions because the linter requires it, and that pays off twice — once in tool selection accuracy, again in tool search recall.

The naming convention `<product>.<verb>...` (e.g., `erp.checkUserAccess`) is also pre-aligned with SEP-1888's library-scoping intent. If SEP-1888 lands as written, the migration is renaming `platform.search_tools` to `linq.searchTools` (or `<product>.searchTools` per product) — a change in the seed-item registry record, not a code change.

See also the wiki entity [`mcp-tool-catalog`](../../../knowledge/wiki/entities/mcp-tool-catalog.md), which already covers the protocol-level basics.

---

## Why ADR 0017 chose Path 1 + Path 5 (custom hook) over the SEPs

The decision lattice for this question reduces to four observations:

1. **Production today vs. speculative future.** Path 1 (Anthropic Tool Search Tool) is GA and working. Paths 4–6 are Draft SEPs without sponsors — the median MCP SEP from 2025 has not yet merged. Building V1 against Drafts bets on uncertain timelines.

2. **The custom-search hook is the bridge.** Anthropic's spec section "Custom tool search implementation" describes exactly how to expose a server-side tool that returns `tool_reference[]` — and that hook's wire shape is structurally identical to SEP-1888's proposed pattern. By implementing `platform.search_tools` today, LINQ gets the production behavior under Path 1 *and* a forward-compat path to Path 5 — for the cost of a single MCP tool.

3. **Path 3 covers the fallback for free.** ADR 0015 already projects `tools/list` per principal. Non-Anthropic clients (any MCP-spec-compliant client that ignores `defer_loading`) get a small, relevant catalog with no extra work. The fallback isn't an awkward second code path — it's the existing primary code path.

4. **The work doesn't lock anything in.** If SEP-1821 ships, we add a native `query` parameter to `tools/list` as a second seam. If SEP-1888 ships, we rename. If SEP-1881 ships, we advertise an existing capability. None of these futures requires re-architecting the V1 implementation.

The combined posture — ship Path 1 + Path 5 (custom hook), keep Path 2 (cursor pagination) for spec parity, and let Path 3 (per-principal projection) handle the fallback — gives LINQ **immediate production capability**, **alignment with the released spec**, and **forward-compat with three plausible spec evolutions**, without betting on any one Draft SEP landing.

---

## Watch-list — when to re-read this doc

Re-evaluate the decision when any of the following occur:

- **SEP-1821 status changes** to Sponsored, Accepted, or merged into a spec release. Adding a native `query` param to `tools/list` becomes worth doing.
- **SEP-1888 status changes** similarly. The `platform.search_tools` registry seed item renames; possibly add a `mode` parameter.
- **SEP-1881 ships**, with SEP-1880 (`tool.authorization.scopes`) landing first. Add a capability advertisement.
- **Any new MCP spec version** introduces a new tool-discovery mechanism we haven't enumerated.
- **LINQ catalog crosses 50 deferred tools.** At that scale, validate that regex search recall is still acceptable. Re-evaluate BM25 (Anthropic's `tool_search_tool_bm25_20251119` variant) if user-prompted natural-language queries become the common case.
- **LINQ adds a non-Anthropic LLM provider** as a primary agent runtime. Path 1 ceases to cover the new provider; the SEP-based paths become more attractive.
- **LINQ scale crosses 800 handlers OR ≥ 2 product teams hit platform-write-path bottleneck**, triggering ADR 0015's federation gate (`handlerType: "remote-mcp"`). Tool search semantics across federated MCP servers may need re-design.

---

## References

**Anthropic spec**
- [Tool Search Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) — full page, including the Custom Tool Search Implementation section, error codes, streaming behavior, and batch-API support.

**MCP spec**
- [MCP `2025-06-18` Tools section](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) — `tools/list`, `tools/call`, `notifications/tools/list_changed`, capability negotiation, pagination.
- [MCP specification index](https://modelcontextprotocol.io/specification/2025-06-18) — top-level spec.
- Wiki entity: [`mcp-tool-catalog`](../../../../knowledge/wiki/entities/mcp-tool-catalog.md).

**MCP SEPs (all Draft as of 2026-05-05)**
- [SEP-1821 — Dynamic Tool Discovery](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1821) (Egor Orlov, 2025-11-17).
- [SEP-1881 — Scope-Filtered Tool Discovery](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1881) (Kevin Gao, 2025-11-23).
- [SEP-1888 — Progressive Disclosure for Typed Library Discovery](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1888) (Harshal Patil, 2025-11-24).
- [Discussion #532 — Hierarchical Tool Management](https://github.com/orgs/modelcontextprotocol/discussions/532) (open since 2025-08, no consensus).

**LINQ context**
- [ADR 0015 — Centralized Platform MCP Server](../../../decisions/0015-centralized-platform-mcp.md).
- [ADR 0017 — Tool Search support for the platform MCP server](../../../decisions/0017-tool-search-support.md).
- [Implementation 03 — MCP Server](../../0015-centralized-platform-mcp/implementation/03-mcp-server.md) — the Lambda scaffold the search route extends.
- [Implementation 04 — Handler Registry](../../0015-centralized-platform-mcp/implementation/04-registry.md) — the registry the search backs onto.
