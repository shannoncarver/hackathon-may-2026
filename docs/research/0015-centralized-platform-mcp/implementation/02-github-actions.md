# Implementation 02 — GitHub Actions CI/CD

**Decision:** [`0015-centralized-platform-mcp`](../../../decisions/0015-centralized-platform-mcp.md) — Phase B CI/CD pipeline.
**Owner:** 11-eng-cloudops (CloudOps Engineer).
**Status:** Draft for Phase B implementation.
**Effort estimate:** `3 d [ASSUMED]`.

## 1. Overview

This artifact specifies the GitHub Actions pipelines that build, lint, test, and deploy the Phase-1 POC of the LINQ Platform MCP Server. The design honors three locked constraints: OIDC federation only — **no long-lived AWS access keys** in repo secrets; `cfn-lint` and `cfn-nag` block merge on every pull request; secrets land in AWS Secrets Manager and reach CloudFormation via `{{resolve:secretsmanager:...}}` references, never as workflow inputs. Three top-level workflows (`pr.yml`, `deploy-main.yml`, `release.yml`) drive PR validation, sandbox deploy on merge to `main`, and signed-tag prod deploy. Three reusable workflows (`stack-deploy.yml`, `lambda-build.yml`, `smoke-test.yml`) factor out repeated jobs. Deployment ordering follows the dependency graph from `01-cloudformation.md` §2.1 (CC-3): `01-network → 02-secrets → 04-registry → 03-mcp-server → 05-identity-broker → 06-audit → 04-registry-seed → 07-product-handler-trust`. V1 prod is sandbox per the locked POC scope; V2 promotion to a true prod environment is gated by GitHub environment protection rules whose specification is recorded below for hand-off.

## 2. Concrete artifacts

### 2.1 Workflow inventory

| Workflow | Trigger | Deploys? | Job set |
|---|---|---|---|
| `.github/workflows/pr.yml` | `pull_request` to `main` | **No** | `actionlint`, `cfn-lint`, `cfn-nag`, `unit-tests`, `contract-tests`, `schema-validate` |
| `.github/workflows/deploy-main.yml` | `push` to `main` | Sandbox via OIDC | All PR jobs + `package` + `deploy-platform` + `deploy-product` + `smoke` |
| `.github/workflows/release.yml` | `push` of signed tag `v*.*.*` | V1: sandbox; V2: prod | Same as `deploy-main` plus environment protection gate |
| `.github/workflows/stack-deploy.yml` | `workflow_call` (reusable) | Single nested stack | OIDC assume → `aws cloudformation deploy` → wait → status assert |
| `.github/workflows/lambda-build.yml` | `workflow_call` (reusable) | No (build only) | `npm ci` → `sam build` → upload SAM artifact to ephemeral S3 |
| `.github/workflows/smoke-test.yml` | `workflow_call` (reusable) | No (test only) | `npm run smoke` against `${ApiEndpoint}` import |

### 2.2 PR workflow — `.github/workflows/pr.yml`

Lint and test only. **No AWS credentials**, no `aws-actions/configure-aws-credentials` step. Required-to-merge per branch protection on `main`.

```yaml
name: pr

on:
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: read

concurrency:
  group: pr-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  actionlint:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - name: actionlint
        uses: rhysd/actionlint@v1
        # See https://github.com/rhysd/actionlint — fails on any workflow error.

  cfn-lint:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install cfn-lint==1.* cfn-flip
      - name: cfn-lint
        run: cfn-lint --info "infrastructure/**/*.yaml"
        # Spec: https://github.com/aws-cloudformation/cfn-lint — zero E findings required.

  cfn-nag:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - name: cfn-nag scan
        uses: stelligent/cfn_nag@master
        with:
          input_path: infrastructure
          extra_args: --fail-on-warnings=false --print-suppression
        # Spec: https://github.com/stelligent/cfn_nag — zero FAIL findings required.

  unit-tests:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
      - run: npm ci
      - run: npm run test:unit -- --coverage
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: unit-coverage
          path: coverage/

  contract-tests:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: npm }
      - run: npm ci
      - run: npm run test:contract
        # Diffs handler input/output against registry-published JSON Schemas (08-testing.md).

  schema-validate:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: npm }
      - run: npm ci
      - run: npm run validate:schemas
        # Validates infra/schemas/*.json against MCP 2025-06-18 JSON Schema draft.
```

`pr.yml` does not request `id-token: write`. The PR job set is provably credential-free — OIDC tokens are only minted by workflows that explicitly opt in.

### 2.3 Main-branch deploy workflow — `.github/workflows/deploy-main.yml` (worked example)

Deploys to sandbox on every merge to `main`. OIDC federation assumes the per-account `gha-deployer` role; **no long-lived AWS keys cross the workflow boundary**. The job graph linearizes the CC-3 deploy ordering by chaining reusable `stack-deploy.yml` calls with `needs:`.

```yaml
name: deploy-main

on:
  push:
    branches: [main]

permissions:
  contents: read
  id-token: write   # Required for OIDC token mint — no static AWS keys.

concurrency:
  group: deploy-main
  cancel-in-progress: false   # Never cancel a running deploy mid-stack.

env:
  AWS_REGION: us-east-1
  ENVIRONMENT: dev
  PLATFORM_ACCOUNT_ID: "111111111111"   # [ASSUMED] — Q3.
  PRODUCT_ACCOUNT_ID:  "444444444444"   # [ASSUMED] — Q3.
  TEMPLATE_BUCKET:     linq-cfn-artifacts-dev

jobs:
  validate:
    uses: ./.github/workflows/pr.yml
    # Re-run PR gates on the merge commit. cfn-lint / cfn-nag must stay green
    # post-merge to catch a `main`-only drift.

  package:
    needs: validate
    runs-on: ubuntu-22.04
    outputs:
      artifact-prefix: ${{ steps.upload.outputs.prefix }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: npm }
      - uses: aws-actions/setup-sam@v2
        with: { use-installer: true }
      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ env.PLATFORM_ACCOUNT_ID }}:role/gha-deployer
          role-session-name: gha-deploy-main-${{ github.run_id }}
          aws-region: ${{ env.AWS_REGION }}
        # OIDC trust: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services
      - name: SAM build
        run: |
          sam build \
            --template infrastructure/master.yaml \
            --build-dir .aws-sam/build \
            --use-container
      - name: Upload nested templates and Lambda artifacts to S3
        id: upload
        run: |
          PREFIX="${ENVIRONMENT}/${GITHUB_SHA}"
          aws s3 sync infrastructure/ "s3://${TEMPLATE_BUCKET}/${PREFIX}/" \
            --exclude "*" --include "*.yaml"
          sam package \
            --s3-bucket "${TEMPLATE_BUCKET}" \
            --s3-prefix "${PREFIX}/lambda" \
            --output-template-file packaged-master.yaml
          aws s3 cp packaged-master.yaml "s3://${TEMPLATE_BUCKET}/${PREFIX}/master.yaml"
          echo "prefix=${PREFIX}" >> "$GITHUB_OUTPUT"

  deploy-network:
    needs: package
    uses: ./.github/workflows/stack-deploy.yml
    with:
      stack-name: platform-mcp-network-dev
      template-key: ${{ needs.package.outputs.artifact-prefix }}/01-network.yaml
      account-id: "111111111111"
      environment: dev
    secrets: inherit

  deploy-secrets:
    needs: deploy-network
    uses: ./.github/workflows/stack-deploy.yml
    with:
      stack-name: platform-mcp-secrets-dev
      template-key: ${{ needs.package.outputs.artifact-prefix }}/02-secrets.yaml
      account-id: "111111111111"
      environment: dev
    secrets: inherit

  deploy-registry:
    needs: deploy-secrets
    uses: ./.github/workflows/stack-deploy.yml
    with:
      stack-name: platform-mcp-registry-dev
      template-key: ${{ needs.package.outputs.artifact-prefix }}/04-registry.yaml
      account-id: "111111111111"
      environment: dev
    secrets: inherit

  deploy-mcp-server:
    needs: deploy-registry
    uses: ./.github/workflows/stack-deploy.yml
    with:
      stack-name: platform-mcp-server-dev
      template-key: ${{ needs.package.outputs.artifact-prefix }}/03-mcp-server.yaml
      account-id: "111111111111"
      environment: dev
    secrets: inherit

  deploy-identity-broker:
    needs: deploy-mcp-server
    uses: ./.github/workflows/stack-deploy.yml
    with:
      stack-name: platform-mcp-identity-broker-dev
      template-key: ${{ needs.package.outputs.artifact-prefix }}/05-identity-broker.yaml
      account-id: "111111111111"
      environment: dev
    secrets: inherit

  deploy-audit:
    needs: deploy-identity-broker
    uses: ./.github/workflows/stack-deploy.yml
    with:
      stack-name: platform-mcp-audit-dev
      template-key: ${{ needs.package.outputs.artifact-prefix }}/06-audit.yaml
      account-id: "111111111111"
      environment: dev
    secrets: inherit

  deploy-registry-seed:
    needs: [deploy-audit, deploy-mcp-server]
    uses: ./.github/workflows/stack-deploy.yml
    with:
      stack-name: platform-mcp-registry-seed-dev
      template-key: ${{ needs.package.outputs.artifact-prefix }}/04-registry-seed.yaml
      account-id: "111111111111"
      environment: dev
    secrets: inherit

  deploy-product-trust:
    needs: deploy-registry-seed
    uses: ./.github/workflows/stack-deploy.yml
    with:
      stack-name: platform-mcp-product-trust-dev
      template-key: ${{ needs.package.outputs.artifact-prefix }}/07-product-handler-trust.yaml
      account-id: "444444444444"   # Product account — separate OIDC trust.
      environment: dev
    secrets: inherit

  smoke:
    needs: deploy-product-trust
    uses: ./.github/workflows/smoke-test.yml
    with:
      environment: dev
      api-endpoint-export: platform-mcp-api-endpoint-dev
    secrets: inherit
```

Key properties:

- **Concurrency `cancel-in-progress: false`** — a second push during a deploy queues; it never aborts a half-completed CFN update which would leave stacks in `UPDATE_ROLLBACK_FAILED`.
- **`validate` re-uses `pr.yml`** via `workflow_call` semantics so the merge commit re-runs every gate.
- **Linear `needs:` chain** matches the CC-3 deploy order from `01-cloudformation.md` §2.1. Parallelism is intentionally avoided — the master template's `DependsOn` graph is the source of truth, but the workflow mirrors it so a partial failure stops the chain at the failed stack rather than racing forward.
- **Cross-account hop** for `deploy-product-trust` is a different OIDC role assumption inside `stack-deploy.yml`; the workflow surface is identical, only `account-id` changes.
- **Smoke job** runs the MCP Inspector probe against `ApiEndpoint` exported by `03-mcp-server`; failure rolls forward to a runbook, not an automatic rollback (V1 sandbox tolerates a broken main; rollback in `main` is a manual `git revert + redeploy`).

### 2.4 Reusable workflow stub — `.github/workflows/stack-deploy.yml`

Wraps a single `aws cloudformation deploy` with OIDC, status assertion, and structured failure output. Caller passes the stack name, S3 template key, target account, and environment.

```yaml
name: stack-deploy

on:
  workflow_call:
    inputs:
      stack-name:    { type: string, required: true }
      template-key:  { type: string, required: true }
      account-id:    { type: string, required: true }
      environment:   { type: string, required: true }

permissions:
  contents: read
  id-token: write

env:
  AWS_REGION:      us-east-1
  TEMPLATE_BUCKET: linq-cfn-artifacts-${{ inputs.environment }}

jobs:
  deploy:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ inputs.account-id }}:role/gha-deployer
          role-session-name: gha-deploy-${{ inputs.stack-name }}-${{ github.run_id }}
          aws-region: ${{ env.AWS_REGION }}
      - name: Deploy CFN stack
        run: |
          aws cloudformation deploy \
            --stack-name "${{ inputs.stack-name }}" \
            --template-file <(aws s3 cp \
              "s3://${TEMPLATE_BUCKET}/${{ inputs.template-key }}" -) \
            --capabilities CAPABILITY_NAMED_IAM \
            --parameter-overrides \
              file://infrastructure/params/${{ inputs.environment }}.json \
            --no-fail-on-empty-changeset
      - name: Assert terminal-success status
        run: |
          STATUS=$(aws cloudformation describe-stacks \
            --stack-name "${{ inputs.stack-name }}" \
            --query "Stacks[0].StackStatus" --output text)
          case "$STATUS" in
            CREATE_COMPLETE|UPDATE_COMPLETE) echo "OK: $STATUS" ;;
            *) echo "FAIL: stack in $STATUS"; exit 1 ;;
          esac
```

`lambda-build.yml` and `smoke-test.yml` follow the same `workflow_call` shape — stubs not duplicated here for brevity; they are listed in §2.1 with their job sets.

### 2.5 OIDC trust policy snippet — `gha-deployer` role per account

Deployed once per account by a bootstrap stack (Platform Services account and the V1 product account). The trust policy is owned by `12-eng-security-iam` per role-boundary; the snippet below is the minimum acceptable shape from the CloudOps consumer perspective and **must be reviewed by Security before deploy**.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GitHubActionsOIDC",
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:linq/linq-platform-mcp:ref:refs/heads/main"
        }
      }
    },
    {
      "Sid": "GitHubActionsOIDCReleaseTags",
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:linq/linq-platform-mcp:ref:refs/tags/v*"
        }
      }
    }
  ]
}
```

The `sub` condition restricts assumption to `main` pushes and signed `v*` tags from the canonical repo — pull-request workflows from forks cannot assume the role because their `sub` is `pull_request`. This protects against the GitHub-hosted-runner-takeover failure mode. Reference: [Configuring OpenID Connect in Amazon Web Services — GitHub Docs](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services). The `gha-deployer` role's permission policy is scoped to the CFN actions and per-stack resources documented in `06-cross-account.md`.

### 2.6 Approval-gate spec

| Stage | V1 (POC) | V2 (prod onboarding) |
|---|---|---|
| PR merge to `main` | Branch protection: required reviewers (1 CODEOWNER), required status checks (`actionlint`, `cfn-lint`, `cfn-nag`, `unit-tests`, `contract-tests`, `schema-validate`), no force-push, signed commits required | Same as V1 plus required reviewer count = 2, dismiss stale reviews on push |
| Sandbox deploy on merge | Automatic; no manual gate | Same |
| Prod deploy on signed tag | V1 prod = sandbox; tag-trigger reuses `deploy-main.yml` job graph against the same `dev` env, no separate gate | GitHub environment `prod` with: required reviewers (Platform on-call + Security), 30-min wait timer, deployment branch policy = `refs/tags/v*.*.*` only, prod secrets scoped to environment |
| Rollback | Manual `git revert + redeploy`; documented in `runbooks/mcp-stuck-stack.md` | Same plus protected-environment "freeze" toggle to halt new deploys during incident |

V2 environment configuration spec (recorded for hand-off): create a GitHub environment named `prod` in repo settings, attach the `gha-deployer-prod` role ARN as an environment-scoped secret, set deployment branch policy to "Selected tags" matching `v*.*.*`, require Platform on-call + Security reviewers, and add a 30-minute wait timer to absorb a "deploy regret" window. See [Using environments for deployment — GitHub Docs](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment).

### 2.7 Release workflow — `.github/workflows/release.yml`

Triggered on `push` of a signed tag matching `v*.*.*`. V1 reuses the same job graph as `deploy-main.yml` against the sandbox environment (because V1 prod = sandbox per locked POC scope). The V2 mechanism is the GitHub environment block sketched in §2.6. Concrete YAML omitted to avoid duplicating §2.3 verbatim — the only deltas are `on: push: tags: ['v*.*.*']`, `environment: prod` on the deploy jobs, and reading `PLATFORM_ACCOUNT_ID` / `PRODUCT_ACCOUNT_ID` from environment-scoped secrets rather than workflow `env`.

### 2.8 Secrets and parameters — sourcing rules

| Material | Source | Where it lands |
|---|---|---|
| AWS credentials | OIDC token via `aws-actions/configure-aws-credentials@v4` | Ephemeral `AssumeRoleWithWebIdentity` session, never written to disk |
| Auth0 client secret | AWS Secrets Manager `platform-mcp/<env>/auth0` (provisioned by `02-secrets`) | CFN reads via `{{resolve:secretsmanager:...}}` at deploy and runtime — **never** a workflow input |
| Account IDs | Workflow `env:` for V1; environment-scoped secrets for V2 prod | Surfaced as CFN `--parameter-overrides` |
| Template-bucket name | Workflow `env:` (per-env naming) | Used for SAM upload |
| GPG signing key for tags | Developer-side; verified by `git verify-tag` in `release.yml` | Never read by workflow runner |

No secret of any kind is permitted to live in `.github/workflows/*.yml` as plain text or in `${{ secrets.* }}` if it represents an AWS credential. Every AWS interaction routes through the OIDC role.

## 3. Acceptance criteria

Observable signals, every one CI- or console-verifiable:

1. A pull request whose CFN change introduces a `cfn-lint` `E` finding **fails** the `cfn-lint` job; merge button is disabled by branch protection.
2. A pull request whose CFN change introduces a `cfn-nag` `FAIL` finding **fails** the `cfn-nag` job; merge button is disabled.
3. A pull request workflow run shows **no** `aws-actions/configure-aws-credentials` step — verified by `gh run view --log` grep on a sample PR.
4. Merging to `main` triggers `deploy-main.yml`; the `package` job's CloudTrail event in the Platform Services account shows `AssumeRoleWithWebIdentity` from `token.actions.githubusercontent.com` with `sub: repo:linq/linq-platform-mcp:ref:refs/heads/main`.
5. `aws iam list-access-keys --user-name gha-deployer` returns an empty list (the role has no IAM user, no static keys).
6. `gh secret list --repo linq/linq-platform-mcp` does **not** include any key matching `^AWS_(ACCESS|SECRET)_KEY` — checked manually and by an `actionlint` custom rule in CI.
7. The `deploy-main` job graph executes stacks in the CC-3 order; `gh run view` shows `deploy-network` finishing before `deploy-secrets`, and `deploy-product-trust` last.
8. A signed tag `v0.1.0` triggers `release.yml`; the run completes the same job set against the sandbox env in V1.
9. `actionlint` returns zero findings on every workflow file under `.github/workflows/`.
10. The `gha-deployer` role's trust policy in both accounts contains the `sub` condition restricting assumption to `refs/heads/main` and `refs/tags/v*` — verified by `aws iam get-role --role-name gha-deployer | jq '.Role.AssumeRolePolicyDocument'`.

## 4. Effort estimate

`3 d [ASSUMED]` — one CloudOps engineer.

- Day 1 — author `pr.yml` + `actionlint` setup + `cfn-lint`/`cfn-nag` jobs; wire branch protection on `main`; validate against a scratch PR.
- Day 2 — author `deploy-main.yml` worked example + the three reusable workflows; coordinate with Security on the `gha-deployer` OIDC trust policy (Security owns; CloudOps consumes); end-to-end deploy to dev sandbox.
- Day 3 — author `release.yml`; document V2 environment-protection spec; smoke-test full chain against a clean sandbox; runbook update for `gh run rerun` / failed-stack recovery.

## 5. Open questions

- **Q-GHA.1.** Should the `gha-deployer` role's `sub` claim restrict to a single GitHub Actions environment name as well as the branch? Forced today: **branch + tag conditions are sufficient for V1**; V2 adds `environment:prod` to the `sub` pattern when the prod environment lands. `[ASSUMED]`. Reference: [Restricting workflows to specific branches and tags — GitHub Docs](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect#filtering-for-a-specific-environment).
- **Q-GHA.2.** Use a self-hosted runner pool for the deploy jobs to enable VPC-private CFN endpoints? Forced today: **GitHub-hosted runners** for V1 — CFN endpoints are public, network egress from `ubuntu-22.04` runners is sufficient, and self-hosted adds operational burden incompatible with POC scope. Re-evaluate at M3 if deploy times exceed 10 minutes or compliance scope tightens. `[ASSUMED]`.
- **Q-GHA.3.** Cache `sam build` artifacts across runs to cut deploy time? Forced today: **no cache for V1** — POC build is < 30 s; cache invalidation complexity outweighs the gain. Re-evaluate at M2 once Lambda layer count grows. `[ASSUMED]`.
- **Q-GHA.4.** Should `deploy-main.yml`'s smoke job block merges retroactively (i.e., a failed smoke reverts the merge)? Forced today: **no auto-revert** — V1 sandbox tolerates `main` red briefly; revert is a human decision documented in `runbooks/mcp-stuck-stack.md`. `[ASSUMED]`.

None of these are in `05-open-questions.md`; they are local to the CI/CD layer and resolvable by CloudOps without stakeholder input.

## 6. Cross-references

- [`prompt.txt`](prompt.txt) — §3 GitHub Actions CI/CD pipelines and the locked CI constraint set.
- [`01-cloudformation.md`](01-cloudformation.md) — §2.1 CC-3 deploy order, §2.4 parameter schema (consumed via `--parameter-overrides`), §2.7 rollback strategy invoked by failed `stack-deploy.yml` runs.
- [`docs/research/0015-centralized-platform-mcp/04-phase-1-poc.md`](../04-phase-1-poc.md) — milestones M1 and M2 are the consumers of this pipeline.
- [`docs/research/0015-centralized-platform-mcp/implementation/06-cross-account.md`](06-cross-account.md) — owns the `gha-deployer` permission policy detail; this artifact owns only the trust shape.
- [`docs/research/0015-centralized-platform-mcp/implementation/08-testing.md`](08-testing.md) — defines the unit/contract/schema-validate scripts invoked by `pr.yml`.

## 7. Risks protected against

- **R6 — Auth0 M2M cost explosion.** The `cfn-lint` and `cfn-nag` PR gates run every change through a custom rule pack (authored alongside `04-registry.md`) that rejects any registry-seed item declaring a per-handler M2M `client_id` distinct from the service-identity-class catalog. The platform contract's "one M2M per service-identity class" constraint is enforced at merge time by lint, not by quarterly audit alone — any drift fails CI. (Implicit) **No long-lived AWS keys ever exist in repo secrets**, so the GitHub-hosted-runner takeover failure mode cannot exfiltrate AWS credentials — every CI principal is OIDC-federated and ephemeral.
