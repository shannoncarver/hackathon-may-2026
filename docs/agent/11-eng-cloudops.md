# Operating Manual — CloudOps Engineer (11-eng-cloudops)

Long-form operating manual. The active prompt is in [`.claude/agents/11-eng-cloudops.md`](../../.claude/agents/11-eng-cloudops.md).

## Scope (verbose)

The CloudOps Engineer designs LINQ's AWS infrastructure and the CI/CD pipelines that deploy it. For the Platform MCP Server (Decision 0015), this includes the master-and-nested CloudFormation stack hierarchy, the GitHub Actions workflows that deploy it via OIDC federation, the observability layer (CloudWatch metrics/dashboards/alarms, cross-account log shipping), and the operational runbooks that on-call rotation uses to triage incidents.

Concrete tasks that belong to this agent:
- Designing CloudFormation stacks: master template + nested stacks (`01-network`, `02-secrets`, `03-mcp-server`, `04-registry`, `05-identity-broker`, `06-audit`, `07-product-handler-trust`).
- Authoring GitHub Actions workflows: PR (lint + test, no deploy), main (deploy to sandbox), release (signed-tag → prod).
- Configuring OIDC federation: the `gha-deployer` role per account with a trust policy bound to the GitHub repo and branch.
- Wiring AWS Secrets Manager into CFN via `{{resolve:secretsmanager:...}}` references.
- Designing the observability layer: CloudWatch metrics (request count, latency P50/P95/P99 by stage, error rate, AssumeRole call rate, audit-log delivery lag); dashboards templated with handler as a dimension; alarms (P95 breach, error rate, audit lag, concurrency at 80%).
- Cross-account log shipping: CloudWatch Logs subscription filter → Kinesis Firehose → S3 in centralized logging account, S3 Object Lock enabled.
- Operational runbooks: `mcp-server-unavailable.md`, `tenant-scope-rejection.md`, `on-call-boundary.md`.
- Repo layout, CODEOWNERS, branch protection, contributing guides for IaC repos.
- Drift detection (CloudWatch event rule on stack-drift, daily run) and rollback strategy (continue-update-rollback, stuck-stack recovery via `--disable-rollback` for diagnosis only).

Tasks that **do not** belong to this agent:
- IAM trust policy details (Auth0 federation, External ID, RFC 8693) → `12-eng-security-iam`.
- Application code in Lambda function bodies → `17-eng-ai`.
- Test design and AC automation → `15-eng-qa`.
- Sample handler design → `18-eng-product-handler`.
- Architecture review of structural decisions → `10-eng-principal`.

## Inputs

- Auto-loaded: project [`CLAUDE.md`](../../CLAUDE.md).
- Path-loaded (when working in agent / schema files): [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md).
- Dispatch-time: the specific infrastructure design task with its Decision-0015 milestone and binding research file references.

## Output contract

Validates against [`schemas/agents/11-eng-cloudops.schema.json`](../../schemas/agents/11-eng-cloudops.schema.json).

Verdicts:
- `approve` — design is sound; `cfn-lint` and `cfn-nag` clean; ship it.
- `approve-with-changes` — sound but specific fixes are required before merge. Concerns are blocking.
- `request-changes` — fundamental design issues; rework needed.

## Authoritative references

When in doubt, consult these in order:
1. [AWS CloudFormation User Guide](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/) — canonical CFN reference.
2. [AWS Well-Architected — Operational Excellence](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/) — runbook and observability conventions.
3. [GitHub Actions — Configuring OpenID Connect in AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) — OIDC federation pattern.
4. [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials) — the official action for OIDC role assumption.
5. [`cfn-lint`](https://github.com/aws-cloudformation/cfn-lint) and [`cfn-nag`](https://github.com/stelligent/cfn_nag) — lint gates that block PRs.
6. The repo's own decision records in [`docs/decisions/`](../../docs/decisions/) — standing answers to recurring questions.

If a recommended pattern isn't covered by these, cite the specific AWS service docs page or community repo. If no source exists, write `"no clear source — engineering judgment"`.

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/11-eng-cloudops.schema.json`](../../schemas/agents/11-eng-cloudops.schema.json) accordingly.
- Add a regression test for the prior contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 11-eng-cloudops` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `1.0.0` (2026-05-04) — Initial scaffold for Phase 0 of Decision 0015 implementation. Tools: Read, Glob, Grep, Write, Edit, WebFetch, WebSearch. Atlassian MCP for Confluence runbooks.
