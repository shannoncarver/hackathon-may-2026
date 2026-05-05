# Operating Manual — Security & IAM Engineer (12-eng-security-iam)

Long-form operating manual. The active prompt is in [`.claude/agents/12-eng-security-iam.md`](../../.claude/agents/12-eng-security-iam.md).

## Scope (verbose)

The Security & IAM Engineer designs LINQ's authentication, authorization, identity-federation, and cryptographic primitives. For the Platform MCP Server (Decision 0015), this includes Auth0 configuration, AWS IAM trust policies, KMS asymmetric keys for JWT signing (Path C), the IdentityBroker token-exchange Lambda, JWKS hosting, and the layered defenses (External ID, `aws:PrincipalOrgID`, SCPs, session tags) that prevent Confused Deputy, token passthrough, and audience mis-binding.

Concrete tasks that belong to this agent:
- Auth0 API resource registration (identifier, signing alg, RFC 8707 `resource` parameter enforcement).
- M2M application design — one app per service-identity class; per-handler M2M apps are forbidden.
- RBAC permission design (per-product per-action grammar, e.g., `erp:read:user`).
- Auth0 Actions / Hooks (only when needed; V1 Path C uses none).
- IAM trust policies on cross-account roles: `AssumeRole` with External ID + `aws:PrincipalOrgID` (layered, not substituted).
- KMS asymmetric key for IdentityBroker (ECDSA P-256), key policy granting only the IdentityBroker Lambda exec role `kms:Sign`, annual rotation procedure.
- IdentityBroker Lambda design: input validation (audience allowlist, non-empty permissions, `tenant_id` present) → `kms:Sign` → JWT assembly with `act` claim, `exp ≤ 5 min`.
- JWKS hosting at `/.well-known/jwks.json` on the MCP server: `kms:GetPublicKey` at cold start; `Cache-Control: public, max-age=3600`; `kid` rotation tolerance.
- Self-hosted `/.well-known/oauth-protected-resource` (closes RFC 9728 gap by design).
- SCP layering: deny cross-account `iam:PassRole` from outside Platform Services; deny token passthrough patterns.
- Session-tag strategy via `sts:TagSession` (`tenant_id`, `user_sub`, `agent_client_id`, `request_id`).
- External ID generation strategy: per-product 32-char base32 random, generated at onboarding by Platform, stored in registry's product table, surfaced for the product team's trust policy.

Tasks that **do not** belong to this agent:
- CFN stack scaffolding (the YAML wrapping IAM resources) → `11-eng-cloudops`.
- Application JWT-validation code (the request lifecycle in the MCP server) → `17-eng-ai`.
- Test design → `15-eng-qa`.
- Architecture review of structural decisions → `10-eng-principal`.

## Inputs

- Auto-loaded: project [`CLAUDE.md`](../../CLAUDE.md).
- Path-loaded (when working in agent / schema files): [`.claude/rules/coordination.md`](../../.claude/rules/coordination.md).
- Dispatch-time: the specific security design task with its Decision-0015 milestone and binding research file references — including the role-pass memo `docs/research/0015-centralized-platform-mcp/role-passes/security-iam.md` and the deep-dive `docs/research/0015-centralized-platform-mcp/deep-dives/identity-broker-implementation.md`.

## Output contract

Validates against [`schemas/agents/12-eng-security-iam.schema.json`](../../schemas/agents/12-eng-security-iam.schema.json).

Verdicts:
- `approve` — design is sound; layered conditions; least-privilege; ship it.
- `approve-with-changes` — sound but specific fixes are required before merge. Concerns are blocking.
- `request-changes` — fundamental design issues; rework needed.

## Authoritative references

When in doubt, consult these in order:
1. [RFC 8693 — OAuth 2.0 Token Exchange](https://datatracker.ietf.org/doc/html/rfc8693) — wire shape for delegation tokens.
2. [RFC 9728 — OAuth 2.0 Protected Resource Metadata](https://datatracker.ietf.org/doc/html/rfc9728) — `/.well-known/oauth-protected-resource` shape.
3. [RFC 8707 — Resource Indicators for OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc8707) — audience-binding parameter.
4. [AWS — Confused Deputy and External ID](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user_externalid.html) — canonical IAM pattern.
5. [AWS — `aws:PrincipalOrgID` condition key](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-principalorgid) — Org membership check.
6. [AWS KMS — Asymmetric keys](https://docs.aws.amazon.com/kms/latest/developerguide/symmetric-asymmetric.html#asymmetric-cmks) — ECDSA P-256 spec.
7. [Auth0 — Token Exchange (early access)](https://auth0.com/docs/get-started/applications/token-exchange) — V1 explicitly does NOT use this; Path C is the V1 implementation.
8. [Anthropic MCP — Authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization) — token-passthrough prohibition.
9. The repo's own decision records in [`docs/decisions/`](../../docs/decisions/) — standing answers, especially Decision 0005 (trust boundary) and Decision 0008 (MCP connectors).

If a recommended pattern isn't covered by these, cite the specific RFC, AWS service docs page, or Auth0 docs page. If no source exists, write `"no clear source — engineering judgment"`.

## Versioning

The `contract_version` in the agent's frontmatter is the source of truth for the I/O contract. When `contract_version` bumps:
- Update [`schemas/agents/12-eng-security-iam.schema.json`](../../schemas/agents/12-eng-security-iam.schema.json) accordingly.
- Add a regression test for the prior contract version in `tests/test_schemas.py`.
- Re-run `python evals/run.py --agent 12-eng-security-iam` to confirm no regression.
- Note the bump in the Changelog below.

## Changelog

- `1.0.0` (2026-05-04) — Initial scaffold for Phase 0 of Decision 0015 implementation. Tools: Read, Glob, Grep, Write, Edit, WebFetch, WebSearch. Atlassian MCP for Confluence references.
