# ADR-0011 — Eval harness: hand-rolled `run.py` + Inspect AI for e2e

**Status:** Accepted (2026-05-01)

## Context

We need an eval harness that catches regressions, validates schema compliance, and grades qualitative output. Options ranged from no harness (skip-for-hackathon) to managed platforms (Braintrust). The reference-quality posture rules out the toy end; the standalone-not-vendored constraint rules out managed platforms.

## Decision

Two-layer harness:

1. **Per-agent unit evals** — hand-rolled `evals/run.py`, ~250 lines Python, demonstrates the pattern transparently. Reads JSONL cases, calls the agent (single-turn, no tools), scores via schema validation + LLM-judge with Unknown escape hatch. Reports written to `evals/reports/`.
2. **End-to-end evals** — [Inspect AI](https://inspect.aisi.org.uk/) suite under `evals/e2e/` (added in a follow-up PR). Uses Inspect's agent-loop support to exercise tool-using agents end-to-end. Citing Inspect AI strengthens the reference posture (it's used by the UK AI Safety Institute).

Judge model and prompt are pinned. Calibration: human-review 20% of judge scores weekly; track divergence as its own metric.

CI runs schema/structural tests on every PR (`pytest tests/`); schema failures block merge.

## Hackathon-scope amendment (2026-05-01)

CI gating on `evals/run.py --ci` is **deferred** for the hackathon. Reasons:
- No `ANTHROPIC_API_KEY` configured for CI yet (no remote, no GitHub secrets).
- Per-run cost ($2-5) and wall-clock time (10-30 min) is unwarranted for the hackathon timeline.
- Schema validation in `tests/test_schemas.py` already catches structural regressions, which is the highest-value CI signal.

The eval harness remains in-repo as a manual tool (`python evals/run.py`) and as a reference artifact for the LINQ best-practice posture. Re-enable in a follow-up PR once a remote is configured and an API-key secret is provisioned.

## Consequences

- ~3 days of distributed build effort for the reference-quality version.
- Both layers cite into our `docs/architecture/` and `docs/research/` so future readers see the rationale.
- The hand-rolled `run.py` is intentionally small and readable — it's a teaching artifact, not just a tool.

## Sources

- [Anthropic — Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Inspect AI (UK AISI)](https://inspect.aisi.org.uk/)
- [arxiv — Empirical Study of LLM-as-a-Judge biases](https://arxiv.org/html/2506.13639v1)
