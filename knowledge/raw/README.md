# `knowledge/raw/` — immutable sources

Files in this tree are inputs, not outputs. The knowledge-curator places source documents here on ingest. Every other agent — and the curator on subsequent operations — reads from this tree but never edits in place.

If a source needs correcting or refreshing, supersede it with a new dated capture (`<slug>-YYYY-MM-DD.<ext>`) and update the matching `wiki/sources/<slug>.md` to point at the new file. The old file stays for provenance.

The synthesized layer — agent-authored summaries, entity pages, and cross-cutting analysis — lives in [`knowledge/wiki/`](../wiki/). Conventions for both layers live in [`knowledge/SCHEMA.md`](../SCHEMA.md).
