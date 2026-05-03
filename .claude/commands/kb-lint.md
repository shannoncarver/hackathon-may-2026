---
description: Lint the knowledge base for orphan raw files, broken links, stale claims, contradictions, bidirectional drift, unknown product tags, and frontmatter completeness. Read-only — surfaces issues, does not fix them.
allowed-tools: Read, Glob, Grep, Bash, Agent
---

# /kb-lint — Health-check the wiki

Run the lint workflow defined in [`knowledge/SCHEMA.md` §7](knowledge/SCHEMA.md). Dispatch the [knowledge-curator](.claude/agents/40-knowledge-curator.md) with a lint task. The curator returns a structured response listing findings; this command does **not** auto-fix anything — fixes are the user's call.

## Checks (per SCHEMA.md §7)

1. **Orphans** — wiki pages not listed in `knowledge/wiki/index.md`.
2. **Orphan raw files** — files in `knowledge/raw/sources/` not referenced by any `wiki/sources/<slug>.md`. (The "I dropped a file and forgot" safety net.)
3. **Broken links** — markdown links pointing to paths that don't exist.
4. **Stale claims** — wiki pages where `updated:` is older than 90 days.
5. **Contradictions** — pages with overlapping tags making incompatible claims about the same entity.
6. **Bidirectional drift** — a source page's `entities[]` includes `wiki/entities/foo.md` but `foo.md`'s `sources[]` does not include the source page (or vice versa).
7. **Unknown product tags** — any `product:*` tag not in the canonical list (currently only `product:cross-cutting`; full list deferred to ADR 0014).
8. **Frontmatter completeness** — required fields per SCHEMA.md §2 are present and non-empty.

## What to do

1. **Dispatch the knowledge-curator** with: "Lint the knowledge base. Run all checks per `knowledge/SCHEMA.md` §7. Return findings as structured output validated against `schemas/agents/40-knowledge-curator.schema.json`."
2. **Report findings.** For each finding category, list affected files with one-line descriptions. Prioritize blockers (broken links, orphans, frontmatter completeness failures) over advisory items (stale claims, unknown tags).
3. **Append a log entry** to `knowledge/wiki/log.md` summarizing the lint result: `## [YYYY-MM-DD] lint | <count> findings`.
4. **Suggest next steps.** If lint is clean, say so explicitly. If findings exist, propose ordered fixes — typically: re-ingest stale or missing sources, then update cross-links, then deal with advisory items.

## Constraints

- Read-only. Do not edit wiki or raw files. The single allowed write is the log entry summarizing the lint run.
- The curator's response validates against the v2.0.0 schema. Validation failures surface to the user with both the raw response and the schema error.
