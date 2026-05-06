---
status: Accepted
date: 2026-05-06
category: skills-management
---

# Decision 0022 — `ha-debug` resource discovery via SSM Parameter Store + AWS API

**Status:** Accepted (2026-05-06).

## Context

[Decision 0021](0021-ha-debug-credential-migration.md) migrated `ha-debug` to named SSO profiles for AWS auth, but kept resource names (DynamoDB tables, Cognito pool, CloudWatch log group) and Auth0 M2M credentials in `.env`. Engineers still had to populate ~14 keys per environment by hand, including pulling the Auth0 client secret out of the LINQ tenant's M2M app UI.

Inspection of the Harmony-Auth Terraform (`~/Projects/temp-hack/Harmony-Auth/infra/main/main.tf`, `locals.tf`) shows that every resource the CLI needs is either:

1. **Already published to SSM Parameter Store** by Harmony-Auth or the SharedServices accounts service, or
2. **Deterministically named** from `${env}` via a documented pattern, or
3. **Discoverable via standard AWS APIs** (`cognito-idp:ListUserPools`, `logs:DescribeLogGroups`).

Once an engineer is authenticated to `linq-platform-services-{env}` via SSO, they have implicit read access to all of these. There is no reason for `ha-debug` to require any per-environment credential beyond `aws sso login --sso-session linq`.

## Decision

Replace `.env`-driven resource discovery with a three-source resolution model. Captured in five rules.

### Rule 1 — SSM Parameter Store is the source of truth for published resources

The CLI reads these parameters at runtime via `ssm:GetParameter` (with decryption when applicable):

| Resource | SSM path | Type | Publisher |
|---|---|---|---|
| `accountsTableName` | `/accounts/${env}/accountsTableName` | String | SharedServices accounts service |
| `appClientsTableName` | `/${env}/harmony/auth/app-clients` | String | Harmony-Auth (`infra/main/main.tf:1833`) |
| `superAdminMfaTableName` | `/${env}/harmony/auth/super-admin-mfa` | String | Harmony-Auth (`infra/main/main.tf:1888`) |
| `auth0ClientId` | `/idp/${env}/userManagement/clientId` | String | SharedServices identity-provider |
| `auth0ClientSecret` | `/idp/${env}/userManagement/clientSecret` | **SecureString** (KMS) | SharedServices identity-provider |

These are the same parameters Harmony-Auth's own Lambdas consume (`infra/main/locals.tf:79-82`). Reusing them keeps `ha-debug` aligned with whatever environment Harmony-Auth itself sees.

### Rule 2 — Deterministic name builders for unpublished resources

These are derived from `${env}` using patterns documented in Harmony-Auth source:

| Resource | Pattern | Source |
|---|---|---|
| Auth0 Management host | `https://linq-accounts-${env}.us.auth0.com` | `src/user/auth0-user.management.service.ts:62-63`, `src/connection/auth0-connection.management.service.ts:14-15` |
| Cognito pool name (district end-users) | `${env}-harmony-auth-district-user-pool` | `infra/main/main.tf:250` + `locals.tf:5` (`base_name = ${env}-harmony-auth`) |
| Cognito pool name (self-signup users) | `${env}-harmony-auth-selfSignup-user-pool` | `infra/main/main.tf:350` |
| CloudWatch log group prefix | `/aws/lambda/${env}-harmony-auth` | `infra/main/main.tf:997-1253` (every Lambda function name starts with `${local.base_name}` = `${env}-harmony-auth`) |

If any of these patterns shift in Harmony-Auth, the CLI breaks; that's the trade-off for not having SSM publishers for them. A follow-up could migrate any of these to SSM publishing in the Harmony-Auth Terraform.

### Rule 3 — AWS API discovery for Cognito pool IDs and log groups

Pool IDs and log group names are not in SSM. The CLI resolves them at runtime:

- **Cognito pool IDs** — `cognito-idp:ListUserPools` (paginate up to 60), match by name against the patterns from Rule 2. Both district and selfSignup pools are resolved; the user lookup tries each and returns whichever finds a match. This handles the reality that "User X cannot log in" could be a district admin or a self-signup user, and the operator does not always know which.
- **CloudWatch log groups** — `logs:DescribeLogGroups` with `logGroupNamePrefix=/aws/lambda/${env}-harmony-auth`. The resulting array is passed to `StartQueryCommand.logGroupNames` (CloudWatch Logs Insights accepts up to 50 log groups in one query). Rationale: any auth flow failure may surface in pre-auth, post-auth, the `auth_lambda` endpoint set, the SMS/email senders, or the migration workers — defaulting to a single log group misses signals. An engineer who wants to narrow can pass `--cw-log-groups <comma-list>`.

### Rule 4 — Per-resource env-var overrides for tests and break-glass

Following [Decision 0016](0016-aws-multi-account-skill-credentials.md) Rule 4, every resolved resource has an env-var override hook intended for local testing (e.g., LocalStack) or break-glass scenarios where SSM is unavailable. Overrides are documented in `.env.example` but commented out by default:

| Resource | Override env var |
|---|---|
| `accountsTableName` | `ACCOUNTS_TABLE_NAME` |
| `appClientsTableName` | `APP_CLIENTS_TABLE_NAME` |
| `superAdminMfaTableName` | `SUPER_ADMIN_MFA_TABLE_NAME` |
| `auth0Domain` | `AUTH0_DOMAIN` |
| `auth0ClientId` | `AUTH0_CLIENT_ID` |
| `auth0ClientSecret` | `AUTH0_CLIENT_SECRET` |
| `cognitoUserPoolIds` | `COGNITO_USER_POOL_IDS` (comma-separated) |
| `cwLogGroupNames` | `CW_LOG_GROUPS` (comma-separated) |

When set, env vars win over discovery. The `doctor` audit banner reports which resources came from `<ssm>` / `<derived>` / `<discovered>` / `<env-override>`.

### Rule 5 — Doctor reports each discovery step independently

Doctor's `checks` array gains rows for SSM lookups, KMS Decrypt, Cognito pool discovery, and CloudWatch log group discovery. Each check is independent: a missing SSM parameter does not abort downstream checks, so the operator sees every problem in one report. The `aws-sso` row remains the gate — discovery checks are skipped if AWS auth itself fails.

## IAM permissions required on the SSO role

Operators on `linq-platform-services-{dev,prod}` already have full read on the platform-services AWS account, which covers all of these. Documented here for future role-narrowing audits:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "HaDebugSsmRead",
      "Effect": "Allow",
      "Action": "ssm:GetParameter",
      "Resource": [
        "arn:aws:ssm:*:*:parameter/accounts/*/accountsTableName",
        "arn:aws:ssm:*:*:parameter/*/harmony/auth/app-clients",
        "arn:aws:ssm:*:*:parameter/*/harmony/auth/super-admin-mfa",
        "arn:aws:ssm:*:*:parameter/idp/*/userManagement/clientId",
        "arn:aws:ssm:*:*:parameter/idp/*/userManagement/clientSecret"
      ]
    },
    {
      "Sid": "HaDebugKmsDecrypt",
      "Effect": "Allow",
      "Action": "kms:Decrypt",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "ssm.us-east-1.amazonaws.com"
        }
      }
    },
    {
      "Sid": "HaDebugDiscovery",
      "Effect": "Allow",
      "Action": [
        "cognito-idp:ListUserPools",
        "logs:DescribeLogGroups"
      ],
      "Resource": "*"
    }
  ]
}
```

## Alternatives Considered

### Alternative A — Keep `.env`-driven keys; add `setup` UX

Wizard-style onboarding inside the CLI that asks questions and writes `.env`.

**Rejected.** Doesn't fix the underlying problem: every engineer ends up with their own copy of secrets that drifts from production. SSM is the only single source of truth.

### Alternative B — Publish every resource to SSM via Harmony-Auth Terraform

Add SSM publishers for Cognito pool IDs and CloudWatch log group names to the Harmony-Auth repo.

**Rejected for this PR; potential follow-up.** Requires a PR to a different repo plus a Terraform deploy. The runtime discovery via `ListUserPools` / `DescribeLogGroups` is only one extra AWS call each, well within the latency budget for a CLI that already does 5+ AWS calls per case-file assembly.

### Alternative C — Single Cognito pool

Use only `district_user_pool` and rely on the operator to specify `selfSignup_user_pool` manually if the user is a self-signup user.

**Rejected.** The operator usually does not know which pool the user belongs to — that is part of what they are trying to debug. Returning the first match across both pools is the simpler, more useful default.

### Alternative D — Single CloudWatch log group

Default to `post-auth-lambda` only.

**Rejected** based on operator feedback. Auth flow failures surface across pre-auth, post-auth, the per-endpoint `auth_lambda` set, and the API Gateway log group. Defaulting to one means the operator misses the signal as often as they find it. Multi-log-group is the default; `--cw-log-groups <comma-list>` narrows when noise becomes a problem.

## Consequences

- **`.env.example` collapses to ~5 lines** — region, optional profile overrides, optional `WIKI_CASES_DIR`, optional break-glass override hooks documented but commented out.
- **First-run UX**: an engineer who has run `aws sso login --sso-session linq` is fully set up. No Auth0 UI scavenger hunt. No table-name copy-paste. No keys in any local file.
- **Latency**: each subcommand now makes 5 SSM `GetParameter` calls + 1 KMS Decrypt + 1 `ListUserPools` + 1 `DescribeLogGroups` in addition to its existing AWS calls. Each is ~50–150 ms; total added latency is ~500–1000 ms per invocation. Acceptable for an interactive CLI.
- **Drift risk**: deterministic name patterns (Rule 2) bind `ha-debug` to Harmony-Auth's resource naming. If Harmony-Auth renames a Lambda or its base_name, `ha-debug` breaks. Mitigation: clear failure messages from `doctor` showing the expected pattern and the actual discovery result.
- **`ha-debug/.env`** can be deleted entirely on most engineer machines after this PR. The CLI still reads it if present (for break-glass overrides) but no keys are required.
- **Decision 0021's preflight remains** — the `doctor` subcommand and Step 0 in SKILL.md gain new rows for SSM / KMS / Cognito-discovery / log-group-discovery but the contract shape does not change.

## References

- [Decision 0016](0016-aws-multi-account-skill-credentials.md) — AWS multi-account skill credential convention.
- [Decision 0021](0021-ha-debug-credential-migration.md) — `ha-debug` credential migration + setup preflight (the foundation this builds on).
- [`~/Projects/temp-hack/Harmony-Auth/infra/main/main.tf`](https://github.com/LINQ-Platform-Services/Harmony-Auth) — source of truth for SSM parameter publishers and resource naming patterns.
- [`~/Projects/temp-hack/Harmony-Auth/infra/main/locals.tf`](https://github.com/LINQ-Platform-Services/Harmony-Auth) — `base_name` and `auth0_domain` derivation rules.
