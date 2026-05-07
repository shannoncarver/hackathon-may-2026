---
status: Accepted
date: 2026-05-07
category: skills-management
---

# Decision 0025 — Merge auth0-logs, auth0-stats, auth0-sec into auth0-management

**Status:** Accepted (2026-05-07). Supersedes parts of [Decision 0014](0014-auth0-logs-skill.md), [Decision 0019](0019-auth0-stats-skill.md), and [Decision 0020](0020-auth0-sec-skill.md) — specifically the skill-folder shape, slash-command shape, and per-skill ADR ownership. The AuthProvider seam from Decision 0014 is preserved unchanged.

## Context

The demo narrative ([`docs/stakeholder/demo-narrative.md`](../stakeholder/demo-narrative.md)) refers to "the Auth0 Management skill" (singular). The repository today carries three sibling skills — `auth0-logs`, `auth0-stats`, `auth0-sec` — that duplicate scaffolding (frontmatter, trust-boundary blocks, error-envelope handling, slash-command shells) and split the skill router across three near-overlapping descriptions. Three drivers for unification:

- **Naming alignment.** The stakeholder-facing artifact says "Auth0 Management"; the implementation says three things. Closing that gap before the demo is cheap and removes a recurring framing question.
- **Code deduplication.** All three scripts share `_auth0_common.py` via a `sys.path` injection trick. A single CLI with subcommands lets `_auth0_common.py` become a sibling import — simpler, no path manipulation, one file to swap when [Decision 0015](0015-centralized-platform-mcp.md) M4 lands.
- **Routing simplification.** Three trigger-rich descriptions on three SKILL.md files compete for the same natural-language requests. One unified description with cumulative trigger phrases gives the router a single, broader match target.

## Decision

Single skill at `.claude/skills/auth0-management/`. Single slash command `/auth0-management`. Single Python CLI at `scripts/auth0_management.py` with subcommands `logs`, `stats`, `sec`. References from the three originals consolidate into `references/`. The shared `_auth0_common.py` becomes a sibling of the merged CLI (no more `sys.path` injection).

Specific binding choices:

- **Subcommands, not separate scripts.** `auth0_management.py logs|stats|sec [flags]` matches the three-lens framing while sharing one argparse setup, one `_auth0_common.py` import, and one error-envelope contract.
- **Same M2M app, same cumulative scope set.** No change to credentials. Cumulative scopes remain `read:logs`, `read:stats`, `read:anomaly_blocks`, `read:attack_protection`, `read:users` — all read-only, sandbox-only.
- **Sandbox only.** Same scope restriction as the three originals. Production access remains gated on Decision 0015 M4.
- **Unified description, cumulative triggers.** The merged SKILL.md description carries every trigger phrase from all three originals, plus new combined phrases ("auth0 management", "is this user set up correctly"). Routing surface shrinks from 3 to 1.

## Alternatives Considered

### Alternative A — Keep three skills, just rename folder for narrative alignment

Rename `auth0-logs` → `auth0-management` in the demo narrative only; leave the three-skill structure intact.

**Rejected.** Doesn't dedupe code or routing. Doesn't simplify the `_auth0_common.py` import path. The demo narrative would still refer to one thing while the menu shows three. The naming gap is the symptom, not the underlying problem.

### Alternative B — Three slash commands feeding one skill

Keep `/auth0-logs`, `/auth0-stats`, `/auth0-sec` as separate slash-command files but point them all at one shared SKILL.md and one unified script.

**Rejected.** The demo narrative is "one skill" and the menu would still surface three commands. Users would still ask "which one do I use?" when the answer is "any of them route to the same place." One slash command with one classification step is simpler.

### Alternative C — Top-level `skills/auth0-management/` bundle (ha-debug pattern)

Adopt the bundled-skill layout from [Decision 0023](0023-ha-debug-skill-bundle-layout.md) — top-level `skills/auth0-management/` with a Typer-based CLI, packaged dependencies, and a richer scaffold.

**Rejected.** The scripts are small Python wrappers around five Auth0 endpoints. The bundle layout's overhead (separate `pyproject.toml`, packaged install path, Typer dep) doesn't justify itself for a thin HTTP-glue CLI. The standard `.claude/skills/<name>/` layout fits.

### Alternative D — Adopt Decision 0024 (tool-search-support) description format

Restructure the SKILL.md description to follow the format introduced in [Decision 0024](0024-tool-search-support.md).

**Out of scope.** Would touch every skill in the repo and is a separate ADR. Defer to a follow-up that addresses skill-description format consistency across the board.

## Consequences

- **Positive:** One skill matches one demo narrative. Routing surface shrinks from 3 to 1. Cumulative trigger phrases give better natural-language match coverage than three competing descriptions.
- **Positive:** `_auth0_common.py` is now a sibling import, not a `sys.path`-injected one. Future BrokerAuthProvider swap (Decision 0015 M4) lands in one file.
- **Positive:** Cumulative scope set on the M2M app is unchanged: `read:logs`, `read:stats`, `read:anomaly_blocks`, `read:attack_protection`, `read:users`. No widening of blast radius.
- **Negative:** Breaking change — `/auth0-logs`, `/auth0-stats`, `/auth0-sec` slash commands are removed in the cutover commit. Anyone with a saved invocation needs to migrate to `/auth0-management <prompt>`. The natural-language description is identical, so prompt translation is mechanical.
- **Negative:** SKILL.md description grows long (~1,200 chars) to cover all trigger phrases from the three originals plus new combined phrases. The router accepts long descriptions, but the file becomes denser to read.
- **Operational:** Closes PR #21 (which broadened only the `auth0-logs` description) — its intent folds into the unified description. The cutover commit removes the three superseded skill folders, three superseded slash-command files, and adds the supersession marker to Decisions 0014 (partial), 0019, and 0020.

## Sources

- [Decision 0014](0014-auth0-logs-skill.md) — auth0-logs hybrid approach. Superseded for skill shape; AuthProvider seam preserved.
- [Decision 0019](0019-auth0-stats-skill.md) — auth0-stats. Superseded.
- [Decision 0020](0020-auth0-sec-skill.md) — auth0-sec. Superseded.
- [Decision 0015](0015-centralized-platform-mcp.md) — centralized platform MCP. Future migration target, unchanged by this merge.
- [Decision 0023](0023-ha-debug-skill-bundle-layout.md) — ha-debug bundle layout. Alternative considered and rejected.
- [`docs/stakeholder/demo-narrative.md`](../stakeholder/demo-narrative.md) — references the "Auth0 Management skill" framing this decision aligns to.
