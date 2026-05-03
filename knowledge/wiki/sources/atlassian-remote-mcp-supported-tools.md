---
title: "Atlassian Rovo MCP Server: Supported Tools (support docs)"
kind: source
raw_path: "raw/sources/atlassian-remote-mcp-supported-tools-2026-05-03.md"
url: "https://support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/"
author: "Atlassian"
fetched_at: 2026-05-03
tags: ["product:cross-cutting", "mcp", "atlassian", "rovo"]
entities: ["wiki/entities/atlassian-mcp.md"]
concepts: []
created: 2026-05-03
updated: 2026-05-03
---

## Why this source

This page closes **Open Question #1** from both [`wiki/sources/atlassian-remote-mcp-server.md`](atlassian-remote-mcp-server.md) and [`wiki/sources/atlassian-remote-mcp-getting-started.md`](atlassian-remote-mcp-getting-started.md): "specific MCP tool names exposed post-auth." It is the authoritative Atlassian reference for every permission group, tool name, required OAuth scope, and auth-mode constraint across all supported products.

This source also reveals two new product surfaces not previously documented in the wiki: **Jira Service Management** and **Bitbucket Cloud** — both available via API token only and both requiring organization admin enablement. It additionally documents two beta capabilities under the "Atlassian Platform" grouping: **Teamwork Graph** (`read_teamwork_graph`) and **cross-product search** (`search_atlassian`).

No new entities or concepts are introduced. This source enriches the existing [`atlassian-mcp`](../entities/atlassian-mcp.md) entity.

## What it covers

- All permission groups organized by product: Jira, Confluence, Jira Service Management, Bitbucket Cloud, Atlassian Platform (Teamwork Graph + search_atlassian), Compass, and Shared Platform
- Per-group authentication constraints (OAuth 2.1, API token, or OAuth-only / API-token-only)
- Required OAuth scopes for each permission group
- Admin-enablement requirements for JSM and Bitbucket
- Beta status for `read_teamwork_graph` and `search_atlassian`
- Shared Platform tools required for MCP server operation (`atlassianUserInfo`, `getAccessibleAtlassianResources`)
- Doc-namespace migration signal: `/rovo/docs/...` → `/atlassian-rovo-mcp-server/docs/...`

## Key claims

All claims cite [`raw/sources/atlassian-remote-mcp-supported-tools-2026-05-03.md`](../../raw/sources/atlassian-remote-mcp-supported-tools-2026-05-03.md).

- **`read_jira` (8 tools).** OAuth 2.1 and API token. Scope: `read:jira-work`. Tools: `getJiraIssue`, `getJiraIssueRemoteIssueLinks`, `getJiraIssueTypeMetaWithFields`, `getJiraProjectIssueTypesMetadata`, `getIssueLinkTypes`, `getTransitionsForJiraIssue`, `getVisibleJiraProjects`, `lookupJiraAccountId`.

- **`write_jira` (5 tools).** OAuth 2.1 and API token. Scope: `write:jira-work`. Tools: `addCommentToJiraIssue`, `addWorklogToJiraIssue`, `createJiraIssue`, `editJiraIssue`, `transitionJiraIssue`. Note: the source description for `createJiraIssue` reads "Create a link between two Jira issues" — this appears to mismatch the tool name; preserved verbatim, flagged for human verification in Open Questions.

- **`search_jira` (1 tool).** Scope: `search:jira-work`. Tool: `searchJiraIssuesUsingJql`.

- **`read_confluence` (7 tools).** Tools include `getConfluencePage`, `getConfluencePageDescendants`, `getConfluencePageFooterComments`, `getConfluencePageInlineComments`, `getConfluenceCommentChildren`, `getConfluenceSpaces`, `getPagesInConfluenceSpace`. Scopes vary per tool (`read:page:confluence`, `read:hierarchical-content:confluence`, `read:comment:confluence`, `read:space:confluence`).

- **`write_confluence` (4 tools).** Tools: `createConfluencePage`, `updateConfluencePage`, `createConfluenceFooterComment`, `createConfluenceInlineComment`. All use scope `write:page:confluence`.

- **`search_confluence` (1 tool).** Scope: `search:confluence`. Tool: `searchConfluenceUsingCql`.

- **`read_jsm` (3 tools) — API token only, admin-enabled.** New surface. Tools: `getJsmOpsAlerts`, `getJsmOpsScheduleInfo`, `getJsmOpsTeamInfo`. Covers operations alerts, on-call schedules, and ops teams.

- **`write_jsm` (1 tool) — API token only, admin-enabled.** Tool: `updateJsmOpsAlert`. Supports acknowledge, unacknowledge, close, and escalate actions on alerts.

- **`read_bitbucket` (8 tool families) — API token only, admin-enabled, requires linked workspace.** New surface. Covers workspace, repository, pull requests, deployments, repo content, pipelines, and environments.

- **`write_bitbucket` (4 tool families) — API token only, admin-enabled.** Covers PR create/merge/approve/comment, branch/commit creation, pipeline runs, and environment management.

- **`read_teamwork_graph` (2 tools) — BETA, OAuth 2.1 and API token.** Tools: `getTeamworkGraphContext`, `getTeamworkGraphObject`. Traverses cross-product entity relationships and fetches all data for objects by ARI or URL. Requires an extensive scope set including `read:3p-data:mcp`, `read:home:mcp`, `read:whiteboard:confluence`, `read:confluence:mcp`, `read:focus:mcp`, `read:loom:mcp`, `read:talent:mcp`.

- **`search_atlassian` (2 tools) — BETA, scope `search:rovo:mcp`.** Tools: `searchAtlassian` (natural-language search across Jira and Confluence via Rovo) and `fetchAtlassian` (fetch content by ARI).

- **`read_compass` (7 tools) — OAuth 2.1 only.** Scope: `read:component:compass`. Tools: `getCompassComponent`, `getCompassComponents`, `getCompassComponentActivityEvents`, `getCompassComponentLabels`, `getCompassComponentTypes`, `getCompassCustomFieldDefinitions`, `getCompassComponentsOwnedByMyTeams`.

- **`write_compass` (3 tools) — OAuth 2.1 only.** Scope: `write:component:compass`. Tools: `createCompassComponent`, `createCompassComponentRelationship`, `createCompassCustomFieldDefinition`.

- **Shared Platform (2 tools, always present).** `atlassianUserInfo` (`read:me`) and `getAccessibleAtlassianResources` (`read:account`, `read:me`). Not part of a permission group; required for MCP server operation.

- **Beta tools are currently free.** Future charges would include advance notice per the source.

## Entities introduced

No new entities. This source updates the existing [`wiki/entities/atlassian-mcp.md`](../entities/atlassian-mcp.md) entity:

- JSM and Bitbucket added to the supported-products list
- "Tools exposed" section replaced with a permission-group-organized table
- Notes added that JSM and Bitbucket require API token + admin enablement
- Teamwork Graph and `search_atlassian` documented as beta surfaces

## Open questions for LINQ

1. **`createJiraIssue` description mismatch.** The Atlassian source gives this tool the description "Create a link between two Jira issues," which matches `createJiraIssueLink` — not `createJiraIssue`. Preserved verbatim from the source. Needs human verification against the live Atlassian docs or tool runtime.
2. **Does LINQ use Jira Service Management?** JSM tools are available only if enabled by an org admin and linked. If LINQ's JSM instance is in scope for agent workflows, the `atlassian-mcp` entity's `serves_hosts:` may need a JSM host pattern added.
3. **Does LINQ use Bitbucket Cloud?** Bitbucket Cloud tools require a linked Bitbucket workspace and API token. If LINQ uses Bitbucket Cloud (distinct from GitHub or other VCS), an org admin must enable the integration.

## Related sources

- [`wiki/sources/atlassian-remote-mcp-server.md`](atlassian-remote-mcp-server.md) — landing-page source; OQ#1 (specific tool names) now **closed** by this source.
- [`wiki/sources/atlassian-remote-mcp-getting-started.md`](atlassian-remote-mcp-getting-started.md) — getting-started guide; OQ#1 (specific tool names) now **closed** by this source.
