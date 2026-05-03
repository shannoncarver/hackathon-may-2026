# Repo Structure Research and Proposal

> **Note (2026-05-03):** Knowledge-base sections of this research are superseded by [Decision 0013](../decisions/0013-karpathy-wiki-pattern.md). References to `knowledge/_shared/`, `knowledge/linq-products/`, and the three-ring/per-product model reflect the original 0004 shape and remain here as historical record only. Current structure: see [`knowledge/SCHEMA.md`](../../knowledge/SCHEMA.md) and [Pillar 1](../pillars/1-knowledge-base.md).

**Project:** LINQ Hackathon — May 2026 ("The Forge: Season 2 — Every Minute Matters")
**Status:** Pre-scaffolding research. Awaiting review before any directories or agent definitions are created.
**Date:** 2026-05-01

This document bundles four deliverables into one review surface:
1. [Research Summary](#1-research-summary) — patterns observed in Anthropic docs and public reference repos, with citations.
2. [Proposed Repo Structure](#2-proposed-repo-structure) — directory tree with one-line purposes.
3. [Rationale](#3-rationale) — why this structure fits the coordinator-plus-specialists model and the six pillars in [`CLAUDE.md`](../../CLAUDE.md).
4. [Open Questions](#4-open-questions) — decisions needed before scaffolding.

---

## 1. Research Summary

### 1.1 Anthropic Official Guidance

#### Sub-agents in Claude Code

- Sub-agents are markdown files with YAML frontmatter, stored at `.claude/agents/<name>.md` (project-level, version-controlled) or `~/.claude/agents/<name>.md` (user-level, personal). Project-level wins on name collisions. ([Sub-agents docs](https://code.claude.com/docs/en/sub-agents))
- Frontmatter fields: `name`, `description` (the most important — used for automatic delegation), `tools` (allowlist), `model` (`opus`/`sonnet`/`haiku`/`inherit`), optional `disallowedTools`, `maxTurns`, `effort`, `permissionMode`, `mcpServers`, `memory`. ([Agent SDK reference](https://code.claude.com/docs/en/agent-sdk/subagents.md))
- Each sub-agent runs in an **isolated context window** — only the final summary returns to the coordinator. Sub-agents do **not** inherit the parent's conversation history or system prompt; they **do** inherit project `CLAUDE.md`.
- **Sub-agents cannot spawn sub-agents.** Only the primary (coordinator) session invokes the `Agent` tool. This shapes the architecture: the coordinator must pre-plan delegation; specialists are leaves.
- Vague descriptions kill delegation. Anthropic's official skill-creator literally calls trigger-rich descriptions "deliberately pushy" — the description is what Claude matches against incoming tasks. ([anthropics/skills — skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator))

#### CLAUDE.md conventions

- Loading cascade: `~/.claude/CLAUDE.md` → project ancestors (root → cwd) → nested directories (lazy-loaded) → `CLAUDE.local.md` overlays at each level. ([Memory docs](https://code.claude.com/docs/en/memory))
- For agent-team projects, the recommended split is:
  - **Root `CLAUDE.md`** — coordinator-facing project context (architecture, agent roster, working conventions).
  - **`.claude/rules/`** — topic-scoped rules with optional `paths:` matchers, lazy-loaded only when relevant.
  - **Sub-agent prompts** — domain expertise lives in each agent's frontmatter `prompt`, not in root CLAUDE.md.
- Keep root `CLAUDE.md` short (<200 lines): every sub-agent load pays the context cost.

#### Skills

- Skills are **folders**, not files: `.claude/skills/<name>/SKILL.md` plus optional `scripts/`, `references/`, `assets/`. ([Skills docs](https://code.claude.com/docs/en/skills); [anthropics/skills](https://github.com/anthropics/skills))
- `SKILL.md` frontmatter: `name`, verbose `description` with trigger phrases, optional `allowed-tools`, `disable-model-invocation`, `user-invocable`, `model`, `effort`, `context: fork`, `agent: Explore`, `paths:` matchers, `argument-hint`, named `arguments`.
- Skills support `` !`shell-command` `` substitution to inject dynamic context before Claude reads the prompt.
- **Skills vs sub-agents**: skills are reference knowledge / step-by-step procedures loaded into the current conversation; sub-agents are isolated executions that return only a summary. Use skills for shared workflows (e.g., `/deploy-checklist`, `/linq-brand-check`) and sub-agents for context-heavy specialist tasks.
- Skills are **plugin-scoped or repo-scoped**, not agent-scoped. There is no per-sub-agent skill allowlist convention in any repo I found — assignment is implicit through the prompt.

#### MCP server configuration

- Project-level: `.mcp.json` at repo root (team-shared, version-controlled). User-level lives in `~/.claude.json`. ([MCP docs](https://code.claude.com/docs/en/mcp))
- Sub-agents **can scope MCP servers** by referencing names in their frontmatter `mcpServers:` field, or by inlining a server definition. Best practice: declare shared servers in `.mcp.json` once, reference by name from each agent.
- Credentials via `${ENV_VAR}` interpolation; never inline secrets. Project `.mcp.json` requires explicit user approval on first use.
- Pin MCP server versions in `.mcp.json` and keep a changelog — a real-world pattern from [legal-agent-orchestrator](https://github.com/kipeum86/legal-agent-orchestrator/blob/main/MCP_VERSION_CHANGELOG.md). MCP servers are still moving fast and a silent upgrade can break a specialist mid-demo.

#### Plugins

- A plugin packages skills + agents + commands + hooks + MCP + LSP + output-styles into a single distributable, with a `.claude-plugin/plugin.json` manifest at root. ([Plugins docs](https://code.claude.com/docs/en/plugins))
- Plugin assets live at the **plugin root** (`skills/`, `agents/`, etc.), **not** inside `.claude-plugin/` — this is a common gotcha.
- Recommendation: stay standalone (`.claude/`) for the hackathon. Plugin packaging is correct only if we plan to redistribute the system to other LINQ teams. We can convert later — the file formats are the same.

#### Settings & hooks

- Precedence (highest → lowest): managed → CLI args → `.claude/settings.local.json` → `.claude/settings.json` → `~/.claude/settings.json`. Array fields like `permissions.allow`/`deny` merge across layers. ([Settings docs](https://code.claude.com/docs/en/settings))
- Hooks fire on session lifecycle (`SessionStart`/`End`), turn lifecycle (`UserPromptSubmit`, `Stop`), and tool calls (`PreToolUse`, `PostToolUse`). ([Hooks docs](https://code.claude.com/docs/en/hooks))
- For agent teams, hooks are the right layer to **deterministically enforce** conventions (block `rm`, auto-format on edit, log subagent invocations). CLAUDE.md is for guidance; hooks are for hard rules.

---

### 1.2 Public Reference Implementations

The most informative repos cross-checked against the GitHub API on 2026-05-01:

| Repo | What it offers | Key takeaway |
| --- | --- | --- |
| [anthropics/skills](https://github.com/anthropics/skills) (126.8k★) | Canonical SKILL.md format, eval harness shipped inside skill folders | Each skill is a self-contained folder with `scripts/`, `references/`, `assets/`, and a real `eval-viewer/` |
| [anthropics/claude-cookbooks — patterns/agents](https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents) | Orchestrator-workers reference prompts | A lead agent that classifies, budgets subagent count, and **never delegates synthesis** ([research_lead_agent.md](https://github.com/anthropics/claude-cookbooks/blob/main/patterns/agents/prompts/research_lead_agent.md)) |
| [anthropics/claude-agent-sdk-demos — research-agent](https://github.com/anthropics/claude-agent-sdk-demos/tree/main/research-agent) (2.3k★) | Two-layer separation: `.claude/` for harness assets, `research_agent/` for code + role prompts | Splits user-facing slash commands (auto-discovered) from internal orchestrator code |
| [wshobson/agents](https://github.com/wshobson/agents) (34.6k★) | 78-plugin marketplace; agent-teams plugin shows the canonical coordinator | **Coordinator gets read-only tools** (`Read, Glob, Grep, Bash`); only specialists get `Write/Edit` ([team-lead.md](https://github.com/wshobson/agents/blob/main/plugins/agent-teams/agents/team-lead.md)) |
| [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) (18.9k★) | 100+ subagents in 10 numbered categories | **Numeric prefixes** (`01-…`, `09-…`) for stable ordering; meta-orchestration is its own category |
| [kipeum86/legal-agent-orchestrator](https://github.com/kipeum86/legal-agent-orchestrator) | Closest analog: 8 specialists + knowledge bases + MCP + audit trails | Specialists as **prompt templates** under `skills/prompt-templates/`; `events.jsonl` audit log; **trust boundary** treats specialist outputs as untrusted data |
| [awslabs/cli-agent-orchestrator](https://github.com/awslabs/cli-agent-orchestrator) (521★) | Supervisor + workers via MCP, cross-CLI | Distinguish **`assign` (parallel/async)** from **`handoff` (sequential/sync)**; "supervisor must yield, never busy-wait" |
| [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) (42.1k★) | Curated index | Useful for discovering further references; not a structural template |

#### 10 Conventions That Recur Across Repos

1. **Subagent file format is universal** — Markdown + YAML frontmatter (`name`, `description`, `tools`, `model`). Don't deviate.
2. **Group agents by domain folder once you exceed ~5–6 specialists.** Pure flat lists only survive in tiny demos.
3. **Coordinators have read-only tools and never do specialist work.** Both [team-lead.md](https://github.com/wshobson/agents/blob/main/plugins/agent-teams/agents/team-lead.md) and [research_lead_agent.md](https://github.com/anthropics/claude-cookbooks/blob/main/patterns/agents/prompts/research_lead_agent.md) enforce this in the prompt.
4. **Triplet bundle** `agents/ + commands/ + skills/` per domain (wshobson). For ~12 specialists, a single flat `agents/` with numeric prefixes is the simpler equivalent.
5. **Skills are folders** with `SKILL.md` + `scripts/` + `references/` + optional `assets/`.
6. **Project `.mcp.json` with version pinning + a `MCP_VERSION_CHANGELOG.md`.** Credentials in `.env` referenced via `${VAR}`.
7. **Knowledge base in three concentric rings**: shared global (`docs/`), per-skill (`skills/<name>/references/`), per-run runtime (`output/<run-id>/`).
8. **Real eval/test harness, not toy.** Test the **router** (does it pick the right specialist?), each **prompt template** (does it stay in scope?), and the **trust boundary** (does sanitization fire?).
9. **Treat subagent outputs as untrusted data.** Sanitize before re-feeding into another agent's context. Log trust-boundary violations.
10. **Coordinators yield, never busy-wait.** Distinguish `assign` (parallel) from `handoff` (sequential) at the prompt level. Document a "one owner per file" rule for parallel writes.

---

### 1.3 Versioning and Evaluation Patterns

#### Versioning

- **In-repo as code** (PRs, git history) is the right fit for this project. Dedicated prompt registries (LangSmith, MLflow, Maxim) add operational overhead we don't need at hackathon scale. ([Anthropic engineering — multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system))
- **Semver for the input/output contract**, not for prose tweaks: major = renamed/removed field, minor = additive, patch = wording. ([Maxim AI — Prompt Versioning](https://www.getmaxim.ai/articles/prompt-versioning-and-its-best-practices-2025/))
- **Immutable history.** Every documented platform agrees: published versions are never edited; changes always create new versions. Git gives us this for free.
- **Git tags for demo checkpoints** (`demo-day-rehearsal-1`, `final-submission`) — fastest possible rollback if something regresses 30 minutes before a demo.
- **Schema-as-contract.** Each specialist publishes a JSON schema for its output; the coordinator validates and retries once on failure before bubbling up. This is the difference between "silent rename breaks downstream" and "loud, immediate failure." ([Sopan Deole — Data Contracts for Agents](https://medium.com/@deolesopan/data-contracts-for-agents-keep-tools-and-schemas-stable-as-systems-evolve-8af6f3e024ba))
- **Skip A/B testing.** For 2–3 weeks, do "replay" instead: keep ~10–20 prompts from real dev sessions and re-run candidate versions before merge.

#### Evaluation

Anthropic's documented advice ([Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)):
- **20–50 cases per specialist, drawn from real failures.** Not synthetic benchmarks.
- **Multi-dimensional rubrics scored in isolation.** Don't ask one judge to grade four dimensions in one call.
- **Give the judge an "Unknown" escape hatch.** Prevents hallucinated scores.
- **Evaluate end-state, not transcript.** Check the final answer/database row, not the path taken.
- **Calibrate judges against humans periodically.** Confidence comes from low divergence.

For hackathon scale, the smallest harness that works:
- Per-specialist eval: ~10 cases each, deterministic scorer (schema validation) + LLM-as-judge with a single-dimension rubric.
- End-to-end eval: ~5 representative tasks, scored on outcome only.
- Hand-rolled `evals/run.py` that prints a markdown pass/fail table; runs in CI on every PR.
- Capture full traces (`traces/<run-id>.jsonl`) — Anthropic's research blog identifies trace observability as the highest-leverage thing they did.
- Counter judge biases: randomise pairwise order (position bias), cap output length the judge sees (verbosity bias). ([arxiv — Empirical Study of LLM-as-a-Judge](https://arxiv.org/html/2506.13639v1))
- Skip: managed platforms, online production scoring, human calibration cycles.

---

## 2. Proposed Repo Structure

```
hackathon-may-2026/
├── CLAUDE.md                          # Coordinator-level project context (already exists)
├── README.md                          # Stakeholder-facing overview (already exists, empty)
├── .claude/
│   ├── settings.json                  # Tool allowlists, model defaults, hooks (team-shared)
│   ├── agents/                        # Sub-agent definitions — flat with numeric prefixes
│   │   ├── 00-coordinator.md          # Primary orchestrator (read-only tools)
│   │   ├── 10-eng-principal.md        # Engineering domain (10–19)
│   │   ├── 11-eng-backend.md
│   │   ├── 12-eng-frontend.md
│   │   ├── 13-eng-qa.md
│   │   ├── 14-eng-cloudops.md
│   │   ├── 15-eng-data.md
│   │   ├── 16-eng-reviewer.md
│   │   ├── 17-eng-ai.md               # Claude ecosystem specialist (agents/skills/connectors)
│   │   ├── 20-product-pm.md           # Product domain (20–29)
│   │   ├── 21-product-owner.md
│   │   ├── 22-product-planner.md
│   │   ├── 23-product-researcher.md
│   │   ├── 30-docs-generator.md       # Documentation domain (30–39)
│   │   ├── 40-knowledge-curator.md    # Knowledge management (40–49)
│   │   └── 50-pm-hackathon-coordinator.md  # Program Management (50–59) — demo prep, judge-facing polish
│   ├── skills/                        # Reusable how-to knowledge (folders, not files)
│   │   ├── routing/SKILL.md           # Pillar classification + specialist selection
│   │   ├── linq-brand-voice/          # /skills brand check; loaded by docs/PM agents
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── pillar-classification/SKILL.md
│   ├── commands/                      # Slash-commands (user-facing entry points)
│   │   └── (TBD per pillar)
│   ├── rules/                         # Topic-scoped, path-matched rules (lazy-loaded)
│   │   └── coordination.md            # How agents communicate via the coordinator
│   └── output-styles/
│       └── demo.md                    # Stakeholder-friendly presentation mode
├── .mcp.json                          # Version-pinned MCP server configs (shared)
├── .mcp.local.json                    # gitignored — personal MCP overrides
├── MCP_VERSION_CHANGELOG.md           # Bumps + reasons (legal-orchestrator pattern)
├── docs/                              # Shared, human-readable knowledge
│   ├── research/                      # Pre-decision research (this file lives here)
│   ├── decisions/                     # Decision records (one record per structural choice)
│   ├── pillars/                       # One brief per project pillar (six files)
│   ├── stakeholder/                   # Demo narrative, presentation script, screenshots
│   ├── developer/                     # Onboarding, contribution guide, run-the-system
│   └── agent/                         # Agent operating manuals (long-form behind frontmatter)
├── knowledge/                         # The "knowledge base" pillar — domain buckets
│   ├── linq-products/                 # LINQ K12 product info (one folder per product)
│   └── demo-domains/                  # Demo-scenario knowledge buckets
├── schemas/                           # JSON schemas — agent input/output contracts
│   └── agents/<agent-name>.schema.json
├── evals/                             # Lightweight harness
│   ├── run.py                         # Runs all eval sets, prints markdown table
│   ├── per-agent/<name>/cases.jsonl
│   └── e2e/cases.jsonl
├── tests/                             # Unit tests for routing, schema validation, MCP pins
│   ├── test_routing.py
│   ├── test_schemas.py
│   └── test_mcp_pins.py
├── scripts/                           # Build/dev tooling (eval runners, lint, package)
├── traces/                            # gitignored — runtime trace logs (one JSONL per run)
├── output/                            # gitignored — per-run agent outputs and audit events
├── .env.example                       # Required env vars; copy to .env
└── .gitignore                         # Excludes .env, traces/, output/, .claude/settings.local.json
```

### Top-level folders, one-line purposes

| Path | Purpose |
| --- | --- |
| `CLAUDE.md` | Loaded automatically by every Claude Code session — coordinator-level project context. |
| `.claude/` | Claude Code configuration the harness auto-discovers (agents, skills, commands, rules, settings, output-styles). |
| `.mcp.json` | Project-level MCP server registry (version-pinned). |
| `MCP_VERSION_CHANGELOG.md` | Append-only log of MCP version bumps and the reason for each. |
| `docs/` | Human-readable docs split by audience: research, architecture, pillars, stakeholder, developer, agent. |
| `knowledge/` | Structured domain knowledge — the literal "knowledge buckets" pillar. |
| `schemas/` | Versioned JSON schemas defining each agent's input/output contract. |
| `evals/` | Eval datasets and runner — per-agent and end-to-end. |
| `tests/` | Unit tests for deterministic logic (routing, schema validation, MCP pinning). |
| `scripts/` | Build/dev tooling kept out of `evals/` and `tests/`. |
| `traces/` | gitignored runtime trace logs for post-hoc debugging. |
| `output/` | gitignored runtime artifacts (per-run agent outputs, audit events). |
| `.env.example` | Documents required env vars without committing secrets. |

---

## 3. Rationale

### Why this fits the coordinator-plus-specialists model

- **Single `.claude/agents/` directory, flat with numeric prefixes** — at ~14 agents we are right at the boundary where flat is still readable but ordering matters. Numeric prefixes (VoltAgent's pattern) give us stable, intentional ordering (`00-coordinator` first, then domain-grouped 10s/20s/30s/40s) without forcing nested folders. We can move to subdirectories later if the roster grows past ~20.
- **Coordinator has read-only tools.** [`00-coordinator.md`](#) gets `Read, Glob, Grep, Bash` only — no `Write`/`Edit`. This is the [team-lead.md](https://github.com/wshobson/agents/blob/main/plugins/agent-teams/agents/team-lead.md) and [research_lead_agent.md](https://github.com/anthropics/claude-cookbooks/blob/main/patterns/agents/prompts/research_lead_agent.md) pattern — the coordinator dispatches and synthesizes; specialists do the work. This makes the "all inter-agent communication flows through the coordinator" rule from `CLAUDE.md` enforceable, not aspirational.
- **JSON schemas in `schemas/agents/<name>.schema.json` define each specialist's output contract.** The coordinator validates outputs and retries once on failure. This addresses the data-contracts pattern — without it, a renamed field silently breaks downstream agents.
- **`.claude/skills/routing/`** holds the coordinator's specialist-selection logic as a skill, not buried in the coordinator's prompt. Skills can be edited, versioned, and tested independently from agent definitions. The coordinator references it with `/skills routing` or via prompt instructions.
- **`.claude/rules/coordination.md`** captures the inter-agent communication protocol with a path matcher so it only loads when working on coordinator/agent files. Keeps root `CLAUDE.md` short.

### Why this fits the six pillars in [`CLAUDE.md`](../../CLAUDE.md)

| Pillar | Where it lives | Why |
| --- | --- | --- |
| **1. Knowledge base** | `knowledge/linq-products/` and `knowledge/demo-domains/` (raw buckets); `.claude/skills/<name>/references/` (per-skill curated extracts) | Three-ring model from public repos: shared raw, per-skill curated, per-run runtime. Keeps cold-storage knowledge separate from active agent context. |
| **2. Repo structure** | The whole tree, with [`docs/decisions/`](#) capturing decision records for each structural decision | Numeric-prefixed flat agents, triplet-equivalent (`agents/`, `commands/`, `skills/` under `.claude/`), and explicit MCP pinning — all observed conventions. |
| **3. Documentation** | `docs/{stakeholder,developer,agent}/` | Three audiences, three folders. Stakeholder = demo narrative; developer = onboarding; agent = long-form operating instructions that feed back into agent prompts. |
| **4. Agent definitions** | `.claude/agents/*.md` (system prompts) + `schemas/agents/*.schema.json` (I/O contracts) + `docs/agent/*.md` (long-form operating manuals) | Frontmatter is concise; schema is the contract; long-form lives in `docs/agent/` and is referenced from prompts to keep frontmatter under context limits. |
| **5. Skills management** | `.claude/skills/<name>/` (folders with `SKILL.md` + `references/` + optional `scripts/`) | Anthropic's canonical layout. Versioning via git; assignment to agents is implicit through prompt references. |
| **6. MCP connector inventory** | `.mcp.json` (pinned versions) + `MCP_VERSION_CHANGELOG.md` (bumps + reasons) + per-agent `mcpServers:` references in frontmatter | Centralized definition, per-agent scoping. The changelog is non-standard but battle-tested in [legal-agent-orchestrator](https://github.com/kipeum86/legal-agent-orchestrator). |

### What this structure deliberately avoids

- **No premature plugin packaging.** Plugin format is a future migration once the design stabilizes, not the day-1 layout.
- **No flat dump of "prompts/" at the root.** Specialists live in `.claude/agents/` so the harness auto-discovers them; we don't run a custom orchestrator that loads prompts from arbitrary paths.
- **No knowledge-base-as-database.** `knowledge/` is markdown + structured docs. If we later need vector search, an index is built over these files — they remain the source of truth.
- **No agent-per-skill folder explosion.** Skills are shared, plugin-scoped equivalents, not per-agent. If two agents need the same procedure, they reference the same skill.

---

## 4. Decisions and Remaining Questions

### Project posture (cross-cutting)

This repo is intended as a **LINQ-internal reference project for AI-driven development best practices**, not just a hackathon demo. Where a recommendation has a "lightweight for hackathon" branch and a "thorough industry-standard" branch, **default to the thorough one.** This decision shapes every other decision below — eval harness, trust boundary, schemas, decision records, traces all stay in scope.

### Resolved Decisions (2026-05-01)

| # | Decision | Resolution |
| --- | --- | --- |
| 1 | Specialist location | **`.claude/agents/`** — Claude Code-native, harness-discovered. |
| 2 | Coordinator placement | **Main session governed by root `CLAUDE.md`** — user talks directly to the coordinator. No `00-coordinator.md` sub-agent. |
| 3 | Plugin packaging | **Standalone.** No `.claude-plugin/` manifest for now. Plugin migration is a future option. |
| 4 | Knowledge base shape | **One folder per LINQ product**, plus a folder for cross-product / over-encompassing docs. Documentation is broken down by product. *(Specific product list TBD — see Remaining Question A.)* |
| 6 | Trust boundary | **In scope** — sanitize subagent outputs, wrap suspicious tokens, log violations to `events.jsonl`. (Reference-quality posture: keep it in.) |
| 7 | CLI / orchestration layer | **Claude Code native only.** No `linq-assist` CLI wrapper. The user runs `claude` in this repo. |
| 8 | Custom output style | **Yes** — draft `.claude/output-styles/demo.md` with `Objective → Progress → Next Steps` format for stakeholder demos. |
| 9 | MCP connectors (initial) | **Confluence and GitHub** for now. Add others as needs emerge. Both pinned in `.mcp.json` with entries in `MCP_VERSION_CHANGELOG.md`. |
| 10 | Branch strategy | **PR for review.** Scaffold on a `scaffold/initial-structure` branch (or equivalent) and open a PR rather than committing straight to `main`. |

### Final Resolutions (2026-05-01, follow-up)

**A. LINQ product list for the knowledge base.**
**Deferred to separate tasks.** Initial scaffold creates the empty `knowledge/_shared/` and `knowledge/linq-products/` folders with `.gitkeep` — product folders get added in follow-up PRs as the knowledge-curator and product-team workstreams kick off.

**B. Eval harness shape.**
**Approved as proposed:**
- Hand-rolled `evals/run.py` runner for per-agent datasets (~150 lines Python; demonstrates the pattern cleanly for the reference role).
- [Inspect AI](https://inspect.aisi.org.uk/) for the end-to-end eval set + trust-boundary safety tests (UK AI Safety Institute framework — citing it strengthens the reference posture).
- ~20 cases per agent, drawn from real failures (Anthropic guidance: 20–50).
- Two scorers per case: deterministic (schema validation, keyword/regex) + LLM-as-judge (single-dimension rubric, "Unknown" escape hatch, pinned judge model).
- Reports written to `evals/reports/<date>-<run-id>.md`.
- CI: GitHub Action runs the full suite on every PR; failure blocks merge.
- Judge-calibration: human-review 20% of judge scores weekly; track divergence as its own metric.

---

## Sources

### Anthropic official
- [Claude Code — Sub-agents docs](https://code.claude.com/docs/en/sub-agents)
- [Claude Code — Memory & CLAUDE.md docs](https://code.claude.com/docs/en/memory)
- [Claude Code — Skills docs](https://code.claude.com/docs/en/skills)
- [Claude Code — MCP docs](https://code.claude.com/docs/en/mcp)
- [Claude Code — Plugins docs](https://code.claude.com/docs/en/plugins)
- [Claude Code — Settings docs](https://code.claude.com/docs/en/settings)
- [Claude Code — Hooks docs](https://code.claude.com/docs/en/hooks)
- [Claude Code — Output Styles docs](https://code.claude.com/docs/en/output-styles)
- [Claude Agent SDK — Sub-agents reference](https://code.claude.com/docs/en/agent-sdk/subagents.md)
- [Anthropic Engineering — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Anthropic Engineering — Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

### Reference repos
- [anthropics/skills](https://github.com/anthropics/skills) — canonical skill format
- [anthropics/claude-cookbooks — patterns/agents](https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents) — orchestrator-workers pattern
- [anthropics/claude-cookbooks — research_lead_agent.md](https://github.com/anthropics/claude-cookbooks/blob/main/patterns/agents/prompts/research_lead_agent.md) — coordinator system prompt
- [anthropics/claude-agent-sdk-demos — research-agent](https://github.com/anthropics/claude-agent-sdk-demos/tree/main/research-agent) — official multi-agent demo
- [anthropics/anthropic-quickstarts](https://github.com/anthropics/anthropic-quickstarts) — single-agent templates
- [wshobson/agents](https://github.com/wshobson/agents) — 78-plugin marketplace
- [wshobson/agents — agent-teams plugin](https://github.com/wshobson/agents/tree/main/plugins/agent-teams) — coordinator pattern with read-only tools
- [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) — 100+ subagents, numeric-prefix categories
- [kipeum86/legal-agent-orchestrator](https://github.com/kipeum86/legal-agent-orchestrator) — closest analog (8 specialists + KB + MCP + audit)
- [awslabs/cli-agent-orchestrator](https://github.com/awslabs/cli-agent-orchestrator) — supervisor + workers via MCP
- [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) — curated index

### Versioning & evals
- [Maxim AI — Prompt Versioning Best Practices](https://www.getmaxim.ai/articles/prompt-versioning-and-its-best-practices-2025/)
- [Maxim AI — Top 5 Prompt Versioning Tools 2026](https://www.getmaxim.ai/articles/top-5-prompt-versioning-tools-in-2026/)
- [LangChain docs — Manage prompts](https://docs.langchain.com/langsmith/manage-prompts)
- [MLflow Prompt Registry](https://mlflow.org/prompt-registry)
- [Sopan Deole — Data Contracts for Agents](https://medium.com/@deolesopan/data-contracts-for-agents-keep-tools-and-schemas-stable-as-systems-evolve-8af6f3e024ba)
- [Inspect AI (UK AISI)](https://inspect.aisi.org.uk/)
- [OpenAI Evals (GitHub)](https://github.com/openai/evals)
- [Braintrust — Evaluate systematically](https://www.braintrust.dev/docs/guides/evals)
- [Promptfoo — LLM Rubric](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/)
- [arxiv — Empirical Study of LLM-as-a-Judge](https://arxiv.org/html/2506.13639v1)
- [Phoenix — Evaluating Multi-Agent Systems](https://arize.com/docs/phoenix/evaluation/concepts-evals/evaluating-multi-agent-systems)
- [Databricks — Supervisor Agent Architecture](https://www.databricks.com/blog/multi-agent-supervisor-architecture-orchestrating-enterprise-ai-scale)

### Items flagged as common-practice claims (no direct source)
- The exact `schemas/agents/<name>.schema.json` filename layout is extrapolated from the data-contracts pattern; no Anthropic doc prescribes this filename.
- Whether Anthropic's research team used per-specialist evals during dev of the multi-agent research system is not stated in their public blog.
