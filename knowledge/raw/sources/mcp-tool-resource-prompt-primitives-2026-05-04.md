---
title: "MCP Specification 2025-06-18 — Tools, Resources, and Prompts"
url: "https://modelcontextprotocol.io/docs/concepts/tools"
fetched_at: 2026-05-04
auth_required: false
license_note: "Model Context Protocol public documentation — condensed for agent reference; cite source for verbatim text"
sources_also_consulted:
  - "https://modelcontextprotocol.io/docs/concepts/resources"
  - "https://modelcontextprotocol.io/docs/concepts/prompts"
  - "https://modelcontextprotocol.io/specification/2025-06-18"
---

# MCP Specification 2025-06-18 — Tools, Resources, and Prompts

## Overview

The Model Context Protocol (MCP) uses JSON-RPC 2.0 messages. Communication is between:
- **Hosts**: LLM applications that initiate connections
- **Clients**: Connectors within the host application
- **Servers**: Services that provide context and capabilities

Servers expose three primitive types: Tools, Resources, and Prompts.

---

## Tools

### User Interaction Model

Tools are **model-controlled** — the LLM discovers and invokes them automatically based on context and prompts. A human SHOULD always be in the loop with ability to deny tool invocations.

### Capability Declaration

Servers that support tools MUST declare the `tools` capability:

```json
{
  "capabilities": {
    "tools": {
      "listChanged": true
    }
  }
}
```

`listChanged: true` means the server will emit notifications when the tool list changes.

### Tool Catalog Shape

A tool definition includes:
- `name` (string, unique identifier)
- `title` (optional string, human-readable display name)
- `description` (string, human-readable description of functionality)
- `inputSchema` (JSON Schema object defining expected parameters)
- `outputSchema` (optional JSON Schema defining expected output structure)
- `annotations` (optional object describing tool behavior hints)

Example tool definition:

```json
{
  "name": "get_weather",
  "title": "Weather Information Provider",
  "description": "Get current weather information for a location",
  "inputSchema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City name or zip code"
      }
    },
    "required": ["location"]
  }
}
```

### Listing Tools — tools/list

Request (supports pagination via cursor):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": { "cursor": "optional-cursor-value" }
}
```

Response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [ /* array of tool definitions */ ],
    "nextCursor": "next-page-cursor"
  }
}
```

### Calling Tools — tools/call

Request:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": { "location": "New York" }
  }
}
```

Response (unstructured content):
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [{ "type": "text", "text": "..." }],
    "isError": false
  }
}
```

Response (structured content — added in 2025-06-18):
```json
{
  "result": {
    "content": [{ "type": "text", "text": "{\"temperature\": 22.5, ...}" }],
    "structuredContent": { "temperature": 22.5, "conditions": "Partly cloudy", "humidity": 65 }
  }
}
```

For structured content: servers MUST provide results conforming to `outputSchema`; clients SHOULD validate against it.

### listChanged Notification

When the tool list changes, servers that declared `listChanged` SHOULD send:
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

### Tool Result Content Types

- **Text**: `{"type": "text", "text": "..."}`
- **Image**: `{"type": "image", "data": "<base64>", "mimeType": "image/png"}`
- **Audio**: `{"type": "audio", "data": "<base64>", "mimeType": "audio/wav"}`
- **Resource link**: `{"type": "resource_link", "uri": "file:///...", "name": "...", "mimeType": "..."}`
- **Embedded resource**: `{"type": "resource", "resource": {"uri": "...", "mimeType": "...", "text": "..."}}`

All content types support optional annotations: `audience` (array: "user"/"assistant"), `priority` (0.0–1.0), `lastModified` (ISO 8601).

### Error Handling

Two mechanisms:
1. **Protocol errors** (JSON-RPC level): unknown tool → `{"code": -32602, "message": "Unknown tool: ..."}`
2. **Tool execution errors** (in result): `{"content": [...], "isError": true}`

### Security Requirements

Servers MUST: validate all tool inputs, implement access controls, rate limit invocations, sanitize outputs. Clients SHOULD: prompt for user confirmation on sensitive operations, validate results before passing to LLM, implement timeouts, log usage for audit.

---

## Resources

### User Interaction Model

Resources are **application-driven** — host applications determine how to incorporate context. Each resource is uniquely identified by a URI (RFC 3986).

### Capability Declaration

```json
{
  "capabilities": {
    "resources": {
      "subscribe": true,
      "listChanged": true
    }
  }
}
```

`subscribe`: client can subscribe to changes to individual resources. `listChanged`: server emits notifications when resource list changes. Both are optional.

### Resource Shape

Fields:
- `uri` (string, unique identifier, required)
- `name` (string, required)
- `title` (optional, human-readable display name)
- `description` (optional string)
- `mimeType` (optional string)
- `size` (optional, size in bytes)
- `annotations` (optional: `audience`, `priority`, `lastModified`)

### Listing Resources — resources/list

Request (supports pagination):
```json
{ "jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": { "cursor": "..." } }
```

Response:
```json
{
  "result": {
    "resources": [
      {
        "uri": "file:///project/src/main.rs",
        "name": "main.rs",
        "title": "Rust Software Application Main File",
        "description": "Primary application entry point",
        "mimeType": "text/x-rust"
      }
    ],
    "nextCursor": "next-page-cursor"
  }
}
```

### Reading Resources — resources/read

```json
{ "jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": { "uri": "file:///project/src/main.rs" } }
```

Response:
```json
{
  "result": {
    "contents": [
      { "uri": "file:///...", "mimeType": "text/x-rust", "text": "fn main() {...}" }
    ]
  }
}
```

Resource contents: text (`text` field) or binary (`blob` field, base64-encoded).

### Resource Templates — resources/templates/list

URI templates follow RFC 6570. Arguments may be auto-completed via the completion API.

Request: `{"method": "resources/templates/list", "params": { "cursor": "..." }}`

Response:
```json
{
  "result": {
    "resourceTemplates": [
      {
        "uriTemplate": "file:///{path}",
        "name": "Project Files",
        "description": "Access files in the project directory",
        "mimeType": "application/octet-stream"
      }
    ]
  }
}
```

### listChanged Notification

```json
{ "jsonrpc": "2.0", "method": "notifications/resources/list_changed" }
```

### Subscriptions

Subscribe to a resource:
```json
{ "method": "resources/subscribe", "params": { "uri": "file:///project/src/main.rs" } }
```

Update notification (server → client):
```json
{ "method": "notifications/resources/updated", "params": { "uri": "file:///project/src/main.rs" } }
```

### Common URI Schemes

- `https://` — web resources (only when client can fetch directly without MCP server)
- `file://` — filesystem-like resources (may use XDG MIME type `inode/directory` for directories)
- `git://` — Git version control integration
- Custom schemes must conform to RFC 3986

### Error Handling

- Resource not found: `-32002`
- Internal errors: `-32603`

---

## Prompts

### User Interaction Model

Prompts are **user-controlled** — exposed to clients with the intent that users explicitly select them. Typically triggered via slash commands or similar UI.

### Capability Declaration

```json
{
  "capabilities": {
    "prompts": { "listChanged": true }
  }
}
```

### Prompt Shape

- `name` (string, unique identifier)
- `title` (optional, human-readable display name)
- `description` (optional, human-readable description)
- `arguments` (optional array of argument descriptors: `name`, `description`, `required`)

### Listing Prompts — prompts/list

Request (pagination supported):
```json
{ "method": "prompts/list", "params": { "cursor": "..." } }
```

Response:
```json
{
  "result": {
    "prompts": [
      {
        "name": "code_review",
        "title": "Request Code Review",
        "description": "Asks the LLM to analyze code quality and suggest improvements",
        "arguments": [
          { "name": "code", "description": "The code to review", "required": true }
        ]
      }
    ]
  }
}
```

### Getting a Prompt — prompts/get

Request:
```json
{
  "method": "prompts/get",
  "params": { "name": "code_review", "arguments": { "code": "def hello():\n    print('world')" } }
}
```

Response:
```json
{
  "result": {
    "description": "Code review prompt",
    "messages": [
      { "role": "user", "content": { "type": "text", "text": "Please review this Python code:..." } }
    ]
  }
}
```

Prompt message content types: text, image, audio, embedded resource.

### listChanged Notification

```json
{ "jsonrpc": "2.0", "method": "notifications/prompts/list_changed" }
```

### Error Codes

- Invalid prompt name or missing required arguments: `-32602` (Invalid params)
- Internal errors: `-32603`
