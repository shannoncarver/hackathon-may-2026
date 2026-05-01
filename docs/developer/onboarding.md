# Developer Onboarding

## Prerequisites

- [Claude Code](https://code.claude.com/) installed
- Anthropic API key
- Atlassian account with access to LINQ Confluence/Jira (for the Atlassian MCP server)
- Python 3.11+ for the eval harness and tests

## Setup

```bash
git clone <repo>
cd hackathon-may-2026
cp .env.example .env
# Edit .env and fill in ANTHROPIC_API_KEY
uv sync                      # or: pip install -e .
claude                       # opens Claude Code in this project
```

The Atlassian MCP server uses per-user OAuth — the first invocation prompts for consent.

## Adding a new sub-agent

The pattern is canonicalized in [`docs/agent/17-eng-ai.md`](../agent/17-eng-ai.md). Steps:

1. **Pick a number.** Domain ranges:
   - 00-09 — Coordinator (currently empty; coordinator is the main session)
   - 10-19 — Engineering
   - 20-29 — Product
   - 30-39 — Documentation
   - 40-49 — Knowledge management / IT
   - 50-59 — Program management
   - 60-99 — Reserved for future domains

   Within a domain, lower numbers are more "principal" (architecture, review); higher numbers are more "implementation."

2. **Create the agent definition** at `.claude/agents/<NN>-<domain>-<role>.md`. Frontmatter must have: `name`, `description` (trigger-rich), `tools`, `model`, optional `mcpServers`, and `contract_version: 1.0.0`.

3. **Create the schema** at `schemas/agents/<NN>-<domain>-<role>.schema.json` (draft 2020-12).

4. **Create the operating manual** at `docs/agent/<NN>-<domain>-<role>.md`. Reference it from the agent's prompt body.

5. **Seed eval cases** at `evals/per-agent/<NN>-<domain>-<role>/cases.jsonl` (5+ cases drawn from real failures).

6. **Add a schema test** in `tests/test_schemas.py` (parametrized by glob — should pick up the new schema automatically; add a sample-output validation test if the structure is novel).

7. **Run locally** — `python evals/run.py --agent <NN>-<domain>-<role>`. Confirm the report passes.

8. **Open a PR.** CI runs `python evals/run.py --ci` and `pytest`. Merge when both pass and a human approves.

## Adding a new skill

Pattern is in `.claude/skills/routing/`:

1. Create `.claude/skills/<name>/SKILL.md` with frontmatter (`name`, `description`, optional `allowed-tools`).
2. Add `references/` for lazy-loaded reference docs and `scripts/` for executable helpers as needed.
3. No schema or eval — skills are reference knowledge, not sub-agents.

## Bumping an MCP server version

1. Edit `.mcp.json` with the new version pin.
2. Add an entry at the top of `MCP_VERSION_CHANGELOG.md` with date, version, and one-line reason.
3. Run `python evals/run.py --ci`. Attach the report to the PR.
4. If any agent's eval set regresses on judge score by ≥0.5, document mitigation before merging.
