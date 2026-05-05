# Pillar 6 — MCP connector inventory

Which connectors each agent needs, how credentials/scopes are managed, and how versions are pinned.

## Where it lives
- [`.mcp.json`](../../.mcp.json) — server registry (version-pinned)
- [`MCP_VERSION_CHANGELOG.md`](../../MCP_VERSION_CHANGELOG.md) — bump log
- Per-agent `mcpServers:` field in [`.claude/agents/`](../../.claude/agents/) frontmatter

## Status
Initial pin: Atlassian (Confluence + Jira). GitHub MCP planned for follow-up PR.

## Owners
- AI Engineer (`17-eng-ai`) — primary
- CloudOps engineer (`14-eng-cloudops`) — secondary (credentials, secret management)

## Related
- [Decision 0008 — MCP connectors (Atlassian, GitHub deferred)](../decisions/0008-mcp-connectors.md) — per-user OAuth pattern for external SaaS.
- [Decision 0015 — Centralized Platform MCP Server](../decisions/0015-centralized-platform-mcp.md) — Auth0 M2M + STS broker pattern for internal LINQ products. Coexists with 0008; does not supersede it.
- [Architecture review folder for 0015](../research/0015-centralized-platform-mcp/00-overview.md) — alternatives, risks, POC scope, and open questions backing the ADR.
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
