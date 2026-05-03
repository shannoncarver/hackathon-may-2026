# LINQ Hackathon — May 2026

> "The Forge: Season 2 — Every Minute Matters."
> Theme: Use of AI for solutions and work.

This repository is LINQ's hackathon entry for May 2026 — an internal AI workflow system that acts as a force multiplier for LINQ employees across Engineering, Product, Support, Documentation, and IT/Knowledge Management. It is also intended as a **LINQ-internal reference project for AI-driven development best practices**.

## Architecture

A primary coordinator (the main Claude Code session, governed by [`CLAUDE.md`](CLAUDE.md)) orchestrates work and delegates to ~14 domain-specialist sub-agents in [`.claude/agents/`](.claude/agents/). All inter-agent communication flows through the coordinator. Each specialist is scoped to a role with a JSON-schema input/output contract in [`schemas/agents/`](schemas/agents/).

See [`docs/research/repo-structure-research.md`](docs/research/repo-structure-research.md) for the full design rationale and citations.

## Quick start

```bash
# 1. Install dependencies
uv sync                       # or: pip install -e .

# 2. Configure secrets
cp .env.example .env
# edit .env and fill in ANTHROPIC_API_KEY

# 3. Open in Claude Code
claude
```

## Repository layout

| Path | Purpose |
| --- | --- |
| [`CLAUDE.md`](CLAUDE.md) | Coordinator project context — auto-loaded by Claude Code. |
| [`.claude/agents/`](.claude/agents/) | Sub-agent definitions (one Markdown file each). |
| [`.claude/commands/`](.claude/commands/) | Project slash commands — `/kb-ingest`, `/kb-lint`. |
| [`.claude/skills/`](.claude/skills/) | Reusable how-to knowledge as `SKILL.md` folders. |
| [`.claude/rules/`](.claude/rules/) | Path-loaded rules — coordination, knowledge base. |
| [`.claude/output-styles/demo.md`](.claude/output-styles/demo.md) | Stakeholder-facing presentation format. |
| [`.mcp.json`](.mcp.json) | MCP server registry, version-pinned. |
| [`schemas/agents/`](schemas/agents/) | JSON-schema input/output contracts. |
| [`evals/`](evals/) | Eval harness — per-agent, end-to-end, judge rubrics. |
| [`docs/decisions/`](docs/decisions/) | Decision records (architecture, process, and posture). |
| [`docs/pillars/`](docs/pillars/) | One brief per project pillar (six pillars). |
| [`knowledge/`](knowledge/) | Three-layer LLM-wiki — `raw/` (immutable sources), `wiki/` (LLM-maintained entities/concepts/sources/synthesis), `SCHEMA.md` (canonical conventions). See [`knowledge/SCHEMA.md`](knowledge/SCHEMA.md). |

## Working conventions

- Ask before hard-to-reverse decisions (directory layout, agent contracts, MCP version bumps).
- Cite sources for any pattern pulled from Anthropic docs or community repos.
- Identify the project pillar at the start of every task.
- Capture structural decisions as decision records in [`docs/decisions/`](docs/decisions/).

## Adding knowledge

The knowledge base is a three-layer wiki under [`knowledge/`](knowledge/) — see [`knowledge/SCHEMA.md`](knowledge/SCHEMA.md) for the canonical conventions. Two slash commands handle the everyday flow:

- **`/kb-ingest <URL-or-path>`** — add a knowledge source. Handles public URLs, auth-required Confluence/Jira pages (via the Atlassian MCP), files already in the repo, and files anywhere on disk. The command classifies the reference, handles MCP auth, and dispatches the [knowledge-curator](.claude/agents/40-knowledge-curator.md) to write the artifacts.
- **`/kb-lint`** — health-check the wiki. Surfaces orphan raw files, broken links, stale claims, contradictions, bidirectional drift, unknown product tags, and frontmatter completeness issues. Read-only — does not auto-fix.

Operational protocol: [`.claude/skills/kb-ingest/SKILL.md`](.claude/skills/kb-ingest/SKILL.md) and [`.claude/skills/kb-ingest/references/source-classification.md`](.claude/skills/kb-ingest/references/source-classification.md).

See [`CLAUDE.md`](CLAUDE.md) for the full set of conventions and brand/voice rules.

## Project status

Initial scaffold landed. Other 13 sub-agents, additional skills, the Inspect AI e2e suite, and CI workflow added in follow-up PRs.
