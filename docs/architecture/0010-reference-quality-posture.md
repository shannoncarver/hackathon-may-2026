# ADR-0010 — Reference-quality posture (no hackathon shortcuts)

**Status:** Accepted (2026-05-01)

## Context

This repo serves a dual purpose: a hackathon entry *and* a LINQ-internal reference project for AI-driven development best practices. Where a recommendation has a "lightweight for hackathon" branch and a "thorough industry-standard" branch, we have to pick.

## Decision

Default to the thorough branch. Specifically:

- Real eval harness (per-agent + e2e + judge calibration + CI), not toy.
- Trust-boundary pattern with `events.jsonl` audit log.
- Pinned MCP versions with changelog.
- JSON schemas for every agent's I/O contract; runtime validation.
- Full traces (`traces/<run-id>.jsonl`) for post-hoc debugging.
- ADRs in `docs/architecture/` for every structural decision.

If a recommendation is "fine for production, overkill for a demo," we flip it: this is meant to look like production.

## Consequences

- More upfront scaffolding work.
- Higher confidence the system survives close inspection by anyone using it as a reference.
- Sets the bar for follow-on work — no "we'll add tests later" PRs.

## Sources

- User direction (2026-05-01): "I want to use best practices and not cut corners since it is a reference."
