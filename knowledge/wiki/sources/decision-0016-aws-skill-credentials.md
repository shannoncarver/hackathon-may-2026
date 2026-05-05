---
title: "Decision 0016 — AWS multi-account, multi-environment credential convention for skills"
kind: source
raw_path: "docs/decisions/0016-aws-multi-account-skill-credentials.md"
url: "docs/decisions/0016-aws-multi-account-skill-credentials.md"
author: "LINQ engineering (internal decision record)"
fetched_at: 2026-05-05
tags: ["aws", "iam", "sso", "skills", "architecture", "decision-record", "product:cross-cutting"]
entities: []
concepts: ["wiki/concepts/aws-skill-credential-pattern.md"]
created: 2026-05-05
updated: 2026-05-05
---

## Why this source

Decision 0016 is the authoritative record establishing the AWS credential convention for every AWS-touching skill in this repo. Without it, the concept page [`wiki/concepts/aws-skill-credential-pattern.md`](../concepts/aws-skill-credential-pattern.md) had no citable source and every body claim was uncitable per the cite-or-flag rule — the BLOCKER flagged by `/kb-lint`.

## What it covers

The decision addresses four problems that emerge as AWS-touching skills multiply: running two skills against two different AWS accounts in a single prompt without re-pasting credentials, promoting skills from dev-only to dev + prod safely, supporting break-glass overrides, and working in both interactive (terminal) and headless (Lambda, GHA OIDC) execution contexts.

## Key claims

All claims below cite [`docs/decisions/0016-aws-multi-account-skill-credentials.md`](../../../docs/decisions/0016-aws-multi-account-skill-credentials.md).

- **Rule 1 — Named profiles.** Skills call `boto3.Session(profile_name="linq-<product>-<env>")`. Shell-global env vars (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`) are the headless fallback only — never the primary mechanism.
- **Rule 2 — Declared accounts in SKILL.md.** Every AWS-touching `SKILL.md` carries an `## AWS profiles` section naming canonical profile names per environment, the skill-specific env-var override, the `--aws-profile` CLI flag, required IAM permissions, and the account ID + role name per profile.
- **Rule 3 — Resolution order.** First match wins: `--aws-profile <name>` flag → `LINQ_<PRODUCT>_AWS_PROFILE` env var → `LINQ_AWS_USE_AMBIENT_CHAIN=1` → derived from `--environment` → headless fallback (`--aws-profile ''`).
- **Rule 4 — Environment drives both profile and resource names.** `--environment dev|prod` derives both the AWS profile (`linq-<product>-{env}`) and product-specific resource name prefixes (DynamoDB tables, S3 prefixes, Lambda names). One toggle eliminates dev-creds-against-prod-data misalignment.
- **Rule 5 — Production requires explicit acknowledgment.** `--environment prod` requires `--i-understand-this-is-prod`. Mirrors Kubernetes and Terraform destructive-op guards; applied even to read-only operations for audit and operator-intent reasons.
- **Rule 6 — Fail fast with exact remediation.** Three credential-failure classes each yield a targeted error: profile missing → literal `[profile <name>]` config block; creds missing/expired → literal `aws sso login --sso-session linq` command; downstream API error → distinct message. Scripts must NOT shell out to `aws sso login` (breaks headless callers).
- **Rule 7 — One SSO session warms every account.** A single `[sso-session linq]` block in `~/.aws/config`, with one `[profile ...]` per product × environment pair. One `aws sso login --sso-session linq` per day warms all profiles. SKILL.md provides the copy-paste config stanza.

## Entities introduced

None — Decision 0016 elaborates an existing credential convention; no new LINQ entities are introduced.

## Open questions for LINQ

- When [Decision 0015](../../../docs/decisions/0015-centralized-platform-mcp.md)'s IdentityBroker reaches GA, AWS-touching skills are expected to migrate from named-profile resolution to broker-issued short-lived credentials. The seam is `boto3.Session(...)` — every layer above it (argparse, audit banner, prod guardrail, SKILL.md contract) is reused unchanged. No ADR has yet been filed for that migration; it is noted as operational debt in Decision 0016.
- The reference implementation ([`skills/verify-user-authorization/SKILL.md`](../../../skills/verify-user-authorization/SKILL.md)) is the single canonical example. As additional AWS-touching skills land, confirm each mirrors the argparse layout, three-phase try/except, and audit-banner pattern.
