---
status: Accepted
date: 2026-05-01
category: architecture
---

# Decision 0008 — MCP connectors: Atlassian (initial), GitHub (follow-up)

**Status:** Accepted (2026-05-01)

## Context

The system needs MCP access to LINQ's existing documentation and code. Initial scope: Confluence (LINQ docs + the hackathon page itself) and GitHub (this repo + LINQ engineering repos).

## Decision

Use a single **Atlassian MCP server** (`https://mcp.atlassian.com/v1/sse`) for Confluence + Jira read access. Per-user OAuth on first invocation — no secrets committed. Pinned in `.mcp.json` and documented in `MCP_VERSION_CHANGELOG.md`. Per-agent scoping via `mcpServers:` in the frontmatter.

GitHub MCP setup deferred to a follow-up PR pending endpoint verification.

## Consequences

- Silent MCP upgrades cannot break specialists mid-demo.
- Credential rotation is a per-user OAuth re-consent, not a code change.
- One auth flow covers both Confluence and Jira — fewer moving parts than separate connectors.
- Adding more MCP servers (GitHub, Slack, Linear, etc.) is additive — open a PR with the new server entry plus a changelog row.

## Sources

- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
- [Atlassian Remote MCP Server](https://www.atlassian.com/platform/remote-mcp-server)
- [legal-agent-orchestrator MCP_VERSION_CHANGELOG pattern](https://github.com/kipeum86/legal-agent-orchestrator/blob/main/MCP_VERSION_CHANGELOG.md)
