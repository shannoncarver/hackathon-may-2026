---
title: "Atlassian Rovo MCP Server: Supported Tools"
url: "https://support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/"
fetched_at: 2026-05-03
auth_required: false
license_note: "Atlassian public support docs — condensed for agent reference; cite source for verbatim text"
---

# Atlassian Rovo MCP Server: Supported Tools

Source URL: https://support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/

---

## Jira Tools

### Permission group: `read_jira`

Authentication: OAuth 2.1 and API token. Required scope: `read:jira-work`.

| Tool | Description |
|---|---|
| `getJiraIssue` | Get a Jira issue by ID or key |
| `getJiraIssueRemoteIssueLinks` | List remote issue links (for example, Confluence links) on a Jira issue |
| `getJiraIssueTypeMetaWithFields` | Get create-field metadata for a project and issue type |
| `getJiraProjectIssueTypesMetadata` | List issue types available in a Jira project |
| `getIssueLinkTypes` | List available issue link types |
| `getTransitionsForJiraIssue` | List available workflow transitions for an issue |
| `getVisibleJiraProjects` | List Jira projects the user can access |
| `lookupJiraAccountId` | Find Jira user account IDs by name or email |

### Permission group: `write_jira`

Authentication: OAuth 2.1 and API token. Required scope: `write:jira-work`.

| Tool | Description |
|---|---|
| `addCommentToJiraIssue` | Add a comment to a Jira issue |
| `addWorklogToJiraIssue` | Adds a time-tracking worklog to a Jira issue |
| `createJiraIssue` | "Create a link between two Jira issues" (verbatim from source — description appears to mismatch tool name; flag for human verification) |
| `editJiraIssue` | Update fields on an existing Jira issue |
| `transitionJiraIssue` | Perform a workflow transition on a Jira issue |

### Permission group: `search_jira`

Required scope: `search:jira-work`.

| Tool | Description |
|---|---|
| `searchJiraIssuesUsingJql` | Search Jira issues using a JQL query |

---

## Confluence Tools

### Permission group: `read_confluence`

| Tool | Scope |
|---|---|
| `getConfluencePage` | `read:page:confluence` — Get a Confluence page or live doc by ID |
| `getConfluencePageDescendants` | `read:hierarchical-content:confluence` — List descendant pages under a parent page |
| `getConfluencePageFooterComments` | `read:comment:confluence` — List footer comments on a page |
| `getConfluencePageInlineComments` | `read:comment:confluence` — List inline comments on a page |
| `getConfluenceCommentChildren` | `read:comment:confluence` — List child comments (replies) of a comment |
| `getConfluenceSpaces` | `read:space:confluence` — List Confluence spaces |
| `getPagesInConfluenceSpace` | `read:page:confluence` — List pages in a space |

### Permission group: `write_confluence`

| Tool | Scope |
|---|---|
| `createConfluencePage` | `write:page:confluence` — Create a new Confluence page or live doc |
| `updateConfluencePage` | `write:page:confluence` — Update an existing Confluence page or live doc |
| `createConfluenceFooterComment` | `write:page:confluence` — Create a footer comment or reply on a page |
| `createConfluenceInlineComment` | `write:page:confluence` — Create an inline comment tied to selected text |

### Permission group: `search_confluence`

| Tool | Scope |
|---|---|
| `searchConfluenceUsingCql` | `search:confluence` — Search Confluence content using CQL |

---

## Jira Service Management Tools

**Authentication: API token ONLY.** Available only if enabled by organization admin.

### Permission group: `read_jsm`

| Tool | Scopes |
|---|---|
| `getJsmOpsAlerts` | `read:ops-alert:jira-service-management`, `read:ops-config:jira-service-management`, `read:jira-user` — Get an operations alert by ID or alias, or search query |
| `getJsmOpsScheduleInfo` | `read:ops-config:jira-service-management`, `read:jira-user` — List on-call schedules or get current/next responders |
| `getJsmOpsTeamInfo` | `read:ops-config:jira-service-management`, `read:jira-user` — List operation teams and team details |

### Permission group: `write_jsm`

| Tool | Scopes |
|---|---|
| `updateJsmOpsAlert` | `read:ops-alert:jira-service-management`, `write:ops-alert:jira-service-management` — Perform alert actions, like acknowledge, unacknowledge, close, or escalate an alert |

---

## Bitbucket Cloud Tools

**Authentication: API token with scopes ONLY.** Requires organization admin enablement and linked Bitbucket workspace.

### Permission group: `read_bitbucket`

| Tool | Scope | Description |
|---|---|---|
| `bitbucketWorkspace` (list, get) | `read:workspace:bitbucket` | Get workspace details |
| `bitbucketRepository` (list, get, defaultReviewers) | `read:repository:bitbucket` | Get repository details and content |
| `bitbucketUser` (pullRequests) | `read:pullrequest:bitbucket` | Get pull requests for the authenticated user |
| `bitbucketDeployment` (list, get) | `read:pipeline:bitbucket` | Get deployment information |
| `bitbucketPullRequest` (list, get, comments, diff) | `read:pullrequest:bitbucket` | Get pull requests |
| `bitbucketRepoContent` (branch.get, commit.get, files.get) | `read:repository:bitbucket` | Get repository content |
| `bitbucketPipeline` (list, get, steps, step.get, step.log) | `read:pipeline:bitbucket` | Get pipeline details |
| `bitbucketEnvironment` (list, get) | `read:pipeline:bitbucket` | Get an environment |

### Permission group: `write_bitbucket`

| Tool | Scope | Description |
|---|---|---|
| `bitbucketPullRequest` (create, merge, approve, comment) | `write:pullrequest:bitbucket` | Create and update pull requests |
| `bitbucketRepoContent` (branch.create, commit.create) | `write:repository:bitbucket` | Create or update repository content |
| `bitbucketPipeline` (run) | `write:pipeline:bitbucket` | Run or manage pipelines |
| `bitbucketEnvironment` (create, delete, update) | `admin:pipeline:bitbucket` | Manage deployment environments |

---

## Atlassian Platform

### Permission group: `read_teamwork_graph` (BETA)

Authentication: OAuth 2.1 and API token.

Required scopes: `read:jira-work`, `read:page:confluence`, `read:comment:confluence`, `read:space:confluence`, `read:account`, `read:3p-data:mcp`, `read:home:mcp`, `read:whiteboard:confluence`, `read:confluence:mcp`, `read:focus:mcp`, `read:loom:mcp`, `read:talent:mcp`.

| Tool | Description |
|---|---|
| `getTeamworkGraphContext` | Retrieves connected context from Teamwork Graph for any Atlassian entity. Returns all relationships and linked objects in one traversal |
| `getTeamworkGraphObject` | Fetches all available data for one or more objects using their ARIs or URLs |

### Permission group: `search_atlassian` (BETA)

Required scope: `search:rovo:mcp`.

| Tool | Description |
|---|---|
| `searchAtlassian` | Search across Jira and Confluence using natural language via Rovo |
| `fetchAtlassian` | Fetch Jira or Confluence content by Atlassian Resource Identifier (ARI) |

---

## Compass Tools

**Authentication: OAuth 2.1 ONLY (no API token).**

### Permission group: `read_compass`

Required scope: `read:component:compass`.

| Tool | Description |
|---|---|
| `getCompassComponent` | Get details for a Compass component by ID |
| `getCompassComponents` | Search or list Compass components |
| `getCompassComponentActivityEvents` | List recent activity events for a component |
| `getCompassComponentLabels` | Get the labels applied to a component |
| `getCompassComponentTypes` | List available Compass component types |
| `getCompassCustomFieldDefinitions` | List custom field definitions |
| `getCompassComponentsOwnedByMyTeams` | List components owned by your teams |

### Permission group: `write_compass`

| Tool | Scope | Description |
|---|---|---|
| `createCompassComponent` | `write:component:compass` | Create a Compass component |
| `createCompassComponentRelationship` | `write:component:compass` | Create a relationship between two components |
| `createCompassCustomFieldDefinition` | `write:component:compass` | Create a Compass custom field definition |

---

## Shared Platform Tools

Not part of a permission group; required for MCP server operation.

| Tool | Scope | Description |
|---|---|---|
| `atlassianUserInfo` | `read:me` | Get current Atlassian user details, such as account ID |
| `getAccessibleAtlassianResources` | `read:account`, `read:me` | List Atlassian cloud sites (cloudId) that the user can access |

---

## Key notes

- Beta tools (`read_teamwork_graph`, `search_atlassian`) are currently free; future pricing would include advance notice.
- All tools inherit access control from their permission group.
- MCP clients perform actions with the user's existing permissions; organization admins control group-level access.
- JSM and Bitbucket tools require API token authentication (no OAuth 2.1) and must be enabled by an organization admin.
- Compass tools require OAuth 2.1 (no API token support).

---

## Doc-namespace observation

The supported-tools page lives at `support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/`, while the previously-ingested getting-started page lives at `support.atlassian.com/rovo/docs/getting-started-with-the-atlassian-remote-mcp-server/`. Atlassian appears to be migrating docs from the `/rovo/...` namespace to `/atlassian-rovo-mcp-server/...`. Both paths currently resolve. This migration is not yet tracked as a wiki fact.
