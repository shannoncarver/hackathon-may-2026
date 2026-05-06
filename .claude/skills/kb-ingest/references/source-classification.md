# Source classification rules

How `/kb-ingest` decides which fetch path to run for a given reference. Step 1 of the [`kb-ingest` skill](../SKILL.md).

## Canonical routing comes from the wiki

> **Canonical routing comes from `wiki/entities/<mcp>.md` frontmatter (`serves_hosts:` + `mcp_server_name:`).** This file is a starter / fallback for hosts not yet ingested as wiki entities. When you ingest an MCP server's docs via `/kb-ingest`, the resulting wiki entity supersedes the rules below for any host its `serves_hosts:` covers.
>
> **To bootstrap routing for a new MCP:**
> 1. Register the MCP in `.mcp.json` (or per-agent `mcpServers:`) — one-time wiring step.
> 2. Run `/kb-ingest <mcp-docs-url>` against the MCP's documentation page.
> 3. The resulting `wiki/entities/<mcp-name>.md` populates `serves_hosts:`, `mcp_server_name:`, `auth_required:`, and `auth_tools:`.
> 4. From then on, `/kb-ingest <any URL whose host matches serves_hosts>` auto-routes through that MCP. No edits to this file required.
>
> The kb-ingest skill's classification step (per [`SKILL.md`](../SKILL.md) Step 1) consults wiki entities first, falls back to the tables below, and finally falls through to public WebFetch.

## URL classification

The host determines public vs. auth-required. The wiki-entity scan supersedes these tables when an entity exists; the tables remain for hosts whose MCP docs haven't been ingested yet, and as a human-readable reference.

### Auth-required hosts (use MCP-mediated fetch → stub form)

| Host pattern | Tooling |
|---|---|
| `confluence.atlassian.linq.com` | Atlassian MCP (`mcp__atlassian__*`) |
| `*.atlassian.net` (LINQ Confluence Cloud, Jira Cloud) | Atlassian MCP |
| `linear.app/<linq-workspace>/...` | Linear MCP (when configured) |
| `*.slack.com/archives/...` | Slack MCP (when configured) |
| Internal LINQ hostnames (`*.linq.internal`, etc.) | Case-by-case; surface as gap if no MCP exists |

For these, the raw file is a **frontmatter-only stub** with `auth_required: true`, `requires_mcp: "<server-name>"`, and a fair-use 2–4 paragraph `excerpt:`. See [`knowledge/SCHEMA.md` §2 (stub form)](../../../../knowledge/SCHEMA.md).

### Public hosts (use WebFetch → condensed-with-citation copy)

Anything else. Common examples:

- `docs.claude.com`, `code.claude.com`, `anthropic.com`, `claude.com`
- Public LINQ marketing pages (`linq.com`, `linqit.com`, etc.)
- GitHub README files (`github.com/.../blob/...`)
- Engineering blogs, public RFCs, public vendor docs

For these, the raw file is a **condensed copy**: section headers and key paragraphs preserved verbatim where load-bearing, supporting prose summarized. Always include `source_url`, `fetched_at`, and `license_note` in frontmatter. See [`knowledge/SCHEMA.md` §2 (condensed-copy form)](../../../../knowledge/SCHEMA.md).

### URLs that redirect

Many doc hosts redirect (e.g., `docs.claude.com → code.claude.com`). On redirect:

1. Re-classify against the redirect target host.
2. Prefer the redirect target URL in the wiki summary's `url:` field — it's the canonical destination.
3. Note the original URL in the source page if teammates may search by it.

## File-path classification

### In-repo path (no copy needed)

The path resolves under the current worktree root. Detection:

```bash
realpath "$REFERENCE" | grep -q "^$(realpath .)/" && echo "in-repo" || echo "external"
```

For in-repo paths under `knowledge/raw/sources/`, the curator processes the file in place. For in-repo paths elsewhere (e.g., `docs/research/foo.md`), copy to `knowledge/raw/sources/<slug>-YYYY-MM-DD.<ext>` first — the wiki ingests files via `raw/`, never elsewhere in the tree.

### External absolute path

Anything outside the worktree (most commonly `~/Downloads/`, `/tmp/`, `/Users/<user>/Documents/`).

1. Compute the slug from the filename, stripping extension and dates.
2. Copy the file to `knowledge/raw/sources/<slug>-YYYY-MM-DD.<ext>` using `cp` (preserving the extension).
3. The curator processes from `raw/sources/`.

### Refused file types

Wiki ingest is for documents the LLM can read. Refuse with an explanation:

- Archives: `.zip`, `.tar`, `.tar.gz`, `.7z`
- Binaries: `.exe`, `.dmg`, `.iso`, `.bin`
- Build artifacts: `.so`, `.dylib`, `.dll`, `.o`
- Fonts and audio/video: `.ttf`, `.otf`, `.mp4`, `.mov`, etc.

Acceptable types include: `.md`, `.txt`, `.pdf`, `.json`, `.yaml`, `.yml`, `.html`, `.htm`, `.csv`, `.tsv`, `.docx`, `.pptx`, `.xlsx` (the last three via the appropriate skill).

## Slug computation

From a URL:

1. Drop scheme and host.
2. Drop common path noise (`docs/`, `wiki/spaces/<NAME>/pages/<NUMERIC-ID>/`, locale prefixes like `/en/`).
3. Take the last meaningful path segment, replace `+` and `_` with `-`, lowercase.
4. Strip trailing slashes, query strings, and `.html`.

Examples:

| URL | Slug |
|---|---|
| `https://code.claude.com/docs/en/sub-agents` | `anthropic-sub-agents` (the host's purpose informs the prefix) |
| `https://confluence.atlassian.linq.com/wiki/spaces/CTO/pages/419659784/The+Forge+LINQ+Hackathon+Program` | `forge-linq-hackathon-program` |
| `https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md` | `skill-creator` |

From a file path:

1. Take the basename.
2. Drop the extension.
3. Drop trailing date stamps (`-2026-05-03`) — the date goes into the dated filename, not the slug.
4. Lowercase, kebab-case.

If the slug collides with an existing wiki entry that's already a different source, prefix with the source author or domain (e.g., `anthropic-` or `linq-`) to disambiguate.

## Tag inference

Tags fall into two buckets:

- **Always present:** `product:cross-cutting` (until ADR 0014 lands).
- **Topic tags:** inferred from the source. Take 2–4 obvious topical keywords. Examples: `anthropic`, `claude-code`, `confluence`, `hackathon`, `forge`, `mcp`, `llm`, `wiki`.

Avoid: redundant tags (`document`, `source`, `summary`), generic tags (`tech`, `engineering`), and tags that duplicate the slug.

When in doubt, propose a tag set in pre-flight and let the user override.
