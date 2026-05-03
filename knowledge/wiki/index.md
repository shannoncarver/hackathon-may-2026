# Wiki index

Master catalog for the LINQ Hackathon knowledge base. Every wiki page is listed here under its bucket with a one-line summary and tag set. The knowledge-curator updates this file on every ingest. Conventions: [`knowledge/SCHEMA.md`](../SCHEMA.md).

## Entities

| Page | Tags | Summary |
|---|---|---|
| [atlassian-mcp](entities/atlassian-mcp.md) | `mcp`, `atlassian`, `confluence`, `jira`, `jira-service-management`, `bitbucket`, `compass`, `rovo`, `product:cross-cutting` | Atlassian Remote MCP Server — OAuth-mediated integration layer connecting AI clients to Jira, Confluence, JSM, Bitbucket Cloud, Compass, and beta cross-product search. 15 permission groups; ~60 tools. |
| [forge-linq-hackathon-program](entities/forge-linq-hackathon-program.md) | `product:cross-cutting`, `hackathon`, `forge`, `confluence` | LINQ's internal quarterly hackathon program — two formats (Race and Project), 2026 season schedule, recognition structure, and business-cycle rationale. |
| [forge-season-2-every-minute-matters](entities/forge-season-2-every-minute-matters.md) | `product:cross-cutting`, `hackathon`, `forge`, `confluence`, `season-2` | The Forge Season 2 (Q2 2026) — "Every Minute Matters" — May 4–8, five-criterion judging rubric, AI-required Project Format event. |
| [sub-agent](entities/sub-agent.md) | `product:cross-cutting`, `anthropic`, `claude-code` | Specialized Claude Code AI assistant with its own context window, system prompt, and tools. |

## Concepts

| Page | Tags | Summary |
|---|---|---|
| [project-format](concepts/project-format.md) | `hackathon`, `forge`, `product:cross-cutting` | Four-day cross-functional hackathon event format — self-formed teams, working prototype submission, judging on impact, creativity, feasibility, and theme alignment. |
| [race-format](concepts/race-format.md) | `hackathon`, `forge`, `product:cross-cutting` | Biweekly hackathon challenge series — four races per quarter, PR-label-based scoring, cumulative season leaderboard, used in lower-capacity quarters. |

## Sources

| Page | Tags | Summary |
|---|---|---|
| [Understand Atlassian Rovo MCP Server](sources/atlassian-remote-mcp-understand.md) | `mcp`, `atlassian`, `rovo`, `admin`, `product:cross-cutting` | Atlassian admin support page — IP allowlisting integration with MCP requests, AI-tool outbound IP gotcha, auth method overview. Thin page; primary value is confirming that regional variants, data residency, and compliance certifications are absent from this source. |
| [Available Atlassian Rovo MCP Server Domains](sources/atlassian-remote-mcp-available-domains.md) | `mcp`, `atlassian`, `rovo`, `admin`, `product:cross-cutting` | Atlassian admin support page — pre-allowlisted AI-client / partner domains (OAuth allowlist), four custom domain pattern types, admin UI navigation path. Distinct from kb-ingest `serves_hosts:` routing. |
| [Atlassian Rovo MCP Server: Supported Tools](sources/atlassian-remote-mcp-supported-tools.md) | `mcp`, `atlassian`, `rovo`, `product:cross-cutting` | Atlassian supported-tools reference — all 15 permission groups, ~60 tools, required scopes, and auth-mode constraints across Jira, Confluence, JSM, Bitbucket Cloud, Teamwork Graph, search_atlassian, and Compass. Closes OQ#1 on specific tool names. |
| [Atlassian Rovo MCP Server — Getting Started](sources/atlassian-remote-mcp-getting-started.md) | `mcp`, `atlassian`, `rovo`, `product:cross-cutting` | Atlassian support getting-started guide — current endpoint, supported clients and IDEs, capabilities by product (Jira, Confluence, Compass), auth methods, admin model. |
| [Atlassian Remote MCP Server](sources/atlassian-remote-mcp-server.md) | `mcp`, `atlassian`, `product:cross-cutting` | Atlassian public landing page for the Rovo MCP server — auth model, rate limits, restrictions, and runtime endpoints. |
| [Anthropic — Create custom subagents](sources/anthropic-sub-agents.md) | `anthropic`, `claude-code`, `product:cross-cutting` | Canonical Anthropic documentation for the Claude Code sub-agent primitive. |
| [The Forge — LINQ Hackathon Program](sources/forge-linq-hackathon-program.md) | `product:cross-cutting`, `hackathon`, `forge`, `confluence` | Confluence program page (auth-required stub) — The Forge purpose, Race Format, Project Format, 2026 season schedule, and recognition structure. |
| [The Forge — Season 2: Every Minute Matters](sources/forge-season-2-every-minute-matters.md) | `product:cross-cutting`, `hackathon`, `forge`, `confluence`, `season-2` | Confluence Season 2 event page (auth-required stub) — dates, theme, team rules, AI requirement, five-criterion judging rubric, tracking app, and Slack channel. |

## Synthesis

_None yet._
