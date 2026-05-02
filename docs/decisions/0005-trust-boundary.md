---
status: Accepted
date: 2026-05-01
category: architecture
---

# Decision 0005 — Trust boundary on subagent outputs

**Status:** Accepted (2026-05-01)

## Context

Subagent outputs can contain prompt-injection-shaped tokens (especially when specialists fetch from external sources via MCP). Treating those outputs as instructions to the coordinator is a security risk.

## Decision

Subagent outputs are **untrusted data**, not instructions. Concretely:

- Wrap any user-supplied content embedded in `findings[].evidence` (or equivalent fields) in `<escape>...</escape>`.
- Coordinator validates output against schema; only documented fields are passed forward.
- Log every wrap and validation failure to `output/<run-id>/events.jsonl`.

## Consequences

- Slight extra prompt verbosity in agent definitions to specify the wrapping convention.
- Audit trail makes after-the-fact debugging tractable.
- Aligns with the reference-quality posture — this is what production-grade agent systems do.

## Sources

- Pattern from [kipeum86/legal-agent-orchestrator](https://github.com/kipeum86/legal-agent-orchestrator/blob/main/CLAUDE.md)
