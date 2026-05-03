---
title: "The Forge — Season 2: Every Minute Matters (Confluence)"
kind: source
raw_path: "raw/sources/forge-season-2-every-minute-matters-2026-05-03.md"
url: "https://confluence.atlassian.linq.com/wiki/spaces/CTO/pages/732856331/The+Forge+Season+2+Every+Minute+Matters"
author: "Eric Wood"
fetched_at: 2026-05-03
tags: ["product:cross-cutting", "hackathon", "forge", "confluence", "season-2"]
entities: ["wiki/entities/forge-season-2-every-minute-matters.md"]
concepts:
  - "wiki/concepts/project-format.md"
created: 2026-05-03
updated: 2026-05-03
---

## Why this source

This is the canonical Confluence page for The Forge Season 2 — the specific event page that details dates, theme, format rules, team size, judging criteria, preparation guidance, and tracking channels for the Q2 2026 hackathon. It is the authoritative source for any agent reasoning about Season 2 particulars: what to build, how teams are judged, where to submit, and when the event runs. It establishes that Season 2's theme is "Every Minute Matters" — not merely "Internal Efficiency" as named on the program-level page — and introduces a five-criterion judging rubric distinct from the four-criterion rubric described on the program page.

This source was classified as auth-required because the URL host (`confluence.atlassian.linq.com`) matches `serves_hosts:` on [`wiki/entities/atlassian-mcp.md`](../entities/atlassian-mcp.md). Atlassian MCP read tools were unavailable at fetch time; content was retrieved via Chrome MCP fallback. Stub form applies regardless of fetch channel.

## What it covers

- Event dates: May 4–8, 2026 (with an internal date-range discrepancy — see Open Questions)
- Timezone: America/Chicago (Central)
- Format: Project Format; four-day group project
- Team size: 3–5 people (note: the program page says 2–5; Season 2 page says 3–5 — see Open Questions)
- AI requirement: AI tooling must be load-bearing, not decorative
- Scope: internal or customer-facing workflows are both in scope
- Theme statement and tagline
- Preparation guidance (problem statement or lightweight PRD encouraged before May 4)
- Judging criteria: five criteria, each scored 1–10, 50 points maximum
- Submission tracking: The Forge app at forge.labs.linq.com
- Event Slack channel: #event-the-forge
- Related Confluence pages linked at the bottom of the Season 2 page

## Key claims

All claims below cite [`raw/sources/forge-season-2-every-minute-matters-2026-05-03.md`](../../raw/sources/forge-season-2-every-minute-matters-2026-05-03.md).

- **Event window.** The page header and lede state "May 4–8, 2026"; the format table row reads "May 4–8, 2026 (Monday through Thursday)." May 8, 2026 is a Friday, so "Monday through Thursday" implies May 4–7. The body also says "4-day group project." The page contains an internal discrepancy; both readings are preserved here verbatim and flagged in Open Questions.
- **Theme.** <escape>"Find a workflow that's too slow, too manual, or too painful — for us or for our customers — and simplify it with AI. Fewer steps, fewer handoffs, faster outcomes."</escape>
- **Tagline.** <escape>"Every minute you save a district staff member is a minute back toward students."</escape>
- **Lede framing.** <escape>"Season 1 was about momentum — 360+ PRs against Platform Health. Season 2 is about leverage."</escape>
- **AI requirement.** AI tooling must be load-bearing, not decorative.
- **Scope.** Internal or customer-facing workflows are both fair game.
- **Team size.** 3–5 people (per the Season 2 page format table).
- **Preparation.** Teams are encouraged to write a short problem statement, one-pager, or lightweight PRD before May 4; preparation is not required but confers an advantage.
- **Judging criteria (five, 1–10 each, 50 pts max):**
  1. Problem Worth Solving — does this problem eat real time today?
  2. Time Compression — how dramatically does the solution simplify the workflow?
  3. AI Application — is AI doing real work, or is it cosmetic?
  4. Working Demo — did they ship it or pitch it?
  5. Creativity & "Wow" Factor — would I pull someone over to see this?
- **Judging philosophy.** <escape>"We're not scoring volume; we're scoring impact."</escape>
- **Tracking.** All submissions and results are tracked in The Forge app: forge.labs.linq.com.
- **Slack channel.** Discussion and updates in #event-the-forge.
- **Prize structure.** Not listed on this page — "unable to verify."
- **Judges roster.** Not listed on this page — "unable to verify."
- **Daily schedule.** Not listed on this page beyond the May 4–8 window — "unable to verify."

## Entities introduced

- [`wiki/entities/forge-season-2-every-minute-matters.md`](../entities/forge-season-2-every-minute-matters.md) — The Forge Season 2 as a discrete entity: dates, theme, judging rubric, tracking, and Slack channel.

## Open questions for LINQ

1. **Date-range discrepancy.** The page states "May 4–8, 2026 (Monday through Thursday)" in the format table, but May 8 is a Friday — "Monday through Thursday" would be May 4–7. The body also says "4-day group project" and the lede says "May 4–8." It is unclear whether the event runs four days (Mon–Thu, May 4–7) or five days ending Friday May 8. Preserved verbatim from source; a human should resolve this against the calendar or event organizer.
2. **Prize structure.** No prizes are listed on the Season 2 page. The program-level page notes prizes are announced per season. Source for prize details: "unable to verify" — needs a follow-up Confluence page or Eric Wood directly.
3. **Judges roster.** No judges are named on the Season 2 page. Source: "unable to verify."
4. **Daily schedule.** No intra-event schedule (kickoff time, check-ins, demo session) is given beyond the May 4–8 window. Source: "unable to verify."
5. **Team size discrepancy.** The program page ([`wiki/sources/forge-linq-hackathon-program.md`](forge-linq-hackathon-program.md)) states team size as 2–5 people. The Season 2 page states 3–5. It is unclear whether Season 2 raised the minimum from 2 to 3, or whether the program page is simply less specific. Needs confirmation.
6. **The Forge app.** forge.labs.linq.com is listed as the submission and tracking platform. No documentation for this app has been ingested. See gaps.
