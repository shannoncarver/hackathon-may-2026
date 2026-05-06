---
status: Accepted
date: 2026-05-04
category: knowledge-base
---

# Decision 0016 — Canonical product-slug list

**Status:** Accepted (2026-05-04)

## Context

[Decision 0013](0013-karpathy-wiki-pattern.md) established that LINQ products are tags, not folders. [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) §4 commits to a `tags: ["product:<canonical-slug>"]` convention but defers the canonical slug list to a future ADR. The `/kb-lint` workflow flags any `product:*` tag not in the canonical list, which means the list must exist before any product-specific page can pass lint cleanly.

The Tech Services debugger work (introduced in [Decision 0018](0018-ts-debugger-architecture.md)) writes the first product-scoped material — Harmony-Auth case pages — and triggers the need for this ADR.

## Decision

Establish the canonical product-slug list. Format and initial list are below; future products amend this ADR by adding to the list.

### Slug format

- All product slugs are lowercase kebab-case, prefixed with `product:` in the `tags:` array.
- A product slug names a LINQ product or a meta-bucket. Slugs are stable identifiers — once a slug is canonical, it does not change. New product names get new slugs; rebrands keep the old slug as an alias.

### Initial canonical list

| Slug | Refers to |
|---|---|
| `product:cross-cutting` | LINQ-wide, third-party, or methodology material that does not belong to a single product. The default tag when no product applies. |
| `product:harmony-auth` | Harmony-Auth — LINQ's authentication and authorization service. Dual-provider (Auth0 + Cognito), TypeScript Lambdas behind API Gateway, Terraform infrastructure. |

### Amendment process

Adding a slug is a small change — a one-line entry in the table above plus a brief context paragraph in this ADR is sufficient. No new ADR is required. Track each amendment with a dated bullet in the History section below.

## Consequences

- Pro: `/kb-lint` can validate `product:*` tags against a known list. Unknown tags surface as warnings instead of being silently accepted.
- Pro: Wiki pages tagged with `product:harmony-auth` (cases, entities, sources, etc.) pass lint without provisional `product:cross-cutting` tagging.
- Pro: The list grows on demand — no upfront enumeration of every LINQ product is required.
- Con: Adding a product requires editing this file. Acceptable: product creation is rare and structured.

## Sources

- [Decision 0013 — Three-layer LLM-wiki pattern](0013-karpathy-wiki-pattern.md), §4.
- [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) §4 (Product tagging).

## Migration

- [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) §4 updated: replaces the "future ADR" placeholder with a link to this decision.
- No existing wiki pages need retagging — `product:cross-cutting` was already the de facto canonical slug.

## History

- 2026-05-04 — Initial canonical list with two slugs (`product:cross-cutting`, `product:harmony-auth`). ADR originally numbered 0014; renumbered 0016 to avoid collision with `feature/auth0-logs-skill` branch (which claims 0014 for the auth0-logs-skill decision).
