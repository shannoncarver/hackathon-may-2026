# Auth0 Attack Protection—Glossary and Baselines

What each `/auth0-sec` policy field means in plain language, what counts as a healthy posture, and what to drill into when something looks off.

## Breached Password Detection

**Source:** `GET /api/v2/attack-protection/breached-password-detection`

Auth0 cross-references login passwords against known credential-breach corpuses (HaveIBeenPwned-style). When a user logs in with a credential that's appeared in a public breach, the policy decides what happens.

### Key fields

| Field | Meaning |
|-------|---------|
| `enabled` | `true` to do anything. `false` means breach detection is off; no signal at all. |
| `shields` | List of actions. Common values: `block` (deny login), `admin_notification` (email an admin), and `user_notification` (email the user). Combinations are allowed. |
| `admin_notification_frequency` | How often the admin email fires (immediately / daily / weekly). |
| `method` | Detection method. `standard` (passwords vs. breach corpus) or `enhanced` (broader signals). |

### Healthy baseline

- `enabled: true` for any tenant that handles real user credentials
- `shields` should at minimum include `user_notification` (so users can rotate). `block` is stronger but increases support load
- `admin_notification_frequency: immediately` for security-sensitive tenants

### Drill-down

If a user logged in with a breached credential, `/auth0-logs type:pwd_leak` shows the events. Then `ha-debug get-user --email <user>` for state and contact info.

## Brute Force Protection

**Source:** `GET /api/v2/attack-protection/brute-force-protection`

Tracks repeated failed logins from the same user account. After a threshold, blocks further attempts from involved IPs.

### Key fields

| Field | Meaning |
|-------|---------|
| `enabled` | Master switch. |
| `mode` | `count_per_identifier_and_ip` (default—track per user+IP combo) or `count_per_identifier` (track per user across IPs). |
| `max_attempts` | After this many failures within the window, block. Default is `10`. |
| `allowlist` | IPs and CIDRs that are exempt. Typical: known office / VPN ranges. |
| `shields` | Actions. `block` (deny further attempts), `user_notification` (email the user that someone's trying to break in). |

### Healthy baseline

- `enabled: true`
- `max_attempts` between 5 and 15—under 5 generates false positives from typo-prone humans, over 20 lets brute-force succeed
- `mode: count_per_identifier_and_ip` is the safer default; `count_per_identifier` is stricter but locks legitimate users out faster
- `allowlist` should be small (under 10 entries). A large allowlist suggests broken access control upstream

### Drill-down

If `enabled: false`, that's a real finding—escalate to eng-security-iam. If `max_attempts > 20`, ask whether the relaxed threshold is intentional. The `/auth0-logs type:limit_mu` query shows recent brute-force blocks.

## Suspicious IP Throttling

**Source:** `GET /api/v2/attack-protection/suspicious-ip-throttling`

Tracks failed logins by IP across all users. Catches credential-stuffing attempts (an attacker tries one password against many accounts from one IP).

### Key fields

| Field | Meaning |
|-------|---------|
| `enabled` | Master switch. |
| `shields` | `block` (throttle further attempts), `admin_notification` (email an admin). |
| `allowlist` | IPs and CIDRs that are exempt. **Capped at 100 entries.** |
| `stage.pre-login` | Throttle config before login attempt—`max_attempts` and `rate` (per second). |
| `stage.pre-user-registration` | Throttle config for signup attempts. |

### Healthy baseline

- `enabled: true`
- `pre-login.max_attempts` typically 100 in a 15-minute window
- `allowlist` should not include 0.0.0.0/0 or any wide CIDR—that defeats the purpose
- Both `pre-login` and `pre-user-registration` should be enabled if the tenant accepts signups

### Drill-down

If you see this policy disabled, treat as a real finding—credential-stuffing protection is the table-stakes baseline. The `/auth0-logs type:limit_wc OR type:limit_sul` query shows IPs being throttled.

## IP Block (anomaly endpoint)

**Source:** `GET /api/v2/anomaly/blocks/ips/{ip}`

This is per-IP, not policy. Returns 200 with details if the IP is currently blocked by suspicious-IP throttling, or 404 if not blocked. The `/auth0-sec` script handles both responses cleanly and surfaces a boolean `blocked` field.

### What "currently blocked" means

The IP hit the suspicious-IP-throttling threshold in a recent window. Auth0 will reject login attempts from this IP until either:
- The throttle window expires (typically 15 minutes)
- An admin manually unblocks the IP via `DELETE /api/v2/anomaly/blocks/ips/{ip}` (out of scope for this skill)

### Drill-down

If an IP shows `blocked: true`, run `/auth0-logs ip:"<ip>"` to see the underlying events and decide whether the block is correct or a false positive (e.g., a shared-NAT egress).

## User Blocks (per-user lockout state)

**Source:** `GET /api/v2/user-blocks?identifier=...` or `GET /api/v2/user-blocks/{id}`

Auth0 separately tracks per-user lockout state from too many failed logins on that user's account (different mechanism from suspicious-IP throttling—same effect on the user).

### Response shape

`blocked_for` is an array of `{identifier, ip}` records. Empty array means the user is not currently locked out. Each entry shows which IP tripped the block.

### Drill-down

If a user reports "I can't log in," check this first. If `blocked_for` is non-empty, the user is throttled—wait for the window or unblock manually in the Dashboard. The user's normal credential might still be correct.

## Cross-skill follow-ups

| `/auth0-sec` finding | Next slash command |
|---------------------|--------------------|
| IP currently blocked, want details | `/auth0-logs ip:"<ip>"` |
| Policy enabled but you want to see how often it fires | `/auth0-stats failures` (failure breakdown) |
| User blocked, want full state across systems | `ha-debug get-user --email <addr>` |
| Tenant looks fine, want pattern detection | `/auth0-analytics` (Phase 5) |
