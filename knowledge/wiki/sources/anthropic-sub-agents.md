---
title: "Anthropic — Create custom subagents (Claude Code docs)"
kind: source
raw_path: "raw/sources/anthropic-sub-agents-2026-05-03.md"
url: "https://code.claude.com/docs/en/sub-agents"
author: "Anthropic"
fetched_at: 2026-05-03
tags: ["anthropic", "claude-code", "product:cross-cutting"]
entities: ["wiki/entities/sub-agent.md"]
concepts: []
created: 2026-05-03
updated: 2026-05-03
---

# Anthropic — Create custom subagents

Summary of the Claude Code documentation page on subagents. The full condensed capture is in [`raw/sources/anthropic-sub-agents-2026-05-03.md`](../../raw/sources/anthropic-sub-agents-2026-05-03.md).

## Why this source

This is the canonical Anthropic reference for the sub-agent primitive in Claude Code. Every agent definition under [`.claude/agents/`](../../../.claude/agents/) — and every architectural decision about how the LINQ Hackathon orchestrates work — relies on the contract this page describes. Ingesting it gives the curator and the eng-ai sub-agent a citable, fetched-on-disk source for claims about what sub-agents are, how they're configured, and what they can and cannot do.

## What it covers

- The motivation for sub-agents (context preservation, constraint enforcement, reuse, specialization, cost control).
- The set of built-in sub-agents (Explore, Plan, General-purpose, plus helper agents).
- The five scopes where a sub-agent can be defined (managed, CLI flag, project, user, plugin) and their priority order.
- The Markdown + YAML-frontmatter file format and the seventeen frontmatter fields, with `name` and `description` as the only required ones.
- Model selection (alias, full ID, `inherit`) and the four-step resolution order at invocation time.
- Tool restriction via allowlist (`tools`) and denylist (`disallowedTools`), and the precedence rule when both are set.
- Spawning restrictions: subagents cannot spawn other subagents; main-thread agents can use `Agent(agent_type)` to allowlist spawnable sub-agents.
- Per-subagent MCP server scoping (inline definitions or by-name references) and the optimization of keeping MCP servers out of the parent context.
- Skill preloading at subagent startup and the rule that subagents do not inherit skills from the parent.

## Key claims

- Subagents run in their own context window with a custom system prompt, specific tool access, and independent permissions. Source: [raw/sources/anthropic-sub-agents-2026-05-03.md](../../raw/sources/anthropic-sub-agents-2026-05-03.md) — "What subagents are."
- Subagents cannot spawn other subagents. Source: [raw/sources/anthropic-sub-agents-2026-05-03.md](../../raw/sources/anthropic-sub-agents-2026-05-03.md) — "Built-in subagents."
- Subagents receive only the system prompt and basic environment details — not the full Claude Code system prompt. Source: [raw/sources/anthropic-sub-agents-2026-05-03.md](../../raw/sources/anthropic-sub-agents-2026-05-03.md) — "File format."
- Higher-priority subagent locations override lower-priority ones with the same name. Order: managed > CLI > project > user > plugin. Source: [raw/sources/anthropic-sub-agents-2026-05-03.md](../../raw/sources/anthropic-sub-agents-2026-05-03.md) — "Subagent scope and priority."
- Default model is `inherit`. Source: [raw/sources/anthropic-sub-agents-2026-05-03.md](../../raw/sources/anthropic-sub-agents-2026-05-03.md) — "Models."
- When both `tools` and `disallowedTools` are set, `disallowedTools` is applied first. A tool listed in both is removed. Source: [raw/sources/anthropic-sub-agents-2026-05-03.md](../../raw/sources/anthropic-sub-agents-2026-05-03.md) — "Supported frontmatter fields."
- Plugin sub-agents do not support `hooks`, `mcpServers`, or `permissionMode` for security reasons; these fields are ignored when loaded from a plugin. Source: [raw/sources/anthropic-sub-agents-2026-05-03.md](../../raw/sources/anthropic-sub-agents-2026-05-03.md) — "Subagent scope and priority."
- Skills preloaded via the `skills` field are fully injected into the sub-agent's context at startup, not just made available for invocation. Subagents do not inherit skills from the parent. Source: [raw/sources/anthropic-sub-agents-2026-05-03.md](../../raw/sources/anthropic-sub-agents-2026-05-03.md) — "Preloading skills."

## Entities introduced

- [`wiki/entities/sub-agent.md`](../entities/sub-agent.md) — the sub-agent primitive itself.

## Open questions for LINQ

- How does the LINQ coordinator pattern (one main session, specialists called via Agent) map to Anthropic's "subagents cannot spawn subagents" rule? Confirmed compatible — only the main thread spawns specialists. Document this as a load-bearing constraint when authoring future agent definitions.
- Plugin sub-agents lose `hooks`, `mcpServers`, and `permissionMode`. We currently ship sub-agents at project scope (`.claude/agents/`); if the project ever moves to plugin distribution, the trust boundary in [`coordination.md`](../../../.claude/rules/coordination.md) needs revisiting.
- Skill preloading vs. on-demand invocation is a per-agent design choice. Surface to eng-ai when the next agent definition lands.
