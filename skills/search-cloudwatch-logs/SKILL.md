---
name: search-cloudwatch-logs
description: Read-only CloudWatch Logs across LINQ AWS accounts. Use when the user asks "search cloudwatch logs", "grep the logs for X", "find errors in the last hour", "tail the lambda logs", "what does the log group for Y say", "run a Logs Insights query", "list log groups", "list streams", or wants raw log events as evidence for an incident. Six verbs — groups, streams, search, insights, tail, get — all read-only via boto3. Mirrors the credential pattern in verify-user-authorization (named profile linq-{product}-{env}, --i-understand-this-is-prod for prod, --aws-profile break-glass override, sts:GetCallerIdentity audit banner). Multi-product via --product; the agent infers product and environment from the user's prompt and asks if either is missing or unmatched against the operator's ~/.aws/config.
allowed-tools: Bash
argument-hint: verb (groups|streams|search|insights|tail|get), product, environment (dev|prod), and verb-specific flags
---

# search-cloudwatch-logs

Read-only CloudWatch Logs primitive for any LINQ AWS account. One script, six verbs:

| Verb | Boto3 call | When to reach for it |
|---|---|---|
| `groups` | `describe_log_groups` | Discover what log groups exist; filter by prefix |
| `streams` | `describe_log_streams` | List streams under a known group |
| `search` | `filter_log_events` | Pattern search (the 80% case) |
| `insights` | `start_query` + `get_query_results` | Structured queries — parse, stats, fields |
| `tail` | poll `get_log_events` | Live-follow a single stream (NDJSON output) |
| `get` | `get_log_events` | One-shot slice of a known stream |

The skill never mutates anything. The boto3 call list is an explicit allowlist; the script cannot put, delete, or tag.

## Install

Three paths, depending on where you want to use the skill.

**1. In this repo (Claude Code) — already installed.** Clone the repo and start Claude Code from the repo root. The skill auto-loads via the [.claude/skills/search-cloudwatch-logs](../../.claude/skills/search-cloudwatch-logs) symlink. No further steps.

**2. In another repo or globally (Claude Code).** Symlink this folder into the target location:

```bash
# Globally for all your Claude Code sessions:
ln -s "$(pwd)/skills/search-cloudwatch-logs" ~/.claude/skills/search-cloudwatch-logs

# Or into a specific project:
ln -s "$(pwd)/skills/search-cloudwatch-logs" /path/to/other-repo/.claude/skills/search-cloudwatch-logs
```

**3. In Claude Desktop (the app, not Claude Code).** Zip the skill folder and upload via Settings → Capabilities → Skills:

```bash
cd skills && zip -r search-cloudwatch-logs.zip search-cloudwatch-logs/
```

Then drag the resulting `.zip` into Claude Desktop's Skills settings.

> Windows users: enable git symlink support once with `git config --global core.symlinks true` before cloning.

## When to use

- "Search the ERP prod logs for `HarmonyAuth` 401s in the last hour."
- "Tail the deploy stream for the Forms web service in dev."
- "Run a Logs Insights query to count 5xx by Lambda function over the last 24h."
- "Why did request `abc-123` fail?" — pairs with `verify-user-authorization` for full incident triage.
- An incident agent needs raw log events as evidence.

## When NOT to use

- Anything that mutates log state. This skill is read-only by design.
- Production runs from CI without an explicit, named workflow that has been pre-approved. Interactive prod runs are supported but require `--i-understand-this-is-prod`.
- Bulk export of a log group's full history. CloudWatch Logs is not a data lake — use `logs:CreateExportTask` (not exposed by this skill) and S3 for that.

## Agent-inference rules

The script always takes explicit `--product` and `--environment` flags. The *agent* (Claude in the main thread) infers both from the user's prompt before invoking. Apply these rules consistently:

### Environment

- Explicit "prod" / "production" → `--environment prod` *and* `--i-understand-this-is-prod`. **Always confirm with the user before invoking prod.**
- Explicit "dev" / "staging" / "non-prod" → `--environment dev`.
- **Silent on environment → ask the user.** Do not default. The cost of a wrong-account run is higher than the cost of one extra question.

### Product

1. **Enumerate the operator's profiles first.** Run this one-liner before deciding on `--product`:

   ```bash
   awk '/^\[profile linq-/{gsub(/[\[\]]/,""); print $2}' ~/.aws/config | sort -u
   ```

   That returns the list of `linq-<product>-<env>` profiles the operator actually has configured.

2. **If the prompt names a product and a matching profile exists** (e.g. prompt says "ERP" and `linq-erp-dev` is in the list) → use it.

3. **If the prompt names a product but no matching profile exists** → tell the user what you do see and ask which one they meant. Do not guess.

4. **If the prompt is silent on product and `~/.aws/config` has `linq-*` profiles** → present the discovered product list and ask.

5. **If `~/.aws/config` has zero `linq-*` profiles** → ask the user what the product is, then point them at the "AWS profiles" section below to add the profile.

This grounds inference in the operator's real setup, not a hardcoded product list. It also self-documents: when the operator adds new products, the agent picks them up automatically.

## Inputs

### Common to every verb

| Argument | Required | Notes |
|---|---|---|
| verb | yes | One of `groups`, `streams`, `search`, `insights`, `tail`, `get`. |
| `--product` | yes | Slug like `erp`, `forms`, `compass`. Drives profile `linq-<product>-<env>`. |
| `--environment` | yes | `dev` or `prod`. |
| `--i-understand-this-is-prod` | iff `--environment=prod` | Required acknowledgment for any prod run. The script refuses prod without it. |
| `--aws-profile` | no | Override the derived profile (e.g. for break-glass / incident profiles). Pass empty string (`--aws-profile ''`) to use boto3's default credential chain. See "AWS profiles" below. |

### Verb-specific

**`groups`** — list log groups.

| Argument | Required | Notes |
|---|---|---|
| `--name-prefix` | no | Filter to log groups whose name starts with this prefix (e.g. `/aws/lambda/`). |
| `--limit` | no | Default 50. |

**`streams`** — list streams in a log group.

| Argument | Required | Notes |
|---|---|---|
| `--log-group` | yes | |
| `--name-prefix` | no | Filter streams by prefix. When supplied, results are not sorted by `LastEventTime`. |
| `--limit` | no | Default 50. |

**`search`** — pattern search across a log group.

| Argument | Required | Notes |
|---|---|---|
| `--log-group` | yes | |
| `--pattern` | no | CloudWatch filter-pattern syntax — *not regex*. Omit to return all events in window. |
| `--stream-prefix` | no | Restrict to streams matching this prefix. |
| `--since` | yes | Start of window. Accepts `1h`, `30m`, `15s`, `2d`, ISO 8601, or epoch seconds. |
| `--until` | no | End of window (default: now). Same formats as `--since`. |
| `--limit` | no | Default 1000. |
| `--format` | no | `json` (default) or `text` (human-readable, one event per line). |

**`insights`** — Logs Insights query.

| Argument | Required | Notes |
|---|---|---|
| `--log-group` | yes | Repeat the flag for multi-group queries. |
| `--query` | yes | Logs Insights query string. |
| `--since` | yes | Start of window. |
| `--until` | no | Default now. |
| `--limit` | no | Default 1000 (API max 10 000). |
| `--query-timeout` | no | Seconds to wait for completion before stopping the query. Default 60. |

**`tail`** — live-follow a stream (NDJSON output).

| Argument | Required | Notes |
|---|---|---|
| `--log-group` | yes | |
| `--stream` | yes | |
| `--duration` | no | Max seconds to follow. Default 300. Bounded so the script exits even unattended. |
| `--poll-interval` | no | Seconds between empty polls. Default 5. |

**`get`** — one-shot slice of a known stream.

| Argument | Required | Notes |
|---|---|---|
| `--log-group` | yes | |
| `--stream` | yes | |
| `--since` | yes | |
| `--until` | no | Default now. |
| `--limit` | no | Default 1000. |
| `--format` | no | `json` (default) or `text`. |

## Output envelope

Every verb except `tail` emits a single JSON object on stdout:

```json
{
  "result": {"status": "OK", "verb": "search", "reason": null},
  "data": { "...verb-specific shape..." }
}
```

On error, `status` is `"ERROR"`, `data` is `null`, and `reason` carries a human-readable message:

```json
{
  "result": {"status": "ERROR", "verb": "search", "reason": "AWS profile 'linq-erp-dev' not found in ~/.aws/config. ..."},
  "data": null
}
```

The script always exits 0. Diagnostic output goes to stderr.

### Verb-specific `data` shapes

- `groups` → `{"groups": [{name, arn, stored_bytes, retention_days, creation_time}, ...], "count": N}`
- `streams` → `{"streams": [{name, first_event_time, last_event_time, stored_bytes}, ...], "count": N, "log_group": "..."}`
- `search` → `{"events": [{timestamp, ingestion_time, stream, message, event_id}, ...], "count": N, "log_group", "pattern", "start_ms", "end_ms"}`
- `insights` → `{"query_id", "rows": [...], "count", "statistics": {records_matched, records_scanned, bytes_scanned}, "log_groups", "query", "start_ms", "end_ms"}`
- `get` → `{"events": [...], "count", "log_group", "stream", "start_ms", "end_ms"}`

### Tail output (NDJSON)

`tail` is the lone exception. It emits one JSON object per line, flushed:

```
{"timestamp": 1715091600000, "ingestion_time": 1715091600100, "stream": "2026/05/07/[$LATEST]abc", "message": "Hello"}
{"timestamp": 1715091601000, "ingestion_time": 1715091601100, "stream": "2026/05/07/[$LATEST]abc", "message": "World"}
```

This makes `tail` pipeable into `jq`. Errors during the tail loop are emitted as a single envelope-shaped JSON object (with `result.status == "ERROR"`) on its own line, so consumers can distinguish events from errors via `select(.message)` or `select(.result?)`.

## How to invoke

**Default dev (the 99% case):**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/search_cloudwatch_logs.py" search \
  --product erp \
  --environment dev \
  --log-group /aws/lambda/HarmonyAuthAuthorize \
  --pattern '"401"' \
  --since 1h
```

**Insights query across multiple groups:**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/search_cloudwatch_logs.py" insights \
  --product erp \
  --environment dev \
  --log-group /aws/lambda/HarmonyAuthAuthorize \
  --log-group /aws/lambda/HarmonyAuthIssueToken \
  --query 'fields @timestamp, @message | filter @message like /401/ | stats count() by bin(5m)' \
  --since 24h
```

**Tail a known stream for 60 seconds:**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/search_cloudwatch_logs.py" tail \
  --product forms \
  --environment dev \
  --log-group /aws/lambda/FormsSubmitHandler \
  --stream '2026/05/07/[$LATEST]abc123' \
  --duration 60
```

**Prod (requires explicit acknowledgment):**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/search_cloudwatch_logs.py" search \
  --product erp \
  --environment prod \
  --i-understand-this-is-prod \
  --log-group /aws/lambda/HarmonyAuthAuthorize \
  --pattern '"401"' \
  --since 30m
```

**Break-glass override profile:**

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/search_cloudwatch_logs.py" search \
  --product erp \
  --environment prod \
  --i-understand-this-is-prod \
  --aws-profile linq-erp-prod-incident-2026-05-07 \
  --log-group /aws/lambda/HarmonyAuthAuthorize \
  --since 15m
```

## Required environment

| Variable | Default | Notes |
|---|---|---|
| `AWS_REGION` | `us-east-1` | Override only if a product runs in a non-default region. |
| `LINQ_<PRODUCT>_AWS_PROFILE` | (unset) | Workflow-level override of the derived `linq-<product>-<env>` profile. The product slug is uppercased and dashes become underscores: `--product harmony-auth` → `LINQ_HARMONY_AUTH_AWS_PROFILE`. Wins over the derived default; loses to `--aws-profile`. |
| `LINQ_AWS_USE_AMBIENT_CHAIN` | (unset) | Set to `1` to skip named-profile resolution entirely; boto3 uses its default credential chain (Lambda role, GHA OIDC, instance profile). |
| AWS credentials | — | Resolved via named profile (default) or boto3's default credential chain (when profile is empty / ambient). See "AWS profiles" below. |

## AWS profiles

This skill follows the convention in [Decision 0016](../../docs/decisions/0016-aws-multi-account-skill-credentials.md) — every AWS-touching skill in this repo uses named profiles, derives its target account from `--environment` (and now also from `--product`), and supports a break-glass override.

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

# Add one block per product you need access to:
# [profile linq-forms-dev]
# [profile linq-compass-dev]
# ...
```

Alternative: run `aws configure sso` for an interactive wizard that creates the same entries. The wizard opens a browser, lets you pick the account and role from your entitled list, and writes the `[profile ...]` block automatically. **When prompted for an SSO session name, enter `linq`** — the skill derives profile names as `linq-{product}-{env}` and the login command references `--sso-session linq`, so the name must match.

### One-time login (per day)

```bash
aws sso login --sso-session linq
```

Opens a browser, authenticates once, writes a token to `~/.aws/sso/cache/`. **That single token covers every profile that references `sso-session linq`** — every product and environment. Tokens typically last 8 hours.

### How the skill picks a profile

Resolution order (first match wins):

1. **`--aws-profile <name>`** — explicit operator override (break-glass / incident).
2. **`LINQ_<PRODUCT>_AWS_PROFILE` env var** — workflow-level override (e.g. `LINQ_ERP_AWS_PROFILE`).
3. **`LINQ_AWS_USE_AMBIENT_CHAIN=1` env var** — skip named profiles, use boto3's default chain.
4. **Derived from `--product` + `--environment`** — `linq-<product>-<env>`. The default path.
5. **Headless fallback** — `--aws-profile ''` (empty string) → `boto3.Session()` with no profile, default chain (Lambda role, GHA OIDC, instance profile).

The script prints the resolved profile, account ID, role ARN, and the resource it will touch to stderr before any CloudWatch call (via `sts:GetCallerIdentity`). That line is the per-invocation audit log; check it whenever a result looks suspicious.

### Override — when and how

Use `--aws-profile <name>` when:

- Incident response with a time-boxed elevated role (e.g. `linq-erp-prod-incident-2026-05-07`).
- Debugging an IAM policy under a non-default role.
- A coworker handed you a temporary profile name to reproduce their bug.

Do NOT use `--aws-profile` to swap dev↔prod intentionally — that's `--environment`'s job. The override changes *which IAM identity makes the calls*, not *which dataset the calls hit*.

### Headless / agent / CI

For Lambda, GHA OIDC web-identity, EC2 instance profiles, or any context where named profiles aren't configured, pass `--aws-profile ''` (or set `LINQ_AWS_USE_AMBIENT_CHAIN=1`). The skill calls `boto3.Session()` with no profile and lets the default credential chain resolve credentials from the environment. The audit banner still prints — it'll show `profile=<ambient>` and the resolved account / ARN.

### Troubleshooting

| Symptom (in `reason`) | Fix |
|---|---|
| `Could not resolve AWS identity ... aws sso login --sso-session linq` | Run that command. Token expired or never logged in. |
| `AWS profile 'linq-<product>-<env>' not found in ~/.aws/config` | Add the `[profile linq-<product>-<env>]` block (see "One-time setup"). |
| `AccessDenied calling logs:...` | Your SSO profile lacks CloudWatch Logs read permissions in the target account. Contact whoever owns your AWS access; ask them to grant `logs:Filter*`, `logs:Get*`, `logs:Describe*`, and `logs:StartQuery` (read-only) on the SSO permission set you use. |
| `Resource not found` | Log group or stream name is wrong. Run the `groups` or `streams` verb to discover the right name. |
| `Insights query did not complete within 60s` | Re-run with `--query-timeout 180` or narrow `--since`. |
| `Refusing prod run without --i-understand-this-is-prod` | Add the flag. Confirms explicit prod intent. |
| Wrong account ID in stderr banner | Profile is pointing at the wrong account. Re-check `sso_account_id` in `~/.aws/config`. |

## Examples

### `search` — pattern hits

```json
{
  "result": {"status": "OK", "verb": "search", "reason": null},
  "data": {
    "events": [
      {
        "timestamp": 1715091600000,
        "ingestion_time": 1715091600100,
        "stream": "2026/05/07/[$LATEST]abc123",
        "message": "ERROR: HarmonyAuthAuthorize returned 401 for tenant=acme-isd",
        "event_id": "12345"
      }
    ],
    "count": 1,
    "log_group": "/aws/lambda/HarmonyAuthAuthorize",
    "pattern": "\"401\"",
    "start_ms": 1715088000000,
    "end_ms": null
  }
}
```

### `insights` — counted by bin

```json
{
  "result": {"status": "OK", "verb": "insights", "reason": null},
  "data": {
    "query_id": "abcd-1234",
    "rows": [
      {"@timestamp": "2026-05-07 14:00:00.000", "count(*)": "12"},
      {"@timestamp": "2026-05-07 14:05:00.000", "count(*)": "8"}
    ],
    "count": 2,
    "statistics": {"records_matched": 20, "records_scanned": 5832, "bytes_scanned": 1048576},
    "log_groups": ["/aws/lambda/HarmonyAuthAuthorize"],
    "query": "fields @timestamp, @message | filter @message like /401/ | stats count() by bin(5m)",
    "start_ms": 1715005200000,
    "end_ms": 1715091600000
  }
}
```

### Error — AccessDenied

```json
{
  "result": {
    "status": "ERROR",
    "verb": "search",
    "reason": "AccessDenied calling logs:FilterLogEvents. Your SSO profile 'linq-erp-dev' does not have CloudWatch Logs read permissions in account 111111111111. Ask whoever owns your AWS access to grant logs:Filter*, logs:Get*, logs:Describe*, and logs:StartQuery on this account (read-only)."
  },
  "data": null
}
```

## Notes for the agent

- **Never default `--environment`.** If the user is silent, ask. Wrong-account runs are expensive to undo.
- **Always announce the resolved env in your reply.** Even when the user said "dev" explicitly. The audit banner is your source of truth.
- **For prod runs, always confirm with the user before invoking** — the `--i-understand-this-is-prod` flag is a guardrail, not a free pass.
- **Pair with `verify-user-authorization`** for auth-incident triage: verify → grep CloudWatch for the request ID → root-cause.
- **Filter pattern syntax is not regex.** Use double-quoted literals for terms; reference [CloudWatch filter and pattern syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html) when the operator needs more than literal matches.
- **Logs Insights costs money per scanned byte.** The `bytes_scanned` field in the response is your sanity check; surface it back to the user when they ran a wide query.
