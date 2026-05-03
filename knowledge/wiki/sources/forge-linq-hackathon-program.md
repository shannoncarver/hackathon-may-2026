---
title: "The Forge — LINQ Hackathon Program (Confluence)"
kind: source
raw_path: "raw/sources/forge-linq-hackathon-program-2026-05-03.md"
url: "https://confluence.atlassian.linq.com/wiki/spaces/CTO/pages/419659784/The+Forge+LINQ+Hackathon+Program"
author: "Eric Wood"
fetched_at: 2026-05-03
tags: ["product:cross-cutting", "hackathon", "forge", "confluence"]
entities: ["wiki/entities/forge-linq-hackathon-program.md"]
concepts:
  - "wiki/concepts/race-format.md"
  - "wiki/concepts/project-format.md"
created: 2026-05-03
updated: 2026-05-03
---

## Why this source

The Forge program page is the canonical definition of LINQ's internal hackathon program — its purpose, its two formats, its 2026 season schedule, and the recognition structure for participants. It is authoritative for any agent reasoning about hackathon structure, submission requirements, scoring rules, or season themes. It is also the primary source confirming that the LINQ Hackathon May 2026 repository (this project) is itself a Season 2 Project Format submission.

This source was ingested as part of the smoke-test of wiki-first routing: the source URL (`confluence.atlassian.linq.com`) matched the `serves_hosts:` list on [`wiki/entities/atlassian-mcp.md`](../entities/atlassian-mcp.md), which correctly classified this as an auth-required ingest requiring stub-form treatment — no edits to the kb-ingest skill or static classification table were needed.

Note: Atlassian MCP read tools were unavailable at fetch time. Content was retrieved via Chrome MCP fallback (user authenticated to Confluence in browser). The output shape is identical — stub form applies because `auth_required: true` regardless of fetch channel.

## What it covers

- The Forge's purpose: protected time for innovation, experimentation, and platform housekeeping that doesn't surface in sprint planning
- Two formats: Race Format (biweekly challenge series) and Project Format (four-day cross-functional event)
- The 2026 season schedule: four seasons mapped to quarters, alternating formats and themes
- Race Format mechanics: four biweekly races per quarter, Thursday 8 am–Friday 8 am Central, PR-label-based participation, 1 point per merged qualifying PR
- Project Format mechanics: self-formed cross-functional teams (2–5 people), working prototype plus demo submission, judging on four criteria
- Season 2 (Q2 2026, Internal Efficiency): current season, tied to LINQ's AI Enablement Program
- Season 4 (Q4 2026, Customer Innovation): winning prototypes get dedicated Q1 sprint time to productize
- Recognition structure: Slack shoutouts, all-hands acknowledgment, prizes (per-season details TBD)
- Platform for participation: GitHub PR labels or Azure DevOps tags for Race Format; source code access required

## Key claims

All claims below cite [`raw/sources/forge-linq-hackathon-program-2026-05-03.md`](../../raw/sources/forge-linq-hackathon-program-2026-05-03.md).

- **Program purpose.** The Forge gives teams protected time to innovate, experiment, and address platform housekeeping that doesn't reach the top of a prioritized backlog.
- **Quarterly cadence, two formats.** Each quarter is a Season; formats alternate between Race and Project to fit capacity and the business cycle.
- **2026 schedule.** Q1 Platform Health (Race), Q2 Internal Efficiency (Project), Q3 Platform Health (Race), Q4 Customer Innovation (Project).
- **Race Format mechanics.** Four biweekly races per quarter. Races run Thursday 8 am to Friday 8 am Central Time. Platform Health categories: Bug Blitz (`hackathon:bugs`), Code Diet (`hackathon:red-diff`), Tech Debt Takedown (`hackathon:tech-debt`). Scoring: 1 merged PR with a qualifying label = 1 point; multiple labels on one PR still = 1 point; `merged_at` must fall within the race window. Participation requires source code access (GitHub or Azure DevOps).
- **Project Format mechanics.** Four-day event. Self-formed cross-functional teams of 2–5 people. Submissions: working prototype plus demo (video or live). Judging criteria: impact, creativity, feasibility, theme alignment. Open to all disciplines — engineering, product, design, support, and sales.
- **Season 2 theme and strategic link.** Internal Efficiency; tied to LINQ's AI Enablement Program as the flagship adoption event.
- **Season 4 productization path.** Customer Innovation Project Format winners receive dedicated Q1 sprint time to productize winning prototypes.
- **Business-cycle alignment.** Q2 efficiency work pays off during Q3 back-to-school crunch; Q4 prototypes feed Q1 features for spring sales cycles.
- **Tracking app.** Tracking is currently manual (participants link qualifying PRs, admin tallies on the season's Confluence page). A tracking app is in development; no link or timeline given on this page.

## Entities introduced

- [`wiki/entities/forge-linq-hackathon-program.md`](../entities/forge-linq-hackathon-program.md) — The Forge as a first-class entity: cadence, formats, 2026 schedule, and recognition structure.

## Open questions for LINQ

1. **Season 2 sub-page.** Specific Season 2 details — event dates, judges, demo schedule, and prize structure — are expected on a Season 2 sub-page, not this program-level page. Ingest that sub-page when located. Candidate URL: Forge Season 2 linked from https://confluence.atlassian.linq.com/wiki/spaces/CTO/pages/732856331/The+Forge+Season+2+Every+Minute+Matters (the Forge Season 2 event page; already referenced in CLAUDE.md as the hackathon detail page).
2. **Tracking app.** A tracking app for Race Format scoring is noted as "in development" on this page but no link, owner, or timeline is given. Identify the app and ingest its documentation when available.
3. **Prize structure per season.** Prize details are announced per season and are not specified on this program page. The Season 2 sub-page should include them.
4. **Azure DevOps PR tags.** The page mentions Azure DevOps as an alternative platform alongside GitHub. Confirm which LINQ repositories use Azure DevOps and whether the `hackathon:*` tag format translates directly.
