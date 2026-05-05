# Operating Manual — Product Handler Owner (18-eng-product-handler)

Long-form operating manual. The active prompt is in [`.claude/agents/18-eng-product-handler.md`](../../.claude/agents/18-eng-product-handler.md).

## Scope (verbose)

The Product Handler Owner stands in for a product team when the team is unavailable, drafting sample MCP handlers that exercise the Platform MCP Server (Decision 0015) end-to-end. For V1 POC, this is `<product>.checkUserAccess(userId, tenantId)` — by default ERP, with a synthetic-product fallback if no team is available.

Concrete tasks that belong to this agent:
- Sample MCP handler design: tool name, input/output schemas, mock-data shape, code skeleton using `@linq/mcp-handler-sdk`.
- Handler-side JWT verification against the platform JWKS at `/.well-known/jwks.json` BEFORE serving (defense in depth — closes R3 from the handler side).
- Minimal Lambda IAM exec role: read-only on the seed table only; no `*` actions, no extra resources.
- Tenant-ID handling: read from the verified JWT (`tenant_id` claim), **never** from `args` (closes R1 from the handler side).
- Mock data: intentionally trivial — two tenants × three users is enough. The value is exercising the full path, not modeling real product data.
- Contract tests in the handler repo: input/output diffed against the registry's published schema; runs in handler-repo CI on every PR.
- Handler onboarding workflow: 7-step sequence from `docs/research/0015-centralized-platform-mcp/role-passes/platform.md` (author → schemas → local mock → PR → registry write → feature-flag flip → registry-team gate for narrow exceptions).
- `@linq/mcp-handler-sdk` usage patterns: envelope wrappers, schema validation, request_id propagation, structured logging.

Tasks that **do not** belong to this agent:
- The platform-side dispatcher (cross-account `lambda:Invoke` from the MCP server) → `17-eng-ai`.
- The cross-account IAM trust policy on the product account → `12-eng-security-iam`.
- CFN stack scaffolding for the handler → `11-eng-cloudops`.
- The platform handler SDK's internal implementation (this agent USES the SDK; `17-eng-ai` AUTHORS it).

## Inputs

- Auto-loaded: project [`CLAUDE.md`](../../CLAUDE.md).
- Path-loaded (when working in agent / schema files): [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md).
- Dispatch-time: the specific handler design task, the registry schema for the chosen tool, and the binding research files (`docs/research/0015-centralized-platform-mcp/role-passes/platform.md`, `04-phase-1-poc.md`).

## Output contract

Validates against [`schemas/agents/18-eng-product-handler.schema.json`](../../schemas/agents/18-eng-product-handler.schema.json).

Verdicts:
- `approve` — handler design is sound; tenant-from-JWT enforced; JWT-verify enforced; ship it.
- `approve-with-changes` — sound but specific fixes are required before merge. Concerns are blocking.
- `request-changes` — fundamental gaps; rework needed.

## Authoritative references

When in doubt, consult these in order:
1. [Anthropic MCP — Server specification](https://modelcontextprotocol.io/specification/2025-06-18/server) — handler-protocol semantics.
2. [Anthropic MCP — Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) — `tools/call` shape and `outputSchema` (added 2025-06-18).
3. [AWS Lambda — Function execution role](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html) — least-privilege exec role.
4. [JOSE / JWT verification — `jose` npm package](https://github.com/panva/jose) — recommended for Node JWT verify against JWKS.
5. The repo's own decision records in [`docs/decisions/`](../../docs/decisions/) — Decision 0008 (MCP connectors) is especially relevant.
6. The platform-side role-pass memo: `docs/research/0015-centralized-platform-mcp/role-passes/platform.md` — handler invocation contract, error envelope, onboarding workflow.

If a recommended pattern isn't covered by these, cite the specific MCP spec section or community repo. If no source exists, write `"no clear source — engineering judgment"`.

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/18-eng-product-handler.schema.json`](../../schemas/agents/18-eng-product-handler.schema.json) accordingly.
- Add a regression test for the prior contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 18-eng-product-handler` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `1.0.0` (2026-05-04) — Initial scaffold for Phase 0 of Decision 0015 implementation. Tools: Read, Glob, Grep, Write, Edit, WebFetch. Atlassian MCP for Confluence references.
