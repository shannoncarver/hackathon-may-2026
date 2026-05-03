---
title: "Sub-agent"
kind: entity
tags: ["product:cross-cutting", "anthropic", "claude-code"]
aliases: ["specialist", "sub agent", "subagent"]
sources: ["wiki/sources/anthropic-sub-agents.md"]
related: []
created: 2026-05-03
updated: 2026-05-03
---

# Sub-agent

## Definition

A sub-agent is a specialized AI assistant in Claude Code with its own context window, custom system prompt, specific tool access, and independent permissions. The main session (the coordinator) delegates a task to a sub-agent when that sub-agent's `description` matches; the sub-agent works in isolation and returns only its result. Sub-agents preserve the main session's context, enforce per-task constraints, and let the project route work to faster or cheaper models when appropriate.

## Properties

A sub-agent definition is a Markdown file with YAML frontmatter. The body of the file becomes the sub-agent's system prompt. Two fields are required (`name`, `description`); the rest are optional.

| Field | Purpose |
|---|---|
| `name` | Unique identifier (lowercase letters and hyphens). |
| `description` | When the coordinator should delegate to this sub-agent. Trigger-rich phrasing improves matching. |
| `tools` | Allowlist of tools the sub-agent may use. Inherits all if omitted. |
| `disallowedTools` | Denylist applied before `tools` resolves. |
| `model` | `sonnet`, `opus`, `haiku`, full model ID, or `inherit` (default). |
| `permissionMode` | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, or `plan`. |
| `maxTurns` | Cap on agentic turns. |
| `skills` | Skills injected at startup. Sub-agents do not inherit skills from the parent. |
| `mcpServers` | MCP servers available to this sub-agent only (inline or by-name). |
| `hooks` | Lifecycle hooks scoped to this sub-agent. |
| `memory` | Persistent memory scope: `user`, `project`, or `local`. |
| `background`, `effort`, `isolation`, `color`, `initialPrompt` | Runtime behavior knobs. |

Constraints:

- A sub-agent cannot spawn other sub-agents.
- A sub-agent receives only its system prompt and basic environment details — not the parent's full system prompt or conversation.
- Plugin sub-agents ignore `hooks`, `mcpServers`, and `permissionMode` for security reasons.

## How LINQ uses this

The LINQ Hackathon project organizes specialist work into project-scope sub-agents under [`.claude/agents/`](../../../.claude/agents/). The coordinator pattern is documented in [Pillar 4 — Agent definitions](../../../docs/pillars/4-agent-definitions.md), and inter-agent communication is governed by [`.claude/rules/coordination.md`](../../../.claude/rules/coordination.md). Knowledge-base usage by sub-agents is governed by [`.claude/rules/knowledge-base.md`](../../../.claude/rules/knowledge-base.md), which auto-loads on every dispatch.

## Sources

- [`wiki/sources/anthropic-sub-agents.md`](../sources/anthropic-sub-agents.md) — Anthropic's canonical Claude Code sub-agents documentation. Original URL: https://code.claude.com/docs/en/sub-agents.
