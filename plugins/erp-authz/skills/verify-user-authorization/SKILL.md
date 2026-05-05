---
name: verify-user-authorization
description: Verify whether a user is authorized for a LINQ ERP tenant. Use when the user asks "is this user authorized for tenant X", "verify user authorization", "check ERP access for user", "ERP authz check", "harmony auth lookup", "why can't <email> log in to ERP", "can <email> sign in for tenant <id>", or wants the raw erp_users / erp_tenants records as evidence. Reads DynamoDB directly via boto3 and mirrors the HarmonyAuthAuthorize C# endpoint's decision logic. Returns a JSON envelope with authorized=true|false, a status enum (AUTHORIZED_SUPERUSER, AUTHORIZED_USER, USER_NOT_FOUND, USER_DISABLED, SUPERUSER_DISABLED, TENANT_DISABLED, TENANT_MISSING_BUT_USER_AUTHORIZED, TENANT_MISSING_USER_NOT_AUTHORIZED, ERROR), the matched user-record kind, and the raw user and tenant attributes. Dev environment only.
allowed-tools: Bash
argument-hint: <tenant_id> <user_email>
---

# verify-user-authorization

Reproduces the LINQ ERP `HarmonyAuthAuthorize` C# endpoint's decision logic locally. Use when an operator asks whether a user can sign in to ERP for a given tenant, or when an incident-triage agent needs raw evidence from `erp_users` and `erp_tenants`.

**Decision semantics mirror the C# exactly**, including two surprising-but-real behaviors:

- A superuser row that exists but is *not active* prevents the user-in-tenant row from being consulted.
- A *missing* tenant row does NOT invalidate authorization (only an *inactive* tenant does).

If you need the corrected/intuitive logic instead, ask the user before deviating.

## When to use

- "Is `alice@example.com` authorized for tenant `acme-isd`?"
- "Verify ERP access for `bob@example.com` in `springfield-school-district`."
- "Run the harmony auth check against `<email>` and `<tenant>`."
- "Why is this user getting a 401 from the product after Auth0 login?"
- An incident agent needs the raw user / tenant DynamoDB records as evidence.

## When NOT to use

- Production lookups. This skill is gated to `--environment dev`.
- Anything that mutates ERP state (read-only).

## Inputs

| Argument | Required | Notes |
|---|---|---|
| `tenant_id` | yes | Lowercased internally before key construction. |
| `user_email` | yes | Must be a valid email; lowercased internally. |
| `environment` | yes | Only `dev` is accepted in the POC. |

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

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/verify_authorization.py" \
  --tenant-id "<tenant>" \
  --user-email "<email>" \
  --environment dev
```

Pass `--include-sensitive` only when the operator has explicitly asked for the raw `*_id` values (e.g. `db_user_id`, `db_id`, `connection_string_id`). By default, those are returned as the literal string `"<redacted>"` in the authorized envelope. Unauthorized envelopes always return `null` for `user` and `tenant` regardless of this flag.

The script always exits 0; the JSON envelope on stdout is the only contract. Diagnostic messages go to stderr.

## Required environment

| Variable | Default | Notes |
|---|---|---|
| `AWS_REGION` | `us-east-1` | Matches `LINQ-ERP-v4/appsettings.json`. |
| `ERP_USERS_TABLE_NAME` | `dev_erp_users` | Convention `{env}_erp_users`; prod is unprefixed `erp_users`. |
| `ERP_TENANTS_TABLE_NAME` | `dev_erp_tenants` | Convention `{env}_erp_tenants`; prod is unprefixed `erp_tenants`. |
| AWS credentials | — | boto3 default chain — see "AWS auth" below. |

## AWS auth — most seamless flow for AWS-console SSO users

If you sign in to the AWS console via SSO / Identity Center, you already have everything boto3 needs. Two patterns, easiest first:

### Pattern A — paste-from-console (zero setup, ~30s per session)

1. Open the AWS access portal (the SSO start page).
2. Click your dev account → role → **"Command line or programmatic access"**.
3. Copy the **"Option 1: Set AWS environment variables"** block. It looks like:
   ```bash
   export AWS_ACCESS_KEY_ID="ASIA..."
   export AWS_SECRET_ACCESS_KEY="..."
   export AWS_SESSION_TOKEN="..."
   ```
4. Paste into the same terminal where Claude Code is running. boto3's default credential chain picks them up automatically. Tokens typically last 1–12 hours.

This is the recommended hackathon path — no AWS CLI configuration, no profile management, just three env vars from a button click.

### Pattern B — `aws sso login` (one-time setup, refresh on demand)

```bash
# One-time:
aws configure sso
# Daily / when expired:
aws sso login --profile <profile-name>
export AWS_PROFILE=<profile-name>
```

boto3 reads `~/.aws/sso/cache/` automatically. Use this if you'll be running the skill many times across days.

Both patterns work with this skill unchanged — boto3's default credential chain order is: env vars (Pattern A) → `AWS_PROFILE` (Pattern B) → instance role. No code changes required.

## Least-privilege IAM policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ErpAuthzReadOnly",
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
