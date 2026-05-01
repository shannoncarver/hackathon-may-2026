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
- [ADR-0008 — MCP connectors](../architecture/0008-mcp-connectors.md)
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
