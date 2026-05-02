---
status: Accepted
date: 2026-05-01
category: architecture
---

# Decision 0007 — Custom output style for stakeholder demos

**Status:** Accepted (2026-05-01)

## Context

The audience for the hackathon demo includes stakeholders and judges. Default Claude Code output is engineer-facing. We need a polished presentation format.

## Decision

Add `.claude/output-styles/demo.md` with the format `Objective → Progress → Next Steps`. Set as default in `.claude/settings.json` so it's active out of the box.

## Consequences

- Demo audience sees a structured response format consistently.
- Trivial responses (acknowledgements, single-fact answers) opt out of the structure to avoid template-padding.
- Engineers working in the repo see the same format; if it gets in the way during dev, they can switch styles per-session.

## Sources

- [Claude Code output styles docs](https://code.claude.com/docs/en/output-styles)
