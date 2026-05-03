# Operating Manual — Knowledge Curator (40-knowledge-curator)

Long-form operating manual. The active prompt is in [`.claude/agents/40-knowledge-curator.md`](../../.claude/agents/40-knowledge-curator.md). Canonical conventions are in [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md).

## Scope (verbose)

The Knowledge Curator owns the structure and integrity of the `knowledge/` tree — the authoritative source for LINQ product, API, architecture, and demo-domain context. The standing decision on tree shape is [Decision 0013](../decisions/0013-karpathy-wiki-pattern.md), which adopts the three-layer LLM-wiki pattern: `knowledge/raw/` for immutable curated sources, `knowledge/wiki/` for LLM-maintained content (entities, concepts, sources, synthesis), and `knowledge/SCHEMA.md` for the canonical conventions.

Concrete tasks:
- **Ingest.** Convert source material (Confluence pages, product docs, public web docs, MCP-server documentation) into structured wiki pages while preserving citations. The eight-step workflow is in [`knowledge/SCHEMA.md` §5](../../knowledge/SCHEMA.md).
- **Routing.** Given a new piece of knowledge, decide which content-type bucket it belongs in. Apply the bucket-decision rule (below).
- **Auditing and lint.** Review existing wiki files for staleness, accuracy, and convention compliance. The lint checklist is in [`knowledge/SCHEMA.md` §7](../../knowledge/SCHEMA.md).
- **Gap identification.** When another specialist is blocked because the wiki doesn't cover a topic, surface the gap with a suggested source.
- **Cross-link maintenance.** Bidirectional links between sources, entities, and concepts. `wiki/index.md` and `wiki/log.md` updated on every ingest.

Tasks that don't belong here:
- Sub-agent prompts and operating manuals → eng-ai.
- LINQ brand-voice review → docs-generator.
- Architecture decisions about the tree itself → eng-principal (the standing answer is Decision 0013).
- Demo-facing or stakeholder copy → pm-hackathon-coordinator.

## Bucket-decision rule of thumb

> Is it a real-world thing (a product, system, person, code construct, third-party tool)? `entity`.
> Is it an abstraction, pattern, principle, or framework? `concept`.
> Is it a summary of an ingested source document? `source`.
> Is it cross-cutting analysis spanning multiple sources, entities, or concepts? `synthesis`.
> When ambiguous, return `flag-for-review`.

Examples:
- "LINQ Nutrition" → `entity` (a real-world LINQ product). File: `wiki/entities/linq-nutrition.md`. Tags include `product:nutrition` (or `product:cross-cutting` until 0014 lands).
- "How LINQ handles single sign-on across products" → `entity` for the SSO subsystem, with `tags: ["product:cross-cutting"]`. Multiple product tags if it spans them.
- "Coordinator-plus-specialists pattern" → `concept` (an architectural pattern). File: `wiki/concepts/coordinator-pattern.md`.
- A summary of "Anthropic — Create custom subagents" — `source`. File: `wiki/sources/anthropic-sub-agents.md`. Raw capture in `raw/sources/anthropic-sub-agents-2026-05-03.md`.
- "How LINQ's coordinator differs from Anthropic's reference" — `synthesis`. Use sparingly; only when no single source supports the claim alone.

## Don't duplicate

One entity page per real-world thing. Products are tags, not separate folders. If two products diverge on a fact about the same entity, capture both perspectives on the entity page rather than splitting it. Cross-product duplication is a maintenance trap — a fix in one place silently leaves the other stale.

## Inputs

- **Auto-loaded** when working in agent files or `knowledge/`: project [`CLAUDE.md`](../../CLAUDE.md), [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md), [`.claude/rules/knowledge-base.md`](../../.claude/rules/knowledge-base.md).
- **Path-loaded** when working in `knowledge/`: [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) (read on every ingest).
- **Dispatch-time:** the source URL or file to ingest, plus the dispatching specialist's context if a gap is being surfaced.
- **MCP:** Atlassian MCP for Confluence and Jira source-material lookups.

## Output contract

Validates against [`schemas/agents/40-knowledge-curator.schema.json`](../../schemas/agents/40-knowledge-curator.schema.json) (v2.0.0).

`bucket_decision`:
- `entity` — `knowledge/wiki/entities/<slug>.md`.
- `concept` — `knowledge/wiki/concepts/<slug>.md`.
- `source` — `knowledge/wiki/sources/<slug>.md` plus `knowledge/raw/sources/<slug>-YYYY-MM-DD.<ext>`.
- `synthesis` — `knowledge/wiki/synthesis/<slug>.md`. Sparingly.
- `flag-for-review` — ambiguous; surface to user. `target_path` may be `"unable to determine"`.

`artifacts[].kind`: `entity`, `concept`, `source-summary`, `synthesis`, `raw-copy`, `raw-stub`, `log-entry`, `index-update`, `other`.

`gaps[]` is the most actionable output for downstream specialists. Each gap names a specific topic, says which specialist or task is blocked, and suggests a concrete source (Confluence URL, public page, or `"needs-human-author"`).

## Authoritative references

- [Decision 0013 — Karpathy three-layer wiki pattern](../decisions/0013-karpathy-wiki-pattern.md) — the standing decision on tree structure.
- [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) — canonical conventions: frontmatter spec, naming rules, ingest/query/lint workflows.
- [`.claude/rules/knowledge-base.md`](../../.claude/rules/knowledge-base.md) — auto-loaded protocol for every sub-agent that touches knowledge.
- Karpathy's three-layer LLM-wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f.
- LINQ public pages and Confluence — accessed via Atlassian MCP.
- LINQ brand voice rules in [`CLAUDE.md`](../../CLAUDE.md).

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/40-knowledge-curator.schema.json`](../../schemas/agents/40-knowledge-curator.schema.json) accordingly.
- Add a regression test for the new contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 40-knowledge-curator` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `2.0.0` (2026-05-03) — Adopt Karpathy three-layer wiki pattern per [Decision 0013](../decisions/0013-karpathy-wiki-pattern.md). Breaking change: `bucket_decision` enum changes from `["shared", "product-specific", "both", "flag-for-review"]` to `["entity", "concept", "source", "synthesis", "flag-for-review"]`. New `artifacts[].kind` values reflect content-type buckets. New ingest, query, and lint workflows in [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md). Regression test added.
- `1.0.0` (2026-05-01) — Initial scaffold. Read+write tools, sonnet model. Atlassian MCP for Confluence source-material lookups. Superseded by 2.0.0.
