---
title: "AWS skill credential pattern"
kind: concept
tags: ["aws", "skills", "iam", "sso", "product:cross-cutting"]
sources: ["wiki/sources/decision-0016-aws-skill-credentials.md"]
related:
  - "wiki/synthesis/centralized-mcp-broker.md"
created: 2026-05-05
updated: 2026-05-05
---

## Definition

The **AWS skill credential pattern** is the LINQ-internal convention every skill in this repo uses to authenticate to AWS. It standardizes how skills name their target account, resolve credentials, support multiple environments, and gate production access. The pattern is established by [Decision 0016](../../../docs/decisions/0016-aws-multi-account-skill-credentials.md); the auto-load rule [`.claude/rules/aws-skill-credentials.md`](../../../.claude/rules/aws-skill-credentials.md) makes sub-agents follow it when authoring or reviewing AWS-touching skills.

## Why this pattern exists

Without a convention, AWS-touching skills default to boto3's "ambient" credential chain — typically the three env vars (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`) pasted from the AWS access portal. That works for one skill in one shell. It breaks the moment a coordinator agent invokes two skills targeting two different LINQ AWS accounts in the same prompt — the second invocation cannot have valid creds without overwriting the first's.

The convention solves three problems simultaneously: multi-account composition, dev↔prod safety, and head-and-headless support.

## The five mechanics

1. **Named profiles, not env vars.** Skills call `boto3.Session(profile_name="linq-<product>-<env>")` rather than reading shell-global env vars. Each profile is defined in `~/.aws/config` and points at one (account ID, role) pair via IAM Identity Center.
2. **Environment-derived defaults.** A single `--environment dev|prod` flag drives both the profile name (`linq-<product>-{env}`) and any product-specific resource names (table prefixes, bucket prefixes). One toggle, two consequences, no way to misalign them.
3. **Resolution order with override.** First match wins: `--aws-profile <name>` flag → `LINQ_<PRODUCT>_AWS_PROFILE` env var → `LINQ_AWS_USE_AMBIENT_CHAIN=1` → derived default → headless fallback (`--aws-profile ''`).
4. **Production guardrail.** `--environment prod` requires `--i-understand-this-is-prod`. The script refuses to run prod without it.
5. **Audit banner before any AWS call.** Every script calls `sts:GetCallerIdentity` first, prints `env`, `profile`, `account`, `arn`, and the resource names to stderr, then proceeds. The banner doubles as the per-invocation audit log and as the canonical fail-fast credential-validity check.

## One SSO session, many accounts

The pattern depends on LINQ's IAM Identity Center topology — one Identity Center covers all LINQ AWS accounts. A single `aws sso login --sso-session linq` warms every profile that references that session. A coordinator agent invoking three skills against three different accounts in one prompt makes one round-trip through SSO total, not three.

If LINQ ever splits Identity Center across organizational boundaries, this pattern degrades to "one login per Identity Center" — still vastly better than per-skill env-var pasting, but no longer single-login.

## What this pattern does NOT cover

- **Cross-account skills.** A single skill that needs to call *two* accounts in one invocation (e.g., a reconciliation script comparing prod ERP against prod Platform). The pattern targets exactly one account per skill. Cross-account skills require AssumeRole chaining, deferred until a real use case lands.
- **CI prod access.** Production from CI requires a separately reviewed workflow with its own role-assumption shape (typically GHA OIDC web-identity into a CI-only role). The pattern's ambient-chain fallback supports this technically but does not authorize it operationally.
- **Per-tenant role scoping.** One IAM role per LINQ customer tenant is a different design problem; this pattern is environment-scoped, not tenant-scoped.

## Migration path

When [Decision 0015](../../../docs/decisions/0015-centralized-platform-mcp.md)'s centralized platform MCP server and IdentityBroker reach GA, AWS-touching skills can migrate off named-profile resolution to broker-issued short-lived credentials. The seam is `boto3.Session(...)` — everything above it (argparse, audit banner, prod guardrail, SKILL.md contract) stays unchanged. Migration is a single block per skill, not a rewrite.

## Reference implementation

[`skills/verify-user-authorization/`](../../../skills/verify-user-authorization/SKILL.md) is the canonical implementation. New AWS-touching skills should mirror its layout: argparse with `--environment` / `--aws-profile` / `--i-understand-this-is-prod`, three-phase try/except for session construction → identity resolution → downstream calls, and the stderr audit banner before any DynamoDB / S3 / Lambda call.
