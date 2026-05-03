---
status: Accepted
date: 2026-05-03
category: architecture
supersedes: 0004
---

# Decision 0013 — Knowledge base: three-layer LLM-wiki pattern

**Status:** Accepted (2026-05-03). **Supersedes:** [Decision 0004](0004-knowledge-base-shape.md).

## Context

Pillar 1 ("knowledge base — structured information about LINQ products and demo domains") shipped under [Decision 0004](0004-knowledge-base-shape.md) as an empty two-folder skeleton: `knowledge/_shared/` and `knowledge/linq-products/<product>/`. That shape declared *where* product-scoped vs. cross-product material lives, but it had three gaps:

- No opinion on *what* a knowledge file is — overview, glossary, runbook, quote, raw scrape.
- No separation between immutable inputs (source documents we ingest) and synthesized outputs (the answers agents give from those sources).
- No ingest/query/lint pipeline for the curator or any consumer agent to follow.

[Decision 0010](0010-reference-quality-posture.md) commits us to the thorough branch over the lightweight one. A reference-quality knowledge base needs auditable provenance ("which source backs this claim?") and a deterministic operating model the curator can follow ingest after ingest.

## Decision

Adopt the three-layer LLM-wiki pattern from Karpathy's gist — adapted to Claude Code's path-loaded rules.

```
knowledge/
├── SCHEMA.md            # canonical conventions for agents
├── raw/                 # immutable curated sources; LLM never modifies
│   ├── README.md
│   └── sources/
└── wiki/                # LLM-maintained markdown
    ├── index.md         # master catalog
    ├── log.md           # append-only chronological record
    ├── entities/        # concrete things (a product, a person, a system)
    ├── concepts/        # abstractions, patterns, principles
    ├── sources/         # one summary per ingested source
    └── synthesis/       # cross-cutting analysis spanning multiple sources
```

Specific choices:

- **Content-type primary, products as tags.** Buckets in `wiki/` are `entities/`, `concepts/`, `sources/`, `synthesis/`. LINQ products are YAML frontmatter tags (`tags: ["product:cross-cutting"]`), not folders. Rationale: products are facets, not categories — one entity (e.g., single sign-on) often spans many products, and forcing a folder choice creates duplication.
- **`SCHEMA.md` is canonical.** Frontmatter spec, naming rules, ingest/query/lint workflows, and source-stub format live there. Other docs link to it.
- **Auto-loaded protocol via path-loaded rule.** A new `.claude/rules/knowledge-base.md` (Claude Code-specific) auto-loads on every sub-agent dispatch (it scopes to `.claude/agents/**` and `knowledge/**`, mirroring [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md)). Sub-agents follow the wiki-first protocol without per-prompt instruction — and without bloating the always-loaded root context.
- **Curator schema bumps to 2.0.0.** `bucket_decision` enum changes from `["shared", "product-specific", "both", "flag-for-review"]` to `["entity", "concept", "source", "synthesis", "flag-for-review"]`. Breaking change, fully versioned with a regression test.

## Consequences

- Pro: deterministic ingest pipeline. Every wiki claim cites a `raw/` file; every raw source has at least one wiki summary.
- Pro: one entity page per real-world thing. Cross-product duplication trap solved by tagging instead of foldering.
- Pro: schema-driven. Frontmatter is enforceable; orphans, stale dates, and unknown product tags are lintable.
- Pro: agents auto-consult the wiki via the path-loaded rule. New agents inherit the behavior for free.
- Con: more upfront convention than the 0004 two-folder shape. Mitigation: SCHEMA.md is the single source of truth.
- Con: breaking schema bump on knowledge-curator (`2.0.0`). Mitigation: regression test added; change is internal to this repo.
- Con: the auto-loading mechanism is Claude Code-specific. The protocol itself (wiki-first, cite-or-flag, gap-routing) is portable; only the path-load shim isn't. Acceptable per user direction — this repo targets Claude Code specifically.

## Alternatives considered

- **Keep 0004.** Rejected: the two-folder shape had no operations and no audit story.
- **Product primary, content-type secondary** (`wiki/products/<product>/{entities,concepts,...}/`). Rejected: locks us into a product taxonomy before we have one, and forces ambiguous content into a single product home.
- **Auto-load `index.md` via CLAUDE.md.** Rejected: bloats the always-loaded root context and changes on every ingest.
- **Per-agent prompt edits ("consult the wiki first").** Rejected: requires retrofitting every current and future agent file. Path-loaded rule scales without touching prompts.

## Sources

- Karpathy's three-layer LLM-wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- [Decision 0004 — Knowledge base shape](0004-knowledge-base-shape.md) (superseded)
- [Decision 0010 — Reference-quality posture](0010-reference-quality-posture.md)
- Claude Code path-loaded rules: https://code.claude.com/docs/en/sub-agents (and the existing pattern in [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md))
- Anthropic sub-agents doc — used as the worked example in this change: https://code.claude.com/docs/en/sub-agents

## Migration

- `knowledge/_shared/.gitkeep` and `knowledge/linq-products/.gitkeep` are deleted.
- `knowledge/{raw,wiki}/` scaffolds created with one worked example (Anthropic sub-agents doc).
- `schemas/agents/40-knowledge-curator.schema.json` bumps to `2.0.0`. Regression test added in `tests/test_schemas.py`.
- All five sub-agent prompts are updated to point at the new structure.
- ADR 0004 receives a Superseded header pointing here.
- A future Decision 0014 will establish the canonical product-slug list. Until then, the worked example uses `product:cross-cutting`.
