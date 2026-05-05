---
status: Accepted
date: 2026-05-04
category: skills-management
---

# Decision 0014 — Auth0 logs skill: hybrid approach with swappable auth layer

**Status:** Accepted (2026-05-04).

## Context

Frontline auth debugging on LINQ apps requires querying Auth0 logs — failed logins, rule errors, tenant-specific signal. Today the only path is the Auth0 Dashboard, which is gated behind admin access and offers no natural-language query interface. Engineers, support, and on-call all hit the same wall: the data exists, but the lookup loop is slow and concentrated on a small number of admin holders.

[Decision 0015](0015-centralized-platform-mcp.md) establishes a centralized platform MCP server as the long-term gateway for internal AI access to LINQ product data, with shared M2M apps managed at the platform level under the rule "one M2M app per service-identity class — never per handler." That ADR was promoted to Accepted on 2026-05-04, but the IdentityBroker, registry, and cross-account STS infrastructure described in its M1–M4 plan do not yet exist.

The hackathon needs a working Auth0 query capability now, not at M4. The constraint is to ship something useful immediately without locking in a design that conflicts with the eventual centralized model.

## Decision

Build a standalone skill at `.claude/skills/auth0-logs/` that queries the Auth0 sandbox tenant directly, using a dedicated M2M application with `read:logs` scope. The skill is self-contained — no agent dispatch, no writes — and mirrors the routing skill pattern from [Decision 0011](0011-eval-harness-shape.md)'s skill conventions.

Structure the data-retrieval script (`scripts/auth0_logs.py`) in three layers:

1. **Auth Provider** (swappable). `EnvAuthProvider` reads credentials from `.env` and performs the client-credentials grant against the sandbox tenant. `BrokerAuthProvider` is a placeholder for the centralized-platform mode — when Decision 0015 reaches M4, it implements the broker call and `EnvAuthProvider` is retired.
2. **API Client** (stable). `Auth0LogsClient` handles HTTP, pagination (search-based and checkpoint-based per the Management API contract), rate limiting, and structured errors. Same shape regardless of which auth provider is wired in.
3. **CLI / Output** (stable). argparse interface, JSON to stdout, structured errors to stderr. The `SKILL.md` protocol calls into this layer; query construction and formatting live here.

Specific binding choices:

- **Sandbox only.** Scope is restricted to `linq-accounts-sandbox.us.auth0.com`. Production tenants are out of scope until the centralized platform broker exists.
- **Credential storage.** `.env` is gitignored and holds `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, and `AUTH0_CLIENT_SECRET`. The Management API token caches to `.auth0-token.json` (gitignored, 24-hour TTL) so we don't re-grant on every invocation.
- **Self-contained.** No dispatch into another sub-agent, no writes to Auth0, no chained tool calls beyond the local script. The skill answers a query and exits.

## Alternatives Considered

### Alternative A — Pure Bash + curl + jq

Build the data retrieval as a Bash script using `curl` for HTTP and `jq` for JSON parsing, with the SKILL.md protocol doing all query construction in-prompt.

**Rejected.** Lucene query construction, checkpoint-based pagination via `Link` headers, structured-error envelopes, and rate-limit back-off logic that needs state across requests are all awkward in shell. Python earns its keep here on pagination and error handling.

### Alternative B — Build directly against Decision 0015's IdentityBroker

Skip the standalone phase entirely. Stub out the broker locally and migrate when the real broker exists.

**Rejected.** Forces the hackathon timeline to wait on platform infrastructure that does not yet exist. Couples skill development to broker development. Inverts the "ship value now" constraint.

### Alternative C — AuthProvider Protocol only, no `BrokerAuthProvider` placeholder

Keep the swappable seam (the `AuthProvider` Protocol) but delete the placeholder class. When Decision 0015 M4 lands, the actual broker interface informs the real implementation.

**Adopted in revision.** The Protocol alone is sufficient documentation that the auth source is swappable. The placeholder class committed to an interface shape (`__init__(broker_token, domain)`) that Decision 0015 has not specified in code. See revision noted in Consequences.

## Consequences

- **Positive:** Hackathon gets immediate Auth0 query capability via `/auth0-logs <natural-language>`. No dependency on the centralized platform timeline.
- **Positive:** Three-layer design isolates the auth seam. When Decision 0015 lands at M4, only `BrokerAuthProvider` swaps in; query construction, pagination, formatting, and the `SKILL.md` protocol remain untouched. The migration is one file, not a rewrite.
- **Positive:** Per-skill `.env` credentials are gitignored and scoped to a single M2M app with the minimum permission set (`read:logs` only).
- **Negative:** Per-skill M2M apps violate the Decision 0015 § 09-auth0-config rule "one M2M app per service-identity class — never per handler." This is acceptable as a temporary deviation only because the centralized platform does not yet exist; it must be retired when 0015 reaches M4.
- **Negative:** No automated rotation of the Client Secret. Rotate the Client Secret manually in the Auth0 Dashboard if you suspect compromise.
- **Operational debt:** Retire `.claude/skills/auth0-logs/scripts/auth0_logs.py`'s `EnvAuthProvider` and the standalone sandbox M2M app when [Decision 0015](0015-centralized-platform-mcp.md) M4 lands. Track this debt under [Decision 0015](0015-centralized-platform-mcp.md) M4. When M4 work begins, the centralized-platform handler should subsume this skill's auth seam by adding an `AuthProvider` implementation that integrates with the IdentityBroker. At that point, this decision should be revisited and either superseded or amended.

## Sources

- Auth0 Management API — Logs endpoint: https://auth0.com/docs/api/management/v2/logs/get-logs
- Auth0 Client Credentials Flow: https://auth0.com/docs/api/authentication/client-credentials-flow
- [`knowledge/wiki/entities/auth0-m2m.md`](../../knowledge/wiki/entities/auth0-m2m.md) — Auth0 M2M entity in the LINQ wiki
- [`knowledge/wiki/sources/auth0-client-credentials-flow.md`](../../knowledge/wiki/sources/auth0-client-credentials-flow.md) — ingested source summary
- [Decision 0015](0015-centralized-platform-mcp.md) — centralized platform MCP (target migration)
