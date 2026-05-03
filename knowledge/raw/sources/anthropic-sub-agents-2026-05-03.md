---
title: "Anthropic — Create custom subagents"
url: "https://code.claude.com/docs/en/sub-agents"
fetched_at: 2026-05-03
auth_required: false
license_note: "Anthropic public docs — condensed for agent reference; cite source for verbatim text"
tags: ["anthropic", "claude-code", "product:cross-cutting"]
---

# Create custom subagents

Condensed capture of the Anthropic Claude Code documentation page on subagents. Verbatim quotes are in code blocks; section headers and key claims are reproduced as written. Refer to the source URL above for the complete page.

## What subagents are

> Subagents are specialized AI assistants that handle specific types of tasks. Use one when a side task would flood your main conversation with search results, logs, or file contents you won't reference again: the subagent does that work in its own context and returns only the summary. Define a custom subagent when you keep spawning the same kind of worker with the same instructions.

> Each subagent runs in its own context window with a custom system prompt, specific tool access, and independent permissions. When Claude encounters a task that matches a subagent's description, it delegates to that subagent, which works independently and returns results.

Subagents help you:

- Preserve context by keeping exploration and implementation out of your main conversation.
- Enforce constraints by limiting which tools a subagent can use.
- Reuse configurations across projects with user-level subagents.
- Specialize behavior with focused system prompts for specific domains.
- Control costs by routing tasks to faster, cheaper models like Haiku.

## Built-in subagents

Claude Code ships with built-in subagents Claude delegates to automatically.

| Built-in | Model | Tools | Purpose |
|---|---|---|---|
| Explore | Haiku | Read-only (no Write/Edit) | File discovery, code search, codebase exploration |
| Plan | Inherit | Read-only (no Write/Edit) | Codebase research during plan mode |
| General-purpose | Inherit | All tools | Complex research, multi-step operations, code modifications |
| statusline-setup | Sonnet | n/a | Configure status line via `/statusline` |
| Claude Code Guide | Haiku | n/a | Answer questions about Claude Code features |

> Subagents cannot spawn other subagents.

## Subagent scope and priority

Subagents are Markdown files with YAML frontmatter. Higher-priority locations win when names collide.

| Location | Scope | Priority |
|---|---|---|
| Managed settings | Organization-wide | 1 (highest) |
| `--agents` CLI flag | Current session | 2 |
| `.claude/agents/` | Current project | 3 |
| `~/.claude/agents/` | All your projects | 4 |
| Plugin's `agents/` directory | Where plugin is enabled | 5 (lowest) |

Project subagents (`.claude/agents/`) are checked into version control. User subagents (`~/.claude/agents/`) are personal across projects.

## File format

```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
---

You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.
```

> The frontmatter defines the subagent's metadata and configuration. The body becomes the system prompt that guides the subagent's behavior. Subagents receive only this system prompt (plus basic environment details like working directory), not the full Claude Code system prompt.

> Subagents are loaded at session start. If you create a subagent by manually adding a file, restart your session or use `/agents` to load it immediately.

## Supported frontmatter fields

Only `name` and `description` are required. The full set, as documented:

| Field | Required | Notes |
|---|---|---|
| `name` | Yes | Unique identifier; lowercase letters and hyphens |
| `description` | Yes | When Claude should delegate to this subagent |
| `tools` | No | Tools the subagent can use; inherits all if omitted |
| `disallowedTools` | No | Tools to deny |
| `model` | No | `sonnet`, `opus`, `haiku`, full model ID, or `inherit` (default) |
| `permissionMode` | No | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | No | Cap on agentic turns |
| `skills` | No | Skills injected at startup; subagents do not inherit skills from the parent |
| `mcpServers` | No | MCP servers available to this subagent (inline or by name) |
| `hooks` | No | Lifecycle hooks scoped to this subagent |
| `memory` | No | Persistent memory scope: `user`, `project`, or `local` |
| `background` | No | Always run as background task when `true` |
| `effort` | No | Effort level overrides session default |
| `isolation` | No | `worktree` runs the subagent in a temporary git worktree |
| `color` | No | Display color in transcript |
| `initialPrompt` | No | Auto-submitted as first user turn when this agent runs as the main session agent |

> If both [`tools` and `disallowedTools`] are set, `disallowedTools` is applied first, then `tools` is resolved against the remaining pool. A tool listed in both is removed.

## Models

> The `model` field controls which AI model the subagent uses:
> - **Model alias**: `sonnet`, `opus`, or `haiku`
> - **Full model ID**: `claude-opus-4-7`, `claude-sonnet-4-6`, etc.
> - **inherit**: same model as the main conversation
> - **Omitted**: defaults to `inherit`

Resolution order at invocation:
1. `CLAUDE_CODE_SUBAGENT_MODEL` env var
2. Per-invocation `model` parameter
3. Subagent definition's `model` frontmatter
4. Main conversation's model

## Tool restriction examples

Allowlist via `tools`:

```yaml
---
name: safe-researcher
description: Research agent with restricted capabilities
tools: Read, Grep, Glob, Bash
---
```

Denylist via `disallowedTools` (inherits everything else):

```yaml
---
name: no-writes
description: Inherits every tool except file writes
disallowedTools: Write, Edit
---
```

## Spawning restrictions

> When an agent runs as the main thread with `claude --agent`, it can spawn subagents using the Agent tool. To restrict which subagent types it can spawn, use `Agent(agent_type)` syntax in the `tools` field.

> Subagents cannot spawn other subagents, so `Agent(agent_type)` has no effect in subagent definitions.

Note: in version 2.1.63, the Task tool was renamed to Agent. Existing `Task(...)` references in settings and agent definitions still work as aliases.

## Scoping MCP servers

> Use the `mcpServers` field to give a subagent access to MCP servers that aren't available in the main conversation. Inline servers defined here are connected when the subagent starts and disconnected when it finishes.

> To keep an MCP server out of the main conversation entirely and avoid its tool descriptions consuming context there, define it inline here rather than in `.mcp.json`. The subagent gets the tools; the parent conversation does not.

## Preloading skills

> Use the `skills` field to inject skill content into a subagent's context at startup. This gives the subagent domain knowledge without requiring it to discover and load skills during execution.

> The full content of each skill is injected into the subagent's context, not just made available for invocation. Subagents don't inherit skills from the parent conversation; you must list them explicitly.

## Source

https://code.claude.com/docs/en/sub-agents (fetched 2026-05-03)
