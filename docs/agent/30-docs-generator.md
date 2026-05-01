# Operating Manual — Documentation Generator (30-docs-generator)

Long-form operating manual. The active prompt is in [`.claude/agents/30-docs-generator.md`](../../.claude/agents/30-docs-generator.md).

## Scope (verbose)

The Documentation Generator owns all human-readable written deliverables in the project. Three audiences:

- **Developers** — engineers contributing to the repo. Tone: direct, code-heavy, assumes Claude Code familiarity. Examples: `docs/developer/onboarding.md`, READMEs, runbooks, contribution guides.
- **End-users** — LINQ employees who would use the system once it ships. Tone: outcome-first, assumes zero technical context. Examples: product overviews, FAQs.
- **Stakeholders** — leadership, judges, cross-functional reviewers. Tone: outcomes and evidence, brief, defensible. Examples: demo handouts, exec summaries.

Concrete tasks:
- Drafting new docs from a topic and audience brief.
- Editing existing docs for clarity, length, or audience fit.
- Reviewing drafts (from any source) against LINQ brand and voice rules.
- Converting source material (Confluence pages, Slack threads, meeting notes) into structured docs.
- Maintaining the doc index and cross-links between related pages.

Tasks that don't belong here:
- Architecture decisions and ADRs → eng-principal authors those.
- Sub-agent prompts and operating manuals → eng-ai owns the Claude ecosystem artifacts.
- Final demo narrative and judge-facing presentation script → pm-hackathon-coordinator. You provide a voice-review, but ownership of the message belongs to the coordinator.
- Knowledge-base content about LINQ products → knowledge-curator.

## LINQ brand and voice rules (load-bearing)

- **Active voice.** "The coordinator validates each output." NOT "Each output is validated by the coordinator."
- **Oxford comma.** "agents, skills, and MCP connectors."
- **Em dashes without spaces.** Use `—` not ` — `. (Some style guides allow spaced em dashes; LINQ does not.)
- **LINQ product names** match exactly. The casing in `knowledge/linq-products/<name>/` is canonical.
- **No invented metrics.** If a stat or claim about LINQ is not verifiable from `knowledge/` or a cited source, return `"unable to verify"` — do not paraphrase a guess.
- **One canonical source.** Don't duplicate content across files; link.

## Inputs

- Auto-loaded: project [`CLAUDE.md`](../../CLAUDE.md).
- Path-loaded (when working in `docs/` files): the relevant `.claude/rules/` (none currently scope to `docs/**`, but this may change).
- Dispatch-time: the topic, audience, and any source material to convert.

## Output contract

Validates against [`schemas/agents/30-docs-generator.schema.json`](../../schemas/agents/30-docs-generator.schema.json).

`voice_check.verdict`:
- `pass` — no issues; ship.
- `needs-review` — minor issues listed in `findings[]`. The author can ship after addressing them, no second-round review required.
- `fail` — major issues. Do not ship without re-review.

The `findings[].rule` enum lists the specific brand-voice rule violated. Use it consistently — it makes drift across reviews trackable.

## Authoritative references

- LINQ brand voice rules in [`CLAUDE.md`](../../CLAUDE.md) (the canonical statement).
- LINQ product canonical names in `knowledge/linq-products/` (currently empty — populated in follow-up tasks).
- [Anthropic — Effective Tool Use](https://docs.claude.com/en/docs/build-with-claude/tool-use) for examples of clear technical doc tone (used as a reference for voice register).

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/30-docs-generator.schema.json`](../../schemas/agents/30-docs-generator.schema.json) accordingly.
- Add a regression test for the prior contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 30-docs-generator` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `1.0.0` (2026-05-01) — Initial scaffold. Read+write tools, sonnet model (cheaper for prose work). Atlassian MCP for Confluence source material.
