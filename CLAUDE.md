# LINQ Hackathon — May 2026

## Project Context

This repository is for the **LINQ Hackathon (May 2026) — "The Forge: Season 2 — Every Minute Matters."**
Hackathon details: https://confluence.atlassian.linq.com/wiki/spaces/CTO/pages/732856331/The+Forge+Season+2+Every+Minute+Matters

**Theme:** Use of AI for solutions and work.

## Project Vision

Build an **internal AI workflow system** that acts as a force multiplier for LINQ employees across disciplines — Engineering, Product, Support, Documentation, and IT/Knowledge Management — by providing on-demand assistance, knowledge transfer, solution enablement, and resolution support across LINQ's products and platform services.

The system leverages modern AI primitives:
- **Agents and sub-agents** organized into domain-specific teams
- **MCP connectors** for external system integration
- **Skills, tools, and plugins** for specialized capabilities
- **CLIs and orchestration layers** for workflow automation

## Architecture

### Coordinator + Specialist Sub-Agents

A **primary coordinator agent** orchestrates work and delegates to domain-specialist sub-agents on demand. All inter-agent communication flows through the coordinator — no peer-to-peer chatter between specialists. Each sub-agent is scoped to a specific role with defined inputs, outputs, qualifications, and skills.

### Sub-Agent Roster

**Engineering**
- Principal Engineer (architecture, design review)
- Frontend Developer
- Backend Developer
- QA / Tester
- CloudOps Engineer
- Data Engineer
- Code Reviewer
- AI Engineer (Claude ecosystem — agents, sub-agents, skills, connectors, plugins, routines, live artifacts; AI/agent design patterns and best practices)

**Product**
- Product Manager
- Product Owner
- Task Planner
- Researcher

**Documentation**
- Document Generator (technical, user-facing, internal)

**Knowledge Management / IT**
- Knowledge curator and retrieval specialist

**Program Management**
- Hackathon Coordinator (organizes "The Forge: Season 2 — Every Minute Matters"; owns demo prep, presentation polish, and content review for stakeholders and judges; source of truth: https://confluence.atlassian.linq.com/wiki/spaces/CTO/pages/732856331/The+Forge+Season+2+Every+Minute+Matters)

This roster will evolve. Treat it as the current best understanding, not a fixed contract.

## Project Pillars

The system is built around six pillars. Most tasks map to one of these — when starting work, identify which pillar applies.

1. **Knowledge base** — three-layer LLM-wiki: `knowledge/raw/` (immutable curated sources), `knowledge/wiki/` (LLM-maintained entities, concepts, sources, synthesis), and `knowledge/SCHEMA.md` (canonical conventions). Standing decision: [Decision 0013](docs/decisions/0013-karpathy-wiki-pattern.md).
2. **Repo structure** — directory layout, naming conventions, and organization that scales with new agents, skills, and connectors.
3. **Documentation** — separate tracks for developers, agents (system prompts and operating instructions), and stakeholders evaluating the demo.
4. **Agent definitions** — qualifications, system prompts, allowed tools, input/output contracts, and inter-communication protocols.
5. **Skills management** — how skills are authored, versioned, discovered, and assigned to agents.
6. **MCP connector inventory** — which connectors each agent needs and how credentials/scopes are managed.

## Working Conventions

- **Ask before hard-to-reverse decisions.** Directory layout, naming schemes, and agent contracts should be proposed and reviewed before being committed.
- **Cite sources.** When pulling patterns from Anthropic docs or community repos, include URLs in the relevant doc.
- **Prefer small, reviewable proposals over large speculative scaffolding.** Don't generate ten agent definitions when one example would let us validate the pattern.
- **Capture decisions in `docs/`.** Every structural decision, link, and rationale lives in the repo so future agents and teammates can onboard without external context.
- **Identify the pillar.** When starting a task, state which of the six pillars it belongs to. If it doesn't fit one, flag that.
- **Knowledge base usage.** Conventions live in [`knowledge/SCHEMA.md`](knowledge/SCHEMA.md). Sub-agents that touch knowledge follow [`.claude/rules/knowledge-base.md`](.claude/rules/knowledge-base.md), which auto-loads on every dispatch. To add a source, run `/kb-ingest <URL-or-path>`. To health-check the wiki, run `/kb-lint`. Operational protocol: [`.claude/skills/kb-ingest/SKILL.md`](.claude/skills/kb-ingest/SKILL.md).
- **AWS-touching skills.** Follow the convention in [Decision 0016](docs/decisions/0016-aws-multi-account-skill-credentials.md) — named profiles, environment-derived defaults (`linq-<product>-{env}`), `--i-understand-this-is-prod` guardrail, `--aws-profile` override for break-glass, and the `sts:GetCallerIdentity` audit banner before any downstream call. Reference implementation: [`skills/verify-user-authorization/`](skills/verify-user-authorization/SKILL.md). Auto-load rule: [`.claude/rules/aws-skill-credentials.md`](.claude/rules/aws-skill-credentials.md).

## Brand and Voice

When generating any user-facing or stakeholder-facing content (demos, docs, presentations, emails), follow LINQ's brand and writing guidelines. Key rules: active voice, Oxford comma, em dashes without spaces, capitalize LINQ product names. Do not invent metrics or facts about LINQ — if unverified, say "Unable to verify."
