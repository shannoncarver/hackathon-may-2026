---
description: Query Auth0 logs for authentication events on the LINQ sandbox tenant. Translates natural-language prompts into Lucene queries.
argument-hint: <natural-language description of what to look for>
allowed-tools: Read, Glob, Grep, Bash
---

# /auth0-logs — Query Auth0 sandbox logs

Query: $ARGUMENTS

You are the **Auth0 logs query coordinator**. The user invoked `/auth0-logs` with the prompt above. Your job is to interpret the natural-language request, build the appropriate Lucene query, confirm with the user, execute the data retrieval script, and summarize the results. The full operational protocol lives in the [`auth0-logs` skill](.claude/skills/auth0-logs/SKILL.md) — read it before proceeding.

## What to do

1. **Read the skill.** Open `.claude/skills/auth0-logs/SKILL.md` and follow its four-step flow: interpret → pre-flight → execute → summarize.
2. **If `$ARGUMENTS` is empty**, tell the user the command needs a natural-language query (e.g., "failed logins in the last 24 hours") and stop. Do not invent one.
3. **Interpret the prompt.** Read `.claude/skills/auth0-logs/references/auth0-event-codes.md` and `.claude/skills/auth0-logs/references/lucene-query-guide.md`. Construct a Lucene query, computing literal `YYYY-MM-DD` dates from today's date (Auth0 has no relative-date syntax).
4. **Pre-flight.** Show the user the constructed query, sort, and max-pages. Ask "proceed?" before execution. Skip only for unambiguous trivial queries.
5. **Execute.** Run the data retrieval script with `set -a && source .env && set +a && python .claude/skills/auth0-logs/scripts/auth0_logs.py --query '<lucene>' --max-pages <N> --sort '<dir>'`. Parse JSON from stdout; surface stderr errors with concrete next steps.
6. **Summarize.** Use the demo output style (Objective → Progress → Next Steps). Cover: total events, breakdown by type, top affected users, notable patterns. Do not dump raw JSON unless asked or `total < 5`.

## Constraints

- This skill targets the **sandbox tenant** (`linq-accounts-sandbox.us.auth0.com`) only. Production-tenant queries are out of scope.
- Requires `.env` populated with `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`. See `docs/developer/onboarding.md` for setup.
- Trust boundary applies. Wrap user-identifiable log fields (`user_name`, `user_id`, `ip`, `description`, `details`, `user_agent`) in `<escape>...</escape>` per [`.claude/rules/coordination.md`](.claude/rules/coordination.md) before forwarding to another agent.
- Sandbox rate limit is 2 req/sec, 10 burst. The script handles backoff automatically; users only see this if they hit it via repeated invocations.

## Behavior on common edge cases

- **Missing env vars** (`missing_env` error): point the user to `docs/developer/onboarding.md` § "Auth0 Logs Setup". Do not attempt to acquire credentials yourself.
- **Zero results**: state explicitly that no matching events were found. If the date range is wide and no events appear, note that sandbox-tenant log retention may be limited (verify in the Auth0 Dashboard → Logs section). Suggest broadening or narrowing the query as appropriate.
- **Capped results** (`capped: true`): surface the reason (`max_pages_reached` or `api_ceiling_1000`) and suggest narrowing — by date range, specific user, specific connection, or fewer OR clauses.
- **Bad query syntax** (`bad_query` error): show the user the query that was attempted and the error message verbatim. Refer them to `.claude/skills/auth0-logs/references/lucene-query-guide.md` § "Common Pitfalls".
- **Rate limited** (`rate_limited` error): wait briefly and offer to retry once. If it persists, suggest narrowing the query.

After this command runs, the user can run `/auth0-logs` again with a more specific query, or hand off the structured logs to another agent for deeper analysis.
