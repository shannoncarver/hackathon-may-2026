# Wiki log

Append-only chronological record of operations against the knowledge base. One entry per ingest, lint, or major synthesis. Format: `## [YYYY-MM-DD] <op> | <Title>`. Conventions: [`knowledge/SCHEMA.md`](../SCHEMA.md).

## [2026-05-04] milestone | Decision 0015 M1 Phase A — `linq-platform-mcp` repo scaffolded and pushed

Per cross-cutting decision **CC-2** in [`docs/research/0015-centralized-platform-mcp/implementation/00-overview.md`](../../docs/research/0015-centralized-platform-mcp/implementation/00-overview.md), the M1 Platform Services build lives in a separate repo, not in this hackathon repo. Phase A (repo scaffold per [`implementation/11-repo-layout.md`](../../docs/research/0015-centralized-platform-mcp/implementation/11-repo-layout.md) §2.1) is complete.

- New repo: <https://github.com/shannoncarver/linq-platform-mcp> (public, default branch `main`).
- Local path: `/Users/scarver/LINQ/development/repositories/linq-platform-mcp/`.
- Initial commit: `822eaae` — "Phase A scaffold per Decision 0015 implementation/11-repo-layout.md" (50 files).
- `infra/master.yaml` carries `Default:` values for `PlatformAccountId` (`631916786699`), `ProductAccountId` (`529394632305`), and `LoggingAccountId` (`631916786699` — single-account logging per session-locked decision D5; full ADR-level decision deferred to Phase B).
- `CODEOWNERS` uses `@shannoncarver` only — personal account cannot host `@linq/*` teams; revisit when collaborators join.
- Stack files under `infra/stacks/` and workflow files under `.github/workflows/` are header-only stubs. Body authoring is **Phase B** (bootstrap CFN + GHA OIDC); M1.1–M1.4 deliverables are **Phase C**. Both are out of scope for this session.
- Coordinator: `10-eng-principal` (dispatch); writer: `11-eng-cloudops` (file authoring); coordinator handled `git init` + `gh repo create --public --push` since the dispatched specialist did not have shell access.

## [2026-05-04] lint | Post-Phase-D-tail full wiki audit — 0 blocking findings; 1 advisory resolved

All 8 SCHEMA §7 checks passed across 21 wiki pages (10 entities, 2 concepts, 14 sources, 1 synthesis) and 14 raw files.

(1) Orphans — none; all 21 pages present in `index.md`.
(2) Orphan raw files — none; all 14 raw files referenced by `raw_path:` on a matching wiki source page.
(3) Broken links — none; all frontmatter paths and synthesis body links resolve.
(4) Stale claims — none; all pages updated 2026-05-03 or 2026-05-04.
(5) Contradictions — 1 advisory raised: six Phase A entity bodies referenced "Decision 0014" in section headers after the ADR slot was renumbered to 0015. **Resolved during lint follow-up:** entity bodies for `mcp-authorization`, `mcp-tool-catalog`, `auth0-m2m`, `oauth-token-exchange`, `sts-assume-role-external-id`, and `lambda-resource-policy` updated to "Decision 0015". `SCHEMA.md` §4's "Decision 0014 lands" references for the still-pending product-slug ADR were preserved.
(6) Bidirectional drift — none; all 17 source↔entity/concept pairs confirmed bidirectional. SCHEMA §7 bidirectional rule applies only to source `entities:` ↔ entity `sources:`; synthesis backlinks on entity/source pages are not required and not raised as false positives.
(7) Unknown product tags — none; only `product:cross-cutting` used.
(8) Frontmatter completeness — none; all 21 pages have required fields.

Curator: knowledge-curator (lint pass); coordinator (advisory resolution).

## [2026-05-04] synthesis | Centralized MCP broker pattern for LINQ

- Page: [wiki/synthesis/centralized-mcp-broker.md](synthesis/centralized-mcp-broker.md)
- Composes six entities (mcp-authorization, mcp-tool-catalog, auth0-m2m, oauth-token-exchange, sts-assume-role-external-id, lambda-resource-policy) plus the Atlassian MCP and sub-agent entities into the LINQ-specific "Auth0-fronted MCP broker with cross-account credential exchange" pattern adopted in [Decision 0015](../../docs/decisions/0015-centralized-platform-mcp.md).
- Distinguishes the centralized broker pattern (internal LINQ products) from the per-user OAuth pattern of [Decision 0008](../../docs/decisions/0008-mcp-connectors.md) (external SaaS via Atlassian MCP). Coexist; neither supersedes.
- Backed by the architecture review at [`docs/research/0015-centralized-platform-mcp/`](../../docs/research/0015-centralized-platform-mcp/00-overview.md): five role-pass memos plus six synthesis artifacts.
- Curator: coordinator (synthesis is coordinator-owned per [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md)).

## [2026-05-04] ingest | Phase A batch — Decision 0015 Platform MCP Server knowledge base

Six sources ingested to close confirmed KB gaps for Decision 0015 (Centralized Platform MCP Server — multi-account AWS, Auth0 identity, read-only v1, 4 products / 40–200 handlers).

> **Slot correction:** the curator dispatched Phase A under "Decision 0014"; mid-review the coordinator discovered slot 0014 is reserved by [Decision 0013](../../docs/decisions/0013-karpathy-wiki-pattern.md) for the canonical LINQ product-slug list. The work was renumbered to 0015. All six ingested wiki entries are correct as-is — they reference the standards (MCP, OAuth, RFC 8693, AWS STS, Lambda) generically, not the LINQ ADR number.

**Sources:**

1. Source: [wiki/sources/mcp-tool-resource-prompt-primitives.md](sources/mcp-tool-resource-prompt-primitives.md)
   - Raw: [raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md](../raw/sources/mcp-tool-resource-prompt-primitives-2026-05-04.md) (condensed-copy form — `auth_required: false`)
   - URLs consulted: `https://modelcontextprotocol.io/docs/concepts/tools`, `https://modelcontextprotocol.io/docs/concepts/resources`, `https://modelcontextprotocol.io/docs/concepts/prompts`, `https://modelcontextprotocol.io/specification/2025-06-18`
   - New entities: [mcp-tool-catalog](entities/mcp-tool-catalog.md)

2. Source: [wiki/sources/mcp-authorization-spec.md](sources/mcp-authorization-spec.md)
   - Raw: [raw/sources/mcp-authorization-spec-2026-05-04.md](../raw/sources/mcp-authorization-spec-2026-05-04.md) (condensed-copy form — `auth_required: false`)
   - URL: `https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization`
   - New entities: [mcp-authorization](entities/mcp-authorization.md)

3. Source: [wiki/sources/auth0-client-credentials-flow.md](sources/auth0-client-credentials-flow.md)
   - Raw: [raw/sources/auth0-client-credentials-flow-2026-05-04.md](../raw/sources/auth0-client-credentials-flow-2026-05-04.md) (condensed-copy form — `auth_required: false`)
   - URL: `https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow`
   - Fetch note: primary URL with trailing `s` on `flows` returned HTTP 404; canonical URL without `s` used.
   - New entities: [auth0-m2m](entities/auth0-m2m.md)

4. Source: [wiki/sources/oauth-token-exchange-rfc8693.md](sources/oauth-token-exchange-rfc8693.md)
   - Raw: [raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md](../raw/sources/oauth-token-exchange-rfc8693-2026-05-04.md) (condensed-copy form — `auth_required: false`)
   - URL: `https://datatracker.ietf.org/doc/html/rfc8693`
   - New entities: [oauth-token-exchange](entities/oauth-token-exchange.md)

5. Source: [wiki/sources/aws-sts-assume-role-external-id.md](sources/aws-sts-assume-role-external-id.md)
   - Raw: [raw/sources/aws-sts-assume-role-external-id-2026-05-04.md](../raw/sources/aws-sts-assume-role-external-id-2026-05-04.md) (condensed-copy form — `auth_required: false`)
   - URL: `https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user_externalid.html`
   - New entities: [sts-assume-role-external-id](entities/sts-assume-role-external-id.md)

6. Source: [wiki/sources/aws-lambda-resource-based-policies.md](sources/aws-lambda-resource-based-policies.md)
   - Raw: [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md](../raw/sources/aws-lambda-resource-based-policies-2026-05-04.md) (condensed-copy form — `auth_required: false`)
   - URLs consulted: `https://docs.aws.amazon.com/lambda/latest/dg/access-control-resource-based.html`, `https://docs.aws.amazon.com/lambda/latest/dg/permissions-function-cross-account.html`
   - New entities: [lambda-resource-policy](entities/lambda-resource-policy.md)

**New concepts:** (none — all ingests produced entities)

**Fetch failures:** Auth0 primary URL (`authentication-and-authorization-flows/client-credentials-flow`, with trailing `s`) returned HTTP 404 on multiple attempts. Recovered via canonical URL variant and the `call-your-api` sub-page. Content is complete. The broken URL is noted in the raw file and source wiki page.

**Curator:** knowledge-curator

## [2026-05-03] lint | 0 findings

All 8 checks passed post-ingest of `atlassian-remote-mcp-understand`. Checks run: (1) orphans — none (14 wiki pages, all in index.md: 4 entities, 2 concepts, 8 sources, 0 synthesis); (2) orphan raw files — none (8 raw files, all referenced by a `raw_path:` field on the matching wiki source page); (3) broken links — none (new source page links, `atlassian-mcp.md` `## IP allowlisting integration` section link to `../sources/atlassian-remote-mcp-understand.md` resolves, `atlassian-remote-mcp-available-domains.md` OQ#2 relative link to `atlassian-remote-mcp-understand.md` resolves, all raw-file links in entity body resolve); (4) stale claims — none (all pages `updated: 2026-05-03`; 90-day threshold is 2026-02-02); (5) contradictions — none (team-size and judging-criterion discrepancies remain acknowledged open questions, not unresolved contradictions); (6) bidirectional drift — none (`atlassian-remote-mcp-understand.md` `entities: ["wiki/entities/atlassian-mcp.md"]` confirmed; `atlassian-mcp.md` `sources:` array entry `"wiki/sources/atlassian-remote-mcp-understand.md"` confirmed; all 14 source↔entity/concept pairs verified); (7) unknown product tags — none (only `product:cross-cutting` used as product tag across all pages; no other `product:*` tags present); (8) frontmatter completeness — none (new source page has all required source-kind fields per SCHEMA §2; no `related:` field on source-kind frontmatter). 14 wiki pages reviewed; 8 raw files reviewed. Curator: knowledge-curator.

## [2026-05-03] ingest | Understand Atlassian Rovo MCP Server (admin support docs)

- Source: [wiki/sources/atlassian-remote-mcp-understand.md](sources/atlassian-remote-mcp-understand.md)
- Raw: [raw/sources/atlassian-remote-mcp-understand-2026-05-03.md](../raw/sources/atlassian-remote-mcp-understand-2026-05-03.md) (condensed-copy form — `auth_required: false`)
- New entities: (none)
- New concepts: (none)
- Modified entities: [atlassian-mcp](entities/atlassian-mcp.md) — added "IP allowlisting integration" section covering: IP allowlists are configured in Atlassian Administration separately from MCP settings; verbatim blocked-IP error message; AI-tool outbound IP gotcha. Appended `atlassian-remote-mcp-understand` to `sources:` array. `serves_hosts:`, `mcp_server_name:`, `auth_required:`, `auth_tools:`, and all existing product surfaces left unchanged.
- Modified sources: [atlassian-remote-mcp-available-domains](sources/atlassian-remote-mcp-available-domains.md) — OQ#2 (regional MCP variants) updated: the "Understand" page was the candidate source; it does NOT address regional variants; gap remains open; suggested source updated to Atlassian Trust Center or vendor inquiry.
- **Regional-variant gap NOT closed.** The primary expectation for this ingest was that the admin "Understand" page would address regional MCP endpoints, data residency, and compliance. It does not. The documentation-gap signal itself is the most valuable artifact of this ingest — a confirmed negative that redirects the search to the Atlassian Trust Center.
- Incremental additions: IP allowlisting integration semantics and AI-tool outbound IP gotcha (the page's only substantive new content).
- Curator: knowledge-curator

## [2026-05-03] lint | 0 findings

All 8 checks passed post-ingest of `atlassian-remote-mcp-available-domains`. Checks run: (1) orphans — none (13 wiki pages, all in index.md); (2) orphan raw files — none (7 raw files, all referenced by a `raw_path:` field); (3) broken links — none (new source page links, entity `## Org admin domain allowlist` section links, and updated getting-started OQ#2 link all resolve); (4) stale claims — none (all pages `updated: 2026-05-03`); (5) contradictions — none (project-format/season-2 team-size discrepancy remains an acknowledged open question, not an unresolved contradiction); (6) bidirectional drift — none (`atlassian-remote-mcp-available-domains.md` `entities:` → `atlassian-mcp.md` confirmed; `atlassian-mcp.md` `sources:` → `atlassian-remote-mcp-available-domains.md` confirmed; all 13 source↔entity/concept pairs verified); (7) unknown product tags — none (only `product:cross-cutting` used as product tag across all pages; `atlassian-mcp.md` tags array unchanged from prior lint); (8) frontmatter completeness — none (new source page has all required source-kind fields; no `related:` field on any source-kind frontmatter; entity page has all required fields including MCP-server optional fields). 13 wiki pages reviewed; 7 raw files reviewed. Curator: knowledge-curator.

## [2026-05-03] ingest | Available Atlassian Rovo MCP Server Domains (admin support docs)

- Source: [wiki/sources/atlassian-remote-mcp-available-domains.md](sources/atlassian-remote-mcp-available-domains.md)
- Raw: [raw/sources/atlassian-remote-mcp-available-domains-2026-05-03.md](../raw/sources/atlassian-remote-mcp-available-domains-2026-05-03.md) (condensed-copy form — `auth_required: false`)
- New entities: (none)
- New concepts: (none)
- Modified entities: [atlassian-mcp](entities/atlassian-mcp.md) — added "Org admin domain allowlist" section documenting pre-allowlisted AI-client / partner domains, four custom pattern types, and admin UI navigation; appended `atlassian-remote-mcp-available-domains` to `sources:` array. `serves_hosts:`, `mcp_server_name:`, `auth_required:`, and `auth_tools:` left unchanged.
- Modified sources: [atlassian-remote-mcp-getting-started](sources/atlassian-remote-mcp-getting-started.md) — OQ#2 re-framed: the available-domains page documents the AI-client OAuth allowlist mechanism, distinct from `/kb-ingest` routing (`serves_hosts:`). Original framing "may reveal additional serves_hosts: patterns" was incorrect. Documentation gap is filled; routing-extension question was never applicable.
- Framing correction: this page lists AI-client domains (OAuth callback origins of tools connecting INTO Atlassian), not Atlassian tenant hostnames for kb-ingest routing. The two mechanisms are separate and should not be conflated.
- Doc-namespace observation: confirmed three Atlassian doc namespaces for Rovo MCP content: `/rovo/docs/...` (legacy), `/atlassian-rovo-mcp-server/docs/...` (current user docs), `/security-and-access-policies/docs/...` (admin policies).
- New gaps surfaced: (a) doc-namespace fragmentation — canonical URL preference not yet in kb-ingest skill or wiki; (b) which AI client domains has LINQ's org admin actually allowlisted?; (c) regional MCP variants not addressed by any ingest
- Curator: knowledge-curator

## [2026-05-03] lint | 0 findings

All 8 checks passed post-ingest of `atlassian-remote-mcp-supported-tools`. Checks run: (1) orphans — none; (2) orphan raw files — none (6 raw files, all referenced); (3) broken links — none in new source page, new entity section, or updated source pages; (4) stale claims — none (all pages `updated: 2026-05-03`); (5) contradictions — none (project-format/season-2 team-size discrepancy is an acknowledged open question, not an unresolved contradiction); (6) bidirectional drift — none (`atlassian-remote-mcp-supported-tools.md` entities↔`atlassian-mcp.md` sources bidirectional link confirmed in both directions; all 6 source↔entity/concept pairs verified); (7) unknown product tags — none (`jira-service-management` and `bitbucket` on `atlassian-mcp.md` are topic tags, not `product:*` tags; only `product:cross-cutting` used as product tag across all pages); (8) frontmatter completeness — none (new source page has all required fields; no `related:` field on any source-kind page). 12 wiki pages reviewed; 6 raw files reviewed. Curator: knowledge-curator.

## [2026-05-03] ingest | Atlassian Rovo MCP Server: Supported Tools

- Source: [wiki/sources/atlassian-remote-mcp-supported-tools.md](sources/atlassian-remote-mcp-supported-tools.md)
- Raw: [raw/sources/atlassian-remote-mcp-supported-tools-2026-05-03.md](../raw/sources/atlassian-remote-mcp-supported-tools-2026-05-03.md) (condensed-copy form — `auth_required: false`)
- New entities: (none — enriched existing [atlassian-mcp](entities/atlassian-mcp.md))
- New concepts: (none)
- Modified entities: [atlassian-mcp](entities/atlassian-mcp.md) — added JSM and Bitbucket Cloud to product list; replaced generic "Tools exposed" section with permission-group table (15 groups, ~60 total tools); added Teamwork Graph and search_atlassian as beta surfaces; added Open Questions section; bumped `sources:` array; added `jira-service-management` and `bitbucket` tags
- Closes: OQ#1 ("specific tool names") from both [wiki/sources/atlassian-remote-mcp-server.md](sources/atlassian-remote-mcp-server.md) and [wiki/sources/atlassian-remote-mcp-getting-started.md](sources/atlassian-remote-mcp-getting-started.md)
- New gaps surfaced: (a) Atlassian doc-namespace migration `/rovo/docs/...` → `/atlassian-rovo-mcp-server/docs/...`; (b) JSM at LINQ — does LINQ use JSM?; (c) Bitbucket Cloud at LINQ — does LINQ use Bitbucket Cloud?; (d) `createJiraIssue` description mismatch — needs human verification
- Curator: knowledge-curator

## [2026-05-03] lint | 0 findings

All 8 checks passed (orphans, broken links, stale claims, contradictions, bidirectional drift, unknown product tags, frontmatter completeness, prior-fix verification). Confirmed: `related:` field removed from `wiki/sources/atlassian-remote-mcp-server.md` frontmatter; body `## Related sources` cross-link to `atlassian-remote-mcp-getting-started.md` intact. 11 wiki pages reviewed; 5 raw files reviewed. Curator: knowledge-curator.

## [2026-05-03] lint | 1 finding

`wiki/sources/atlassian-remote-mcp-server.md` — non-standard `related:` frontmatter field (SCHEMA §2 source spec does not define `related:`; relationship should be expressed in the body's `## Related sources` section, as done in the getting-started source page). All other checks (orphans, orphan raw files, broken links, stale claims, contradictions, bidirectional drift, unknown product tags, required-field completeness) passed. 11 wiki pages reviewed; 5 raw files reviewed. Curator: knowledge-curator.

## [2026-05-03] ingest | Atlassian Rovo MCP Server — Getting Started (support docs)

- Source: [wiki/sources/atlassian-remote-mcp-getting-started.md](sources/atlassian-remote-mcp-getting-started.md)
- Raw: [raw/sources/atlassian-remote-mcp-getting-started-2026-05-03.md](../raw/sources/atlassian-remote-mcp-getting-started-2026-05-03.md) (condensed-copy form — `auth_required: false`)
- New entities: (none — enriched existing [atlassian-mcp](entities/atlassian-mcp.md))
- New concepts: (none)
- Modified entities: [atlassian-mcp](entities/atlassian-mcp.md) — added Compass to product list, current endpoint `/v1/mcp/authv2` and legacy sunset note, supported-clients list, API-token auth method
- Partially closes: OQ#1 (capabilities now known; specific tool names still gap), OQ#2 (Compass confirmed), OQ#3 (current endpoint confirmed) from [wiki/sources/atlassian-remote-mcp-server.md](sources/atlassian-remote-mcp-server.md)
- New gaps surfaced: "Supported tools" sub-page (specific tool names), "Available Atlassian Rovo MCP Server domains" (routing), "Setting up IDEs" (developer onboarding)
- Curator: knowledge-curator (via /kb-ingest skill)

## [2026-05-03] lint | 0 findings

All 8 checks passed (orphans, orphan raw files, broken links, stale claims, contradictions, bidirectional drift, unknown product tags, frontmatter completeness). 10 wiki pages reviewed; 4 raw files reviewed. Curator: knowledge-curator.

## [2026-05-03] ingest | The Forge — Season 2: Every Minute Matters (Confluence)

- Source: [wiki/sources/forge-season-2-every-minute-matters.md](sources/forge-season-2-every-minute-matters.md)
- Raw: [raw/sources/forge-season-2-every-minute-matters-2026-05-03.md](../raw/sources/forge-season-2-every-minute-matters-2026-05-03.md) (stub form — `auth_required: true`)
- New entities: [forge-season-2-every-minute-matters](entities/forge-season-2-every-minute-matters.md)
- New concepts: (none — Project Format concept already exists at [wiki/concepts/project-format.md](concepts/project-format.md))
- Modified entities: [forge-linq-hackathon-program](entities/forge-linq-hackathon-program.md) — added Season 2 to `related:`, updated prize-specifics note
- Routing: auth-required stub; URL host `confluence.atlassian.linq.com` matched `serves_hosts:` on [wiki/entities/atlassian-mcp.md](entities/atlassian-mcp.md). Atlassian MCP read tools unavailable; content retrieved via Chrome MCP fallback (user authenticated to Confluence in browser).
- Open questions flagged: date-range discrepancy (May 4–8 vs. Monday–Thursday), prize structure, judges roster, daily schedule, team-size discrepancy (program page: 2–5; Season 2 page: 3–5)
- Curator: knowledge-curator (via /kb-ingest skill)

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
