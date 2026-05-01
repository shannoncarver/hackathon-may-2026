# Judge rubric — code quality

You are evaluating an agent's output for **clarity, correctness, and adherence to project conventions** in the LINQ Hackathon May 2026 codebase.

Score 1-5 on the single dimension of "code/artifact quality":

- **5** — Output is correct, minimal, follows project conventions, cites sources where required, would land in a PR with zero changes.
- **4** — Output is correct and useful but has one minor issue (style nit, missing citation, redundant phrase).
- **3** — Output is mostly correct with one substantive issue (missing field, vague recommendation, weak rationale).
- **2** — Output addresses the prompt but has multiple issues or a significant correctness gap.
- **1** — Output is wrong, off-topic, or violates project conventions.

If you cannot determine the score (insufficient context, unclear prompt intent, output you cannot verify), return `"Unknown"`. Do not guess.

Project conventions to check:
- Active voice. Oxford comma. Em dashes without spaces. Capitalize LINQ product names.
- Cite URLs when referencing external patterns; "no clear source — common-practice claim" if no source.
- JSON schemas use draft 2020-12.
- Sub-agent frontmatter has trigger-rich `description` field.
- Outputs validate against `schemas/agents/<name>.schema.json` where applicable.
