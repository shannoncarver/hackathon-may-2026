# Wiki log

Append-only chronological record of operations against the knowledge base. One entry per ingest, lint, or major synthesis. Format: `## [YYYY-MM-DD] <op> | <Title>`. Conventions: [`knowledge/SCHEMA.md`](../SCHEMA.md).

## [2026-05-03] ingest | The Forge — LINQ Hackathon Program (Confluence)

- Source: [wiki/sources/forge-linq-hackathon-program.md](sources/forge-linq-hackathon-program.md)
- Raw: [raw/sources/forge-linq-hackathon-program-2026-05-03.md](../raw/sources/forge-linq-hackathon-program-2026-05-03.md) (stub form — `auth_required: true`)
- New entities: [forge-linq-hackathon-program](entities/forge-linq-hackathon-program.md)
- New concepts: [race-format](concepts/race-format.md), [project-format](concepts/project-format.md)
- Routing: classified via wiki-first scan against [wiki/entities/atlassian-mcp.md](entities/atlassian-mcp.md) — `serves_hosts: confluence.atlassian.linq.com` matched; smoke test of auto-extension routing passed. No skill or static-table edits required.
- Curator: knowledge-curator (via /kb-ingest skill)
- Note: Atlassian MCP read tools unavailable at fetch time; content retrieved via Chrome MCP fallback (user authenticated to Confluence in browser). Output shape unchanged — stub form applies regardless of fetch channel because `auth_required: true`.

## [2026-05-03] ingest | Atlassian Remote MCP Server

- Source: [wiki/sources/atlassian-remote-mcp-server.md](sources/atlassian-remote-mcp-server.md)
- Raw: [raw/sources/atlassian-remote-mcp-server-2026-05-03.md](../raw/sources/atlassian-remote-mcp-server-2026-05-03.md)
- New entities: [atlassian-mcp](entities/atlassian-mcp.md) — with `serves_hosts:` populated; auto-extends /kb-ingest routing for `confluence.atlassian.linq.com` and `*.atlassian.net`
- New concepts: (none)
- Curator: knowledge-curator (via /kb-ingest skill)

## [2026-05-03] ingest | Anthropic sub-agents doc

- Source: [wiki/sources/anthropic-sub-agents.md](sources/anthropic-sub-agents.md)
- Raw: [raw/sources/anthropic-sub-agents-2026-05-03.md](../raw/sources/anthropic-sub-agents-2026-05-03.md)
- New entities: [sub-agent](entities/sub-agent.md)
- New concepts: (none yet)
- Curator: knowledge-curator (worked example for Decision 0013)
