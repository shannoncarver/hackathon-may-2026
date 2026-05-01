# Pillar classification

The six project pillars from [CLAUDE.md](../../../../CLAUDE.md), with disambiguation guidance.

## 1. Knowledge base
**About:** structured info about LINQ products and demo domains.
**Where it lives:** `knowledge/_shared/`, `knowledge/linq-products/<product>/`.
**Triggers:** "what does product X do", "lookup customer scenario", "ingest documentation".
**Vs adjacent:** Documentation (pillar 3) is *human-authored docs about the system itself*; knowledge base is *content the system reasons over*.

## 2. Repo structure
**About:** directory layout, naming conventions, scaffolding decisions.
**Where it lives:** the tree itself, plus ADRs in `docs/architecture/`.
**Triggers:** "where should this go", "scaffold X", "rename folder".

## 3. Documentation
**About:** human-readable docs split by audience — stakeholder, developer, agent.
**Where it lives:** `docs/{stakeholder,developer,agent}/`, `README.md`, `CLAUDE.md`.
**Triggers:** "write a doc", "onboarding", "demo script".

## 4. Agent definitions
**About:** sub-agent system prompts, frontmatter, I/O contracts.
**Where it lives:** `.claude/agents/`, `schemas/agents/`, `docs/agent/`.
**Triggers:** "new agent", "review agent prompt", "agent contract".

## 5. Skills management
**About:** authoring, versioning, discovery, assignment of skills.
**Where it lives:** `.claude/skills/<name>/`.
**Triggers:** "new skill", "skill vs agent", "skill discovery".

## 6. MCP connector inventory
**About:** which connectors each agent needs, credentials, scoping.
**Where it lives:** `.mcp.json`, `MCP_VERSION_CHANGELOG.md`, per-agent `mcpServers:` fields.
**Triggers:** "add MCP server", "version bump connector", "scope MCP to agent".

## When a task fits multiple pillars
Assign to the pillar that owns the *primary deliverable*, dispatch secondary specialists for review. Document the chain explicitly.

## When a task fits no pillar
Flag to the user before proceeding. Don't force-fit.
