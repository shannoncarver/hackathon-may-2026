---
status: Accepted
date: 2026-05-05
category: skills-management
---

# Decision 0016 — AWS multi-account, multi-environment credential convention for skills

**Status:** Accepted (2026-05-05).

## Context

The repo's first AWS-touching skill, [verify-user-authorization](../../skills/verify-user-authorization/SKILL.md), was initially dev-only and relied on boto3's default credential chain — typically the three-env-var paste (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`) from the AWS access portal's "command line" panel. As more AWS-touching skills land — platform telemetry, S3 audits, Lambda introspection — the project needs to:

1. Run **two skills targeting two AWS accounts in the same prompt** without re-pasting credentials between calls. Today's blocker: the env-var paste is shell-global, so two skills cannot both have valid creds at the same time.
2. Promote skills from dev-only to **dev + prod** without losing the safety properties of the original dev gate.
3. Support **break-glass overrides** (one-off profiles for incident response, time-boxed elevated roles, IAM debugging) without breaking the default seamless flow.
4. Work in **two execution contexts**: a human at a terminal AND a background agent / scheduled run / Lambda / GHA OIDC.

LINQ AWS accounts share one IAM Identity Center (one `aws sso login --sso-session linq` warms many profiles). The repo posture is reference-quality — every structural decision earns a record.

## Decision

Adopt the following convention for every AWS-touching skill in this repo. Captured in seven rules; they apply to skills authored in this repository and to any skill that reuses these scripts as a template.

### Rule 1 — Use named profiles via `boto3.Session(profile_name=...)`

Skills construct sessions with an explicit profile name. They do not read or rely on shell-global `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`. boto3's default credential chain remains the **headless fallback** (Lambda execution role, GHA OIDC web-identity, EC2 instance profile) when no profile is specified.

### Rule 2 — Declare target accounts in SKILL.md

Every AWS-touching SKILL.md has an `## AWS profiles` section that names: canonical profile names per supported environment (e.g., `linq-erp-dev`, `linq-erp-prod`), a skill-specific env-var override (e.g., `LINQ_ERP_AWS_PROFILE`), the `--aws-profile` CLI flag, the required IAM permissions, and the account ID + role name per profile so operators can verify which account they hit.

### Rule 3 — Profile resolution order in the script

1. `--aws-profile <name>` CLI flag — explicit operator override (incident, debugging).
2. `LINQ_<PRODUCT>_AWS_PROFILE` env var — workflow-level override.
3. `LINQ_AWS_USE_AMBIENT_CHAIN=1` env var — skip named profiles, use boto3's default chain.
4. Derived from `--environment` — `linq-<product>-{env}`.
5. Headless fallback — `--aws-profile ''` (empty string) → `boto3.Session()` with no profile.

### Rule 4 — Environment drives both profile and table names

`--environment dev|prod` is the single user-facing toggle. The script derives both the AWS profile and any product-specific resource names (DynamoDB tables, S3 bucket prefixes, Lambda function-name prefixes) from `--environment` so a user typing `--environment prod` cannot accidentally point dev creds at prod data, or vice versa.

### Rule 5 — Production requires explicit acknowledgment

When `--environment prod`, the script refuses to run unless `--i-understand-this-is-prod` is also passed. Mirrors how `kubectl` and `terraform` guard destructive ops, but applied to read-only too — because the audit trail and the operator's mental model both benefit from explicit prod intent. The flag has no shorter alias by design.

### Rule 6 — Fail fast with the exact remediation

Three credential-failure classes, each with a targeted error message:

- **Profile missing from `~/.aws/config`** → `botocore.exceptions.ProfileNotFound` → `reason` includes the literal `[profile <name>]` block the operator must add.
- **Credentials missing or expired** → `NoCredentialsError` / `ClientError` from `sts:GetCallerIdentity` → `reason` includes the literal command `aws sso login --sso-session linq`.
- **DynamoDB / downstream API error** → existing message, distinct from credential errors.

The script MUST NOT shell out to `aws sso login` itself — that breaks headless callers (no TTY, no browser).

### Rule 7 — One SSO session warms every account

Standardize on a single `[sso-session linq]` block in `~/.aws/config`, with one `[profile ...]` per (product × environment). One `aws sso login --sso-session linq` warms all of them. Per-skill SKILL.md provides the canonical stanza; operators copy-paste once.

## Reference implementation

[verify-user-authorization](../../skills/verify-user-authorization/SKILL.md) is the canonical implementation of this convention. New AWS-touching skills should mirror its argparse layout, profile resolution, prod guardrail, three-phase try/except, and the `sts:GetCallerIdentity` audit banner before any downstream call.

## Alternatives Considered

### Alternative A — Keep the env-var paste pattern (status quo)

Operator copies three env vars from the SSO console per session. Works for one account at a time.

**Rejected.** Cannot support two skills targeting two accounts in the same prompt without re-pasting between calls. Hostile to the coordinator UX the project is built around.

### Alternative B — Wrapper command (`aws-vault exec <profile> -- python …`) per invocation

Caller wraps every script call with a credential-broker command; the script itself is account-agnostic.

**Rejected.** Requires every operator to install and configure `aws-vault`. Adds a dependency that solves nothing Identity Center + named profiles doesn't already solve. Does not help skills that need to know their target account at the SKILL.md / agent-discovery layer.

### Alternative C — Centralized credential broker / token-exchange Lambda

Skills call a platform service that exchanges an Auth0 identity for short-lived AWS creds (analogous to the IdentityBroker in [Decision 0015](0015-centralized-platform-mcp.md)).

**Deferred.** This is the long-term destination for **the platform MCP server** ([Decision 0015](0015-centralized-platform-mcp.md)), but it does not yet exist. Skills land in months, not at M4. When the platform broker reaches GA, AWS-touching skills migrate by replacing the named-profile resolution block with a broker call — argparse, audit banner, prod guardrail, and SKILL.md contract all stay unchanged. The seam is at `boto3.Session(...)`; everything above it is reusable.

### Alternative D — Cross-account AssumeRole chain from a single baseline profile

Operator authenticates once into an "agent" account; each skill assumes a role into its target account using a known role ARN.

**Rejected for v1.** Requires per-account trust policies and an "agent" account that LINQ does not have today. Identity Center already covers the same threat model with one login, and Identity Center is what LINQ uses. Reserve AssumeRole chaining for cross-account skills (one skill that touches both accounts in a single invocation) — that's the only case the named-profile pattern doesn't cover, and it's deferred.

## Consequences

- **Positive:** One `aws sso login --sso-session linq` per day warms every LINQ account. Two skills in one prompt compose seamlessly with no shared shell state.
- **Positive:** Headless callers (Lambda, GHA OIDC, agent runners) use the ambient chain via `--aws-profile ''`. Same skill code serves both human and machine without branching logic.
- **Positive:** Prod runs require explicit `--i-understand-this-is-prod`. Audit trail at CloudTrail names the role; per-invocation stderr banner names the resolved account and ARN.
- **Positive:** Convention scales to N products and N environments without re-architecture. Adding a new product is one new `[profile ...]` block + one new env-var name in that product's SKILL.md.
- **Negative:** One-time setup cost — operators must add the `[sso-session linq]` block and per-product profiles to `~/.aws/config`. SKILL.md provides the copy-paste stanza; alternative is the `aws configure sso` wizard.
- **Negative:** Operators must understand the difference between `--environment` (dataset) and `--aws-profile` (identity). SKILL.md "Override — when and how" makes the distinction explicit.
- **Operational debt:** When [Decision 0015](0015-centralized-platform-mcp.md)'s IdentityBroker reaches GA, evaluate migrating AWS-touching skills off named-profile resolution to broker-issued short-lived credentials. This convention's seam (`boto3.Session(...)`) is designed to make that swap a single-block change per skill.

## Sources

- [verify-user-authorization SKILL.md](../../skills/verify-user-authorization/SKILL.md) — reference implementation.
- [knowledge/wiki/concepts/aws-skill-credential-pattern.md](../../knowledge/wiki/concepts/aws-skill-credential-pattern.md) — wiki concept page mirroring this decision.
- [.claude/rules/aws-skill-credentials.md](../../.claude/rules/aws-skill-credentials.md) — auto-load rule for sub-agents authoring AWS-touching skills.
- [Decision 0015](0015-centralized-platform-mcp.md) — long-term centralized credential broker; this decision is the bridge until that broker reaches GA.
- [AWS IAM Identity Center user guide](https://docs.aws.amazon.com/singlesignon/latest/userguide/what-is.html).
- [boto3 Session — `profile_name`](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/session.html).
- [AWS CLI — `aws configure sso`](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).
