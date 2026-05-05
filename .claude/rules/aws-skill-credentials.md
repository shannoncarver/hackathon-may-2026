# AWS skill credential rules

These rules govern how every sub-agent authors, reviews, or invokes AWS-touching skills in this repo. They auto-load whenever an agent touches a skill that imports `boto3` or names a LINQ AWS resource. Standing decision: [Decision 0016](../../docs/decisions/0016-aws-multi-account-skill-credentials.md). Concept page: [`knowledge/wiki/concepts/aws-skill-credential-pattern.md`](../../knowledge/wiki/concepts/aws-skill-credential-pattern.md). Reference implementation: [`skills/verify-user-authorization/SKILL.md`](../../skills/verify-user-authorization/SKILL.md).

## The named-profile rule

Every AWS-touching script constructs its session via `boto3.Session(profile_name=<resolved>)`. Scripts MUST NOT read or rely on shell-global `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`. boto3's default credential chain remains the headless fallback, accessed via `--aws-profile ''` or `LINQ_AWS_USE_AMBIENT_CHAIN=1` — never as the implicit default.

## The environment-toggle rule

A single `--environment dev|prod` flag drives both the AWS profile (`linq-<product>-{env}`) and any product-specific resource names (DynamoDB tables, S3 buckets, Lambda functions). Scripts MUST NOT take a separate "which AWS account" flag — that lets dev creds point at prod data, or vice versa. Resource-name overrides are env-var only (`ERP_USERS_TABLE_NAME`, etc.), documented in SKILL.md, and intended for tests.

## The prod-acknowledgment rule

When `--environment prod`, scripts refuse to run unless `--i-understand-this-is-prod` is also passed. The flag has no shorter alias by design. Sub-agents drafting prompts that target prod MUST include the flag explicitly; if the user's intent is ambiguous about prod, ask before adding it.

## The audit-banner rule

Before any DynamoDB / S3 / Lambda / downstream API call, scripts call `sts:GetCallerIdentity` and print to stderr: `env`, `profile` (or `<ambient>`), `account`, `arn`, and the resource names the script will touch. The banner doubles as (a) per-invocation audit log and (b) fail-fast credential-validity check. Any expired SSO token, missing profile, or unconfigured ambient chain surfaces here, before downstream calls.

## The three-phase error rule

Credential errors split into three classes, each with a targeted `reason`:

- `ProfileNotFound` (profile missing from `~/.aws/config`) → name the profile and the literal `[profile <name>]` block to add.
- `NoCredentialsError` / `ClientError` from `sts:GetCallerIdentity` → include the literal command `aws sso login --sso-session linq`.
- `ClientError` / `BotoCoreError` from downstream calls → existing message, distinct from credential errors.

Scripts MUST NOT shell out to `aws sso login` themselves — that breaks headless callers (no TTY, no browser).

## The SKILL.md contract rule

Every AWS-touching SKILL.md has an `## AWS profiles` section that mirrors the structure in [`skills/verify-user-authorization/SKILL.md`](../../skills/verify-user-authorization/SKILL.md): what an AWS profile is, where profiles are stored, the one-time `~/.aws/config` stanza, the one-time login command, the resolution order, override semantics, headless / agent / CI guidance, and a troubleshooting table mapping `reason` strings to fixes. Reuse the headings verbatim — operators learning one skill should recognize the layout in every other AWS-touching skill in the repo.

## Pointer

Full convention: [Decision 0016](../../docs/decisions/0016-aws-multi-account-skill-credentials.md). When in doubt, that decision wins. When the centralized platform MCP server's IdentityBroker reaches GA ([Decision 0015](../../docs/decisions/0015-centralized-platform-mcp.md) M4+), evaluate migrating off named-profile resolution; the `boto3.Session(...)` seam is designed to make that swap a single-block change per skill.
