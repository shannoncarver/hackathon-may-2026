# Implementation 10 — Observability and Runbooks

**Decision:** [`0015-centralized-platform-mcp`](../../../decisions/0015-centralized-platform-mcp.md) — Phase B observability backbone.
**Owner:** 11-eng-cloudops (CloudOps Engineer).
**Status:** Draft for Phase B implementation.
**Effort estimate:** `4 d [ASSUMED]`.

## 1. Overview

This artifact specifies the observability stack and operational runbooks for the LINQ Platform MCP Server. It covers CloudWatch metrics emitted by the MCP server Lambda and the IdentityBroker, the **single templated dashboard** that uses `Handler` as a CloudWatch dimension (per the cost memo's sub-linear-cost precondition — per-handler dashboards are forbidden), CloudWatch alarms covering availability, latency, error rate, AssumeRole call rate, audit-log delivery lag, MCP-server Lambda concurrency utilization, `listChanged` storm rate, and Auth0 M2M token issuance. It defines the cross-account log-shipping pipeline (CloudWatch Logs subscription filter → Kinesis Data Firehose → S3 in the centralized logging account, S3 Object Lock enabled with 1-year retention V1 and a documented upgrade path to 7-year before any compliance scope). It captures three operational runbooks in full — `mcp-server-unavailable.md` (degradation playbook), `tenant-scope-rejection.md` (false-positive triage), and `on-call-boundary.md` (failure-stage routing matrix from `01-architecture.md`). Together these close [Phase-1 POC AC10](../04-phase-1-poc.md) and the observability gates required for [R7](../03-risks-register.md#r7--mcp-server-availability-is-the-entire-systems-availability), [R11](../03-risks-register.md#r11--listchanged-storms-during-multi-team-handler-deploys), [R15](../03-risks-register.md#r15--cold-start-latency-violating-claude-code-timeouts), [R18](../03-risks-register.md#r18--cross-account-log-shipping-fails-silently), and [R23](../03-risks-register.md#r23--auth0-outage).

## 2. Concrete artifacts

### 2.1 CloudWatch metric specs

All custom metrics publish to the `LINQ/PlatformMCP` namespace from the MCP-server Lambda and the IdentityBroker Lambda using the [embedded metric format (EMF)](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html), so a single structured log line emits both the metric and the audit context. EMF lets the Lambda code emit one JSON record that CloudWatch parses into both a metric data point and a Logs entry — no separate `PutMetricData` call, no PutMetricData throttling risk.

| Metric | Unit | Dimensions | Namespace | Source | Purpose |
|---|---|---|---|---|---|
| `RequestCount` | `Count` | `Stage`, `Handler`, `AgentClientId` | `LINQ/PlatformMCP` | MCP-server Lambda | Top-line request volume; `Stage` ∈ `{auth, registry, identity-broker, sts, dispatch, total}` |
| `LatencyMs` | `Milliseconds` | `Stage`, `Handler` | `LINQ/PlatformMCP` | MCP-server Lambda | Per-stage P50/P95/P99 latency (drives R15 cold-start gate) |
| `ErrorCount` | `Count` | `Class`, `Handler` | `LINQ/PlatformMCP` | MCP-server Lambda | `Class` ∈ `{AUTH, REGISTRY, UPSTREAM_TIMEOUT, UPSTREAM_ERROR, INTERNAL, TENANT_SCOPE_VIOLATION}` |
| `AssumeRoleCallCount` | `Count` | `ProductAccount`, `CacheResult` | `LINQ/PlatformMCP` | MCP-server Lambda | `CacheResult` ∈ `{hit, miss}`; tracks STS rate vs. R16 quota |
| `AssumeRoleThrottle` | `Count` | `ProductAccount` | `LINQ/PlatformMCP` | MCP-server Lambda | Counts `ThrottlingException` from STS — R16 leading indicator |
| `AuditLogDeliveryLagSeconds` | `Seconds` | `LogGroup` | `LINQ/PlatformMCP` | Reconciliation job (Lambda + EventBridge, 5 min) | Time delta between MCP-server emit and S3 object-creation timestamp; alarms at 300 s |
| `AuditReconciliationDelta` | `Count` | `LogGroup` | `LINQ/PlatformMCP` | Daily reconciliation Lambda | `\|MCP RequestCount − S3 row count\|` over the prior 24 h window — R18 silent-failure detector |
| `Auth0M2MTokenIssued` | `Count` | `ServiceIdentity`, `Result` | `LINQ/PlatformMCP` | MCP-server Lambda | `Result` ∈ `{ok, fail-network, fail-auth0-5xx, fail-cached-fallback}`; sustained zero `ok` for ≥ 30 min triggers Auth0-outage alarm (R23) |
| `IdentityBrokerExchangeCount` | `Count` | `Result` | `LINQ/PlatformMCP` | IdentityBroker Lambda | `Result` ∈ `{ok, fail-kms, fail-claim-validation, fail-rate-limit}` |
| `IdentityBrokerKMSSignLatencyMs` | `Milliseconds` | (none) | `LINQ/PlatformMCP` | IdentityBroker Lambda | KMS `Sign` is the path bottleneck — separate budget alarm |
| `ToolsListChangedNotifications` | `Count` | `Trigger` | `LINQ/PlatformMCP` | MCP-server Lambda | `Trigger` ∈ `{registry-write, manual, scheduled}`; spike detector for R11 storm |
| `ColdStartCount` | `Count` | `FunctionName` | `LINQ/PlatformMCP` | MCP-server / IdentityBroker Lambdas | Init-phase increments; gates the R15 provisioned-concurrency decision |
| `RegistryCacheHitRatio` | `Percent` | `CacheTier` | `LINQ/PlatformMCP` | MCP-server Lambda | `CacheTier` ∈ `{in-process, elasticache}`; sustained < 90% is a cost / latency warning |

AWS-managed metrics consumed without re-publishing: `AWS/Lambda` `ConcurrentExecutions`, `Throttles`, `Errors`, `Duration`; `AWS/ApiGateway` `4XXError`, `5XXError`, `Count`, `Latency`; `AWS/DynamoDB` `ThrottledRequests`, `UserErrors`; `AWS/Firehose` `DeliveryToS3.DataFreshness`, `IncomingBytes`. See [AWS Lambda metrics docs](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics.html), [API Gateway metrics docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-metrics-and-dimensions.html), [DynamoDB CloudWatch metrics](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html), and [Kinesis Firehose metrics](https://docs.aws.amazon.com/firehose/latest/dev/monitoring-with-cloudwatch-metrics.html).

### 2.2 Templated dashboard JSON — `Handler` as a dimension

One dashboard, named `linq-platform-mcp-${Environment}`. Operators **filter** by handler via the dashboard's per-widget `Variables` block — they do not get a separate dashboard per handler. This is what keeps observability cost sub-linear in handler count (cost memo precondition #3); per-handler dashboards are forbidden by platform contract.

```json
{
  "DashboardName": "linq-platform-mcp-${Environment}",
  "DashboardBody": {
    "variables": [
      {
        "type": "property",
        "property": "Handler",
        "inputType": "select",
        "id": "handler",
        "label": "Handler",
        "visible": true,
        "search": "{LINQ/PlatformMCP,Stage,Handler} MetricName=\"LatencyMs\"",
        "populateFrom": "Handler",
        "defaultValue": "__ALL__"
      },
      {
        "type": "property",
        "property": "Stage",
        "inputType": "select",
        "id": "stage",
        "label": "Stage",
        "defaultValue": "total",
        "values": [
          {"label": "Total",            "value": "total"},
          {"label": "Auth",             "value": "auth"},
          {"label": "Registry",         "value": "registry"},
          {"label": "Identity Broker",  "value": "identity-broker"},
          {"label": "STS",              "value": "sts"},
          {"label": "Dispatch",         "value": "dispatch"}
        ]
      }
    ],
    "widgets": [
      {
        "type": "metric",
        "x": 0, "y": 0, "width": 12, "height": 6,
        "properties": {
          "title": "Request rate by stage (templated by handler)",
          "view": "timeSeries",
          "stat": "Sum",
          "period": 60,
          "region": "${AWS::Region}",
          "metrics": [
            ["LINQ/PlatformMCP", "RequestCount", "Stage", "${stage}", "Handler", "${handler}"]
          ]
        }
      },
      {
        "type": "metric",
        "x": 12, "y": 0, "width": 12, "height": 6,
        "properties": {
          "title": "Latency P50 / P95 / P99 (templated by handler and stage)",
          "view": "timeSeries",
          "period": 60,
          "region": "${AWS::Region}",
          "metrics": [
            ["LINQ/PlatformMCP", "LatencyMs", "Stage", "${stage}", "Handler", "${handler}", {"stat": "p50", "label": "P50"}],
            ["...",                                                                          {"stat": "p95", "label": "P95"}],
            ["...",                                                                          {"stat": "p99", "label": "P99"}]
          ],
          "annotations": {
            "horizontal": [
              {"label": "v1 P95 SLO 1500 ms", "value": 1500},
              {"label": "v1 P99 SLO 3000 ms", "value": 3000}
            ]
          }
        }
      },
      {
        "type": "metric",
        "x": 0, "y": 6, "width": 12, "height": 6,
        "properties": {
          "title": "Error rate by class (templated by handler)",
          "view": "timeSeries",
          "stat": "Sum",
          "period": 60,
          "region": "${AWS::Region}",
          "metrics": [
            ["LINQ/PlatformMCP", "ErrorCount", "Class", "AUTH",                     "Handler", "${handler}"],
            ["...",                            "Class", "REGISTRY",                 "Handler", "${handler}"],
            ["...",                            "Class", "UPSTREAM_TIMEOUT",         "Handler", "${handler}"],
            ["...",                            "Class", "UPSTREAM_ERROR",           "Handler", "${handler}"],
            ["...",                            "Class", "INTERNAL",                 "Handler", "${handler}"],
            ["...",                            "Class", "TENANT_SCOPE_VIOLATION",   "Handler", "${handler}"]
          ]
        }
      },
      {
        "type": "metric",
        "x": 12, "y": 6, "width": 12, "height": 6,
        "properties": {
          "title": "AssumeRole call rate and STS throttle",
          "view": "timeSeries",
          "stat": "Sum",
          "period": 60,
          "region": "${AWS::Region}",
          "metrics": [
            ["LINQ/PlatformMCP", "AssumeRoleCallCount", "ProductAccount", "${ProductAccountId}", "CacheResult", "miss"],
            ["...",              "AssumeRoleCallCount", "ProductAccount", "${ProductAccountId}", "CacheResult", "hit"],
            ["...",              "AssumeRoleThrottle",  "ProductAccount", "${ProductAccountId}"]
          ]
        }
      },
      {
        "type": "metric",
        "x": 0, "y": 12, "width": 8, "height": 6,
        "properties": {
          "title": "Audit-log delivery lag (R18)",
          "view": "timeSeries",
          "stat": "Maximum",
          "period": 60,
          "region": "${AWS::Region}",
          "metrics": [
            ["LINQ/PlatformMCP", "AuditLogDeliveryLagSeconds", "LogGroup", "/linq/platform-mcp/audit"],
            ["AWS/Firehose",     "DeliveryToS3.DataFreshness", "DeliveryStreamName", "linq-platform-mcp-audit"]
          ],
          "annotations": {
            "horizontal": [{"label": "v1 SLO 5 min", "value": 300}]
          }
        }
      },
      {
        "type": "metric",
        "x": 8, "y": 12, "width": 8, "height": 6,
        "properties": {
          "title": "MCP-server Lambda concurrency utilization (R7)",
          "view": "timeSeries",
          "stat": "Maximum",
          "period": 60,
          "region": "${AWS::Region}",
          "metrics": [
            ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", "linq-platform-mcp-server"]
          ],
          "annotations": {
            "horizontal": [{"label": "Reserved 50 — alarm at 80%", "value": 40}]
          }
        }
      },
      {
        "type": "metric",
        "x": 16, "y": 12, "width": 8, "height": 6,
        "properties": {
          "title": "Auth0 M2M token issuance (R23)",
          "view": "timeSeries",
          "stat": "Sum",
          "period": 300,
          "region": "${AWS::Region}",
          "metrics": [
            ["LINQ/PlatformMCP", "Auth0M2MTokenIssued", "Result", "ok"],
            ["...",              "Auth0M2MTokenIssued", "Result", "fail-network"],
            ["...",              "Auth0M2MTokenIssued", "Result", "fail-auth0-5xx"],
            ["...",              "Auth0M2MTokenIssued", "Result", "fail-cached-fallback"]
          ]
        }
      },
      {
        "type": "metric",
        "x": 0, "y": 18, "width": 12, "height": 6,
        "properties": {
          "title": "tools/list_changed rate (R11 storm detector)",
          "view": "timeSeries",
          "stat": "Sum",
          "period": 60,
          "region": "${AWS::Region}",
          "metrics": [
            ["LINQ/PlatformMCP", "ToolsListChangedNotifications", "Trigger", "registry-write"]
          ],
          "annotations": {
            "horizontal": [{"label": "Coalesce window 60 s — alarm > 6/min", "value": 6}]
          }
        }
      },
      {
        "type": "metric",
        "x": 12, "y": 18, "width": 12, "height": 6,
        "properties": {
          "title": "Cold-start count (R15 provisioned-concurrency gate)",
          "view": "timeSeries",
          "stat": "Sum",
          "period": 300,
          "region": "${AWS::Region}",
          "metrics": [
            ["LINQ/PlatformMCP", "ColdStartCount", "FunctionName", "linq-platform-mcp-server"],
            ["...",              "ColdStartCount", "FunctionName", "linq-identity-broker"]
          ]
        }
      }
    ]
  }
}
```

The `variables` block is the AWS-supported [dashboard variables feature](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_dashboards_variables.html) — operators select a handler from a populated dropdown (search-source `{LINQ/PlatformMCP,Stage,Handler}`) and every widget retargets. One dashboard scales to all V1 and Phase-B handlers.

### 2.3 CloudWatch alarm specs

All alarms publish to the `linq-platform-mcp-alarms` SNS topic, which fans out to PagerDuty (Platform on-call) and a Slack `#platform-mcp-alerts` channel. Threshold values come from the [SLO recommendation table in `cost-reliability.md`](../role-passes/cost-reliability.md#slo-recommendation-table).

| Alarm | Metric | Threshold | Eval period | Datapoints to alarm | Action | Risk |
|---|---|---|---|---|---|---|
| `mcp-availability-breach` | `AWS/ApiGateway 5XXError / Count` (math expression `e1 = m1 / m2 * 100`) | `> 1.0` (%) | `60 s` | `5 of 5` | Page Platform | R7 |
| `mcp-p95-latency-breach` | `LINQ/PlatformMCP LatencyMs Stage=total` p95 | `> 1500 ms` | `60 s` | `5 of 5` | Page Platform | R7, R15 |
| `mcp-cold-start-7d-trigger` | `LINQ/PlatformMCP LatencyMs Stage=total` p95 (math expression — daily max over 7 days) | `> 1500 ms each day for 7 consecutive days` | `1 day` | `7 of 7` | Notify (no page) — opens provisioned-concurrency RFC | R15 |
| `mcp-error-rate-breach` | `LINQ/PlatformMCP ErrorCount` Sum / `RequestCount` Sum | `> 1.0` (%) | `60 s` | `5 of 5` | Page Platform | R7 |
| `mcp-tenant-scope-rejection-spike` | `LINQ/PlatformMCP ErrorCount Class=TENANT_SCOPE_VIOLATION` | `> 5/min` | `60 s` | `5 of 5` | Notify Platform; auto-link runbook | R1 (signal), false-positive triage |
| `mcp-assume-role-throttle` | `LINQ/PlatformMCP AssumeRoleThrottle` | `> 0` | `60 s` | `1 of 1` | Page Platform | R16 |
| `mcp-audit-delivery-lag` | `LINQ/PlatformMCP AuditLogDeliveryLagSeconds` Maximum | `> 300 s` | `300 s` | `2 of 2` | Page Platform | R18 |
| `mcp-audit-reconciliation-delta` | `LINQ/PlatformMCP AuditReconciliationDelta` | `> 0` (any drop) | `1 day` | `1 of 1` | Page Platform | R18 |
| `mcp-firehose-data-freshness` | `AWS/Firehose DeliveryToS3.DataFreshness` Maximum | `> 300 s` | `300 s` | `2 of 2` | Page Platform | R18 |
| `mcp-lambda-concurrency-80pct` | `AWS/Lambda ConcurrentExecutions FunctionName=linq-platform-mcp-server` | `> 40` (80% of reserved 50) | `60 s` | `3 of 3` | Page Platform; opens scale-up RFC | R7, R8 |
| `mcp-listchanged-storm` | `LINQ/PlatformMCP ToolsListChangedNotifications Trigger=registry-write` | `> 6/min` | `60 s` | `5 of 5` | Notify Platform | R11 |
| `mcp-auth0-token-issuance-zero` | `LINQ/PlatformMCP Auth0M2MTokenIssued Result=ok` | `< 1` | `300 s` | `6 of 6` (30 min sustained) | Page Platform; cross-link Auth0 status | R23 |
| `mcp-auth0-cached-fallback-active` | `LINQ/PlatformMCP Auth0M2MTokenIssued Result=fail-cached-fallback` | `> 0` | `300 s` | `2 of 2` | Notify Platform — operating cached | R23 |
| `mcp-error-budget-burn-fast` | Composite — 50% of monthly budget consumed within 25% of window | `breach` | `1 h` | `1 of 1` | Page Platform; freeze deploys | R7 |

`mcp-audit-delivery-lag` and `mcp-audit-reconciliation-delta` are layered intentionally — Firehose `DeliveryToS3.DataFreshness` flags pipeline-wire health; the reconciliation alarm flags **silent** drift where the pipeline is healthy but rows are missing (R18's exact failure mode).

### 2.4 Cross-account Firehose CFN snippet — subscription filter to S3 with Object Lock

The audit log group lives in Platform Services. A CloudWatch Logs subscription filter forwards every record to Kinesis Data Firehose; Firehose lands records into S3 in the centralized logging account (CC-5 Q4 — assumed exists). The S3 bucket has Object Lock enabled in `COMPLIANCE` mode with a default retention period of `365 days` (1-year V1). The upgrade path to `2555 days` (7-year) is a single parameter flip plus a documented [`s3:PutObjectRetention` per-object override](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html) at write time before any compliance scope (HIPAA, FERPA, SOC 2 Type II) is taken.

```yaml
# infrastructure/06-audit.yaml — excerpt
AWSTemplateFormatVersion: "2010-09-09"
Description: Cross-account audit-log shipping (Decision 0015 — R18).

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, stage, prod]
  PlatformAccountId:
    Type: String
    AllowedPattern: "^[0-9]{12}$"
  LoggingAccountId:
    Type: String
    AllowedPattern: "^[0-9]{12}$"
    Description: Centralized logging-OU account (Q4 [ASSUMED]).
  AuditRetentionDays:
    Type: Number
    Default: 365
    AllowedValues: [365, 2555]
    Description: |
      V1 ships at 365 (1 year). Flip to 2555 (7 year) before any compliance scope.
      Increasing this value re-applies to new objects only; existing objects must be
      relocked via s3:PutObjectRetention in a one-shot Lambda.

Resources:

  # 1) Audit log group in Platform Services account.
  AuditLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub /linq/platform-mcp/audit-${Environment}
      RetentionInDays: 30   # CloudWatch-side retention is a hot tier; durable copy lives in S3.
      KmsKeyId: !GetAtt AuditLogsKmsKey.Arn

  AuditLogsKmsKey:
    Type: AWS::KMS::Key
    Properties:
      Description: KMS key for /linq/platform-mcp/audit log group.
      EnableKeyRotation: true
      KeyPolicy:
        Version: "2012-10-17"
        Statement:
          - Sid: EnableRootPermissions
            Effect: Allow
            Principal: { AWS: !Sub "arn:aws:iam::${PlatformAccountId}:root" }
            Action: "kms:*"
            Resource: "*"
          - Sid: AllowCloudWatchLogs
            Effect: Allow
            Principal: { Service: !Sub "logs.${AWS::Region}.amazonaws.com" }
            Action: ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:Describe*"]
            Resource: "*"
            Condition:
              ArnLike:
                "kms:EncryptionContext:aws:logs:arn":
                  !Sub "arn:aws:logs:${AWS::Region}:${PlatformAccountId}:*"

  # 2) IAM role that Logs assumes to publish to Firehose.
  LogsToFirehoseRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal: { Service: !Sub "logs.${AWS::Region}.amazonaws.com" }
            Action: "sts:AssumeRole"
      Policies:
        - PolicyName: AllowFirehosePut
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action: ["firehose:PutRecord", "firehose:PutRecordBatch"]
                Resource: !GetAtt AuditDeliveryStream.Arn

  # 3) Firehose delivery stream — Platform Services account.
  AuditDeliveryStream:
    Type: AWS::KinesisFirehose::DeliveryStream
    Properties:
      DeliveryStreamName: !Sub linq-platform-mcp-audit-${Environment}
      DeliveryStreamType: DirectPut
      ExtendedS3DestinationConfiguration:
        BucketARN: !Sub arn:aws:s3:::linq-audit-${LoggingAccountId}-${Environment}
        RoleARN: !GetAtt FirehoseDeliveryRole.Arn
        Prefix: !Sub "platform-mcp/${Environment}/!{timestamp:yyyy/MM/dd/HH}/"
        ErrorOutputPrefix: !Sub "platform-mcp/${Environment}/errors/!{timestamp:yyyy/MM/dd}/!{firehose:error-output-type}/"
        BufferingHints: { IntervalInSeconds: 60, SizeInMBs: 5 }   # 60 s drives the 5-min audit-lag SLO with margin.
        CompressionFormat: GZIP
        CloudWatchLoggingOptions:
          Enabled: true
          LogGroupName: !Sub /aws/kinesisfirehose/linq-platform-mcp-audit-${Environment}
          LogStreamName: S3Delivery
        EncryptionConfiguration:
          KMSEncryptionConfig:
            AWSKMSKeyARN: !GetAtt AuditLogsKmsKey.Arn

  FirehoseDeliveryRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal: { Service: firehose.amazonaws.com }
            Action: "sts:AssumeRole"
            Condition:
              StringEquals: { "sts:ExternalId": !Ref PlatformAccountId }
      Policies:
        - PolicyName: WriteToLoggingAccountBucket
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - "s3:AbortMultipartUpload"
                  - "s3:GetBucketLocation"
                  - "s3:GetObject"
                  - "s3:ListBucket"
                  - "s3:ListBucketMultipartUploads"
                  - "s3:PutObject"
                Resource:
                  - !Sub "arn:aws:s3:::linq-audit-${LoggingAccountId}-${Environment}"
                  - !Sub "arn:aws:s3:::linq-audit-${LoggingAccountId}-${Environment}/*"
              - Effect: Allow
                Action: ["kms:GenerateDataKey", "kms:Decrypt"]
                Resource: !GetAtt AuditLogsKmsKey.Arn

  # 4) Subscription filter — every audit log record forwards to Firehose.
  AuditSubscriptionFilter:
    Type: AWS::Logs::SubscriptionFilter
    DependsOn: AuditDeliveryStream
    Properties:
      LogGroupName: !Ref AuditLogGroup
      FilterPattern: ""   # forward everything; sampling is a future cost lever, not V1.
      DestinationArn: !GetAtt AuditDeliveryStream.Arn
      RoleArn: !GetAtt LogsToFirehoseRole.Arn

Outputs:
  AuditLogGroupName:
    Value: !Ref AuditLogGroup
    Export: { Name: !Sub "${AWS::StackName}-AuditLogGroup" }
  AuditDeliveryStreamArn:
    Value: !GetAtt AuditDeliveryStream.Arn
    Export: { Name: !Sub "${AWS::StackName}-AuditDeliveryStreamArn" }
```

The S3 bucket itself lives in the centralized logging account; deploying it is the [companion stack `06-audit-bucket.yaml`] in the logging account. Excerpt:

```yaml
# infrastructure/logging-account/06-audit-bucket.yaml — excerpt (deployed to logging account)
Parameters:
  PlatformAccountId:
    Type: String
    AllowedPattern: "^[0-9]{12}$"
  AuditRetentionDays:
    Type: Number
    Default: 365
    AllowedValues: [365, 2555]

Resources:
  AuditBucket:
    Type: AWS::S3::Bucket
    DeletionPolicy: Retain
    UpdateReplacePolicy: Retain
    Properties:
      BucketName: !Sub linq-audit-${AWS::AccountId}-${Environment}
      ObjectLockEnabled: true                 # must be set at create-time; cannot be enabled later.
      ObjectLockConfiguration:
        ObjectLockEnabled: Enabled
        Rule:
          DefaultRetention:
            Mode: COMPLIANCE                   # COMPLIANCE = even root cannot delete before retention.
            Days: !Ref AuditRetentionDays
      VersioningConfiguration: { Status: Enabled }
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
              KMSMasterKeyID: !Ref AuditBucketKmsKey
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  AuditBucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref AuditBucket
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Sid: AllowFirehoseDelivery
            Effect: Allow
            Principal: { AWS: !Sub "arn:aws:iam::${PlatformAccountId}:role/linq-platform-mcp-audit-firehose-role" }
            Action: ["s3:PutObject", "s3:PutObjectAcl"]
            Resource: !Sub "${AuditBucket.Arn}/*"
            Condition:
              StringEquals: { "s3:x-amz-acl": "bucket-owner-full-control" }
          - Sid: DenyDeleteBeforeRetention
            Effect: Deny
            Principal: "*"
            Action: ["s3:DeleteObject", "s3:DeleteObjectVersion"]
            Resource: !Sub "${AuditBucket.Arn}/*"
            Condition:
              StringNotEqualsIfExists:
                "s3:object-lock-mode": COMPLIANCE
```

Cite: [AWS Logs subscription filter docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/SubscriptionFilters.html), [Firehose to S3 destination docs](https://docs.aws.amazon.com/firehose/latest/dev/create-destination.html), [S3 Object Lock overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-overview.html).

**Locked constraint — retention upgrade path.** The 1-year-to-7-year migration is a two-step procedure: (a) update `AuditRetentionDays` parameter from `365` to `2555` and redeploy `06-audit-bucket.yaml` (applies to **new** objects only — Object Lock cannot retroactively shorten retention but extending it requires per-object `s3:PutObjectRetention`); (b) run the one-shot `relock-audit-objects` Lambda (referenced in the runbook below) which iterates extant objects and calls `PutObjectRetention` with `RetainUntilDate = ObjectCreatedAt + 7 years`. This procedure is documented before any compliance certification work begins; no compliance scope ships under a 1-year lock.

### 2.5 Runbooks (in full)

The three runbooks below ship as living documents under `docs/research/0015-centralized-platform-mcp/implementation/runbooks/` once Phase B implementation lands. The full text below is the source of truth — copy verbatim into the runbook files at implementation time.

---

#### `mcp-server-unavailable.md` — degradation playbook

**Symptom.** Agents (Claude Code, ops dashboards, internal dev tools) cannot reach the Platform MCP Server. `mcp-availability-breach` and / or `mcp-p95-latency-breach` are firing, or API Gateway is returning sustained 5xx, or the health-check endpoint `/healthz` is timing out.

**Severity.** SEV-2 by default; SEV-1 if any non-internal traffic is on the path (V1 contract bars this — escalate immediately if it happens).

**On-call.** Platform on-call (primary). Identity team (secondary, if Auth0 / IdentityBroker-side). CloudOps (tertiary, if cross-account log shipping is also broken — see `audit-delivery-lag`).

**What "operating without agent automation" looks like.** During an MCP-server outage, every consumer falls back to its pre-MCP workflow:

- **Claude Code agents** lose access to `linq.*` tools but retain Atlassian MCP (separate per-user OAuth path under [ADR 0008](../../../decisions/0008-mcp-connectors.md)) and any local tools. Agents continue to function; they cannot read LINQ product data via the broker.
- **Ops dashboards** that wire LINQ product data through the MCP server fall back to direct, human-driven AWS console access in each product account using break-glass IAM roles. Each product team owns a documented break-glass path; this runbook does **not** authorize bypassing it.
- **Internal dev tools** that depend on `linq.*` tool calls degrade gracefully — show a "MCP unavailable, retrying" banner and surface direct-link alternatives.

**Who decides to declare degradation.** Platform on-call, after one of:
1. `mcp-availability-breach` fires for ≥ 5 minutes with no recovery trend in 1-min granularity.
2. API Gateway 5xx rate ≥ 50% sustained 2 minutes.
3. `/healthz` endpoint returns non-200 for ≥ 3 consecutive minute checks.
4. Manual confirmation of a downstream dependency outage (Auth0 prolonged outage exceeding the 23 h M2M token cache, AWS regional event affecting `us-east-1`).

**Communication.** Platform on-call posts a `#platform-mcp-incidents` Slack message within 5 minutes of declaration with: summary, suspected cause, ETA, link to this runbook, link to the incident ticket. Updates every 15 minutes minimum until recovered.

**Recovery steps.**

1. **Confirm scope.** Check the dashboard `linq-platform-mcp-prod`. If `mcp-lambda-concurrency-80pct` is also firing, this is a saturation event — go to step 2a. If `mcp-auth0-token-issuance-zero` is firing, this is upstream auth — go to step 2b. If `AWS/Lambda Errors` is high but concurrency is low, this is application-layer — go to step 2c. If none are firing but availability is breached, suspect API Gateway or DNS — go to step 2d.

2. **Branch by symptom.**
   - **2a — Saturation (R8 runaway agent suspected).** Check `RequestCount` by `AgentClientId`. If a single `client_id` is > 5× baseline, apply a per-agent throttle override via the Lambda env-var `THROTTLE_OVERRIDE_<client_id>=1` (deploy via `infrastructure/03-mcp-server.yaml` parameter; effect within 60 s). Open a ticket with the agent owner. Expected mitigation time: 5 min.
   - **2b — Auth0 outage (R23).** Confirm via [Auth0 status page](https://status.auth0.com/). The 23 h M2M token cache absorbs short outages — verify `Auth0M2MTokenIssued Result=fail-cached-fallback` is firing, indicating cached operation. If the outage extends past 23 h (unprecedented), declare SEV-1 and execute the `cached-mode-extension` procedure (renew cached tokens via the break-glass admin client; documented separately).
   - **2c — Application error.** Check CloudWatch Logs Insights query: `fields @timestamp, errorClass, message | filter ispresent(errorClass) | sort @timestamp desc | limit 100` against `/aws/lambda/linq-platform-mcp-server`. If a recent deploy correlates, **roll back** via the GitHub Actions `release-rollback` workflow (parameter: previous green `release-tag`). Expected mitigation time: 10 min if rollback path is clean.
   - **2d — Infrastructure (API Gateway, Route 53, AWS regional).** Check [AWS Health Dashboard](https://health.aws.amazon.com/). If a regional event, mark the incident as awaiting AWS recovery, post an internal status, and notify stakeholders. Multi-region failover is **not** in V1 scope.

3. **Verify recovery.** Once the root cause is mitigated, watch the dashboard for 10 minutes. Recovery is declared when `mcp-availability-breach` clears and `mcp-p95-latency-breach` stays in OK for 10 consecutive minute samples.

4. **Post-incident.** Within 48 hours, the on-call writes a postmortem in the `incidents/` repo, links it from this runbook, and adds new alarms or runbook steps if the incident exposed gaps. Audit any data shipped to S3 during the window for completeness — if `mcp-audit-reconciliation-delta` fires for the incident window, follow `tenant-scope-rejection.md` step 5 (reconciliation backfill).

**Anti-patterns — do not do.**
- Do not bypass MCP server with direct cross-account AssumeRole from agent hosts. The audit chain is the broker's responsibility; bypassing it creates an unaudited blast radius.
- Do not increase Lambda reserved concurrency above 100 without an architecture review. Doubling concurrency does not double availability if the bottleneck is downstream.
- Do not disable alarms during the incident "to reduce noise." Alarms drive the recovery telemetry.

---

#### `tenant-scope-rejection.md` — false-positive triage

**Symptom.** `mcp-tenant-scope-rejection-spike` is firing — `ErrorCount` with `Class=TENANT_SCOPE_VIOLATION` is > 5 / minute. Or a user reports "the agent says I don't have access to my own data."

**Severity.** SEV-3 default (security signal, not outage). SEV-2 if affected user count > 10 or if a single tenant's traffic is being uniformly blocked (suggests a registry / claim-mapping bug, not an attack).

**On-call.** Platform on-call (primary, until classification completes). Hands off per the decision tree below.

**Why this matters.** Tenant-scope rejection is the [R1 (tenant leakage)](../03-risks-register.md#r1--tenant-leakage-at-the-handler) safety gate firing as designed. **A genuine rejection is the system working.** A spike of false positives is either: a registry misconfiguration of `tenantSourceClaim`, an Auth0 RBAC mapping bug that injects the wrong `tenant_id` claim, an agent-side bug that supplies tenant in the input envelope (which the broker correctly ignores), or — in the worst case — an actual cross-tenant access attempt by a misbehaving agent or compromised credential. Each is a different fix; the runbook is a decision tree.

**Decision tree.**

1. **Pull the rejection sample.** Run the CloudWatch Logs Insights query against `/linq/platform-mcp/audit-prod`:
   ```
   fields @timestamp, request_id, agent_client_id, user_sub, tool_id, tenant_jwt_claim, tenant_input_arg, denial_reason
   | filter denial_reason = "tenant_scope"
   | stats count() as rejections by agent_client_id, tool_id, tenant_jwt_claim, tenant_input_arg
   | sort rejections desc
   | limit 50
   ```
   This shows the shape of rejections in the last 15 minutes by default (Insights respects the dashboard time range).

2. **Classify by `tenant_jwt_claim` vs. `tenant_input_arg`.**
   - **(a) `tenant_jwt_claim = NULL` for all hits → registry / Auth0 mapping bug.** The user's JWT does not carry a `tenant_id` claim where the registry expects it. Skip to step 3a.
   - **(b) `tenant_jwt_claim = X`, `tenant_input_arg = Y`, X ≠ Y, all hits same `agent_client_id` → likely agent bug.** The agent is supplying tenant in input; broker correctly overrides. Skip to step 3b.
   - **(c) `tenant_jwt_claim = X`, `tenant_input_arg = Y`, X ≠ Y, mixed `agent_client_id`, mixed `user_sub`, narrow `tool_id` → likely registry `tenantSourceClaim` mismatch.** Skip to step 3c.
   - **(d) `tenant_jwt_claim = X`, `tenant_input_arg = Y`, X ≠ Y, single `user_sub` repeating, with X consistent → suspicious. Possible token theft or cross-tenant probe.** Skip to step 3d (escalation).

3. **Branch by classification.**
   - **3a — Auth0 / registry mapping bug.** Page the Identity team. Confirm the user's [Auth0 token contains `tenant_id`](../../../knowledge/wiki/entities/auth0-m2m.md). If yes, confirm the registry's `tenantSourceClaim` for the affected tool matches the claim path (e.g., `https://linq.com/tenant_id` vs. `app_metadata.tenant_id`). Update registry via the registration API (this is a config fix, not code). Mitigation time: 30 min.
   - **3b — Agent bug.** Open a ticket against the agent owner (use the `owner` field from the registry tool entry). The broker correctly ignored the agent's input — this is a working-as-intended event. The fix lives in the agent; the broker contract does not change. Communicate to the agent owner that supplying tenant in input is a no-op; they should remove it from their request shape.
   - **3c — Registry `tenantSourceClaim` mismatch.** Suspect a recent registry write. Check the registry-write audit (DynamoDB stream → CloudWatch log group `/linq/platform-mcp/registry-writes`) for changes to the affected `tool_id` in the last 24 h. If a recent write set `tenantSourceClaim` incorrectly, **roll back** the registry item by promoting the previous `VERSION#` via the `LABEL#stable` relabel mechanism (atomic — see [`04-registry.md`](04-registry.md)). Mitigation: 10 min.
   - **3d — Suspicious activity.** **Stop here.** Page the security on-call (`#sec-incident` channel + PagerDuty). Do not communicate with the agent owner directly. Preserve the audit-log window in S3 (Object Lock already prevents tampering). Security drives from this point. The CloudOps responsibility ends after the page.

4. **Verify recovery.** After fix, watch `mcp-tenant-scope-rejection-spike` for 15 minutes. If rejection rate returns to baseline (< 1 / minute steady-state, dominated by genuine RBAC denials), close the ticket.

5. **Reconciliation backfill (if needed).** If the incident window also fired `mcp-audit-reconciliation-delta`, run the `audit-backfill` Lambda (deployed in `06-audit.yaml`) against the affected window; it reads the Lambda's CloudWatch Logs directly and re-emits any missing rows to Firehose. This is a destructive-write-safe operation — Firehose dedupes by `request_id`.

**False-positive baseline.** Expect ~0.5 to 1 rejection per minute steady-state at V1 scale, dominated by users who genuinely lack access (the system working). The alarm at > 5 / minute reflects a 10× signal-to-noise threshold that catches real spikes without paging on baseline.

---

#### `on-call-boundary.md` — failure-stage routing matrix

**Purpose.** Every failure mode in the Platform MCP Server has exactly **one named first-responder.** This matrix encodes the rule from [`01-architecture.md`](../01-architecture.md#on-call-boundary-matrix) so that paging logic, ticket routing, and post-incident ownership are unambiguous. New failure modes added in Phase B update this table.

| Failure stage | Symptom (alarm or report) | First-responder | Escalation path | Notes |
|---|---|---|---|---|
| MCP-server JWT validation fails | `ErrorCount Class=AUTH` spike; 401 from MCP | Platform | → Identity if Auth0 misconfiguration is suspected (e.g., new agent client not in Auth0) | The `WWW-Authenticate` header points clients to the resource-server metadata; if that endpoint is also down, escalate to Platform infra lead |
| Registry GetItem 5xx | `tools/list` empty; `tools/call` returns NOT_FOUND; `AWS/DynamoDB ThrottledRequests` > 0 | Platform | Stop the bus — registry is V1 hot path. Failover-mode: serve from in-process cache only; reject `tools/list_changed`. | Mitigation: enable circuit breaker; deploy registry table on-demand mode if not already (V1 default is on-demand) |
| IdentityBroker / token exchange | `IdentityBrokerExchangeCount Result=fail-*`; 502 with `Class=AUTH` | Platform | → Identity if KMS or Auth0-side; → Security if `fail-claim-validation` (potential token misuse) | KMS `Sign` failures are extremely rare; treat as platform infra |
| STS AssumeRole AccessDenied | `mcp-assume-role-throttle` is 0 but `Errors` show AccessDenied; CloudTrail in product account shows `AssumeRole` deny | Platform until product-side IAM trust policy is proven mis-set, then product | Joint debug; trust-policy ownership lives with product. The product team owns `PlatformMcpInvoker` role trust policy. | Common cause: External ID mismatch after a registry write put a stale value |
| STS rate limit | `mcp-assume-role-throttle` > 0 | Platform | → AWS support if persistent (account-level quota increase) | R16 mitigation is session caching — confirm `RegistryCacheHitRatio` and STS cache hit rate first |
| Handler invoke 5xx (Lambda failed) | `ErrorCount Class=UPSTREAM_ERROR`, 502 to agent | Owning product team | Stop incidents at the handler boundary | Handler `owner` field in the registry routes the page |
| Handler invoke timeout | `ErrorCount Class=UPSTREAM_TIMEOUT`, 504 to agent | Owning product team | Negotiate `timeoutMs` increase via registry update; Platform reviews if > 30 s | R13 — agents should not silently absorb a 30 s timeout |
| Handler resource throttle (DynamoDB / Lambda concurrency in product account) | Product-account CloudWatch alarms; downstream `Throttles` | Owning product team | → Platform if cross-product correlation suggests broker is the amplifier (R8) | Per-tool circuit-break in the broker fires at 5× baseline |
| Audit log shipping lag | `mcp-audit-delivery-lag` or `mcp-firehose-data-freshness` | Platform | → CloudOps if cross-account / IAM | Subscription filter, Firehose, S3 bucket policy — three failure points; `06-audit.yaml` outputs aid root cause |
| Audit reconciliation delta | `mcp-audit-reconciliation-delta` | Platform | → CloudOps if Firehose-side; → Security if delta cannot be explained | Run `audit-backfill` Lambda; Object Lock prevents tampering, so source-of-truth is the Lambda log group |
| Auth0 outage | `mcp-auth0-token-issuance-zero` or `Auth0M2MTokenIssued Result=fail-cached-fallback` | Identity team | → Platform bypasses with cached tokens within 23 h; document break-glass at hour 22 | R23 — cached mode is the only V1 mitigation |
| Agent-side timeout | Agent reports MCP timeout but MCP `total` latency was within SLO | Agent owner first; escalate to Platform if MCP server is responsive | If MCP returned a result and agent timed out, agent owner | Common cause: agent SDK retry budget too tight — see [`role-passes/cost-reliability.md` Q10](../role-passes/cost-reliability.md) |
| `tools/list_changed` storm | `mcp-listchanged-storm` | Platform | Identify the registry-writer firing the storm (CI? human? misbehaving Lambda?); add coalescing window | R11 — server-side debounce already coalesces 60 s; storms exceeding the alarm are abnormal |
| MCP-server Lambda concurrency saturated | `mcp-lambda-concurrency-80pct` | Platform | If saturating from a single agent, throttle that agent; if broad-based, scale reserved concurrency RFC | R8 — runaway agent vs. organic growth distinguishable from `RequestCount` by `AgentClientId` |
| Cold-start budget breached | `mcp-cold-start-7d-trigger` | Platform | Open the provisioned-concurrency RFC (R15 gate) | The 7-day window is the gate, not the alarm — this fires once and opens an architecture decision, not a page |
| External ID compromise (theoretical) | Anomalous AssumeRole patterns; Access Analyzer findings | Security | → Platform for External ID rotation | External ID is identifier, not credential (R20) — but if a registry compromise is suspected, rotate proactively |
| Cross-account audit pipeline IAM drift | Firehose `DeliveryToS3` errors with AccessDenied; bucket policy changes flagged in CloudTrail | Platform | → CloudOps; → Security if audit gap is durable | The bucket lives in the logging account; ownership is split — CloudOps owns the wire, Security owns the bucket policy |

**Routing rules in plain language.**

- **Auth, registry, dispatch, transport** → Platform.
- **Handler logic, IAM trust-policy misconfiguration, downstream-resource fault** → owning product.
- **STS AssumeRole** → Platform until product IAM is proven mis-set, then product.
- **Audit pipeline** → Platform owns the wire (CloudWatch Logs + Firehose + Lambda); CloudOps escalation if cross-account; Security escalation if audit gap is durable.
- **Auth0 outage** → Identity. Platform operates in cached mode for up to 23 h.
- **Agent-side timeout** → agent owner first. Escalate to Platform only if MCP server is unresponsive in correlated logs.

**Update protocol.** This document is updated by the Platform on-call rotation. Any new alarm added to the dashboard requires a corresponding row in this table at the same PR. Reviewed quarterly during the platform health review.

## 3. Acceptance criteria

- **AC10 (POC documentation parity).** All three runbooks present and content-complete: `mcp-server-unavailable.md` (degradation playbook with branched recovery and "operating without agent automation" definition), `tenant-scope-rejection.md` (false-positive triage decision tree), `on-call-boundary.md` (failure-stage routing matrix). Reviewed by Platform on-call rotation before POC sign-off.
- **Observable signals — every alarm in the table has a matching dashboard widget** in `linq-platform-mcp-${Environment}`, and every dashboard widget templates by `Handler` where the metric carries a `Handler` dimension.
- **Audit-delivery SLO.** `mcp-audit-delivery-lag` is in OK state for 7 consecutive days against synthetic traffic before POC sign-off.
- **Reconciliation SLO.** Daily `mcp-audit-reconciliation-delta` is `0` (no missing rows) for 7 consecutive days.
- **Cold-start gate.** `ColdStartCount` and `LatencyMs Stage=total` are emitted continuously so the 7-day P95 > 1500 ms condition is measurable. Provisioned concurrency is **not** enabled in V1 unless this condition fires (R15).
- **`listChanged` storm guard.** `mcp-listchanged-storm` is wired and the broker enforces the 60-s coalesce window (verified in [`08-testing.md`](08-testing.md)) before second handler onboards.
- **Auth0-outage detection.** `mcp-auth0-token-issuance-zero` and `mcp-auth0-cached-fallback-active` are wired; the 23-h cached-mode behavior is documented in `mcp-server-unavailable.md` step 2b.
- **Object Lock.** S3 audit bucket has Object Lock enabled in `COMPLIANCE` mode at create time with 365-day default retention, and `06-audit-bucket.yaml` parameter `AuditRetentionDays` accepts only `[365, 2555]`. The 7-year upgrade procedure is documented in this artifact.

## 4. Effort estimate

`4 d [ASSUMED]`.

Breakdown: 1 d metric instrumentation (EMF blocks in MCP-server and IdentityBroker Lambdas); 0.5 d dashboard JSON + variables block; 0.5 d alarm CFN; 0.5 d Firehose + S3 + bucket-policy CFN; 1 d runbook authorship and on-call review; 0.5 d reconciliation Lambda + daily schedule. Excludes the [Phase B implementation of the IdentityBroker and audit-emit code paths](05-identity-broker.md) — this artifact assumes those Lambdas are emitting structured records.

## 5. Open questions

- **Q4 (does Platform Services already operate a centralized logging account) — disposition.** This artifact assumes **yes** per the cross-cutting decision CC-5 Q4 (`[ASSUMED]`). If LINQ CloudOps confirms no logging-OU account, scope a parallel ~1-week workstream to stand one up before POC sign-off. The CFN snippets above split cleanly across the two accounts (Platform Services owns `06-audit.yaml`; logging account owns `06-audit-bucket.yaml`), so the existence of a logging account is a deployment-target question, not a design question. Q5 — does the logging account already publish a [centralized observability sharing](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Unified-Cross-Account-Setup.html) ARN that CloudWatch can consume cross-account? If yes, dashboards and alarms can live in the logging account too, with the Platform Services account as a source. V1 keeps dashboards in Platform Services; Phase B revisits.

## 6. Cross-references

- [`role-passes/cost-reliability.md`](../role-passes/cost-reliability.md) — SLO recommendation table, caching strategy, sub-linear cost preconditions (precondition #3 is what mandates handler-as-dimension dashboards).
- [`01-architecture.md`](../01-architecture.md) — failure-stage on-call matrix; cold-path latency budget; cross-account log shipping topology.
- [`03-risks-register.md`](../03-risks-register.md) — R7, R11, R15, R18, R23 sources for alarm thresholds.
- [`04-phase-1-poc.md`](../04-phase-1-poc.md) — AC10 documentation parity; M6 milestone audit reconciliation.
- [`implementation/01-cloudformation.md`](01-cloudformation.md) — master template; `06-audit` nested stack imports `AuditDeliveryStreamArn` from this artifact.
- [`implementation/03-mcp-server.md`](03-mcp-server.md) — MCP-server Lambda code emits the EMF blocks defined in §2.1.
- [`implementation/05-identity-broker.md`](05-identity-broker.md) — IdentityBroker emits `IdentityBrokerExchangeCount` and `IdentityBrokerKMSSignLatencyMs`.
- [`implementation/08-testing.md`](08-testing.md) — synthetic traffic and reconciliation test harness.
- [Decision 0015 ADR](../../../decisions/0015-centralized-platform-mcp.md) — observability and audit consequences.

## 7. Risks protected against

- **R7 (MCP-server availability is the entire system's availability).** `mcp-availability-breach`, `mcp-p95-latency-breach`, `mcp-error-rate-breach`, `mcp-lambda-concurrency-80pct`, and `mcp-error-budget-burn-fast` collectively detect the four ways the broker can fail (5xx, slow, error class, saturation). The `mcp-server-unavailable.md` runbook is the documented degradation playbook the cost-reliability memo demanded before any non-internal user touches the system.
- **R11 (`listChanged` storms during multi-team handler deploys).** `mcp-listchanged-storm` alarms when `ToolsListChangedNotifications Trigger=registry-write` exceeds 6 / minute, the threshold above the broker's 60-s coalesce window — i.e., it fires only when the coalescer itself is overwhelmed.
- **R15 (cold-start latency violating Claude Code timeouts).** `ColdStartCount` plus the 7-day P95 latency math expression (`mcp-cold-start-7d-trigger`) is the **measurement gate** that decides whether to enable provisioned concurrency. Observability is the gate — the metric is the trigger condition, not a heuristic.
- **R18 (cross-account log shipping fails silently).** `mcp-audit-delivery-lag`, `mcp-firehose-data-freshness`, and the daily `mcp-audit-reconciliation-delta` triple-stack catches the silent-failure mode the cost-reliability memo specifically called out — pipeline appears healthy but rows are quietly dropped.
- **R23 (Auth0 outage detection via M2M token issuance metric).** `mcp-auth0-token-issuance-zero` (sustained 30 min absence of successful issuances) and `mcp-auth0-cached-fallback-active` (cached-mode active) make the 23-h cache window observable; the runbook step 2b spells out the cached-mode operation and break-glass procedure.
