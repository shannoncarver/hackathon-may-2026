# MCP Server Version Changelog

Append-only log of MCP server additions and version bumps. Each entry records the server, the reason, and the auth model so future agents and teammates can audit how the connector inventory grew.

## 2026-05-01 — Atlassian (initial)
- Added remote Atlassian MCP server (Confluence + Jira read access).
- Reason: Hackathon Coordinator sub-agent must read the Forge Season 2 page (auth-gated).
- Endpoint: `https://mcp.atlassian.com/v1/sse`
- Auth: per-user OAuth on first invocation. No secrets committed.
- Note: confirm endpoint/transport against the current Atlassian MCP docs at first use — the URL has shifted between SSE and HTTP variants in the past.
