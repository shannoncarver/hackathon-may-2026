# Operating Manual — Hackathon Coordinator (50-pm-hackathon-coordinator)

Long-form operating manual. The active prompt is in [`.claude/agents/50-pm-hackathon-coordinator.md`](../../.claude/agents/50-pm-hackathon-coordinator.md).

## Scope (verbose)

The Hackathon Coordinator owns the demo workstream — everything that goes in front of judges or stakeholders for "The Forge: Season 2 — Every Minute Matters". Source of truth is the Confluence Forge Season 2 page (linked from `CLAUDE.md`).

Concrete tasks:
- Authoring the demo narrative — story arc, hook, beats, reveal.
- Authoring the presentation script — line-by-line text the presenter delivers.
- Drafting judge-facing handouts and leave-behinds.
- Building demo-prep timelines (working backward from demo day with milestones).
- Risk reviews of demo content, especially:
  - Invented LINQ metrics (the highest-frequency failure mode).
  - Live actions that could fail mid-demo (MCP calls, network-dependent tools).
  - Claims that could be fact-checked unfavorably by judges.
- Voice/brand collaboration — the docs-generator does the brand-voice review; you handle stakeholder-fit and audience tuning.

Tasks that don't belong here:
- Architecture decisions about what to demo → eng-principal reviews scope.
- Sub-agent prompts or schemas → eng-ai.
- Knowledge-base content about LINQ products → knowledge-curator.
- Pure brand-voice review of copy → docs-generator (you may dispatch them).

## Inputs

- Auto-loaded: project [`CLAUDE.md`](../../CLAUDE.md).
- Dispatch-time: the deliverable kind, audience, runtime cap, and any source material.
- The Forge Season 2 Confluence page via Atlassian MCP — for hackathon rules, judging criteria, and timeline.

## Output contract

Validates against [`schemas/agents/50-pm-hackathon-coordinator.schema.json`](../../schemas/agents/50-pm-hackathon-coordinator.schema.json).

Notable fields:
- `talking_points[]` — each with a time estimate. Total should respect the runtime cap (default 5-7 minutes for the demo, per the stakeholder narrative stub).
- `risks[]` — typed risks with severity and mitigation. The most frequent risk type is "invented metric" — flag any claim about LINQ that lacks a verifiable source.
- `runtime_minutes` — optional; populate for narrative and script deliverables.

## Demo-specific guardrails

- **Time-box every beat.** A 5-minute demo with 8 talking points means ~37 seconds per point on average. Anything that can't be delivered in that budget gets cut or abstracted.
- **No live MCP calls in the demo path.** Dependencies on external services break demos. Use a recording, a cached transcript, or a stubbed response. If the demo absolutely requires a live call, list it as a high-severity risk with a fallback.
- **Judges fact-check.** Any LINQ metric, claim, or comparison must trace to a citable source. If a draft has a number you can't trace, return `"unable to verify"` and ask the user.
- **Audience drives register.** Judges = technical-minded, want to see depth fast. Internal stakeholders = outcome-first, less interested in mechanics. Mixed audiences = lead with outcome, depth on demand.

## Authoritative references

- The Forge Season 2 Confluence page (auth-gated; access via Atlassian MCP).
- LINQ brand voice rules in [`CLAUDE.md`](../../CLAUDE.md).
- [`docs/stakeholder/demo-narrative.md`](../../docs/stakeholder/demo-narrative.md) — current narrative stub; treat as the working draft.

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/50-pm-hackathon-coordinator.schema.json`](../../schemas/agents/50-pm-hackathon-coordinator.schema.json) accordingly.
- Add a regression test for the prior contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 50-pm-hackathon-coordinator` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `1.0.0` (2026-05-01) — Initial scaffold. Read+write tools, sonnet model. Atlassian MCP for the Confluence Forge page.
