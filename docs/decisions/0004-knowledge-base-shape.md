---
status: Accepted
date: 2026-05-01
category: architecture
---

# Decision 0004 — Knowledge base: one folder per LINQ product plus `_shared/`

**Status:** Accepted (2026-05-01)

## Context

Pillar 1 is "knowledge base — structured information about LINQ products and demo domains, organized into clear knowledge buckets." We need a directory shape for it.

## Decision

```
knowledge/
├── _shared/                   # cross-product, over-encompassing (LINQ company, brand, integration patterns, customer personas)
└── linq-products/
    └── <product-name>/        # one folder per product, populated in follow-up tasks
```

The product list is deferred to follow-up tasks owned by the knowledge-curator and product specialists.

## Consequences

- Documentation tracks product boundaries; cross-product material has a deliberate home in `_shared/` rather than a junk drawer.
- Initial scaffold creates empty `_shared/` and `linq-products/` with `.gitkeep`. Product folders are added per-product.
- A vector index, if added later, treats this directory as the source of truth — files are markdown, embeddings are derived.

## Sources

- Pillar 1 in [`CLAUDE.md`](../../CLAUDE.md)
- Three-ring knowledge pattern from [kipeum86/legal-agent-orchestrator](https://github.com/kipeum86/legal-agent-orchestrator) and [wshobson/agents](https://github.com/wshobson/agents)
