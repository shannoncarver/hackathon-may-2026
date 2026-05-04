---
title: "AWS Lambda — Resource-Based Policies and Cross-Account Invoke"
url: "https://docs.aws.amazon.com/lambda/latest/dg/access-control-resource-based.html"
fetched_at: 2026-05-04
auth_required: false
license_note: "AWS public documentation — condensed for agent reference; cite source for verbatim text"
sources_also_consulted:
  - "https://docs.aws.amazon.com/lambda/latest/dg/permissions-function-cross-account.html"
---

# AWS Lambda — Resource-Based Policies and Cross-Account Invoke

## Overview

Lambda supports resource-based permissions policies for Lambda functions, versions, aliases, and layers. Resource-based policies:
- Grant access to other AWS accounts, organizations, or AWS services.
- Apply to a single function, version, alias, or layer version.
- Are an alternative to AssumeRole-based cross-account invocation.

## Resource-Based Policy Structure

Example policy statement granting Amazon S3 to invoke a function:

```json
{
  "Version": "2012-10-17",
  "Id": "default",
  "Statement": [
    {
      "Sid": "lambda-allow-s3-my-function",
      "Effect": "Allow",
      "Principal": { "Service": "s3.amazonaws.com" },
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:us-east-2:123456789012:function:my-function",
      "Condition": {
        "StringEquals": { "AWS:SourceAccount": "123456789012" },
        "ArnLike": { "AWS:SourceArn": "arn:aws:s3:::amzn-s3-demo-bucket" }
      }
    }
  ]
}
```

Key fields:
- `Principal`: The AWS account, IAM entity, or service being granted access.
- `Action`: `lambda:InvokeFunction` for invocation.
- `Resource`: The specific function ARN (may include version or alias).
- `Condition`: Optional — restrict by `AWS:SourceAccount` and/or `AWS:SourceArn` to prevent confused deputy attacks.

## Cross-Account Invoke via Resource-Based Policy

### Granting Account-Level Access

Use `aws lambda add-permission` CLI:

```bash
aws lambda add-permission \
  --function-name my-function:prod \
  --statement-id xaccount \
  --action lambda:InvokeFunction \
  --principal 111122223333 \
  --output text
```

Result policy statement: `Principal` becomes `arn:aws:iam::111122223333:root` — granting all IAM identities in that account invoke access (subject to their own IAM policies).

### Granting Specific User or Role Access

To limit access to a specific IAM user or role in another account, specify the full ARN as the principal:

```bash
--principal arn:aws:iam::123456789012:user/developer
```

### Invoking from Another Account

The other account then invokes using the function ARN with alias:

```bash
aws lambda invoke \
  --function-name arn:aws:lambda:us-east-2:123456789012:function:my-function:prod out
```

The alias (`prod`) controls which version the other account can invoke. The function owner can update the alias to point to a new version without the caller needing to change their invocation ARN.

## Viewing Resource-Based Policies

Console: Functions → Configuration → Permissions → Resource-based policy → View policy document.

CLI:
```bash
aws lambda get-policy \
  --function-name my-function \
  --output text
```

For a version or alias: append to function name, e.g., `my-function:PROD`.

For layers:
```bash
aws lambda get-layer-version-policy \
  --layer-name my-layer \
  --version-number 3 \
  --output text
```

## Removing Permissions

```bash
aws lambda remove-permission \
  --function-name example \
  --statement-id sns
```

## Supported Actions

Resource-based policies support most Lambda API actions, including:
- `lambda:InvokeFunction` (most common for cross-account)
- `lambda:InvokeFunctionUrl` (for function URLs)
- `lambda:GetFunction`, `lambda:ListAliases`, `lambda:PublishVersion`
- Most other function management actions

## Cross-Account Policy vs. AssumeRole Comparison

| Aspect | Resource-based policy | AssumeRole (identity-based) |
|--------|----------------------|---------------------------|
| Where policy lives | On the Lambda function | On the calling principal's role |
| Grants access to | A specific function, version, alias, or layer | Any resource the role has permission for |
| Temporary credentials needed | No — caller uses their own credentials | Yes — caller must first assume a role |
| Best for | Simple function-level sharing, AWS service integrations | Broad cross-account access across multiple resources |
| Condition support | `SourceAccount`, `SourceArn` | `sts:ExternalId`, `aws:PrincipalArn`, etc. |

> "To grant other accounts permission for multiple functions, or for actions that don't operate on a function, we recommend that you use IAM roles."

## SourceAccount and SourceArn Conditions

When granting an AWS service (like S3) permission to invoke a Lambda function, always include `AWS:SourceAccount` and/or `AWS:SourceArn` conditions. This prevents confused deputy attacks where the service might be manipulated into invoking your function on behalf of another account's resources.

- `AWS:SourceAccount`: restricts to a specific account's S3 bucket triggers.
- `AWS:SourceArn`: restricts to a specific resource ARN (e.g., specific S3 bucket).

## Organization-Level Access

To grant access to all accounts in an AWS Organization, use:
```json
"Condition": { "StringEquals": { "aws:PrincipalOrgID": "o-t194hfs8cz" } }
```

With `"Principal": "*"` — restricts to any identity within the specified organization.
