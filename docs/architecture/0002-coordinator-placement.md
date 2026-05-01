# ADR-0002 — Coordinator is the main session

**Status:** Accepted (2026-05-01)

## Context

The coordinator can be either (A) a dedicated `00-coordinator.md` sub-agent that the user dispatches into, or (B) the main Claude Code session governed by root `CLAUDE.md`.

## Decision

Option B. The user talks directly to the main session, which acts as coordinator. No `00-coordinator.md` sub-agent.

## Consequences

- One less indirection for the demo: "you talk to the LINQ workforce assistant" maps to "you open Claude Code in this repo."
- Coordinator behavior is governed by `CLAUDE.md` plus `.claude/rules/coordination.md`, plus the `routing` skill.
- We cannot swap the coordinator's model independently of the user-facing session — both use the project's default model.
- If non-coordinator specialists ever need to be invoked directly via slash-command, that's still possible via `/agents`.

## Sources

- Working conventions in [`CLAUDE.md`](../../CLAUDE.md)
- [Claude Code sub-agents docs](https://code.claude.com/docs/en/sub-agents)
