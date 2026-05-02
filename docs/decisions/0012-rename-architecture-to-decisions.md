---
status: Accepted
date: 2026-05-02
category: process
---

# Decision 0012 — Rename `docs/architecture/` to `docs/decisions/`

**Status:** Accepted (2026-05-02)

## Context

The folder `docs/architecture/` (previously called the ADR folder, for Architecture Decision Records) accumulated 11 records spanning architecture, process, and project posture. Several were not architectural — for example, `0009-pr-review-flow.md` is a process decision and `0010-reference-quality-posture.md` is a project-posture decision. The folder name set the wrong bar for adding future records about process, branding, demo prep, or scope.

## Decision

Rename the folder, headings, and prose terminology:

- Folder: `docs/architecture/` → `docs/decisions/`.
- Heading prefix in records: `# ADR-NNNN — Title` → `# Decision NNNN — Title`.
- Term in prose: `ADR-NNNN` → `Decision NNNN`; `ADRs` → `decision records`.
- YAML frontmatter (`status`, `date`, `category`) added to every record so a categorized index can be generated later without further migration.

"ADR" remains acceptable as conversational shorthand — the term is industry-standard and well-known. In-repo artifacts (filenames, headings, prose) use "Decision NNNN" going forward.

## Consequences

- Folder, headings, and prose all use a single consistent term — no leakage of "architecture" back into conversations about process or posture decisions.
- Frontmatter is now present on every record; future tooling (categorized index, status filters) can consume it without a second migration.
- Existing inline `**Status:** Accepted (date)` lines remain alongside the new frontmatter — duplication is mild, and removing them is out of scope.
- The single-folder, flat-numbering convention is preserved. Sub-folder organization by category remains a future option only if record count grows substantially.

## Sources

- User direction (2026-05-02): folder name should match the actual decision mix.
- Industry conventions (`adr-tools`, Log4brains, structurizr) — flat numbered folder with frontmatter for categorization is the norm; sub-folders by category are uncommon.
