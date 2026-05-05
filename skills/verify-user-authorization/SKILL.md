---
name: verify-user-authorization
description: Verify whether a user is authorized for a LINQ ERP tenant. Use when the user asks "is this user authorized for tenant X", "verify user authorization", "check ERP access for user", "ERP authz check", "harmony auth lookup", "why can't this user log in to ERP", "can this user sign in for a given tenant", or wants the raw erp_users / erp_tenants records as evidence. Reads DynamoDB directly via boto3 and mirrors the HarmonyAuthAuthorize C# endpoint's decision logic. Returns a JSON envelope with authorized=true or false, a status enum (AUTHORIZED_SUPERUSER, AUTHORIZED_USER, USER_NOT_FOUND, USER_DISABLED, SUPERUSER_DISABLED, TENANT_DISABLED, TENANT_MISSING_BUT_USER_AUTHORIZED, TENANT_MISSING_USER_NOT_AUTHORIZED, ERROR), the matched user-record kind, and the raw user and tenant attributes. Supports dev and prod; prod runs require explicit --i-understand-this-is-prod opt-in.
allowed-tools: Bash
argument-hint: tenant_id, user_email, and environment (dev|prod)
---

# verify-user-authorization

Reproduces the LINQ ERP `HarmonyAuthAuthorize` C# endpoint's decision logic locally. Use when an operator asks whether a user can sign in to ERP for a given tenant, or when an incident-triage agent needs raw evidence from `erp_users` and `erp_tenants`.

**Decision semantics mirror the C# exactly**, including two surprising-but-real behaviors:

- A superuser row that exists but is *not active* prevents the user-in-tenant row from being consulted.
- A *missing* tenant row does NOT invalidate authorization (only an *inactive* tenant does).

If you need the corrected/intuitive logic instead, ask the user before deviating.

## Install

Three paths, depending on where you want to use the skill.

**1. In this repo (Claude Code) — already installed.** Clone the repo and start Claude Code from the repo root. The skill auto-loads via the [.claude/skills/verify-user-authorization](../../.claude/skills/verify-user-authorization) symlink. No further steps.

**2. In another repo or globally (Claude Code).** Symlink this folder into the target location:

```bash
# Globally for all your Claude Code sessions:
ln -s "$(pwd)/skills/verify-user-authorization" ~/.claude/skills/verify-user-authorization

# Or into a specific project:
ln -s "$(pwd)/skills/verify-user-authorization" /path/to/other-repo/.claude/skills/verify-user-authorization
```

**3. In Claude Desktop (the app, not Claude Code).** Zip the skill folder and upload via Settings → Capabilities → Skills:

```bash
cd skills && zip -r verify-user-authorization.zip verify-user-authorization/
```

Then drag the resulting `.zip` into Claude Desktop's Skills settings.

> Windows users: enable git symlink support once with `git config --global core.symlinks true` before cloning.

## When to use

- "Is `alice@example.com` authorized for tenant `acme-isd`?"
- "Verify ERP access for `bob@example.com` in `springfield-school-district`."
- "Run the harmony auth check against `<email>` and `<tenant>`."
- "Why is this user getting a 401 from the product after Auth0 login?"
- An incident agent needs the raw user / tenant DynamoDB records as evidence.

## When NOT to use

- Anything that mutates ERP state. This skill is read-only by design.
- Production runs from CI without an explicit, named workflow that has been pre-approved by Operations. Interactive prod runs are supported but require `--i-understand-this-is-prod`.

## Inputs

| Argument | Required | Notes |
|---|---|---|
| `--tenant-id` | yes | Lowercased internally before key construction. |
| `--user-email` | yes | Must be a valid email; lowercased internally. |
| `--environment` | yes | `dev` or `prod`. Drives both the AWS profile (`linq-erp-{env}`) and the DynamoDB table prefix (`dev_` for dev, none for prod). |
| `--i-understand-this-is-prod` | iff `--environment=prod` | Required acknowledgment for any prod run. The script refuses to run prod without it. |
| `--aws-profile` | no | Override the derived profile (e.g. for break-glass / incident profiles). Pass empty string (`--aws-profile ''`) to use boto3's default credential chain (Lambda role, GHA OIDC, instance profile). See "AWS profiles" below. |
| `--include-sensitive` | no | Return raw values for `*_id` attributes; default redacts them. |

## Output envelope (stdout, JSON)

```json
{
  "authorization": {
    "authorized": true,
    "status": "AUTHORIZED_USER",
    "reason": null
  },
  "user": { "PK": "...", "SK": "...", "status": "active", "db_user_id": "...", "...": "..." },
  "tenant": { "PK": "...", "SK": "...", "status": "active", "db_id": "...", "connection_string_id": "...", "...": "..." },
  "matched_user_record": "in_tenant"
}
```

`status` enum:

| Status | Meaning |
|---|---|
| `AUTHORIZED_SUPERUSER` | Active superuser row + active tenant. |
| `AUTHORIZED_USER` | No superuser row, active user-in-tenant row, active tenant. |
| `SUPERUSER_DISABLED` | Superuser row exists but inactive (user-in-tenant not consulted, per C#). |
| `USER_DISABLED` | No superuser row, user-in-tenant exists but inactive. |
| `USER_NOT_FOUND` | Neither user row exists. Tenant active or absent. |
| `TENANT_DISABLED` | Tenant exists but inactive. Overrides any user-side authorization. |
| `TENANT_MISSING_BUT_USER_AUTHORIZED` | Tenant row absent **but** user/superuser is active → authorized per C#. Surface this loudly. |
| `TENANT_MISSING_USER_NOT_AUTHORIZED` | Tenant row absent and user-side decision is also unauthorized. |
| `ERROR` | AWS credential / network / input error. See `reason`. |

`matched_user_record`: `"in_tenant"`, `"superuser"`, or `null`. When `superuser` matched, the `user` field carries the superuser row.

## How to invoke

**Default dev (the 99% case):**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/verify_authorization.py" \
  --tenant-id "<tenant>" \
  --user-email "<email>" \
  --environment dev
```

**Prod (requires explicit acknowledgment):**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/verify_authorization.py" \
  --tenant-id "<tenant>" \
  --user-email "<email>" \
  --environment prod \
  --i-understand-this-is-prod
```

**Break-glass override profile:**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/verify_authorization.py" \
  --tenant-id "<tenant>" \
  --user-email "<email>" \
  --environment prod \
  --i-understand-this-is-prod \
  --aws-profile linq-erp-prod-incident-2026-05-05
```

Pass `--include-sensitive` only when the operator has explicitly asked for the raw `*_id` values (e.g. `db_user_id`, `db_id`, `connection_string_id`). By default, those are returned as the literal string `"<redacted>"` in the authorized envelope. Unauthorized envelopes always return `null` for `user` and `tenant` regardless of this flag.

The script always exits 0; the JSON envelope on stdout is the only contract. Diagnostic messages go to stderr.

## Required environment

| Variable | Default | Notes |
|---|---|---|
| `AWS_REGION` | `us-east-1` | Matches `LINQ-ERP-v4/appsettings.json`. |
| `LINQ_ERP_AWS_PROFILE` | (unset) | Workflow-level override of the derived `linq-erp-{env}` profile. Wins over the derived default; loses to `--aws-profile`. |
| `LINQ_AWS_USE_AMBIENT_CHAIN` | (unset) | Set to `1` to skip named-profile resolution entirely; boto3 uses its default credential chain (Lambda role, GHA OIDC, instance profile). |
| `ERP_USERS_TABLE_NAME` | derived from `--environment` | Override only. Default: `dev_erp_users` for dev, `erp_users` for prod. |
| `ERP_TENANTS_TABLE_NAME` | derived from `--environment` | Override only. Default: `dev_erp_tenants` for dev, `erp_tenants` for prod. |
| AWS credentials | — | Resolved via named profile (default) or boto3's default credential chain (when profile is empty / ambient). See "AWS profiles" below. |

## AWS profiles

This skill follows the convention in [Decision 0016](../../docs/decisions/0016-aws-multi-account-skill-credentials.md) — every AWS-touching skill in this repo uses named profiles, derives its target account from `--environment`, and supports a break-glass override.

### What an AWS profile is

An AWS profile is a named bundle of "how to get AWS credentials" stored in `~/.aws/config`. Each profile names a target account, a role to assume in that account, and (for SSO) which Identity Center session to use. boto3, the AWS CLI, and every official AWS SDK read the same files — there is no skill-specific credential format.

### Where profiles are stored

| Path | Purpose | Edited by |
|---|---|---|
| `~/.aws/config` | Profile definitions — region, SSO session, role, MFA | You (hand-edit or `aws configure sso`) |
| `~/.aws/credentials` | Long-lived static IAM keys (legacy) | Usually empty when using SSO |
| `~/.aws/sso/cache/*.json` | Short-lived SSO access tokens | `aws sso login` writes them |
| `~/.aws/cli/cache/*.json` | Short-lived role credentials derived from SSO | AWS CLI / boto3 automatically |

You only edit `~/.aws/config`. The cache directories refresh themselves whenever `aws sso login` runs or boto3 needs a fresh credential.

### One-time setup — `~/.aws/config`

Paste this stanza, replacing the placeholder account IDs with the real LINQ account IDs from the AWS access portal. **One `[sso-session linq]` block, one `[profile ...]` per (product × environment).**

```ini
[sso-session linq]
sso_start_url = https://linq.awsapps.com/start
sso_region = us-east-1
sso_registration_scopes = sso:account:access

[profile linq-erp-dev]
sso_session = linq
sso_account_id = 111111111111
sso_role_name = ERPDevReadOnly
region = us-east-1

[profile linq-erp-prod]
sso_session = linq
sso_account_id = 333333333333
sso_role_name = ERPProdReadOnly
region = us-east-1
```

Alternative: run `aws configure sso` for an interactive wizard that creates the same entries. The wizard opens a browser, lets you pick the account and role from your entitled list, and writes the `[profile ...]` block automatically.

### One-time login (per day)

```bash
aws sso login --sso-session linq
```

Opens a browser, authenticates once, writes a token to `~/.aws/sso/cache/`. **That single token covers every profile that references `sso-session linq`** — both `linq-erp-dev` and `linq-erp-prod`, plus any other LINQ profiles you've configured against the same SSO session. Tokens typically last 8 hours.

### How the skill picks a profile

Resolution order (first match wins):

1. **`--aws-profile <name>`** — explicit operator override (break-glass / incident).
2. **`LINQ_ERP_AWS_PROFILE` env var** — workflow-level override.
3. **`LINQ_AWS_USE_AMBIENT_CHAIN=1` env var** — skip named profiles, use boto3's default chain.
4. **Derived from `--environment`** — `linq-erp-dev` or `linq-erp-prod`. The default path.
5. **Headless fallback** — `--aws-profile ''` (empty string) → `boto3.Session()` with no profile, default chain (Lambda role, GHA OIDC, instance profile).

The script prints the resolved profile, account ID, and role ARN to stderr before any DynamoDB call (via `sts:GetCallerIdentity`). That line is the per-invocation audit log; check it whenever a result looks suspicious.

### Override — when and how

Use `--aws-profile <name>` when:

- Incident response with a time-boxed elevated role (e.g. `linq-erp-prod-incident-2026-05-05`).
- Debugging an IAM policy under a non-default role.
- A coworker handed you a temporary profile name to reproduce their bug.

Do NOT use `--aws-profile` to swap dev↔prod intentionally — that's `--environment`'s job. The override changes *which IAM identity makes the calls*, not *which dataset the calls hit*. Table names always come from `--environment` (or the `ERP_*_TABLE_NAME` env vars), never from the profile.

### Headless / agent / CI

For Lambda, GHA OIDC web-identity, EC2 instance profiles, or any context where named profiles aren't configured, pass `--aws-profile ''` (or set `LINQ_AWS_USE_AMBIENT_CHAIN=1`). The skill calls `boto3.Session()` with no profile and lets the default credential chain resolve credentials from the environment. The audit banner still prints — it'll show `profile=<ambient>` and the resolved account / ARN.

### Troubleshooting

| Symptom (in `reason`) | Fix |
|---|---|
| `Could not resolve AWS identity ... aws sso login --sso-session linq` | Run that command. Token expired or never logged in. |
| `AWS profile 'linq-erp-prod' not found in ~/.aws/config` | Add the `[profile linq-erp-prod]` block (see "One-time setup"). |
| `AccessDenied: ... is not authorized to perform: dynamodb:GetItem` | Your SSO permission set is missing the role. Ask Operations to grant `ERPDevReadOnly` / `ERPProdReadOnly` for your user. |
| `Refusing prod run without --i-understand-this-is-prod` | Add the flag. Confirms explicit prod intent. |
| Wrong account ID in stderr banner | Profile is pointing at the wrong account. Re-check `sso_account_id` in `~/.aws/config`. |

## Least-privilege IAM policies

Two policies — one per environment. Both stay `dynamodb:GetItem`-only; the skill never writes. Prod role grants are managed by Operations, not self-service.

### `ERPDevReadOnly` (dev account)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ErpAuthzReadOnlyDev",
      "Effect": "Allow",
      "Action": "dynamodb:GetItem",
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/dev_erp_users",
        "arn:aws:dynamodb:us-east-1:*:table/dev_erp_tenants"
      ]
    }
  ]
}
```

### `ERPProdReadOnly` (prod account)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ErpAuthzReadOnlyProd",
      "Effect": "Allow",
      "Action": "dynamodb:GetItem",
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/erp_users",
        "arn:aws:dynamodb:us-east-1:*:table/erp_tenants"
      ]
    }
  ]
}
```

## Examples

### Authorized (default — `*_id` attributes redacted)

```json
{
  "authorization": {"authorized": true, "status": "AUTHORIZED_USER", "reason": null},
  "user": {"PK": "#USRID#alice@example.com", "SK": "#TEN#acme-isd", "status": "active", "db_user_id": "<redacted>"},
  "tenant": {"PK": "#TEN#acme-isd", "SK": "#TEN#", "status": "active", "db_id": "<redacted>", "connection_string_id": "<redacted>"},
  "matched_user_record": "in_tenant"
}
```

### Authorized — with `--include-sensitive`

```json
{
  "authorization": {"authorized": true, "status": "AUTHORIZED_USER", "reason": null},
  "user": {"PK": "#USRID#alice@example.com", "SK": "#TEN#acme-isd", "status": "active", "db_user_id": "u-123"},
  "tenant": {"PK": "#TEN#acme-isd", "SK": "#TEN#", "status": "active", "db_id": "t-789", "connection_string_id": "cs-555"},
  "matched_user_record": "in_tenant"
}
```

### Unauthorized — tenant disabled

`user` and `tenant` are nulled on any unauthorized outcome to avoid leaking partial records. Diagnostic detail lives in `reason` and `matched_user_record`.

```json
{
  "authorization": {
    "authorized": false,
    "status": "TENANT_DISABLED",
    "reason": "Tenant exists but status is 'inactive'."
  },
  "user": null,
  "tenant": null,
  "matched_user_record": "in_tenant"
}
```

## Notes for the agent

- Records are returned only when authorized. By default, any attribute key ending in `_id` (e.g. `db_id`, `db_user_id`, `connection_string_id`, denormalized `tenant_id`) is replaced with `"<redacted>"`. Pass `--include-sensitive` only when the operator has explicitly asked for the raw values, and even then never paste them into a public chat.
- C# does the three GetItems in parallel; the Python helper does them sequentially for readability — irrelevant at three calls.
