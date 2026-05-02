---
status: Accepted
date: 2026-05-01
category: architecture
---

# Decision 0001 — Specialists live in `.claude/agents/`

**Status:** Accepted (2026-05-01)

## Context

We need a single, idiomatic location for ~14 sub-agent definitions. Two patterns exist in the wild:
1. `.claude/agents/<name>.md` — Claude Code-native, harness auto-discovers.
2. `skills/prompt-templates/<name>.md` — pattern from [legal-agent-orchestrator](https://github.com/kipeum86/legal-agent-orchestrator), audit-friendly, more controllable.

## Decision

Use `.claude/agents/<name>.md`. The harness auto-discovers files, the Claude Code documentation treats this as canonical, and 100% of the public Anthropic reference repos use it.

## Consequences

- Specialists are immediately invocable via the `Agent` tool with no custom dispatcher.
- We accept that fine-grained version pinning and parameterization happen via git history rather than an explicit registry.
- If we later need audit-grade controllability, we can author specialists *also* as prompt-templates without losing the `.claude/agents/` versions.

## Sources

- [Claude Code sub-agents docs](https://code.claude.com/docs/en/sub-agents)
- [anthropics/claude-agent-sdk-demos — research-agent](https://github.com/anthropics/claude-agent-sdk-demos/tree/main/research-agent)
- [wshobson/agents — agent-teams plugin](https://github.com/wshobson/agents/tree/main/plugins/agent-teams)
