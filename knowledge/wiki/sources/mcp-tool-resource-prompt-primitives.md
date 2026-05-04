---
title: "MCP Specification 2025-06-18 — Tools, Resources, and Prompts"
kind: source
raw_path: "raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md"
url: "https://modelcontextprotocol.io/docs/concepts/tools"
author: "Model Context Protocol authors"
fetched_at: 2026-05-04
tags: ["mcp", "protocol", "tools", "resources", "prompts", "product:cross-cutting"]
entities:
  - "wiki/entities/mcp-tool-catalog.md"
concepts: []
created: 2026-05-04
updated: 2026-05-04
---

## Why this source

Closes the gap identified in the Decision 0014 Phase A review: no MCP tool/resource/prompt primitives coverage in the knowledge base. Needed to understand the catalog shape, dynamic discovery mechanism, and notification protocol for designing a centralized Platform MCP Server with 40–200 handlers.

## What it covers

The MCP 2025-06-18 specification for three server-side primitive types: Tools, Resources, and Prompts. Covers JSON-RPC 2.0 message shapes, capability negotiation, dynamic discovery via `listChanged` notifications, pagination, content types, annotations, error handling, and security requirements.

## Key claims

- Tools are **model-controlled**; Resources are **application-driven**; Prompts are **user-controlled**. [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- Servers MUST declare capabilities in the `capabilities` object during initialization. `tools.listChanged: true` means the server will emit `notifications/tools/list_changed` when the tool list changes. [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- A tool definition shape: `name` (unique identifier), `title` (optional display name), `description`, `inputSchema` (JSON Schema), `outputSchema` (optional), `annotations` (optional hints). [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- Dynamic discovery: clients send `tools/list` (paginated via cursor); server returns `tools` array and optional `nextCursor`. When the list changes, server sends `notifications/tools/list_changed` and clients re-fetch. [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- Tool invocation: `tools/call` with `name` and `arguments`; response includes `content` array and `isError` boolean. Structured content (2025-06-18 addition) returns `structuredContent` object alongside `content`. [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- Resources use URIs (RFC 3986) as unique identifiers. `resources/templates/list` exposes URI templates (RFC 6570) for parameterized resources. Subscriptions via `resources/subscribe`/`resources/unsubscribe` and `notifications/resources/updated`. [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- Resource content is either text (`text` field) or binary blob (`blob` field, base64-encoded). [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- All content types (tools, resources, prompts) support optional annotations: `audience` (array: `"user"` / `"assistant"`), `priority` (0.0–1.0), `lastModified` (ISO 8601). [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- Prompt definition shape: `name`, `title` (optional), `description` (optional), `arguments` (array of `{name, description, required}`). Retrieved via `prompts/get` with argument values. [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- Two error channels for tools: (1) JSON-RPC protocol errors (unknown tool: code `-32602`); (2) tool execution errors in result (`isError: true`). Resource errors: not found `-32002`, internal `-32603`. [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- All three primitives support `listChanged` notifications. Resources additionally support `subscribe` (per-resource change subscriptions). [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]
- Clients MUST consider tool annotations to be **untrusted** unless they come from trusted servers. [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md]

## Entities introduced

- [wiki/entities/mcp-tool-catalog.md] — new entity: the MCP tool catalog shape, listChanged mechanism, and invocation protocol.

## Open questions for LINQ

1. **Handler count and pagination strategy.** The Platform MCP Server is designed for 40–200 handlers. `tools/list` supports pagination via cursor — does the centralized server need to implement pagination, or are 40–200 tools within a single-page response limit?
2. **Structured content adoption.** The `outputSchema` + `structuredContent` feature was added in the 2025-06-18 spec. Which version of the MCP SDK does LINQ's current toolchain target?
3. **Resource template use.** URI templates (RFC 6570) could be useful for parameterized cross-product resource access (e.g., `jira://issues/{issueKey}`). Is this in scope for the Platform MCP Server v1?
4. **Annotation trust model.** Tool annotations (readOnlyHint, destructiveHint, etc.) are untrusted per spec. How will the Platform MCP Server communicate trust level for its 4-product handler set?
