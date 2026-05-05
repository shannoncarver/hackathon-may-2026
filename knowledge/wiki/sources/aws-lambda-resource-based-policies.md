---
title: "AWS Lambda — Resource-Based Policies and Cross-Account Invoke"
kind: source
raw_path: "raw/sources/aws-lambda-resource-based-policies-2026-05-04.md"
url: "https://docs.aws.amazon.com/lambda/latest/dg/access-control-resource-based.html"
author: "Amazon Web Services"
fetched_at: 2026-05-04
tags: ["aws", "lambda", "iam", "cross-account", "resource-policy", "product:cross-cutting"]
entities:
  - "wiki/entities/lambda-resource-policy.md"
concepts: []
created: 2026-05-04
updated: 2026-05-04
---

## Why this source

Closes the AWS Lambda cross-account access gap identified in the Decision 0014 Phase A review. The Platform MCP Server may invoke Lambda functions across multiple AWS accounts. Resource-based policies are an alternative to AssumeRole-based invocation and are simpler for single-function cross-account grants.

## What it covers

Lambda resource-based permissions policies for cross-account function invocation. Covers: policy structure, `lambda:InvokeFunction` action, `Principal` field for cross-account grants (account-level and specific ARN), `aws:SourceAccount` and `aws:SourceArn` condition keys, `add-permission` CLI usage, alias-locked invocation, `get-policy` for inspection, organization-level access, and comparison with AssumeRole-based invocation.

## Key claims

- Lambda resource-based policies apply per function, version, alias, or layer version. They grant access to other AWS accounts, organizations, or AWS services. [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md]
- Cross-account account-level grant: `aws lambda add-permission --principal 111122223333` results in `Principal: {"AWS": "arn:aws:iam::111122223333:root"}` — all IAM identities in that account can invoke, subject to their own IAM policies. [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md]
- Specific IAM identity grant: use the full ARN as principal (e.g., `arn:aws:iam::123456789012:user/developer`). [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md]
- Alias-locked invocation: specify the alias in the `--function-name` parameter (e.g., `my-function:prod`). Callers must include the alias in their invocation ARN; the function owner can update which version the alias points to without the caller changing anything. [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md]
- The resource-based policy grants invocation access, but callers in the other account still need their own IAM policies permitting Lambda API calls. [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md]
- `aws:SourceAccount` and `aws:SourceArn` conditions prevent confused deputy attacks when granting AWS services (e.g., S3, SNS) permission to invoke Lambda. [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md]
- Organization-level access: `"Principal": "*"` with `"Condition": {"StringEquals": {"aws:PrincipalOrgID": "o-xxxxxxxx"}}` grants all accounts in the org. [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md]
- AWS recommendation: for access to multiple functions or non-function actions, use IAM roles (AssumeRole) rather than resource-based policies. [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md]
- CLI inspection: `aws lambda get-policy --function-name my-function` returns the current resource-based policy JSON. [raw/sources/aws-lambda-resource-based-policies-2026-05-04.md]

## Entities introduced

- [wiki/entities/lambda-resource-policy.md] — new entity: Lambda resource-based policy structure, cross-account grant patterns, and comparison with AssumeRole-based invocation.

## Open questions for LINQ

1. **Resource policy vs. AssumeRole for Platform MCP Server.** The Platform MCP Server must invoke Lambda functions across 4 product accounts. AWS recommends AssumeRole for broad multi-resource access. But resource-based policies are simpler for point-to-point function grants. Which pattern does Decision 0014 prefer?
2. **Alias strategy.** Using aliases (`prod`, `staging`) in resource-based policies decouples version management from access control. Does the Platform MCP Server need alias-based routing, or does it invoke Lambda functions by name directly?
3. **Organization-level access.** If all 4 LINQ product accounts are in the same AWS Organization, an org-level resource policy might be simpler than per-account `add-permission` calls. Is LINQ using AWS Organizations?
4. **Function URL invocation.** The source mentions `lambda:InvokeFunctionUrl` as a supported action. If product APIs are exposed via Lambda Function URLs rather than API Gateway, this is the relevant permission. Is this pattern in use at LINQ?
