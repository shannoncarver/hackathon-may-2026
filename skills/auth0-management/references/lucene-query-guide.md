# Auth0 Logs — Lucene Query Syntax Guide

> **Purpose:** This reference is consumed by an LLM to translate natural-language
> prompts into valid Lucene queries for the Auth0 Management API
> `/api/v2/logs` endpoint's `q` parameter. Use it together with
> `auth0-event-codes.md` for event type code lookups.
>
> **Important — relative dates:** Auth0's Lucene implementation does **not**
> support relative date syntax (e.g., `now-24h`). When the user says "last 24
> hours", "this week", "yesterday", etc., compute the actual `YYYY-MM-DD` date
> using today's date before building the query.

---

## 1. Searchable Fields

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `type` | string | `type:fp` | Event type code — see `auth0-event-codes.md` |
| `user_name` | string | `user_name:"jane@linq.com"` | Email or username of the authenticating user |
| `user_id` | string | `user_id:"auth0\|507f..."` | Auth0 user ID — **must escape the pipe** (`\|`) |
| `connection` | string | `connection:"Username-Password-Authentication"` | Name of the Auth0 connection used |
| `client_name` | string | `client_name:"LINQ Portal"` | Application (client) display name |
| `client_id` | string | `client_id:"abc123def"` | Application (client) ID |
| `ip` | string | `ip:"203.0.113.45"` | IP address of the authenticating client |
| `date` | date | `date:[2026-05-01 TO 2026-05-04]` | ISO date; supports range syntax (see below) |
| `description` | string | `description:"Wrong email"` | Human-readable event description text |
| `hostname` | string | `hostname:"linq-sandbox.us.auth0.com"` | Auth0 tenant hostname |

---

## 2. Syntax Rules

### Operators and grouping

- Boolean operators **must be UPPERCASE**: `AND`, `OR`, `NOT`.
- Parentheses group sub-expressions: `(type:f OR type:fp) AND user_name:"jane@linq.com"`.
- `NOT` negates the immediately following term: `NOT type:s`.

### Quoting

- Multi-word or special-character values **must be double-quoted**: `client_name:"LINQ Portal"`.
- Single-word values may be unquoted: `type:fp`.

### Wildcards

- `*` wildcard is supported but **requires at least 3 literal characters before it**.
  - Works: `user_name:jan*`
  - Fails silently: `user_name:j*`
- Single-character `?` wildcard is **not supported**.

### Date ranges

- Inclusive range (both endpoints included): `date:[2026-05-01 TO 2026-05-04]` — square brackets.
- Exclusive range (endpoints excluded): `date:{2026-05-01 TO 2026-05-04}` — curly brackets.
- Open-ended range: `date:[2026-05-01 TO *]` — star for unbounded end.
- Accepted formats: `YYYY-MM-DD` or full ISO 8601 (`2026-05-01T01:00:00`).

### Escaping

- Pipe `|` in values: escape as `\|` — e.g., `user_id:"auth0\|507f1c..."`.
- Colon `:` inside a value: escape as `\:`.
- All other Lucene special characters (`+ - && || ! ( ) { } [ ] ^ " ~ * ? : \ /`) should be escaped with `\` when they appear inside a value.

### Case sensitivity

- **All searches are case-sensitive.** `type:F` does **not** match `type:f`.

---

## 3. Example Translations

The table below shows how to convert common natural-language requests into valid Lucene queries.

| # | Natural Language | Lucene Query |
|---|-----------------|--------------|
| 1 | "failed logins in the last 24 hours" | `type:f AND date:[2026-05-03 TO *]` |
| 2 | "wrong password attempts for jane@linq.com" | `type:fp AND user_name:"jane@linq.com"` |
| 3 | "all authentication failures for LINQ Portal" | `(type:f OR type:fp OR type:fu) AND client_name:"LINQ Portal"` |
| 4 | "suspicious login attempts from IP 1.2.3.4" | `ip:"1.2.3.4" AND (type:f OR type:fp OR type:fu)` |
| 5 | "successful logins this week" | `type:s AND date:[2026-04-28 TO *]` |
| 6 | "blocked accounts" | `type:limit_wc` |
| 7 | "MFA failures" | `(type:gd_auth_failed OR type:feoobft OR type:fepft OR type:fertft)` |
| 8 | "password reset failures" | `type:fcpr` |
| 9 | "all events for user auth0\|abc123" | `user_id:"auth0\|abc123"` |
| 10 | "failed logins from Google OAuth" | `type:f AND connection:"google-oauth2"` |
| 11 | "rate-limited IPs" | `(type:limit_mu OR type:limit_wc)` |
| 12 | "successful signups today" | `type:ss AND date:[2026-05-04 TO *]` |
| 13 | "cross-origin auth failures" | `type:fcoa` |
| 14 | "all failures between May 1 and May 3" | `(type:f OR type:fp OR type:fu) AND date:[2026-05-01 TO 2026-05-03]` |
| 15 | "client credentials exchange failures" | `type:feccft` |
| 16 | "logout events this month" | `(type:slo OR type:flo) AND date:[2026-05-01 TO *]` |

> **Date note:** Examples 1, 5, 12, 14, and 16 use hard-coded dates computed
> from a reference date of 2026-05-04. When translating relative dates at
> runtime, always compute the actual `YYYY-MM-DD` value from the current date.
> Auth0 does **not** support relative date syntax like `now-24h`.

---

## 4. Common Pitfalls

| Pitfall | Detail |
|---------|--------|
| **Case sensitivity** | `type:F` will not match — event codes are lowercase. Always use `type:f`. |
| **Pipe in `user_id`** | Auth0 user IDs contain a literal `|`. Always escape it: `user_id:"auth0\|507f..."`. Omitting the backslash produces a malformed query. |
| **Wildcard minimum characters** | The wildcard `*` requires 3+ leading characters. `user_name:j*` fails silently and returns no results. Use `user_name:jan*` instead. |
| **Max query length** | Very long `q` values can trigger a `414 URI Too Long` error. If this happens, simplify the query — reduce OR clauses, narrow the date range, or split into multiple API calls. |
| **Default searched fields** | When no field prefix is provided, Auth0 searches these fields: `client_name`, `connection`, `description`, `ip`, `log_id`, `type`, `user_name`. Omitting the field prefix can return unexpected matches. Always specify the field explicitly. |
| **Boolean operator case** | `and`, `or`, `not` (lowercase) are treated as literal search terms, not operators. Always use `AND`, `OR`, `NOT`. |
| **Unquoted multi-word values** | `client_name:LINQ Portal` searches `client_name:LINQ` AND the default fields for `Portal`. Always quote: `client_name:"LINQ Portal"`. |
