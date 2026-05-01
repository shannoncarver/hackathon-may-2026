# ADR-0009 — Structural changes go through PR review

**Status:** Accepted (2026-05-01)

## Context

Working conventions in `CLAUDE.md` say "ask before hard-to-reverse decisions." Directory layout, agent contracts, and MCP version pins are all hard to reverse once they have downstream consumers.

## Decision

All structural changes (new agents, new pillars, MCP bumps, schema changes) land via PR with at least one human reviewer. No direct-to-`main` for structural commits. Trivial doc tweaks and typo fixes can land directly.

## Consequences

- Slower velocity for structural changes — but those are the changes where slowness pays off.
- CI runs `evals/run.py --ci` and `pytest` on every PR; failure blocks merge.
- We accept that the demo period may need a hotfix path (a `hotfix/*` branch with expedited review) — to be defined if needed.

## Sources

- Working conventions in [`CLAUDE.md`](../../CLAUDE.md)
