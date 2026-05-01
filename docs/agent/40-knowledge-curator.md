# Operating Manual — Knowledge Curator (40-knowledge-curator)

Long-form operating manual. The active prompt is in [`.claude/agents/40-knowledge-curator.md`](../../.claude/agents/40-knowledge-curator.md).

## Scope (verbose)

The Knowledge Curator owns the structure and integrity of the `knowledge/` tree — the authoritative source for LINQ product information and demo-domain context. The standing decision on tree shape is [ADR-0004](../architecture/0004-knowledge-base-shape.md): `_shared/` for cross-product material, `linq-products/<product>/` for product-specific content.

Concrete tasks:
- **Routing.** Given a new piece of knowledge, decide which bucket it belongs in. Apply the bucket-decision rule (below).
- **Auditing.** Review existing knowledge files for staleness, accuracy, and convention compliance.
- **Gap identification.** When another specialist is blocked because the knowledge base doesn't cover a topic, surface the gap with a suggested source.
- **Index maintenance.** Keep cross-links and indexes current as the knowledge base grows.
- **Ingesting.** Convert source material (Confluence pages, product docs, internal wikis) into structured knowledge files, preserving citations.

Tasks that don't belong here:
- Sub-agent prompts and operating manuals → eng-ai.
- LINQ brand-voice review → docs-generator.
- Architecture decisions about the tree itself → eng-principal (the standing answer is ADR-0004).
- Demo-facing or stakeholder copy → pm-hackathon-coordinator.

## Bucket-decision rule of thumb

> If removing a single LINQ product would break the document's premise, it belongs in that product's folder. If the document explains how LINQ products work together, or what LINQ as a company stands for, it belongs in `_shared/`.

Examples:
- "How LINQ Nutrition handles USDA reporting" → `linq-products/nutrition/` (specific to Nutrition).
- "LINQ's K-12 customer personas" → `_shared/` (cross-product).
- "Single sign-on across LINQ products" → `_shared/` (a connective topic).
- "LINQ Forms field validation rules" → `linq-products/forms/`.

When the answer is genuinely ambiguous, return `bucket_decision: "flag-for-review"` and let the user or eng-principal decide.

## Don't duplicate

If the same content would live in two product folders, hoist it to `_shared/` and link from each product folder. Cross-product duplication is a maintenance trap — a fix in one place silently leaves the other stale.

## Inputs

- Auto-loaded: project [`CLAUDE.md`](../../CLAUDE.md).
- Path-loaded (in `knowledge/` files when scoped rules are added): TBD.
- Dispatch-time: the source material to route or audit, plus the dispatching specialist's context if a gap is being surfaced.
- Atlassian MCP for Confluence source-material lookups.

## Output contract

Validates against [`schemas/agents/40-knowledge-curator.schema.json`](../../schemas/agents/40-knowledge-curator.schema.json).

`bucket_decision`:
- `shared` — `knowledge/_shared/<path>`.
- `product-specific` — `knowledge/linq-products/<product>/<path>`.
- `both` — primary home plus a pointer in the secondary location. Only use when content is genuinely dual-homed.
- `flag-for-review` — ambiguous; surface to user. `target_path` may be `"unable to determine"` in this case.

`gaps[]` is the most actionable output for downstream specialists. Each gap names a specific topic, says which specialist or task is blocked, and suggests a concrete source (Confluence URL, public page, or `"needs-human-author"`).

## Authoritative references

- [ADR-0004 — Knowledge base shape](../architecture/0004-knowledge-base-shape.md) — the standing decision on tree structure.
- LINQ public pages and Confluence — accessed via Atlassian MCP.
- LINQ brand voice rules in [`CLAUDE.md`](../../CLAUDE.md).

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/40-knowledge-curator.schema.json`](../../schemas/agents/40-knowledge-curator.schema.json) accordingly.
- Add a regression test for the prior contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 40-knowledge-curator` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `1.0.0` (2026-05-01) — Initial scaffold. Read+write tools, sonnet model. Atlassian MCP for Confluence source-material lookups.
