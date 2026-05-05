# Implementation 11 — Repo Layout, Ownership, and Contributing

**Decision:** [`0015-centralized-platform-mcp`](../../../decisions/0015-centralized-platform-mcp.md) — Phase B governance backbone for the `linq-platform-mcp` repository.
**Owner:** 11-eng-cloudops (CloudOps Engineer).
**Status:** Draft for Phase B implementation.
**Effort estimate:** `1.5 d [ASSUMED]`.

## 1. Overview

This artifact specifies the source-control layout, ownership model, branch protection, contributing flow, and SDK versioning policy for the `linq-platform-mcp` repository — the Platform Services-owned monorepo that holds CloudFormation, the MCP Server Lambda, the IdentityBroker Lambda, the registration API, and the `@linq/mcp-handler-sdk`. Per cross-cutting decision **CC-2**, this is a single platform repo paired with **per-product handler repos** owned by product teams; the 13 implementation artifacts in this hackathon repo are reference material only — the production code stand-up happens in the new `linq-platform-mcp` repo. The contributing flow operationalizes the 7-step onboarding workflow from [`role-passes/platform.md`](../role-passes/platform.md). The pattern coexists with [Decision 0008](../../../decisions/0008-mcp-connectors.md): per-user OAuth (Atlassian) is for documentation-fetch agents; the broker pattern is for product-data agents — different problem domains, both valid.

## 2. Concrete artifacts

### 2.1 Full directory tree — `linq-platform-mcp`

```
linq-platform-mcp/
  .github/
    workflows/                       # GitHub Actions (see 02-github-actions.md)
      pr.yml                         # cfn-lint + cfn-nag + actionlint + unit + contract
      main.yml                       # OIDC → sandbox deploy on main merge
      release.yml                    # Signed-tag deploy; V1 prod = sandbox
      reusable-stack-deploy.yml      # Callable workflow per nested stack
      reusable-test.yml              # Callable workflow per test tier
    CODEOWNERS                       # See 2.2 below
    pull_request_template.md         # Risk-register R-numbers checklist
    ISSUE_TEMPLATE/
      handler-onboarding.md          # Used by product teams to track 7-step flow
      runbook-incident.md            # Links to runbooks/ after on-call event
  infra/                             # CloudFormation (see 01-cloudformation.md)
    master.yaml
    stacks/
      01-network.yaml
      02-secrets.yaml
      03-mcp-server.yaml
      04-registry.yaml
      05-identity-broker.yaml
      06-audit.yaml
      07-product-handler-trust.yaml  # Deployed to product account
      bootstrap/
        platform-bootstrap.yaml      # OIDC provider + deploy roles (Platform Services)
        product-bootstrap.yaml       # OIDC provider + deploy roles (product account)
    schemas/                         # JSON Schemas published to S3 by 04-registry-seed
      <product>.checkUserAccess/
        1.0.0/
          input.json
          output.json
    params/
      dev.json
      stage.json
      prod.json
  src/
    mcp-server/                      # MCP Server Lambda (see 03-mcp-server.md)
      package.json
      src/
        index.ts
        auth.ts
        routes/
        errors.ts
        audit.ts
      test/
        unit/
    identity-broker/                 # IdentityBroker Lambda (see 05-identity-broker.md)
      package.json
      src/
      test/unit/
    registration-api/                # Registry write API (see 04-registry.md)
      package.json
      src/
        lint/                        # mcp-handler-lint rule implementations
      test/unit/
  sdk/
    handler/
      typescript/                    # @linq/mcp-handler-sdk — TypeScript
        package.json
        src/
        CHANGELOG.md
      python/                        # linq-mcp-handler-sdk — Python (PEP 440)
        pyproject.toml
        src/
        CHANGELOG.md
  test/
    unit/                            # Cross-package unit suites
    integration/                     # Deployed-sandbox + real Auth0 dev tenant
    e2e/                             # The 10 V1 acceptance criteria
  runbooks/
    mcp-server-unavailable.md
    tenant-scope-rejection.md
    on-call-boundary.md
    egress-ip-allowlist.md           # R24 procedure for product network teams
  docs/
    contributing.md                  # 7-step onboarding flow (see 2.4 below)
    sdk-versioning.md                # @linq/mcp-handler-sdk policy (see 2.5)
    coexistence-decision-0008.md     # Broker vs per-user OAuth pattern boundary
  CODEOWNERS                         # Mirrored at .github/CODEOWNERS for GitHub UI
  CHANGELOG.md                       # Repo-level (separate from SDK CHANGELOGs)
  LICENSE                            # LINQ internal license
  README.md                          # Quickstart, links to 13 implementation artifacts
```

The product team's handler repo is deliberately **out of tree**. A handler repo is named `linq-<product>-mcp-handlers` (for example, `linq-erp-mcp-handlers`), depends on `@linq/mcp-handler-sdk` from LINQ's internal npm/PyPI registry, and owns its own `.github/workflows/` for handler CI plus the registration GitHub Action that writes the registry item via the platform's registration API on merge to `main`. Product handler repos are not branched from `linq-platform-mcp` — they are first-class product-team repos.

### 2.2 `CODEOWNERS` — `.github/CODEOWNERS`

```
# linq-platform-mcp CODEOWNERS
# https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
# Owners are GitHub teams in the @linq org; every PR auto-requests review from the matching team.

# Default: Platform Services owns everything not otherwise routed.
*                                       @linq/platform-services

# CloudFormation, deployment, observability — CloudOps.
/infra/                                 @linq/platform-cloudops
/.github/workflows/                     @linq/platform-cloudops
/runbooks/                              @linq/platform-cloudops
/docs/contributing.md                   @linq/platform-cloudops

# MCP Server, IdentityBroker, registration API — Backend + Security.
/src/mcp-server/                        @linq/platform-backend
/src/identity-broker/                   @linq/platform-security-iam @linq/platform-backend
/src/registration-api/                  @linq/platform-platform-engineering

# IAM trust policies and the Auth0-adjacent stack — Security & IAM gate.
/infra/stacks/05-identity-broker.yaml   @linq/platform-security-iam @linq/platform-cloudops
/infra/stacks/07-product-handler-trust.yaml @linq/platform-security-iam @linq/platform-cloudops

# Handler SDK — Platform Engineering owns the contract; Backend reviews implementation.
/sdk/handler/                           @linq/platform-platform-engineering @linq/platform-backend

# Schemas published to S3 — Platform Engineering owns; CloudOps reviews packaging.
/infra/schemas/                         @linq/platform-platform-engineering

# Tests — QA owns the harness; specialists own the assertions in their domains.
/test/                                  @linq/platform-qa

# Top-level governance docs — Platform Services lead.
/CODEOWNERS                             @linq/platform-services
/.github/CODEOWNERS                     @linq/platform-services
/README.md                              @linq/platform-services
/docs/sdk-versioning.md                 @linq/platform-platform-engineering
/docs/coexistence-decision-0008.md      @linq/platform-services @linq/platform-security-iam
```

The duplicated `CODEOWNERS` at the repo root and `.github/CODEOWNERS` is intentional — GitHub resolves either path, and mirroring removes the "where does it live" foot-gun for new contributors. Source: [GitHub CODEOWNERS docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).

### 2.3 Branch protection on `main` — GitHub UI checklist

Configured under **Settings → Branches → Branch protection rules** for the `main` branch. Source: [GitHub branch protection docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule).

- [x] **Require a pull request before merging**
  - [x] Require approvals — minimum **2**
  - [x] Dismiss stale pull request approvals when new commits are pushed
  - [x] Require review from Code Owners
  - [x] Require approval of the most recent reviewable push
- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - Required checks (must match the job names in `pr.yml`):
    - `cfn-lint`
    - `cfn-nag`
    - `actionlint`
    - `unit-tests`
    - `contract-tests`
    - `schema-validation`
    - `sdk-typescript-build`
    - `sdk-python-build`
- [x] **Require conversation resolution before merging**
- [x] **Require signed commits** — every commit on `main` must carry a verified GPG or SSH signature. Source: [GitHub commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification).
- [x] **Require linear history** — no merge commits; squash or rebase only.
- [x] **Require deployments to succeed before merging** — none in V1; reserved for V2 environment-promotion gating.
- [x] **Lock branch** — off (this protects history; merges are still allowed under the rules above).
- [x] **Do not allow bypassing the above settings** — applies to admins, including Platform Services leadership. The failure mode this prevents is a "just this once" admin bypass that masks a CI regression.
- [x] **Restrict who can push to matching branches** — empty list (force the PR flow for everyone).
- [x] **Allow force pushes** — **off**.
- [x] **Allow deletions** — **off**.

Tag protection rules (under **Settings → Tags**): protect `v*.*.*` from deletion and force-push so signed release tags cannot be rewritten. Source: [GitHub tag protection docs](https://docs.github.com/en/repositories/managing-your-repositorys-releases/managing-releases-in-a-repository#about-release-management).

### 2.4 Contributing guide outline — `docs/contributing.md`

The contributing guide is the canonical, product-facing rendering of the 7-step handler onboarding workflow from [`role-passes/platform.md`](../role-passes/platform.md). Outline:

1. **Prerequisites**
   - Product team's GitHub repo exists; product AWS account is on the registry's account-allowlist (Platform Services gate, Q3 disposition).
   - LINQ Identity team has provisioned an Auth0 M2M client for the agent class that will call the handler (one M2M app per service-identity class — never per-handler; per ADR cost-discipline).
   - LINQ network team has confirmed outbound MCP-server egress IPs are on the product API's allowlist (**R24** mitigation; runbook link below).
2. **Step 1 — Author the handler in the product repo using `@linq/mcp-handler-sdk`.** SDK provides input/output envelope wrappers, error-envelope helpers, schema validators, and `request_id` propagation.
3. **Step 2 — Author `inputSchema` and `outputSchema` (JSON Schema) in the handler repo.** SDK generates a contract-test rig from these schemas. Schemas live in the handler repo for development; CI publishes them to `s3://platform-mcp-schemas/...` on registration (see Step 5).
4. **Step 3 — Run `linq-mcp-local` against the handler.** The SDK ships a local mock MCP server that validates input against `inputSchema`, invokes the handler in `sam local` or container-local mode, validates output against `outputSchema`, and prints a normalized envelope. Zero platform-team interaction at this step.
5. **Step 4 — Open a PR in the product repo.** CI runs unit tests, contract tests, and the platform-published `mcp-handler-lint` (validates registry-item shape, schema syntax, scope spelling, account-allowlist match, owner team exists in the LINQ directory). Lint failures block merge.
6. **Step 5 — Post-merge GitHub Action writes the registry item via the platform's registration API.** New handler enters with `status: "active"`, `visibility.featureFlag: "<team>-canary"`. The MCP server's `tools/list` projects the catalog by authenticated principal — only agents whose identity claim matches the canary flag see the new tool.
7. **Step 6 — Promote by removing the feature flag.** A one-line registry update via the same API. The MCP server emits `notifications/tools/list_changed`; connected agents re-fetch and the tool becomes globally visible to authorized principals.
8. **Step 7 — Platform-team gate (narrow exceptions only).** Platform-team review is required only for: (a) new product account onboarding (new entry in the account-allowlist); (b) new `handlerType` substrate (e.g., adding Fargate as a fourth type — V1 is Lambda-only); (c) new `requiredScopes` value not present in the central scope catalog. None of these fire per-handler — they fire per-product-or-platform-capability and are rare. **A product team adding their 50th read handler hits zero platform-team queues.**
9. **Egress IP allowlist coordination (R24).** Before Step 1, product teams must reconcile the platform MCP server's outbound NAT IPs with their network team's allowlist if any downstream API enforces source-IP gating. Procedure: `runbooks/egress-ip-allowlist.md`. The Atlassian MCP entity in the wiki flags this as a recurring foot-gun across LINQ, so we surface it up front rather than at first 502.
10. **Decision 0008 boundary.** If the agent fetches **documentation** from Confluence/Jira, use the Atlassian per-user OAuth pattern (see `docs/coexistence-decision-0008.md`) — do not register a handler. The broker pattern is for **product-data** agents.

The full guide includes inline diagrams, copy-pasteable CI snippets, an FAQ ("my handler PR has been open 5 days — who do I ping?"), and links to `runbooks/`.

### 2.5 `@linq/mcp-handler-sdk` versioning policy — `docs/sdk-versioning.md`

Versioning follows **SemVer 2.0.0** ([semver.org](https://semver.org/spec/v2.0.0.html)) for both the TypeScript and Python distributions. The two distributions ship in lockstep — a `1.4.2` release of the TypeScript package implies a `1.4.2` release of the Python package against the same wire contract. Failure mode this prevents: a TypeScript handler and a Python handler in two different products binding to silently divergent envelope shapes.

- **MAJOR (`X.0.0`).** Breaking change to the input/output envelope, the error envelope enum, the registry item shape, or the JWT verification contract. A MAJOR bump requires:
  - An ADR amendment to Decision 0015 (or a new decision superseding it).
  - A migration runbook in `runbooks/`.
  - Publication to the internal registry **at least 90 days** before the prior MAJOR is removed.
  - Coordinated comms to product handler owners via the on-call rotation.
- **MINOR (`X.Y.0`).** Additive, non-breaking changes — new helpers, new optional envelope fields, new schema validators that only widen accepted input. New error classes (e.g., the v2 mutation classes `IDEMPOTENCY_CONFLICT`, `PRECONDITION_FAILED`, `PARTIAL_SUCCESS`) ship as MINOR because the enum was reserved at v1; agents pattern-matching on `class` see new variants but never break.
- **PATCH (`X.Y.Z`).** Bug fixes, perf improvements, doc fixes, dependency bumps with no behavior change. PATCH is always safe; product teams should auto-upgrade via Dependabot/Renovate within their handler repo.
- **Pre-release (`X.Y.Z-rc.N`).** Used for IdentityBroker contract changes (the canonical example: future migration from Path C to Auth0 native RFC 8693). Pre-releases are opt-in only; production handlers never depend on `-rc.*`.

**Support windows:**

| Version line | Support state | Active for |
|---|---|---|
| Current MAJOR (`N.x`) | Active — all bug fixes, security patches, new features | Until `(N+1).0.0` ships |
| Previous MAJOR (`(N-1).x`) | Maintenance — security patches and critical fixes only | **180 days** after `N.0.0` ships |
| Older MAJORs | Unsupported — no patches; remove via Dependabot | After 180-day window closes |

**Deprecation window — features within a MAJOR.** A function or field deprecated within a MAJOR line emits a runtime warning for **at least one full MINOR cycle** before removal at the next MAJOR. Deprecations are recorded in `sdk/handler/typescript/CHANGELOG.md` and `sdk/handler/python/CHANGELOG.md` under a `### Deprecated` heading per release.

**Internal registry.** TypeScript packages publish to LINQ's internal npm registry as `@linq/mcp-handler-sdk`. Python packages publish to LINQ's internal PyPI mirror as `linq-mcp-handler-sdk`. Authentication uses the per-team CI service token (rotated quarterly). No public registry exposure — these are internal artifacts.

**Release flow.** Signed git tag (`v1.4.2`) on `main` → `release.yml` workflow (OIDC) → `npm publish` + `twine upload` to internal registries → GitHub Release with auto-generated notes from CHANGELOG. Source: [GitHub Releases docs](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

### 2.6 Coexistence note — `docs/coexistence-decision-0008.md`

[Decision 0008](../../../decisions/0008-mcp-connectors.md) (per-user OAuth via the Atlassian MCP server) and Decision 0015 (the platform broker) are **complementary, not competing** patterns. They serve different problem domains:

| Dimension | Decision 0008 — per-user OAuth | Decision 0015 — platform broker |
|---|---|---|
| Target | External SaaS docs and tickets (Atlassian, future GitHub) | Internal LINQ product data and capabilities |
| Identity model | Per-user OAuth on first invocation | Auth0 M2M agent identity + RFC 8693-shaped user OBO |
| Server topology | Vendor-hosted (Atlassian) or per-vendor MCP server | Single platform-owned MCP server per LINQ Org |
| Catalog | One MCP server per vendor; no central projection | Per-product prefix (`erp.*`, `crm.*`); server-side projection |
| Cross-account dispatch | Not applicable — calls hit the vendor SaaS directly | `sts:AssumeRole` with per-product External ID |
| When to use | Documentation-fetch, ticket-lookup, repo-search agents | Product-data agents that read application records |
| Onboarding | Per-user OAuth consent on first call; no platform code change | 7-step contributing flow above |

If a product team is unsure which pattern applies, the rule is: **does the call land on a LINQ-owned product API in a LINQ AWS account?** If yes, broker (0015). If it lands on a SaaS vendor's API, per-user OAuth (0008). The two patterns will run side by side in the LINQ agent fleet; an agent's `mcpServers:` frontmatter may list both. A product MCP server stood up under the 0008 pattern (e.g., a future LINQ-Slack MCP) would be a **distinct** repo, not a fork of `linq-platform-mcp`.

## 3. Acceptance criteria

Each item below is observable in the deployed `linq-platform-mcp` repo:

- **AC-11.1 — `CODEOWNERS` resolves on every PR.** GitHub auto-requests review from the team named for every changed path. Verifiable via GitHub's pre-merge review-required check; an unowned path triggers no auto-request and is caught by the link audit.
- **AC-11.2 — Branch protection enabled on `main`.** All checkboxes from §2.3 are set. Verifiable via `gh api repos/linq/linq-platform-mcp/branches/main/protection` returning the configured rules. A force push to `main` from any account, including admins, returns HTTP 422.
- **AC-11.3 — Required CI checks block merge.** A PR that fails `cfn-lint`, `cfn-nag`, `actionlint`, or any required test job cannot be merged via the GitHub UI or `gh pr merge`. Verifiable by intentionally breaking each check on a draft PR.
- **AC-11.4 — Signed commits enforced on `main`.** An unsigned commit pushed via PR fails the protection rule and cannot be merged. Verifiable via the green "Verified" badge on every commit in `git log origin/main`.
- **AC-11.5 — `docs/contributing.md` present and referenced from `README.md`.** Renders in GitHub. Each of the 7 steps links to the relevant implementation artifact (01–10) for the deeper detail.
- **AC-11.6 — `docs/sdk-versioning.md` published; CHANGELOGs in both SDK directories.** First SDK release (`1.0.0`) carries an entry in both `sdk/handler/typescript/CHANGELOG.md` and `sdk/handler/python/CHANGELOG.md`.
- **AC-11.7 — `docs/coexistence-decision-0008.md` cross-linked from both ADRs.** Forward-link from 0008 added in a follow-up commit; back-link from 0015 lives here.
- **AC-11.8 — `runbooks/egress-ip-allowlist.md` exists and is linked from the contributing guide.** First product onboarding exercises the runbook end-to-end.

## 4. Effort estimate

`1.5 d [ASSUMED]` — single CloudOps engineer, sequential. Breakdown: directory scaffolding 0.25 d; CODEOWNERS authoring + GitHub team verification 0.25 d; branch protection configuration + protected-tag rules 0.25 d; contributing guide 0.5 d; SDK versioning policy 0.25 d. Excludes the time to create LINQ-org GitHub teams (assumed already in place) and the time to create the LINQ internal npm and PyPI registries (assumed already in place — Q-IMPL.11.1).

## 5. Open questions

- **Q5 — Internal API gateway choice (Kong, Apigee, custom).** From [`05-open-questions.md`](../05-open-questions.md). Disposition for repo layout: V1 dispatcher targets product handler ARNs directly via `sts:AssumeRole`; no gateway integration in V1. If LINQ adopts an internal API gateway in M2+, the dispatcher target becomes `<gateway>/<product>/<handler>` and the `infra/stacks/03-mcp-server.yaml` parameter set adds a `GatewayBaseUrl`. No repo-layout change required today. *Forced-today guess: assume no shared gateway.* `[ASSUMED]`
- **Q8 — Per-user OAuth coexistence with broker.** Disposition: documented in §2.6 and pinned at `docs/coexistence-decision-0008.md`. The two patterns coexist; product teams pick by data-residency criterion (LINQ AWS = broker; SaaS vendor = per-user OAuth). No structural change in the repo — both patterns are first-class.
- **Q-IMPL.11.1 — Internal npm and PyPI registry availability.** Listed as a prerequisite for the SDK versioning policy. If the internal registries are not yet stood up at Phase B kickoff, the SDK ships to a private GitHub Packages namespace (`@linq/`) as an interim destination. *Forced-today guess: GitHub Packages for V1; migrate to internal registry once available.* `[ASSUMED]`
- **Q-IMPL.11.2 — GitHub Org SCM-policy parity.** Whether the LINQ GitHub Org's existing org-level rulesets already enforce signed-commit and force-push-deny defaults, in which case the per-repo branch-protection settings in §2.3 are redundant-by-design rather than the only line of defense. Coordination with LINQ IT/SCM. *Forced-today guess: assume per-repo settings are the sole gate; org-level rulesets are a defense-in-depth layer to confirm in M2.* `[ASSUMED]`

## 6. Cross-references

- [`role-passes/platform.md`](../role-passes/platform.md) — onboarding 7-step workflow (canonical source for §2.4); registry write-path policy-as-code rationale.
- [`role-passes/architecture.md`](../role-passes/architecture.md) — V1 scope-lock posture that drives the "13 implementation artifacts are reference material" framing.
- [`role-passes/cost-reliability.md`](../role-passes/cost-reliability.md) — one M2M app per service identity (cited in §2.4 prerequisites); shared per-product IAM roles.
- [`01-cloudformation.md`](01-cloudformation.md) — the IaC content that lives under `infra/`.
- [`02-github-actions.md`](02-github-actions.md) — the workflow content that lives under `.github/workflows/`; required-check job names referenced in §2.3.
- [`03-mcp-server.md`](03-mcp-server.md) — the Lambda code under `src/mcp-server/`.
- [`04-registry.md`](04-registry.md) — registration API and `mcp-handler-lint` rules invoked at Step 4 of the contributing guide.
- [`05-identity-broker.md`](05-identity-broker.md) — IdentityBroker code under `src/identity-broker/`; SDK MAJOR-bump trigger for any IdentityBroker contract change.
- [`07-poc-handler.md`](07-poc-handler.md) — example of a product-team handler repo against which the contributing guide is validated.
- [`08-testing.md`](08-testing.md) — the test harness under `test/`; required-check job names referenced in §2.3.
- [`10-observability-runbooks.md`](10-observability-runbooks.md) — the three operational runbooks under `runbooks/`; egress-IP runbook referenced in §2.4.
- [`docs/decisions/0008-mcp-connectors.md`](../../../decisions/0008-mcp-connectors.md) — the per-user OAuth pattern that coexists with this broker (§2.6).
- [GitHub CODEOWNERS docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).
- [GitHub branch protection docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule).
- [GitHub commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification).
- [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## 7. Risks protected against

- **R24 — Outbound IP allowlists from agent hosts.** The contributing guide (§2.4) makes egress-IP coordination with each product's network team a Step-0 prerequisite, and `runbooks/egress-ip-allowlist.md` documents the procedure. The wiki entity for the Atlassian MCP flags this as a recurring foot-gun across LINQ; surfacing it up front in the onboarding flow prevents the "first 502 in production" failure mode that would otherwise land in Platform's on-call queue when it belongs to the product network team.
- **Governance — registry-write-path queue (HIGH from `role-passes/platform.md`, not on the numbered R-list).** CODEOWNERS plus the 7-step contributing flow keep the platform-team review gate at boundary expansions only (new account, new substrate, new scope). A product team adding their 50th handler hits zero platform-team queues — this is enforceable because the CODEOWNERS file does not route ordinary handler PRs to `@linq/platform-services` at all (handler PRs live in the product repo, not in `linq-platform-mcp`).
