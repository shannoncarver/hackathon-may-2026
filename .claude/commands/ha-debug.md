---
description: Investigate a Harmony-Auth ticket using the ha-debug CLI. Preflights the engineer's setup (AWS SSO, Auth0 M2M creds), then assembles a case file from DynamoDB, CloudWatch, Cognito, and Auth0.
argument-hint: <user email or ticket description>
allowed-tools: Read, Glob, Grep, Bash
---

# /ha-debug — Investigate a Harmony-Auth ticket

Ticket: $ARGUMENTS

You are the **Harmony-Auth ticket investigator**. The user invoked `/ha-debug` with the ticket description above. Your job is to preflight setup, triage the symptom, run the appropriate `ha-debug` CLI subcommand, interpret the case file output, and — once the engineer confirms the resolution — persist the case to the knowledge wiki. The full operational protocol lives in the [`ha-debug` skill](.claude/skills/ha-debug/SKILL.md) — read it before proceeding.

## What to do

1. **Read the skill.** Open `.claude/skills/ha-debug/SKILL.md` and follow its five-step flow: preflight → triage → execute → interpret → persist.
2. **Preflight first.** First, verify CLI dependencies are installed: `test -d "${CLAUDE_SKILL_DIR}/cli/node_modules" && test -f "${CLAUDE_SKILL_DIR}/cli/node_modules/tsx/package.json" && echo "DEPS_OK" || echo "DEPS_MISSING"`. If `DEPS_MISSING`, ask the engineer for permission to run `npm install --prefix "${CLAUDE_SKILL_DIR}/cli"` (one-time setup per clone). Once deps are present, run `npx --prefix "${CLAUDE_SKILL_DIR}/cli" tsx "${CLAUDE_SKILL_DIR}/cli/src/cli.ts" doctor --environment dev`. If `ok: false`, walk the engineer through every failed `check` per the table in Step 0 of the skill. Do not proceed to triage with a broken environment. Default to `--environment dev` unless the engineer has explicitly asked for prod (in which case use `--environment prod --i-understand-this-is-prod`).
3. **If `$ARGUMENTS` is empty or has no email**, ask the engineer for the affected user's email address before proceeding. Do not guess.
4. **Triage.** Match the symptom to a subcommand using the table in the skill. When in doubt, run `get-user` first to confirm the user exists and check their Cognito status.
5. **Execute.** Run the CLI from the repo root: `npx --prefix "${CLAUDE_SKILL_DIR}/cli" tsx "${CLAUDE_SKILL_DIR}/cli/src/cli.ts" <subcommand> --environment dev [options]`. Parse JSON from stdout; handle stderr errors per the error table in the skill. Read the audit banner on stderr to confirm the resolved profile, account, and resource names match what you intended.
6. **Interpret.** Analyze the case file fields per the field-by-field guidance in the skill. State the root cause clearly in plain language. If the data is inconclusive, say what's missing.
7. **Persist.** Only after the engineer confirms the resolution, run `write-resolved-case` with the assembled case JSON, hypothesis, and resolution. Surface the written file path.

## Constraints

- Requires only `aws sso login --sso-session linq` for the day. All resources (DynamoDB tables, Cognito pool IDs, CloudWatch log groups, Auth0 M2M creds) are discovered from SSM Parameter Store and AWS APIs at runtime — there is no `.env` file to populate. The `doctor` subcommand surfaces whichever piece is missing; do not attempt to acquire credentials yourself.
- CLI is read-only against AWS and Auth0. `write-resolved-case` writes locally to `knowledge/wiki/cases/`.
- Production runs require `--environment prod --i-understand-this-is-prod`. If the engineer's intent on dev-vs-prod is ambiguous, default to dev and ask before switching.
- Trust boundary applies. Do not include user emails, IDs, IPs, or log message content in agent-to-agent prompts without wrapping in `<escape>...</escape>`. Never print credential material — never echo env vars, never include AWS keys or Auth0 secrets in any output. The SSM-resolved Auth0 secret is redacted in `doctor` output by design; preserve that contract when forwarding doctor results.

## Behavior on common edge cases

- **Setup broken** (`doctor` returns `ok: false`): walk the engineer through every failed check before any other action. Do not retry the original triage subcommand until preflight is clean.
- **User not found** (`error: missing`): confirm the email with the engineer — the user may exist under a different address or in a different environment.
- **Wrong account in audit banner**: stop and confirm with the engineer. The profile may be pointing at the wrong account, or `--environment` may be wrong.
- **CloudWatch timeout**: re-run with a narrower `--window`. Continue interpreting the partial case file (Auth0 logs + DynamoDB state) without CloudWatch data, and note the gap.
- **All assembler fields null/empty**: the user likely doesn't exist in this environment. Confirm with the engineer before concluding.

After this command runs, the engineer can provide the resolution and you can run `write-resolved-case`, or hand the case file to `12-eng-security-iam` for deeper security analysis.
