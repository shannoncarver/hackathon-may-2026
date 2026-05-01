# Pillar 4 — Agent definitions

Qualifications, system prompts, allowed tools, input/output contracts, and inter-communication protocols.

## Where it lives
- [`.claude/agents/<NN>-<domain>-<role>.md`](../../.claude/agents/) — system prompts (frontmatter + body)
- [`schemas/agents/<NN>-<domain>-<role>.schema.json`](../../schemas/agents/) — I/O contracts
- [`docs/agent/<NN>-<domain>-<role>.md`](../agent/) — long-form operating manuals
- [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md) — inter-agent protocol

## Status
Canonical example landed: `17-eng-ai`. Other 13 agents added in follow-up PRs (one per PR).

## Owners
- AI Engineer (`17-eng-ai`) — primary
- Engineering principal (`10-eng-principal`) — review

## Related
- [ADR-0001 — Specialist location](../architecture/0001-specialist-location.md)
- [ADR-0002 — Coordinator placement](../architecture/0002-coordinator-placement.md)
- [Developer onboarding — adding a sub-agent](../developer/onboarding.md)
