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

## Auth0 Skills Setup (optional)

To use the `/auth0-management` slash command — a unified skill with three subcommands (`logs`, `stats`, `sec`) for log queries, tenant health stats, and security inspection — you need M2M credentials for the sandbox tenant.

1. In the Auth0 Dashboard at <https://manage.auth0.com>, switch to the `linq-accounts-sandbox` tenant.
2. Navigate to **Applications → Applications → Create Application**.
3. Choose **Machine to Machine Applications**, name it descriptively (e.g., `LINQ AI Workflow - Logs Reader`), and click **Create**.
4. When prompted, authorize against **Auth0 Management API** with the following scopes (principle of least privilege—only what the skill actually needs):
   - `read:logs`—`logs` subcommand and the log-derived metrics in `stats` and `sec`
   - `read:stats`—daily and MAU sections of the `stats` subcommand
   - `read:anomaly_blocks`—IP block status in the `sec` subcommand
   - `read:attack_protection`—policy config endpoints in the `sec` subcommand
   - `read:users`—user-blocks lookup in the `sec` subcommand
5. From the application's Settings tab, copy the **Domain**, **Client ID**, and **Client Secret** into `.env`:
   ```
   AUTH0_DOMAIN=linq-accounts-sandbox.us.auth0.com
   AUTH0_CLIENT_ID=...
   AUTH0_CLIENT_SECRET=...
   ```
6. Test: run `/auth0-management show me failed logins in the last 24 hours` (verifies `read:logs`), `/auth0-management this week` (verifies `read:stats`), and `/auth0-management policy` (verifies `read:attack_protection`).

The Management API token caches to `.auth0-token.json` (gitignored, 24-hour TTL) and is shared across all three subcommands. Per [Decision 0025](../decisions/0025-auth0-management-merge.md) (which supersedes the per-skill ADRs [0014](../decisions/0014-auth0-logs-skill.md), [0019](../decisions/0019-auth0-stats-skill.md), and [0020](../decisions/0020-auth0-sec-skill.md) for skill shape while preserving the AuthProvider seam from 0014), this standalone setup is temporary—it will be retired when the centralized platform per [Decision 0015](../decisions/0015-centralized-platform-mcp.md) reaches M4.

### Adding a scope to an existing M2M app

If you already have the M2M app from an earlier setup and need to add `read:stats`:

1. In the Auth0 Dashboard, navigate to **Applications → [your M2M app] → APIs**.
2. Expand **Auth0 Management API** in the list.
3. Check **`read:stats`** alongside the existing `read:logs`. Click **Update**.
4. Delete the cached token so the next invocation re-grants with the new scope: `rm .auth0-token.json`.
5. Test with `/auth0-management this week`.

No client secret rotation is needed—the existing credentials keep working with the expanded scope.

### If your `.env` is exposed

If you suspect the `.env` file or `.auth0-token.json` was leaked (accidental commit, screenshare, lost laptop, etc.):

1. In the Auth0 Dashboard, navigate to **Applications → [your M2M app] → Settings**, click **Rotate Secret**, and confirm.
2. Delete the local cache: `rm .auth0-token.json`.
3. Update `.env` with the new Client Secret.
4. Re-test with `/auth0-management show me the latest 5 events`.

Per [Decision 0014](../decisions/0014-auth0-logs-skill.md), this manual rotation is operational debt—the centralized platform per [Decision 0015](../decisions/0015-centralized-platform-mcp.md) M4 will replace this with broker-managed tokens.

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

8. **Open a PR.** CI runs `pytest tests/`; schema regressions block merge. Run `python evals/run.py --agent <NN>-<domain>-<role>` locally before opening the PR and attach the report manually if the change is non-trivial. (Eval harness CI gating is deferred for the hackathon — see [Decision 0011](../decisions/0011-eval-harness-shape.md).)

## Adding a new skill

Pattern is in `.claude/skills/routing/`:

1. Create `.claude/skills/<name>/SKILL.md` with frontmatter (`name`, `description`, optional `allowed-tools`).
2. Add `references/` for lazy-loaded reference docs and `scripts/` for executable helpers as needed.
3. No schema or eval — skills are reference knowledge, not sub-agents.

## Bumping an MCP server version

1. Edit `.mcp.json` with the new version pin.
2. Add an entry at the top of `MCP_VERSION_CHANGELOG.md` with date, version, and one-line reason.
3. Run `python evals/run.py` locally. Attach the report to the PR.
4. If any agent's eval set regresses on judge score by ≥0.5, document mitigation before merging.
