---
title: "The Forge — LINQ Hackathon Program"
kind: entity
tags: ["product:cross-cutting", "hackathon", "forge", "confluence"]
aliases: ["the forge", "LINQ hackathon", "forge hackathon program"]
sources: ["wiki/sources/forge-linq-hackathon-program.md"]
related:
  - "wiki/concepts/race-format.md"
  - "wiki/concepts/project-format.md"
created: 2026-05-03
updated: 2026-05-03
---

## Definition

The Forge is LINQ's internal hackathon program. It gives teams protected time to innovate, experiment, and complete platform housekeeping — bug fixes, tech-debt reduction, code cleanup — that rarely surfaces to the top of a prioritized sprint backlog. It runs quarterly; each quarter is a Season. Two formats alternate across seasons to match capacity and LINQ's school-year business cycle.

Source: [`wiki/sources/forge-linq-hackathon-program.md`](../sources/forge-linq-hackathon-program.md).

## Properties

### Quarterly cadence

Each quarter maps to one Season. The 2026 schedule:

| Quarter | Season | Theme | Format |
|---|---|---|---|
| Q1 | Season 1 | Platform Health | Race Format |
| Q2 | Season 2 | Internal Efficiency | Project Format |
| Q3 | Season 3 | Platform Health | Race Format |
| Q4 | Season 4 | Customer Innovation | Project Format |

The schedule tracks LINQ's business cycle: Q2 efficiency work pays off during the Q3 back-to-school crunch; Q4 prototypes feed Q1 productization ahead of spring sales.

### Two formats

**Race Format** — see [`wiki/concepts/race-format.md`](../concepts/race-format.md) for full mechanics. A biweekly challenge series spanning a full quarter — four races, each running Thursday 8 am to Friday 8 am Central Time — with results feeding a cumulative season leaderboard. Used in Q1 and Q3 when large capacity blocks are not available. Participation requires source code access (GitHub PR labels or Azure DevOps tags).

**Project Format** — see [`wiki/concepts/project-format.md`](../concepts/project-format.md) for full mechanics. A dedicated four-day event where cross-functional teams of two to five people self-form, pick a problem, build a working prototype, and submit a demo for judging. Open to all disciplines: engineering, product, design, support, and sales. Used in Q2 and Q4.

### 2026 season highlights

**Season 2 (Q2 2026) — Internal Efficiency.** Current season. Tied to LINQ's AI Enablement Program as its flagship event for driving AI adoption across the organization. Submissions focus on internal tooling, workflow automation, operational improvements, and AI-assisted processes.

**Season 4 (Q4 2026) — Customer Innovation.** Winning Project Format prototypes from Season 4 receive dedicated Q1 sprint time to productize. Focus: feature prototypes addressing customer pain points, AI-assisted product features, and new product concepts.

### Recognition structure

| Scope | Recognition |
|---|---|
| Race winner (per race) | Slack recognition |
| Season champion (Race Format) | Monthly all-hands recognition + small prize |
| Project Format winners | Present at company all-hands; winning projects prioritized for productization |

Prize details are announced per season. Current prize specifics: "unable to verify" until the Season 2 sub-page is ingested.

Source: [`wiki/sources/forge-linq-hackathon-program.md`](../sources/forge-linq-hackathon-program.md).

## How LINQ uses this

The LINQ Hackathon May 2026 repository — this codebase — is itself a **Season 2, Project Format** submission under the Internal Efficiency theme. The project builds an internal AI workflow system that acts as a force multiplier for LINQ employees across Engineering, Product, Support, Documentation, and IT/Knowledge Management. This directly fulfills the Season 2 objectives: internal tooling, AI-assisted processes, and operational improvement.

The connection to Season 2's strategic framing is explicit: Season 2 is the flagship event for LINQ's AI Enablement Program, and this repository is the AI enablement entry.

For architectural context, see `docs/decisions/0013-karpathy-wiki-pattern.md` (the knowledge-base standing decision that shapes Pillar 1 of this project) and `docs/pillars/4-agent-definitions.md` (the agent-definitions pillar that shapes Pillar 4).

### Race Format scoring reference (for Season 1 and Season 3)

Three qualifying PR label categories:
- `hackathon:bugs` — Bug Blitz (bug fixes)
- `hackathon:red-diff` — Code Diet (net lines removed: deletions > additions)
- `hackathon:tech-debt` — Tech Debt Takedown (tech-debt reduction, TODO/FIXME resolution, dependency updates)

Scoring: 1 merged PR with any qualifying label = 1 point. Multiple labels on one PR still = 1 point. `merged_at` must fall within the race window (Thursday 8 am to Friday 8 am Central Time).

Tracking is currently manual; a tracking app is in development (no link or timeline on the source page).

## Sources

- [`wiki/sources/forge-linq-hackathon-program.md`](../sources/forge-linq-hackathon-program.md) — summary of the Confluence program page authored by Eric Wood, ingested 2026-05-03
