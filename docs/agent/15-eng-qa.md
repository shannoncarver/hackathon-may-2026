# Operating Manual — QA / Test Engineer (15-eng-qa)

Long-form operating manual. The active prompt is in [`.claude/agents/15-eng-qa.md`](../../.claude/agents/15-eng-qa.md).

## Scope (verbose)

The QA / Test Engineer designs LINQ's test strategy and ensures every acceptance criterion is observable. For the Platform MCP Server (Decision 0015), this includes the test pyramid, AC-to-test mapping, the local-dev environment, MCP Inspector smoke procedures, CI test stage gating, and the Phase D QA review pass over implementation artifacts.

Concrete tasks that belong to this agent:
- Test pyramid design with named tests at every layer:
  - **Unit** — JWT validation matrix (valid / expired / wrong-aud / wrong-iss / unsigned / missing); error envelope shape; registry resolution; dispatcher adapter; IdentityBroker JWT shape; schema validation.
  - **Contract** — handler input/output diffed against the registry's published schema; runs in handler-repo CI on every PR.
  - **Integration** — deployed sandbox + real Auth0 dev tenant + real cross-account dispatch.
  - **E2E** — every V1 acceptance criterion automated in GitHub Actions, one test per AC.
- AC-to-test mapping: every V1 AC has at least one automated assertion with a named test. ACs that cannot be automated are flagged with a manual-smoke fallback.
- Local-dev environment specs: Docker Compose with localstack for DynamoDB, SAM local for handler invocation, real Auth0 dev tenant.
- CI test stage gating: which stages block PR merge, which gate main-branch deploy, which gate release.
- Manual smoke procedures using `@modelcontextprotocol/inspector` against the deployed sandbox.
- Audit reconciliation tests (daily MCP request count vs audit row count).
- Phase D QA review pass: walk every implementation artifact, verify acceptance criteria are observable, verify cross-references resolve, confirm risk coverage is cited.

Tasks that **do not** belong to this agent:
- Test implementation (specialists implement their own unit tests; this agent specifies what should be tested, not the test code itself).
- Production deployment validation (lives in the runbooks owned by `11-eng-cloudops`).
- Architecture review of test strategy alternatives → `10-eng-principal`.

## Inputs

- Auto-loaded: project [`CLAUDE.md`](../../CLAUDE.md).
- Path-loaded (when working in agent / schema files): [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md).
- Dispatch-time: the specific test-strategy task, the V1 acceptance criteria from `docs/research/0015-centralized-platform-mcp/04-phase-1-poc.md`, and the implementation artifacts under review.

## Output contract

Validates against [`schemas/agents/15-eng-qa.schema.json`](../../schemas/agents/15-eng-qa.schema.json).

Verdicts:
- `approve` — strategy is sound; every AC is observable; ship it.
- `approve-with-changes` — sound but specific fixes are required before merge. Concerns are blocking.
- `request-changes` — fundamental gaps in coverage; rework needed.

## Authoritative references

When in doubt, consult these in order:
1. [Jest documentation](https://jestjs.io/docs/getting-started) — Node test framework.
2. [pytest documentation](https://docs.pytest.org/) — Python test framework.
3. [`@modelcontextprotocol/inspector`](https://github.com/modelcontextprotocol/inspector) — manual smoke for MCP servers.
4. [LocalStack](https://docs.localstack.cloud/) — local AWS service emulation.
5. [AWS SAM CLI — sam local](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-local.html) — local Lambda invocation.
6. [Anthropic MCP — Acceptance criteria patterns](https://modelcontextprotocol.io/specification/2025-06-18/) — protocol conformance.
7. The repo's own decision records in [`docs/decisions/`](../../docs/decisions/) — Decision 0011 (eval harness shape) is especially relevant.

If a recommended pattern isn't covered by these, cite the specific test-framework docs page or community repo. If no source exists, write `"no clear source — engineering judgment"`.

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/15-eng-qa.schema.json`](../../schemas/agents/15-eng-qa.schema.json) accordingly.
- Add a regression test for the prior contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 15-eng-qa` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `1.0.0` (2026-05-04) — Initial scaffold for Phase 0 of Decision 0015 implementation. Tools: Read, Glob, Grep, Write, Edit, Bash, WebFetch, WebSearch. Atlassian MCP for test-doc references.
