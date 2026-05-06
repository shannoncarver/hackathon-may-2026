---
status: Accepted
date: 2026-05-04
category: knowledge-base
---

# Decision 0017 — `case` as a fifth wiki bucket

**Status:** Accepted (2026-05-04)

## Context

[Decision 0013](0013-karpathy-wiki-pattern.md) established four wiki buckets — `entities/`, `concepts/`, `sources/`, `synthesis/`. The Tech Services debugger ([Decision 0018](0018-ts-debugger-architecture.md)) produces a new content type — sanitized resolved debug cases — that does not fit any of the four:

- Not `entity`: a case is an event with a resolution, not a real-world thing.
- Not `concept`: a case is a specific incident, not an abstraction or pattern.
- Not `source`: a case is first-party generated, not a summary of an ingested external document.
- Not `synthesis`: a case captures one symptom-investigation-fix arc, not cross-cutting analysis spanning multiple sources, entities, or concepts.

Forcing cases into `synthesis/` distorts the bucket semantics on both sides. The cleaner option is a fifth bucket. The knowledge-curator review (2026-05-04) confirmed the same conclusion: "case is a fifth bucket — does not fit any existing bucket without distorting bucket semantics."

## Decision

Adopt `cases/` as a fifth wiki bucket alongside `entities/`, `concepts/`, `sources/`, and `synthesis/`. Specifies the bucket purpose, frontmatter, body structure, write workflow, and lint coverage below.

### Bucket purpose

`wiki/cases/` holds sanitized resolved debug cases — symptom-investigation-fix arcs produced by Tech Services debugging tools (initially the Harmony-Auth debugger; future LINQ-product debuggers extend the same bucket). Each case page captures the *pattern*, not the specific incident, so future debug sessions retrieve prior similar resolutions as context.

### Frontmatter spec

```yaml
---
title: "Force-change-password bulk failure — PasswordResetRequiredException"
kind: case
slug: case-2026-05-04-force-change-password-bulk-failure
tags: ["product:harmony-auth", "debug-case"]
status: resolved              # one of: open, resolved, superseded
symptom: "PasswordResetRequiredException for multiple users"
resolution: "send-password-reset-email"
sources: ["raw/sources/case-2026-05-04-force-change-password-bulk-failure-2026-05-04.md"]
related: []
created: 2026-05-04
updated: 2026-05-04
---
```

Required fields: `title`, `kind`, `slug`, `tags`, `status`, `symptom`, `resolution`, `sources`, `created`, `updated`. Optional: `related`. Slug format: `case-YYYY-MM-DD-<short-symptom-slug>`.

### Body structure

Five sections, in order:

1. **Symptom** — one paragraph. What did the Tech Services engineer observe?
2. **Investigation** — which assembler ran and which signals it gathered.
3. **Root cause** — the underlying explanation.
4. **Fix** — the action that resolved the case.
5. **Codepath references** — `file:line` pointers into the product repo, where applicable.

### Write workflow

A `write_resolved_case(case_file, hypothesis, resolution)` function in the TS debugger ([Decision 0018](0018-ts-debugger-architecture.md)) produces case pages. The workflow mirrors [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) §5 (the `/kb-ingest` pipeline) programmatically, without invoking the `/kb-ingest` skill — cases are first-party artifacts, not external sources.

Steps:

1. Sanitize the case file. **PII redaction is deferred** (hackathon scope per user direction, 2026-05-04). A follow-up ADR will spec redaction rules before the tool moves toward production.
2. Write the sanitized capture to `knowledge/raw/sources/case-<slug>-YYYY-MM-DD.md` (condensed-copy form, `auth_required: false`).
3. Write the wiki page to `knowledge/wiki/cases/<slug>.md` citing the raw file in `sources:`.
4. Append a `## [YYYY-MM-DD] case | <Title>` entry to `knowledge/wiki/log.md`.
5. Add a row to the Cases section in `knowledge/wiki/index.md`.

### Lint coverage

`/kb-lint` extends to validate:

- Required fields present per the frontmatter spec above.
- `status:` is one of `open`, `resolved`, `superseded`. An `open` case older than 30 days is flagged.
- `tags:` contains at least one `product:*` tag from the [Decision 0016](0016-product-slug-canonical-list.md) canonical list.
- `sources:` resolves to an existing `raw/sources/<file>.md`.

## Consequences

- Pro: Cases are a first-class content type. `/kb-lint` enforces case-specific conventions; the knowledge-curator's bucket-decision enum extends to include `case`.
- Pro: Resolved cases become retrievable context for future debug sessions. The case corpus compounds value over time.
- Pro: `synthesis/` retains its narrow meaning (cross-cutting analysis across multiple sources). No bucket-semantic distortion.
- Con: Schema bump on the knowledge-curator's `bucket_decision` enum from `["entity", "concept", "source", "synthesis", "flag-for-review"]` to `["entity", "concept", "source", "synthesis", "case", "flag-for-review"]`. The change is additive; existing curator behavior is unaffected.
- Con: One more bucket for the lint workflow to know about. Mitigation: the additions follow the same pattern as the existing buckets.

## Sources

- [Decision 0013 — Three-layer LLM-wiki pattern](0013-karpathy-wiki-pattern.md), §1, §10.
- [Decision 0018 — Tech Services debugger architecture](0018-ts-debugger-architecture.md) (introduces the first writer of case pages).
- [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) §1, §2, §5, §7.
- knowledge-curator review (2026-05-04).

## Migration

- `knowledge/wiki/cases/` directory created with a `.gitkeep`.
- [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) updated: §1 lists `cases/`, §2 adds the case frontmatter block, §5 references this ADR for the case write workflow, §7 adds the case-specific lint checks, §8 adds a Case-write row to the operations table.
- [`knowledge/wiki/index.md`](../../knowledge/wiki/index.md) gains a `## Cases` section header (initially `_None yet._`).
- PII redaction rules deliberately deferred. Hackathon scope per user direction (2026-05-04). A follow-up ADR will spec redaction once the tool moves toward production.
- The `schemas/agents/40-knowledge-curator.schema.json` `bucket_decision` enum bump is deferred to the same follow-up ADR — the hackathon-scope writer (`write_resolved_case`) targets the new bucket directly without the curator's schema needing to update first.

## History

- 2026-05-04 — Initial decision. ADR originally numbered 0015; renumbered 0017 to avoid collision with `feature/auth0-logs-skill` branch (which claims 0015 for the centralized-platform-mcp decision).
