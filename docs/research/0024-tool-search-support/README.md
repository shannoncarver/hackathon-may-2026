# Decision 0024 — Tool Search support: research folder

**Status:** ADR drafted as Proposed (2026-05-05).
**Date:** 2026-05-05
**ADR:** [`docs/decisions/0024-tool-search-support.md`](../../decisions/0024-tool-search-support.md)

## What this folder contains

| File | Purpose |
|---|---|
| [`README.md`](README.md) | This file — landing page, reading order |
| [`deep-dives/mcp-native-progressive-tool-discovery.md`](deep-dives/mcp-native-progressive-tool-discovery.md) | Full design-space survey across the Anthropic Messages API and MCP protocol layers, with verbatim spec quotes, the seven-path comparison matrix, the LINQ positioning analysis, and a watch-list for re-evaluation. Captures the research that ADR 0024 distills. |
| `implementation-plan.md` | Phase 3 deliverable. Authored after the ADR is approved. Ordered task list mapping the decision into M1 Phase C of the `linq-platform-mcp` repo. |

The ADR itself is the canonical decision record. This folder is the durable explanation of *why* and *what alternatives were considered* — for operators reading it later.

## Reading order

1. Start with the ADR: [`docs/decisions/0024-tool-search-support.md`](../../decisions/0024-tool-search-support.md). Locks the decision and the implementation contract.
2. If you want to understand the design space — Anthropic vs MCP, GA vs Draft SEP, the four MCP proposals in flight — read [`deep-dives/mcp-native-progressive-tool-discovery.md`](deep-dives/mcp-native-progressive-tool-discovery.md). Operators triggered by the watch-list (SEP status changes, scale crossings, new MCP spec versions) re-read the deep-dive first.
3. Implementation plan lands here once the ADR is approved.

## Cross-references

- [Decision 0015 — Centralized Platform MCP Server](../../decisions/0015-centralized-platform-mcp.md) — the decision this work extends. The platform MCP server's M1 Phase C absorbs the Tool Search work.
- [`docs/research/0015-centralized-platform-mcp/`](../0015-centralized-platform-mcp/) — the parent research folder, including the implementation artifacts that this work hooks into (`03-mcp-server.md`, `04-registry.md`).
- Wiki entity: [`mcp-tool-catalog`](../../../knowledge/wiki/entities/mcp-tool-catalog.md).
