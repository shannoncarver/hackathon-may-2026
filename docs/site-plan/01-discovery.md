# 01 — Discovery

This document captures the Phase 1 discovery findings that grounded the showcase-site plan: a repo inventory, a reference-site analysis, and a gap analysis. It is read-only history — once complete, the architecture decisions in [02-architecture.md](02-architecture.md) take over.

## Method

- Repo inventoried via Explore-agent sweep across the worktree at `/Users/scarver/LINQ/development/repositories/hackathon-may-2026/`. Read-only.
- Reference site source fetched from `LINQ-Labs/src-service-poc/docs` via `gh api` (the rendered Pages site is gated behind GitHub auth; the source repo is INTERNAL but accessible via authenticated CLI).
- Sensitive-content scan run across the repo: zero plaintext secrets, zero customer data.

## 1. Repo inventory

### Top-level shape

```
hackathon-may-2026/
├── README.md                    Hackathon overview + quick start
├── CLAUDE.md                    Coordinator project context, six pillars, brand voice
├── MCP_VERSION_CHANGELOG.md     MCP server version pins
├── .claude/                     Agents, skills, rules, commands, hooks, output-styles
├── docs/                        agent / architecture / decisions / developer / pillars / plans / research / stakeholder / site-plan
├── knowledge/                   Three-layer wiki: SCHEMA.md + raw/ + wiki/
├── schemas/agents/              JSON-schema I/O contracts (one per agent)
├── skills/                      Standalone shipped skills
├── evals/                       Inspect-AI harness — judges, per-agent, e2e, run.py
├── tests/                       test_schemas.py
├── output/  traces/  scripts/   Runtime + utility (mostly .gitkeep)
├── .env.example  .mcp.json      Config templates (no secrets)
└── pyproject.toml
```

154 markdown files. One PNG diagram. Zero plaintext secrets.

### Content inventory by category

| Bucket | Path | Count | Form | What this is |
|---|---|---|---|---|
| Sub-agents | `.claude/agents/` | 9 | `<NN>-<role>.md` w/ frontmatter | 10/eng-principal, 11/cloudops, 12/security-iam, 15/qa, 17/ai-eng, 18/product-handler, 30/docs-generator, 40/knowledge-curator, 50/pm-hackathon-coordinator |
| Agent persona docs | `docs/agent/` | 9 | Markdown | Public-readable role descriptions |
| Agent schemas | `schemas/agents/` | 9 | JSON | Input/output contracts |
| Skills (project) | `.claude/skills/` | 4 | SKILL.md | auth0-logs, kb-ingest, routing, verify-user-authorization |
| Skills (standalone) | `skills/` | 1 | SKILL.md + scripts/ | verify-user-authorization (shippable) |
| Slash commands | `.claude/commands/` | 3 | Markdown | `/kb-ingest`, `/kb-lint`, `/auth0-logs` |
| Auto-load rules | `.claude/rules/` | 3 | Markdown | coordination, knowledge-base, aws-skill-credentials |
| Output styles | `.claude/output-styles/` | 1 | Markdown | demo |
| Decision records | `docs/decisions/` | 16 | ADR markdown | 0001–0016 (1 superseded) |
| Pillar briefs | `docs/pillars/` | 6 | Markdown | One per pillar |
| Research | `docs/research/` | 20+ | Markdown | repo-structure, scaffold-preview, 0015-centralized-platform-mcp/ |
| Plans | `docs/plans/` | 1 | Markdown | erp-verify-user-authorization-poc-plan |
| Stakeholder | `docs/stakeholder/` | 1 | Markdown | demo-narrative.md (stub) |
| Developer | `docs/developer/` | 1 | Markdown | onboarding.md |
| Architecture diagrams | `docs/architecture/` | 1 PNG | Image | LINQ SSO Flow 1 |
| Knowledge — raw | `knowledge/raw/sources/` | 14 + README | Dated source captures | Public docs as condensed copy + citations; auth-gated as stubs |
| Knowledge — wiki | `knowledge/wiki/` | 33 | Markdown | entities/, concepts/, sources/, synthesis/, index.md, log.md |
| Schema spec | `knowledge/SCHEMA.md` | 1 | Markdown | 200+ lines KB conventions |
| Evals | `evals/` | ~10 | Markdown + Python | judges, per-agent (5), e2e/, run.py |

### Decision-record summary

| # | Title | Status | Stakeholder takeaway |
|---|---|---|---|
| 0001 | Specialist location | Accepted | Architecture origin |
| 0002 | Coordinator placement | Accepted | Architecture origin |
| 0003 | No plugin packaging | Accepted | Trade-off story |
| 0004 | KB shape (early) | Superseded | Honesty about iteration |
| 0005 | Trust boundary | Accepted | Security narrative |
| 0006 | Claude Code native | Accepted | Build-vs-buy story |
| 0007 | Custom output style | Accepted | Voice/brand story |
| 0008 | MCP connectors | Accepted | Integration map |
| 0009 | PR review flow | Accepted | Process story |
| 0010 | Reference quality posture | Accepted | Quality-bar narrative |
| 0011 | Eval harness shape | Accepted | "Not a chatbot" proof point |
| 0012 | Rename architecture→decisions | Accepted | Minor; skip on site |
| 0013 | Karpathy three-layer wiki | Accepted | Knowledge architecture story |
| 0014 | Auth0 logs skill | Accepted | Skill exemplar |
| 0015 | Centralized platform MCP | Accepted | Forward-looking architecture |
| 0016 | AWS multi-account credentials | Accepted | Production-discipline story |

## 2. Reference-site analysis

Reference: `LINQ-Labs/src-service-poc/docs` — the rendered Pages site (`congenial-broccoli-qjw83o7.pages.github.io`) is auth-gated, but the source is plain static HTML (`.nojekyll` present) plus a `training/assets/styles.css` stylesheet that defines a complete design-token system. The site is structured around three landing tiles ("Architecture Training", "Platform Simulator", "Architecture Atlas") and two markdown documentation lists.

### Visual language

- **Sticky dark-teal header** with brand lockup — SVG flame + "LINQ" wordmark + divider + product name; breadcrumb on the right.
- **Hero**: 44 px display heading, 19 px lede, bottom border, generous vertical padding.
- **Primary cards**: dark-teal background, small uppercase eyebrow label, large title, descriptive paragraph, flame-orange CTA pill on the right; subtle `translateY(-2px)` on hover with teal-tinted shadow.
- **Doc list**: white surface with row separators, two-line items (bold title with mono path code + muted description).
- **Callouts**: teal-tinted info, yellow warn, green self-check — each with a small uppercase coloured label.
- **Code blocks**: near-black background with off-white text; inline code is light-grey.
- **Tables**: white with striped header, 1 px borders, rounded outer.
- **Brand rule observed**: orange flame is reserved for the logo only; teal is the primary accent.

Full token spec lives in [design-tokens.md](design-tokens.md).

### Voice

Matter-of-fact, technical-with-warmth. Sample lines from the source:

> "The State Reporting Compliance Service — architecture specs, product framing, and engineering training materials for the centralized multi-tenant reporting platform."

> "Engineering-centric interactive reference for the full architecture. Click any of ~30 components to learn what it does..."

No marketing puffery. No invented metrics. Confident, specific, navigable. This matches Decision 0010 (reference-quality posture).

## 3. Gap analysis

Content not yet in repo that the showcase site will need. Resolved per the authorship choice — I draft from existing artifacts, you edit:

- One-page executive summary (synthesize from `CLAUDE.md` + pillar briefs).
- Per-pillar TL;DR (3 bullets) and Overview (1 page) layered above existing pillar briefs.
- Per-decision TL;DR (one-liner under each ADR title in the explorer).
- Distilled one-pager for `0015-centralized-platform-mcp/` research.
- Hero copy and persona-pivot taglines.
- Outcome cards (top-level "what came of it" units; populated as hackathon winds down).
- Optional later: demo-video embed, headshots, verified metrics.

Sensitive-content scan: clean. The repo is already public, no secrets, no customer data. The Confluence URL in `CLAUDE.md` is an internal reference (LINQ employees only) but not a leak risk. No further redaction needed.

## Pointers

- Architecture decisions, content schema, tech stack, and milestones: [02-architecture.md](02-architecture.md).
- Design tokens, component vocabulary, accessibility targets: [design-tokens.md](design-tokens.md).
- Approved plan source: `~/.claude/plans/role-mission-you-linear-wigderson.md`.
