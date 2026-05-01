# ADR-0006 — Claude Code native, no CLI wrapper

**Status:** Accepted (2026-05-01)

## Context

The CLAUDE.md vision lists "CLIs and orchestration layers for workflow automation" as part of the AI primitives. Two implementations possible: pure Claude Code (user runs `claude` in this repo) or a thin wrapper CLI (`linq-assist <task>`) using the Claude Agent SDK.

## Decision

Pure Claude Code. No `linq-assist` CLI wrapper.

## Consequences

- Smaller surface to build, debug, and demo.
- All harness behavior (tool permissions, hooks, MCP scoping) is governed by Claude Code's own configuration, not custom code.
- If headless automation is needed later, the Agent SDK can wrap the existing agent definitions — they don't need to change.

## Sources

- [Claude Agent SDK docs](https://code.claude.com/docs/en/agent-sdk/subagents.md) — for reference if we revisit
