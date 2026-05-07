# Auth0 Health Metrics—Reference

What each section of `/auth0-management stats` measures, what counts as a healthy baseline, and what to drill into when something looks off. The skill produces these as part of its summary.

## `daily`—daily volume time series

**Source:** `GET /api/v2/stats/daily?from=YYYYMMDD&to=YYYYMMDD`

**What you get:** an array of `{date, logins, signups, breached_password_detections}` per day in the window.

**Useful baselines:**

- **Logins:** stable workday-to-workday for an established tenant. Big day-over-day swings (>2x) usually mean either a launch event or an integration outage. The sandbox tenant has highly variable load; one or two test runs can dominate a day.
- **Signups:** zero on most days for an internal sandbox is normal. Sudden non-zero signups during a quiet period are worth a glance.
- **Breached-password detections:** zero is the healthy baseline. Any non-zero entry means a user attempted login with a credential that's appeared in a known breach corpus—flag the user via `ha-debug get-user --email`.

**Drill-down:** if a day looks anomalous, run `/auth0-management logs --window <date>` to see the raw events.

## `mau`—monthly active users (rolling 30 days)

**Source:** `GET /api/v2/stats/active-users`

**What you get:** a single integer.

**Useful baselines:**

- For a sandbox tenant, MAU is a small handful (test users + developers). Watching MAU on a sandbox tells you how much manual exercise the tenant is getting.
- Sudden jumps on a stable tenant are noteworthy—could indicate a load test or a misconfigured client pointed at the wrong tenant.

**Note:** the endpoint is fixed at 30 days. There is no `--window` knob for this section; whatever window the user asks for, MAU is always 30 days.

## `failures`—failure-event counts

**Source:** derived from `GET /api/v2/logs` with `type:f|fp|fu|fsa|fco|fcoa AND date:[start TO end]`.

**What you get:** total failure count plus a breakdown by event type code.

**Healthy baselines:**

- **Failure rate** (failures ÷ (failures + successes)) varies by tenant but a healthy production tenant typically sits **under 5%**. Sandbox tenants run higher because of test runs.
- **Type mix:** `fp` (wrong password) dominating is a normal-life-of-an-auth-system pattern. **`fu` (invalid email/username) trending up** suggests credential-stuffing or scraping attempts—the attacker is guessing emails. **`fco`/`fcoa` (origin / cross-origin failures) trending up** suggests a frontend deploy went wrong (allowed-origins drifted).

**Cap:** capped at 1,000 results from the API search ceiling. If `capped: true`, the count is a lower bound.

**Drill-down:** run `/auth0-management logs type:fu AND date:[<start> TO *]` to see invalid-email events with timestamps and IPs. Cluster by IP via `auth0-analytics` (when that skill exists) for brute-force signatures.

## `mfa-adoption`—MFA-related events ÷ successful logins

**Source:** derived from `GET /api/v2/logs`. Numerator = `gd_auth_succeed | gd_auth_failed | gd_enrollment_complete | mfar`. Denominator = `type:s`.

**What you get:** numerator count, denominator count, ratio rounded to 3 decimals.

**Healthy baselines:**

- For tenants that **require** MFA, this should approach 1.0. Below 0.5 means a meaningful share of successful logins are bypassing MFA—usually a connection misconfiguration (`enabledClients` allows a client that has MFA off, or a connection has MFA disabled at the connection level).
- For tenants that **offer** MFA but don't enforce, anywhere from 0.05 to 0.5 is typical depending on user education.

**Important caveats:**

- The metric is approximate. Both numerator and denominator are individually capped at 1,000, so the ratio drifts on high-traffic windows—surface this to the user when `capped: true`.
- A user can produce one successful login and multiple `gd_auth_succeed` events (per-step), so the ratio can exceed 1.0 occasionally.

**Drill-down:** `ha-debug assemble-mfa-not-enforced-case --email <user>` for a single user; `ha-debug get-connection --name <connection>` for connection-level MFA policy.

## `top-connections`—auth providers by successful login

**Source:** derived from `GET /api/v2/logs` with `type:s AND date:[start TO end]`, grouped by `connection`.

**What you get:** total successful logins, plus the top 5 connections by login count.

**Useful for:**

- Confirming the expected primary connection is dominant (e.g., `Username-Password-Authentication` for an internal tenant)
- Spotting connections that should be retired—if you see a connection in the top 5 that's supposed to be deprecated, that's a real finding
- Migration tracking—when moving from one connection to another, this is the timeline view

**Cap:** total successful logins capped at 1,000 (API ceiling). The top-5 ranking is robust to capping unless a long tail is being truncated in a way that affects the rank order.

## Cross-section gotchas

- **Sandbox tenant log retention is short.** Auth0 retention varies by plan. Empty `daily` arrays for older windows usually mean retention has expired, not that traffic was zero.
- **Stats endpoints aren't real-time.** `/api/v2/stats/daily` lags by up to 24 hours. Today's row may be a partial count or absent.
- **MAU lags too.** Auth0 computes the active-users metric daily, not on-demand; expect at most a 24-hour delay.

## When something looks off—runbook

1. **Failure rate up:** check the `failures.by_type` mix. `fp` up = users forgot passwords (probably benign). `fu` up = attempted enumeration (suspect). `fco` up = frontend / allowed-origins issue.
2. **MAU dropped sharply:** confirm sandbox traffic—was a test pipeline disabled?
3. **MFA adoption rate dropped:** `ha-debug get-connection` to inspect MFA policy on the top-1 connection.
4. **Breach detections appeared:** identify users via `/auth0-management logs type:pwd_leak`, then `ha-debug get-user --email` for state, and notify the user to rotate.
5. **Top connection list changed:** check if a new client / IdP is pointing at the tenant that wasn't expected.
