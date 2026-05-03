---
title: "Race Format"
kind: concept
tags: ["hackathon", "forge", "product:cross-cutting"]
sources: ["wiki/sources/forge-linq-hackathon-program.md"]
related: ["wiki/entities/forge-linq-hackathon-program.md", "wiki/concepts/project-format.md"]
created: 2026-05-03
updated: 2026-05-03
---

## Definition

The Race Format is one of the two alternating structures used by The Forge, LINQ's quarterly hackathon program. It is a biweekly challenge series that spans an entire quarter — four individual races — with results from each race accumulating on a season leaderboard. A season champion is crowned at quarter end.

The Race Format is designed for quarters where engineering capacity is already heavily committed and multi-day event blocks are not feasible. It keeps momentum and culture without requiring participants to set aside four consecutive days.

Source: [`wiki/sources/forge-linq-hackathon-program.md`](../sources/forge-linq-hackathon-program.md).

## Cadence

- **Quarter span.** One Race Format season runs the full quarter: four biweekly races.
- **Race window.** Each race runs from Thursday 8 am to Friday 8 am Central Time (a 24-hour window).
- **Frequency.** Races run every other Thursday.

## Participation requirements

Participants must have source code access to the relevant repositories. Submissions are made via:
- **GitHub** — PR label matching a qualifying category
- **Azure DevOps** — PR tag matching a qualifying category

No separate registration or submission form; the PR label or tag is the submission.

## Scoring

- 1 merged PR with a qualifying label or tag = **1 point**.
- A PR with multiple qualifying labels still counts as **1 point** (not additive per label).
- The `merged_at` timestamp must fall within the race window (Thursday 8 am–Friday 8 am Central Time).
- Tracking is currently manual: participants link qualifying PRs on the season's Confluence page; an admin tallies. A tracking app is in development (no link or timeline confirmed as of 2026-05-03).

## Platform Health categories (Season 1 and Season 3)

The three qualifying PR label categories for Platform Health seasons:

| Label / Tag | Category Name | What qualifies |
|---|---|---|
| `hackathon:bugs` | Bug Blitz | Bug fixes merged during the race window |
| `hackathon:red-diff` | Code Diet | PRs where net lines removed: deletions > additions |
| `hackathon:tech-debt` | Tech Debt Takedown | Tech-debt reduction, TODO/FIXME resolution, dependency updates |

Category definitions for other season themes (Internal Efficiency, Customer Innovation) are not specified on the program page; they would appear on the season-specific sub-page.

## Recognition

- **Per-race winner.** Slack recognition.
- **Season champion.** Monthly all-hands recognition plus a small prize (prize details announced per season).

## When The Forge uses this format

The Race Format is used in Q1 (Season 1 — Platform Health) and Q3 (Season 3 — Platform Health) of the 2026 schedule. It is deliberately placed in quarters with lower event capacity (Q1 after the holiday period; Q3 during back-to-school crunch) to maintain hackathon engagement without pulling engineering focus.

Source: [`wiki/sources/forge-linq-hackathon-program.md`](../sources/forge-linq-hackathon-program.md).
