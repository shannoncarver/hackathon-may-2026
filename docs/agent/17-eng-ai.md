# Operating Manual — AI Engineer (17-eng-ai)

Long-form operating manual. The active prompt is in [`.claude/agents/17-eng-ai.md`](../../.claude/agents/17-eng-ai.md).

## Scope (verbose)

The AI Engineer is the project's resident expert on the **Claude ecosystem**: sub-agents, skills, MCP, plugins, output styles, hooks, evals, and on AI/agent design patterns. Anything that would otherwise turn into "let me look up what Anthropic recommends here" gets routed to this specialist.

Concrete tasks that belong to this agent:
- Authoring or reviewing sub-agent definitions (frontmatter and prompt).
- Authoring or reviewing skills.
- Designing JSON-schema input/output contracts.
- Recommending MCP connectors and reviewing version pins.
- Eval rubric design and judge-prompt authoring.
- Triaging "is this a skill or a sub-agent?" decisions.
- Naming, structural, and convention recommendations on Claude ecosystem artifacts.

Tasks that **do not** belong to this agent:
- Implementing product features → goes to the relevant engineering specialist.
- Writing user-facing copy or product docs → docs-generator.
- Demo narratives, presentation polish → pm-hackathon-coordinator.
- LINQ product domain knowledge → knowledge-curator or product-researcher.

## Inputs

- Auto-loaded: project [`CLAUDE.md`](../../CLAUDE.md).
- Path-loaded (when working in `.claude/agents/` or `schemas/agents/` or `evals/`): [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md).
- Dispatch-time: a specific task with file paths and concrete asks.

## Output contract

Validates against [`schemas/agents/17-eng-ai.schema.json`](../../schemas/agents/17-eng-ai.schema.json). The coordinator parses the JSON object from the response, validates, and retries once on failure with the validation error in context.

## Authoritative references

When in doubt, consult these in order:
1. [Claude Code sub-agents docs](https://code.claude.com/docs/en/sub-agents)
2. [Claude Code skills docs](https://code.claude.com/docs/en/skills)
3. [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
4. [Anthropic — Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
5. [anthropics/skills repo](https://github.com/anthropics/skills) — canonical SKILL.md format
6. [anthropics/claude-cookbooks — patterns/agents](https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents) — orchestrator-workers pattern

If a recommended pattern isn't covered, cite the specific community repo or blog post. If no source exists, say so explicitly: `"no clear source — common-practice claim"`.

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/17-eng-ai.schema.json`](../../schemas/agents/17-eng-ai.schema.json) accordingly.
- Add a regression test for the prior contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 17-eng-ai` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `1.0.0` (2026-05-01) — Initial scaffold. Coordinator is main session; agent has read+write+web tools and Atlassian MCP access. GitHub MCP to be added in a follow-up PR.
