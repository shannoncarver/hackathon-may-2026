# Deep dive — from natural-language prompt to MCP tools/call

**Status:** Educational / further reading. Not part of the formal review record.
**For:** [Decision 0015 — Centralized Platform MCP Server](../../../decisions/0015-centralized-platform-mcp.md). Backed by review artifacts in [`docs/research/0015-centralized-platform-mcp/`](../00-overview.md).
**Date:** 2026-05-04

This document walks the end-to-end flow when a human types a natural-language prompt into Claude Code and a handler in a LINQ product account ends up returning the answer. It complements [`description-quality.md`](description-quality.md) (which focuses on what makes the model pick the right tool) and the warm-path sequence diagram in [`01-architecture.md`](../01-architecture.md) (which focuses on the MCP server's resolution pipeline).

The traced example: a user types *"can you validate for erp that user alice@example.com is authorized for tenant acme?"*

## Three layers cooperate

Three independent concerns combine into one flow. Recognizing the seam between them is the key to reasoning about the design.

| Layer | Concern | Owner |
|---|---|---|
| **Anthropic API tool-use** | Model picks a tool; model fills arguments | Anthropic API + the model |
| **MCP transport** | Claude Code (the MCP client) talks to the MCP server | MCP protocol; framework code |
| **Platform resolution pipeline** | Auth → registry → token exchange → STS → handler dispatch → audit | Decision 0015 (this work) |

**No layer reads natural language except the first.** The MCP server receives a structured `name` + `arguments` payload — it never parses the user's prompt. This is what makes the same design work for any agent: Claude Code, an internal dev tool, or an ops dashboard each produce the same `tools/call` payload via different model invocations.

## Before you type — what's already loaded

Two things happen before the user prompt arrives.

### Session start — MCP handshake

When the Claude Code session connects to the platform MCP server (configured in `.mcp.json` or equivalent), it runs the MCP `initialize` method exchanging capabilities, then calls `tools/list`.

The server returns a tool catalog **scoped to this agent's identity**. Server-side projection by the M2M `client_id` (e.g., `claude-code-internal`) filters the catalog to the tools that identity is authorized to see — the catalog-leak mitigation for review risk **R4** in [`03-risks-register.md`](../03-risks-register.md). An agent that lacks the `erp:read` scope literally does not see `erp.checkUserAccess` in its `tools/list` response.

Each tool in the response carries the routing surface — `name`, `title`, `description`, `inputSchema`:

```json
{
  "name": "erp.checkUserAccess",
  "title": "Check ERP user access",
  "description": "Read-only. Returns whether a user has access to the LINQ ERP product for a specific tenant, plus the user's role assignments. Inputs: user email and tenant slug. Use this when verifying ERP entitlement before reading ERP data. Do NOT use this for general user profile lookups (see iam.lookupUser). P50 ~180ms.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "userId":   { "type": "string", "format": "email",
                    "description": "User's email address" },
      "tenantId": { "type": "string",
                    "description": "Tenant slug, e.g. 'acme'" }
    },
    "required": ["userId", "tenantId"]
  }
}
```

### Tool catalog injected into the model's context

When Claude Code subsequently calls the Anthropic API, it passes this catalog as the `tools` parameter — the same mechanism the API exposes for any tool use. The model now sees, in its working context, every MCP-advertised tool as a `name + description + inputSchema` triple.

The catalog is reloaded on `notifications/tools/list_changed` from the server (debounced server-side per finding 6 in [`role-passes/mcp-integration.md`](../role-passes/mcp-integration.md) to coalesce multi-team handler deploys).

## Step-by-step: the prompt arrives

User message: *"can you validate for erp that user alice@example.com is authorized for tenant acme?"*

### Step 1 — Model matches semantically

Claude scans the available tools by `name` + `description`, looking for the closest fit to the prompt's intent. The match is not keyword search; it's the same pattern matching the model uses for any tool selection. Signals it picks up:

- **`erp`** → matches the `erp.*` namespace prefix and the description's `"ERP product"`.
- **`validate ... authorized`** → matches `"checkUserAccess"` and the description's `"whether a user has access"`.
- **The shape of the request (a user + a tenant)** → matches the `inputSchema` shape (`userId` + `tenantId`).

Description quality dominates this step. A vague description silently steals invocations or gets skipped entirely. See [`description-quality.md`](description-quality.md) for the rules that protect against this.

### Step 2 — Model extracts arguments

From the same natural-language sentence, the model fills the `inputSchema` slots:

- `"alice@example.com"` → `userId` (matches the `format: email` hint)
- `"acme"` → `tenantId`

If the prompt had said *"validate the latest user"*, the model would either ask the human to clarify (`userId` is `required` and not derivable) or guess wrong. Schema requirements give the model a structured budget for what it must extract.

### Step 3 — Anthropic API responds with a tool-use content block

The model's response back to Claude Code looks like:

```json
{
  "type": "tool_use",
  "id": "toolu_xyz",
  "name": "erp.checkUserAccess",
  "input": { "userId": "alice@example.com", "tenantId": "acme" }
}
```

The model **does not call the MCP server itself.** It only emits this structured intent. The Anthropic API's tool-use mechanism is the same one any Claude API consumer uses — MCP layers on top, not below.

### Step 4 — Claude Code routes the tool call

Claude Code looks up which connected MCP server owns the tool name `erp.checkUserAccess` (the platform MCP server, the only one configured for internal LINQ products per Decision 0015 — versus the Atlassian MCP per [Decision 0008](../../../decisions/0008-mcp-connectors.md), which owns `confluence.*` / `jira.*`). It sends an MCP `tools/call` request:

```json
{
  "method": "tools/call",
  "params": {
    "name": "erp.checkUserAccess",
    "arguments": { "userId": "alice@example.com", "tenantId": "acme" }
  }
}
```

Two tokens travel alongside the request as HTTP headers:

- The agent's Auth0 M2M JWT in `Authorization: Bearer ...` (proves *which agent* is calling).
- The human user's Auth0 JWT in `X-User-Token` (proves *which human* is behind the agent), audience-bound to the MCP server, **never passed through to downstream handlers** per the MCP authorization spec ([`mcp-authorization`](../../../../knowledge/wiki/entities/mcp-authorization.md)).

### Step 5 — Platform MCP server runs the resolution pipeline

The 10-step pipeline is the subject of [`01-architecture.md`](../01-architecture.md) and the security memo. Briefly, in order:

1. Validate both JWTs.
2. Resolve the tool ID to a registry version (cached lookup, falls through to DynamoDB on miss).
3. Coarse-grained authorization (agent scopes + user RBAC permissions).
4. Tenant scope enforcement — read tenant from the user's verified JWT, not the agent's input.
5. Input schema validation against `inputSchema` from S3.
6. `sideEffects: "read"` enforcement gate.
7. RFC 8693 token exchange via the IdentityBroker — outputs a downstream JWT bound to the product handler's audience.
8. Cross-account `sts:AssumeRole` with per-product External ID and session tags.
9. Dispatch via the handler-type adapter (Lambda Invoke / ECS RunTask / Step Functions StartSyncExecution).
10. Validate output, write per-request audit record, return to the agent.

### Step 6 — Tool result comes back to the model

Claude Code receives the MCP server's response and feeds it to the model as a `tool_result` block:

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_xyz",
  "content": [{ "type": "text",
                "text": "{ \"hasAccess\": true, \"roles\": [\"viewer\"] }" }]
}
```

The model's next turn now has the answer in context, structured as a JSON-string-in-a-text-block (the default MCP content shape; structured output via `outputSchema` + `structuredContent` is a 2025-06-18 spec addition, optional in V1 — see finding 2 in [`role-passes/mcp-integration.md`](../role-passes/mcp-integration.md)).

### Step 7 — Model composes the natural-language reply

Claude reads the result and writes back to the user: *"Yes, alice@example.com has access to ERP for tenant acme as a viewer."*

## Why each routing decision lives where it does

A useful frame: every routing decision in this flow is owned by exactly one layer, and putting it elsewhere creates a known anti-pattern.

| Decision | Lives at | If moved elsewhere |
|---|---|---|
| Which tool for this prompt? | The model | Routing on the server side via NLP would re-introduce string parsing the design is specifically designed to avoid. |
| What arguments fit the schema? | The model | Schema enforcement on the server alone (without LLM extraction) requires the agent to pre-structure inputs — defeats the natural-language UX. |
| Which MCP server owns this tool? | Claude Code | Pushing this to the model bloats the prompt with server topology. Pushing it to the platform MCP server requires it to know the entire LINQ MCP estate. |
| Which handler version implements this tool? | The platform MCP server (registry resolution) | Pushing to the agent locks every agent to a specific handler version; pushing to the handler removes versioned rollback. |
| Which AWS account hosts this handler? | The platform MCP server (registry binding) | Exposing to the agent leaks substrate; embedding in the tool name (`erp_acct_111122223333.checkUserAccess`) couples names to deployment topology. |
| Tenant binding | The platform MCP server (read from user JWT) | Trusting the agent to supply tenant is the textbook leakage vector; this is the load-bearing safety call. |

## Comparison: with vs. without the broker

If LINQ had instead chosen federated MCP servers per product, the same prompt flow happens — but with operational fan-out:

- Claude Code would have 4 connected MCP servers, each contributing tools to the catalog.
- The model still picks the tool by name + description.
- The difference is operational: 4 description style guides, 4 auth implementations, 4 audit logs, 4 onboarding paths.

The model's behavior is unchanged. The platform team's surface area quadruples. This is the [comparison-matrix](../02-comparison-matrix.md) governance row in concrete terms.

## What you should pay attention to as a designer

Three takeaways for anyone designing or operating against this architecture:

1. **Description quality is the routing function.** The model's tool selection runs entirely off the catalog. See [`description-quality.md`](description-quality.md) for the discipline that protects this.
2. **Catalog scope determines what's reachable.** Server-side projection by authenticated principal is what makes 200-handler scale work without context-window leak. The model can't pick a tool it doesn't see.
3. **No string parsing on the server.** All natural-language interpretation lives at the model layer. The MCP server receives a structured payload. This separation is what lets the platform MCP serve heterogeneous agents without per-agent integration.

## Related artifacts

- [`01-architecture.md`](../01-architecture.md) — sequence diagrams for warm path, cold path, and tenant-scope rejection.
- [`role-passes/mcp-integration.md`](../role-passes/mcp-integration.md) — MCP protocol findings, including projection mechanics and `listChanged` debouncing.
- [`description-quality.md`](description-quality.md) — sibling deep dive on what makes the model pick the right tool from the catalog.
- [`knowledge/wiki/entities/mcp-tool-catalog.md`](../../../../knowledge/wiki/entities/mcp-tool-catalog.md) — protocol reference for tool catalog shape and `tools/list` semantics.
