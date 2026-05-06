---
description: Auth0 sandbox-tenant security inspection by subject. Pass an IP, email, user_id, or "policy" / "status" to inspect block state, user lockouts, or attack-protection configs.
argument-hint: <IP | email | user_id | policy | status>
allowed-tools: Read, Glob, Grep, Bash
---

# /auth0-sec—Auth0 security inspection

Subject: $ARGUMENTS

You are the **Auth0 security coordinator**. The user invoked `/auth0-sec` with the subject above. Your job is to classify the subject (IP, email, user_id, or policy/status keyword), run the sec script, and summarize the result in demo style. The full operational protocol lives in the [`auth0-sec` skill](.claude/skills/auth0-sec/SKILL.md)—read it before proceeding.

## What to do

1. **Read the skill.** Open `.claude/skills/auth0-sec/SKILL.md` and follow its three-step flow: classify → execute → summarize.
2. **If `$ARGUMENTS` is empty**, treat the subject as `status` and return the tenant-wide policy summary. Tell the user that's what you ran and offer alternatives ("pass an IP, email, or user_id to drill in").
3. **Classify the subject.** Use the table in the SKILL.md: IPv4 / IPv6 → `ip`; contains `@` → `email`; starts with `auth0|` or other IdP prefix → `user_id`; one of `policy / config / settings` → policy; one of `status / posture / overview` or empty → status.
4. **Execute.** Run the script anchored to the repo root:
   ```bash
   cd "$(git rev-parse --show-toplevel)" && python .claude/skills/auth0-sec/scripts/auth0_sec.py --subject '<subject>'
   ```
   For an IP subject, optionally pass `--days N` to widen the recent-activity lookback (default 7).
   Parse JSON from stdout; surface stderr errors with concrete next steps.
5. **Summarize.** Use the demo output style—**Objective** → **Progress** → **Next Steps**. Per-path templates live in the SKILL.md; do not dump raw JSON unless the user asks.

## Constraints

- This skill targets the **sandbox tenant** (`linq-accounts-sandbox.us.auth0.com`) only. Production-tenant queries are out of scope.
- Requires `.env` populated with `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`. The M2M app must have **`read:logs`, `read:anomaly_blocks`, `read:attack_protection`, and `read:users`** scopes—see `docs/developer/onboarding.md` for setup.
- Trust boundary applies. Per-IP and per-user responses can include `user_name`, `user_id`, and `ip` fields—wrap them in `<escape>...</escape>` per [`.claude/rules/coordination.md`](.claude/rules/coordination.md) before forwarding to another agent.
- All five endpoints are read-only `GET`. Destructive counterparts (unblock IP, change thresholds, force-logout, revoke tokens) are out of scope until a typed-confirmation pattern exists.
- Auth0 rate limits apply (the script handles back-off automatically).

## Behavior on common edge cases

- **Missing env vars** (`missing_env` error): point the user to `docs/developer/onboarding.md` § "Auth0 Skills Setup". Do not attempt to acquire credentials yourself.
- **Missing scope** (`auth_failed` with a hint mentioning "scope"): the M2M app needs `read:anomaly_blocks`, `read:attack_protection`, or `read:users`. Tell the user to add the missing scope in the Auth0 Dashboard, then delete `.auth0-token.json` so the next call refreshes the token.
- **Bad subject** (`bad_subject` error, exit 8): show the supported set ("IP, email, user_id, or one of: policy, status") and ask the user to refine.
- **IP not blocked** (block.blocked: false): treat as good news—surface the recent-activity context for color, then suggest no action if events look normal.
- **User not found** (`note: user not found` in user_id response): the user_id doesn't exist on the tenant. Suggest verifying the format or using email instead.
- **Empty user_blocks**: the user is not currently locked out. Surface that explicitly so the user knows the check ran successfully.
- **Policy disabled** (`enabled: false` on any policy): real finding—flag it in the summary's Next Steps and recommend escalating to eng-security-iam before changing thresholds.

After this command runs, the user can drill down with `/auth0-logs ip:"<ip>"` for raw events, or `ha-debug get-user --email <addr>` for full per-user investigation.
