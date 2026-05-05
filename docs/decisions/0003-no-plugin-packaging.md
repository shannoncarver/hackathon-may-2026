---
status: Accepted
date: 2026-05-01
category: architecture
---

# Decision 0003 — No plugin packaging (yet)

**Status:** Accepted (2026-05-01)

## Context

Claude Code plugins bundle agents + skills + commands + hooks + MCP into a distributable. Useful when redistributing across teams; overhead when iterating in-place.

## Decision

Stay standalone. No `.claude-plugin/plugin.json` manifest. Assets live at `.claude/`, `.mcp.json`, etc.

## Consequences

- Faster iteration: edits land directly with no plugin installation step.
- If the system is later adopted by other LINQ teams, we can convert to a plugin without changing file formats — assets relocate, not rewrite.
- We forfeit plugin-level namespacing (skills are `routing`, not `linq-hackathon:routing`).

## Sources

- [Claude Code plugins docs](https://code.claude.com/docs/en/plugins)

## History

- **2026-05-01** — Decision accepted.
- **2026-05-04** — PR #10 introduced a plugin marketplace (`linq-erp-skills`) for the `erp-authz` plugin, briefly contradicting this decision.
- **2026-05-05** — Pivot reverted the marketplace/plugin scaffolding after `/plugin` proved unavailable in Claude Desktop's Claude Code surface. Repo back in line with this decision; skills now ship under top-level [`skills/`](../../skills/) with a `.claude/skills/` symlink for in-repo auto-loading. See [docs/plans/erp-verify-user-authorization-poc-plan.md](../plans/erp-verify-user-authorization-poc-plan.md) for the pivot record.
