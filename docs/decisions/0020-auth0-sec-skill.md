---
status: Accepted
date: 2026-05-06
category: skills-management
---

# Decision 0020—Auth0 sec skill: subject-driven security inspection atop the shared auth seam

**Status:** Accepted (2026-05-06).

## Context

The auth0-* skill family now has three lenses on the LINQ sandbox tenant: `/auth0-logs` answers "what events?" (Decision 0014), `/auth0-stats` answers "what aggregate?" (Decision 0019). PR #8's `ha-debug` covers the per-user / per-ticket workflow. The remaining gap is **tenant-wide security inspection**—the questions a security responder asks during incident triage:

- "Is IP X blocked right now?"
- "Is user Y locked out?"
- "What's our brute-force threshold? Our breached-password policy? Our suspicious-IP allowlist?"
- "What's our overall security posture?"

Every relevant Auth0 Management API endpoint is read-only `GET`—no infrastructure work needed beyond expanding the existing M2M app's scope set.

The Decision 0014 design isolated the auth seam intentionally so siblings could plug in. Decision 0019 was the first sibling and validated the seam. Decision 0020 is the third skill on the same seam, which is the right moment to confirm the pattern is durable before promoting `_auth0_common.py` to a shared location (deferred—see Consequences).

## Decision

Build a sibling skill at `.claude/skills/auth0-sec/` that imports from `.claude/skills/auth0-logs/scripts/_auth0_common.py` (same `sys.path` trick as `/auth0-stats`). The script (`scripts/auth0_sec.py`) classifies a single `--subject` argument into one of five kinds and dispatches to the appropriate Auth0 endpoint(s). Output is structured JSON; the SKILL.md protocol summarizes in demo style.

Specific binding choices:

- **Subject-driven slash command.** `/auth0-sec <subject>` mirrors `/auth0-logs <prompt>` and `/auth0-stats <window>`—one slash command, multiple intents resolved at the SKILL.md layer. No sub-command CLI; classification is straightforward enough to be inline.
- **Five subject kinds.** IP (IPv4 or IPv6) → `/anomaly/blocks/ips/{ip}` plus a recent `/logs?q=ip:"<ip>"` snapshot. Email → `/user-blocks?identifier=<email>`. user_id (`auth0|...` or other IdP-prefixed) → `/user-blocks/{id}`. The keywords `policy / config / settings` → all three `/attack-protection/*` endpoints. The keywords `status / posture / overview` (or empty) → all three policies plus a "no specific subject probed" header.
- **Same M2M app, additional scopes.** The existing M2M gets three new scopes alongside `read:logs` and `read:stats`: `read:anomaly_blocks`, `read:attack_protection`, and `read:users`. All five are read-only and sandbox-scoped. No new identity. This keeps Decision 0015 § 09-auth0-config's "one M2M app per service-identity class" rule intact.
- **Sandbox only.** Same scope restriction as `/auth0-logs` and `/auth0-stats`. Production access remains gated on Decision 0015 M4.
- **Three-step flow, no pre-flight.** Read-only and narrow surface—nothing to confirm before running. Optional pre-flight only when subject classification is ambiguous; otherwise straight Classify → Execute → Summarize.

## Alternatives Considered

### Alternative A—Sub-command CLI (`/auth0-sec ip 1.2.3.4`)

Make the user disambiguate the subject explicitly via a sub-command word.

**Rejected.** Inconsistent with sibling skills, which both take a free-form argument and let the SKILL.md protocol classify. Sub-commands also push more typing onto the user, and the classification is unambiguous in nearly all cases (an IP is obvious, an email is obvious, a user_id starts with `auth0|`).

### Alternative B—Two separate skills (per-subject and tenant-policy)

Split into `/auth0-blocks` (per-IP and per-user lookups) and `/auth0-policy` (config endpoints).

**Rejected.** Over-fragmented. The two surfaces are connected—a security responder asking "is this IP blocked" usually also wants to know "what's our threshold." Keeping them in one skill means a single protocol covers the full incident-triage flow with one slash command in the menu.

### Alternative C—Build destructive operations now (unblock IP, change thresholds)

Add `DELETE`/`PATCH` counterparts so the skill is fully operational, not just inspection-only.

**Rejected.** Destructive Auth0 operations require a typed-confirmation pre-flight pattern that doesn't yet exist in this repo. Adding it inside `/auth0-sec` would couple a cross-cutting trust-boundary concern to a single skill and likely produce something inconsistent with the eventual project-wide pattern. Deferred until the typed-confirmation pattern lands as a standalone concern.

## Consequences

- **Positive:** Closes the security-inspection gap with one read-only skill. The auth0-* family now covers all four lenses on the sandbox tenant: events, aggregates, security posture, and per-subject lookup.
- **Positive:** Third consumer of `_auth0_common.py` confirms the seam is durable. Promotion of `_auth0_common.py` to a shared location (`.claude/skills/_shared/auth0/`) becomes worth doing—but is intentionally **deferred** here. With three consumers, the migration is one PR; doing it inside this PR would mix two concerns. Tracked as a follow-up that can ship any time before a fourth `auth0-*` skill arrives.
- **Positive:** Cumulative scope set on the M2M app is now `{read:logs, read:stats, read:anomaly_blocks, read:attack_protection, read:users}`—comprehensive but still all read-only.
- **Negative:** The IP-block endpoint cannot be live-validated for a *blocked* IP without manufacturing a real attack pattern. The "not blocked" path is verified pre-merge; the "blocked" path is post-merge or post-incident. This is a real coverage gap acknowledged in the test plan.
- **Negative:** The user-blocks endpoint accepts both `?identifier=<email>` and `/{user_id}` forms, but error handling on a malformed user_id is silent (404 → "not found"). A typo in `auth0|...` looks the same as a real not-found. Acceptable for hackathon scope; a future revision could validate the user_id format before issuing the call.
- **Operational debt:** Same as Decision 0014 / 0019—when Decision 0015 M4 retires `EnvAuthProvider`, this skill comes along automatically. No additional retirement step needed beyond what Decision 0014 already tracks.

## Sources

- Auth0 Management API—Get IP block status: https://auth0.com/docs/api/management/v2/anomaly/get-ips-by-id
- Auth0 Management API—Get user blocks: https://auth0.com/docs/api/management/v2/user-blocks/get-user-blocks
- Auth0 Management API—Breached password detection settings: https://auth0.com/docs/api/management/v2/attack-protection/get-breached-password-detection
- Auth0 Management API—Brute force protection settings: https://auth0.com/docs/api/management/v2/attack-protection/get-brute-force-protection
- Auth0 Management API—Suspicious IP throttling settings: https://auth0.com/docs/api/management/v2/attack-protection/get-suspicious-ip-throttling
- [`knowledge/wiki/entities/auth0-m2m.md`](../../knowledge/wiki/entities/auth0-m2m.md)—Auth0 M2M entity in the LINQ wiki
- [Decision 0014](0014-auth0-logs-skill.md)—first sibling skill (auth0-logs) with the AuthProvider seam
- [Decision 0019](0019-auth0-stats-skill.md)—second sibling (auth0-stats); first reuse of the seam
- [Decision 0015](0015-centralized-platform-mcp.md)—centralized platform MCP (target migration)
