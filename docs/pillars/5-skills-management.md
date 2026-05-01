# Pillar 5 — Skills management

How skills are authored, versioned, discovered, and assigned to agents.

## Where it lives
- [`.claude/skills/<name>/SKILL.md`](../../.claude/skills/) — skill definitions (folders, not files)
- [`.claude/skills/<name>/references/`](../../.claude/skills/) — lazy-loaded reference docs
- [`.claude/skills/<name>/scripts/`](../../.claude/skills/) — executable helpers (when needed)

## Status
One canonical skill landed: `routing`. Future skills follow the same folder shape.

## Owners
- AI Engineer (`17-eng-ai`) — primary
- Engineering principal (`10-eng-principal`) — review

## Related
- [Claude Code skills docs](https://code.claude.com/docs/en/skills)
- [anthropics/skills repo](https://github.com/anthropics/skills) — canonical SKILL.md format
