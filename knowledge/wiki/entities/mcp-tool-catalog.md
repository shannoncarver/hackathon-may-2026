---
title: "MCP Tool Catalog"
kind: entity
tags: ["mcp", "protocol", "tools", "discovery", "product:cross-cutting"]
aliases: ["tool catalog", "tools/list", "MCP tool discovery"]
sources:
  - "wiki/sources/mcp-tool-resource-prompt-primitives.md"
related:
  - "wiki/entities/mcp-authorization.md"
  - "wiki/entities/atlassian-mcp.md"
created: 2026-05-04
updated: 2026-05-04
---

# MCP Tool Catalog

The MCP tool catalog is the runtime-discoverable set of tools a server exposes to clients, described using a JSON-RPC 2.0 protocol and governed by the MCP 2025-06-18 specification. Each tool entry describes a callable function that language models can invoke.

Source: [wiki/sources/mcp-tool-resource-prompt-primitives.md]

---

## Tool Definition Shape

A tool definition contains:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | REQUIRED | string | Unique identifier within the server |
| `title` | optional | string | Human-readable display name |
| `description` | REQUIRED | string | Human-readable description for LLM context |
| `inputSchema` | REQUIRED | JSON Schema object | Defines expected parameters and their types |
| `outputSchema` | optional | JSON Schema object | Defines expected structured output (2025-06-18 addition) |
| `annotations` | optional | object | Hints about tool behavior (readOnlyHint, destructiveHint, etc.) |

Annotations are **untrusted** — clients MUST treat them as untrusted unless the server is explicitly trusted.

---

## Dynamic Discovery

### Capability Negotiation

Servers that expose tools MUST declare the `tools` capability during initialization:

```json
{ "capabilities": { "tools": { "listChanged": true } } }
```

`listChanged: true` signals that the server will emit notifications when its tool list changes.

### Listing Tools — tools/list

Clients discover tools by sending a `tools/list` JSON-RPC request. The response supports cursor-based pagination:

```
tools/list request → { tools: [...], nextCursor: "..." }
```

Clients should page through `nextCursor` until it is absent.

### Dynamic Updates — listChanged Notification

When the tool list changes at runtime, servers that declared `listChanged` SHOULD send:

```json
{ "jsonrpc": "2.0", "method": "notifications/tools/list_changed" }
```

Upon receiving this notification, clients SHOULD re-fetch the tool list via `tools/list`. This mechanism supports hot-reload of handlers without reconnecting.

---

## Tool Invocation

Clients invoke tools via `tools/call` with `name` and `arguments`. Two response forms:

**Unstructured** (content array):
```json
{ "content": [{ "type": "text", "text": "..." }], "isError": false }
```

**Structured** (2025-06-18 addition): includes both `content` (for backward compatibility) and `structuredContent` (JSON object conforming to `outputSchema`). Clients SHOULD validate structured content against `outputSchema`.

---

## Content Types in Tool Results

All content types support optional annotations (`audience`, `priority`, `lastModified`):

| Type | Key fields |
|------|-----------|
| Text | `type: "text"`, `text: "..."` |
| Image | `type: "image"`, `data: "<base64>"`, `mimeType: "image/png"` |
| Audio | `type: "audio"`, `data: "<base64>"`, `mimeType: "audio/wav"` |
| Resource link | `type: "resource_link"`, `uri: "file:///..."`, `name`, `mimeType` |
| Embedded resource | `type: "resource"`, `resource: { uri, mimeType, text/blob }` |

---

## Error Handling

Two error channels:

1. **Protocol errors** (JSON-RPC level): unknown tool → `{"code": -32602, "message": "Unknown tool: ..."}`.
2. **Tool execution errors**: returned in the result with `isError: true`; content explains the failure.

---

## Security Requirements

- Servers MUST validate all tool inputs and implement access controls.
- Servers MUST rate-limit tool invocations.
- Clients SHOULD prompt for user confirmation on sensitive operations.
- Clients SHOULD validate results before passing to LLM.
- A human SHOULD always be in the loop with ability to deny tool invocations.

---

## Relationship to Platform MCP Server (Decision 0015)

The Platform MCP Server for Decision 0015 is designed to expose 40–200 handlers across 4 LINQ products. This entity's key implications:

- **Pagination**: 40–200 tools may require cursor-based pagination in `tools/list`. Clients must handle `nextCursor`.
- **listChanged**: Enables runtime handler registration without client reconnection — important for a dynamic multi-product catalog.
- **inputSchema**: Each of the 40–200 handlers needs a JSON Schema that accurately describes its parameters.
- **outputSchema**: The 2025-06-18 structured output feature enables typed responses useful for agent pipelines.

See also: [wiki/entities/mcp-authorization.md] for how the Platform MCP Server authorizes tool invocations.
