# Pillar 1 — Knowledge base

Structured information about LINQ products, APIs, architecture, and demo domains.

## Where it lives

The knowledge base follows the three-layer LLM-wiki pattern adopted in [Decision 0013](../decisions/0013-karpathy-wiki-pattern.md):

- [`knowledge/raw/`](../../knowledge/raw/) — immutable curated sources. Public docs as condensed-with-citation copies; auth-required URLs (Confluence, Jira) as frontmatter stubs. Never edited in place.
- [`knowledge/wiki/`](../../knowledge/wiki/) — LLM-maintained markdown organized into four buckets: `entities/` (real-world things), `concepts/` (patterns and principles), `sources/` (one summary per ingested source), `synthesis/` (cross-cutting analysis). Plus `index.md` (master catalog) and `log.md` (append-only chronological record).
- [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) — canonical conventions: frontmatter spec, naming rules, ingest/query/lint workflows.

LINQ products are YAML frontmatter tags (`tags: ["product:<slug>"]`), not folders. Initial canonical slug is `product:cross-cutting`; a future ADR 0014 will establish the full product-slug list.

## Status

Empty scaffold plus one worked example: the Anthropic Claude Code sub-agents documentation, ingested 2026-05-03. Walk it end-to-end at [`knowledge/wiki/index.md`](../../knowledge/wiki/index.md) → entity → source summary → raw capture.

## How sub-agents discover and use it

Sub-agent usage is governed by [`.claude/rules/knowledge-base.md`](../../.claude/rules/knowledge-base.md), which auto-loads on every sub-agent dispatch (it scopes to `.claude/agents/**` and `knowledge/**`, mirroring the existing [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md) pattern). The rule encodes the wiki-first, cite-or-flag, gap-routing, raw-vs-wiki, and trust-boundary protocols. Agents inherit the behavior without per-prompt instruction.

## Owners

- Knowledge curator ([`40-knowledge-curator`](../agent/40-knowledge-curator.md)) — primary. Owns ingest, routing, lint, gap identification.
- Docs generator ([`30-docs-generator`](../agent/30-docs-generator.md)) — secondary. Fact-checks against `knowledge/wiki/` before quoting.
- Hackathon coordinator ([`50-pm-hackathon-coordinator`](../agent/50-pm-hackathon-coordinator.md)) — secondary. Verifies stakeholder claims against `knowledge/wiki/`.

## Related

- [Decision 0013 — Karpathy three-layer wiki pattern](../decisions/0013-karpathy-wiki-pattern.md) — the standing decision.
- [Decision 0004 — Knowledge base shape](../decisions/0004-knowledge-base-shape.md) — superseded.
- Karpathy's three-layer LLM-wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f.
- [Research summary](../research/repo-structure-research.md).
