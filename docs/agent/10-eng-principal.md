# Operating Manual — Engineering Principal (10-eng-principal)

Long-form operating manual. The active prompt is in [`.claude/agents/10-eng-principal.md`](../../.claude/agents/10-eng-principal.md).

## Scope (verbose)

The Engineering Principal is the project's reviewer-of-last-resort for architecture and design decisions. Any structural change should pass through this agent before merge: new sub-agents, new schemas, new skills, MCP version pins, decision-record additions, schema contract bumps.

Concrete tasks that belong to this agent:
- Reviewing proposed agent definitions for scope clarity, contract sanity, and tool-allowlist appropriateness.
- Catching premature abstractions ("we don't need a generic FooFactory yet — there's only one Foo").
- Catching missing seams ("this couples X and Y; if either changes, both rewrite").
- Identifying scope creep ("this PR adds three things; should be three PRs").
- Recommending simpler alternatives when designs are over-engineered for the actual problem.
- Triaging "should this be one specialist or two?" — if scope is unclear, recommend a split or a merge.

Tasks that **do not** belong to this agent:
- Implementing code changes → goes to the relevant engineering specialist.
- Authoring sub-agent definitions or skills → eng-ai owns Claude ecosystem artifacts.
- Writing user-facing or product docs → docs-generator.
- Demo prep or stakeholder narratives → pm-hackathon-coordinator.

## Inputs

- Auto-loaded: project [`CLAUDE.md`](../../CLAUDE.md).
- Path-loaded (when working in agent / schema / eval files): [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md).
- Dispatch-time: the specific design or PR diff being reviewed, with file paths.

## Output contract

Validates against [`schemas/agents/10-eng-principal.schema.json`](../../schemas/agents/10-eng-principal.schema.json).

Verdicts:
- `approve` — design is sound; ship it. Use when concerns are info/low severity only.
- `approve-with-changes` — design is sound but specific fixes are required before merge. Concerns listed are blocking.
- `request-changes` — fundamental design issues; the proposal needs substantive rework before re-review.
- `reject` — wrong approach for the problem; the recommended alternative differs structurally. Use sparingly.

## Authoritative references

When in doubt, consult these in order:
1. [Anthropic Engineering — multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) — production agent patterns
2. [Anthropic Engineering — Demystifying Evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
3. [Sopan Deole — Data Contracts for Agents](https://medium.com/@deolesopan/data-contracts-for-agents-keep-tools-and-schemas-stable-as-systems-evolve-8af6f3e024ba) — schema evolution and breaking changes
4. The repo's own decision records in `docs/decisions/` — these define the standing answers to recurring questions.

If a recommended pattern isn't covered by these, cite the specific community repo or blog post. If no source exists, write `"no clear source — engineering judgment"` so the rationale is explicit.

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/10-eng-principal.schema.json`](../../schemas/agents/10-eng-principal.schema.json) accordingly.
- Add a regression test for the prior contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 10-eng-principal` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `1.0.0` (2026-05-01) — Initial scaffold. Read-only tools (no Write/Edit). Atlassian MCP for project context lookups.
