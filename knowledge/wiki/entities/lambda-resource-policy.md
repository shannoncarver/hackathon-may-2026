---
title: "AWS Lambda Resource-Based Policy"
kind: entity
tags: ["aws", "lambda", "iam", "cross-account", "resource-policy", "product:cross-cutting"]
aliases: ["Lambda resource policy", "lambda:InvokeFunction cross-account", "add-permission cross-account"]
sources:
  - "wiki/sources/aws-lambda-resource-based-policies.md"
related:
  - "wiki/entities/sts-assume-role-external-id.md"
created: 2026-05-04
updated: 2026-05-04
---

# AWS Lambda Resource-Based Policy

An AWS Lambda resource-based policy is a permissions policy attached directly to a Lambda function (or version, alias, or layer) that grants access to specific AWS accounts, organizations, or services — without requiring the caller to assume an IAM role first. It is an alternative to AssumeRole-based cross-account invocation.

Source: [wiki/sources/aws-lambda-resource-based-policies.md]

---

## Policy Structure

A Lambda resource-based policy statement:

```json
{
  "Sid": "xaccount",
  "Effect": "Allow",
  "Principal": { "AWS": "arn:aws:iam::111122223333:root" },
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
  "Condition": { ... }
}
```

| Field | Description |
|-------|-------------|
| `Principal` | Who is being granted access |
| `Action` | Lambda API action(s) granted |
| `Resource` | Specific function ARN (may include version or alias) |
| `Condition` | Optional restrictions (SourceAccount, SourceArn, PrincipalOrgID) |

---

## Cross-Account Grant Patterns

### Account-Level Grant

```bash
aws lambda add-permission \
  --function-name my-function:prod \
  --statement-id xaccount \
  --action lambda:InvokeFunction \
  --principal 111122223333
```

Result: all IAM identities in account `111122223333` can invoke, subject to their own IAM policies.

### Specific IAM Identity Grant

Provide the full ARN as principal:

```bash
--principal arn:aws:iam::123456789012:role/MyRole
```

### Organization-Level Grant

```json
{
  "Principal": "*",
  "Condition": {
    "StringEquals": { "aws:PrincipalOrgID": "o-xxxxxxxx" }
  }
}
```

Grants all accounts in the AWS Organization.

---

## Alias-Locked Invocation

Specifying an alias in `--function-name` (e.g., `my-function:prod`) locks the permission to that alias. Callers must include the alias in their invocation ARN. The function owner can update which version the alias points to without the caller changing their code.

```bash
aws lambda invoke \
  --function-name arn:aws:lambda:us-east-2:123456789012:function:my-function:prod out
```

---

## Confused Deputy Prevention (Service Principal)

When granting an AWS service (S3, SNS, etc.) permission to invoke Lambda, always include `SourceAccount` and/or `SourceArn` conditions:

```json
"Condition": {
  "StringEquals": { "AWS:SourceAccount": "123456789012" },
  "ArnLike": { "AWS:SourceArn": "arn:aws:s3:::my-bucket" }
}
```

Prevents the service from being manipulated into invoking your Lambda on behalf of another account's resources.

---

## Policy Inspection

```bash
aws lambda get-policy --function-name my-function --output text
```

For a version or alias: `--function-name my-function:PROD`.

---

## Supported Actions

Most Lambda API actions support resource-based policies, including:
- `lambda:InvokeFunction` (invocation)
- `lambda:InvokeFunctionUrl` (Function URL invocation)
- `lambda:GetFunction`, `lambda:PublishVersion`, `lambda:ListAliases`

---

## Resource Policy vs. AssumeRole Comparison

| Aspect | Resource-based policy | AssumeRole (identity-based) |
|--------|----------------------|---------------------------|
| Policy location | On the Lambda function | On the calling principal's role |
| Scope | Single function, version, alias, or layer | Any resources the role has permission for |
| Caller needs temp creds | No — uses their own identity | Yes — must first call `sts:AssumeRole` |
| Best for | Simple function sharing, AWS service integration | Broad multi-resource cross-account access |
| External ID support | No (use `SourceAccount`/`SourceArn` for services) | Yes (`sts:ExternalId` condition) |

AWS guidance: "To grant other accounts permission for multiple functions, or for actions that don't operate on a function, we recommend that you use IAM roles."

---

## Relationship to Platform MCP Server (Decision 0015)

The Platform MCP Server design (Decision 0015) involves cross-account Lambda invocation for product APIs.

- If the Platform MCP Server needs to call one or a few specific Lambda functions per product account, resource-based policies are the simpler path — no role assumption needed.
- If the Platform MCP Server needs broad multi-resource access in each product account (e.g., DynamoDB, SQS, S3 alongside Lambda), AssumeRole via [wiki/entities/sts-assume-role-external-id.md] is the right pattern.
- Alias-locking enables safe version promotion in product accounts without changing the Platform MCP Server's invocation targets.
