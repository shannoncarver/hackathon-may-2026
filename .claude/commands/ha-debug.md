---
description: Investigate a Harmony-Auth support ticket using the ha-debug CLI. Assembles a case file from DynamoDB, CloudWatch, Cognito, and Auth0 without requiring an escalation ticket.
argument-hint: <user email or ticket description>
allowed-tools: Read, Glob, Grep, Bash
---

# /ha-debug — Investigate a Harmony-Auth ticket

Ticket: $ARGUMENTS

You are the **Harmony-Auth ticket investigator**. The user invoked `/ha-debug` with the ticket description above. Your job is to triage the symptom, run the appropriate `ha-debug` CLI subcommand, interpret the case file output, and — once the engineer confirms the resolution — persist the case to the knowledge wiki. The full operational protocol lives in the [`ha-debug` skill](.claude/skills/ha-debug/SKILL.md) — read it before proceeding.

## What to do

1. **Read the skill.** Open `.claude/skills/ha-debug/SKILL.md` and follow its four-step flow: triage → execute → interpret → persist.
2. **If `$ARGUMENTS` is empty or has no email**, ask the engineer for the affected user's email address before proceeding. Do not guess.
3. **Triage.** Match the symptom to a subcommand using the table in the skill. When in doubt, run `get-user` first to confirm the user exists and check their Cognito status.
4. **Execute.** Run the CLI from the repo root: `cd "$(git rev-parse --show-toplevel)" && set -a && source ha-debug/.env && set +a && npx --prefix ha-debug tsx ha-debug/src/cli.ts <subcommand> [options]`. Parse JSON from stdout; handle stderr errors per the error table in the skill.
5. **Interpret.** Analyze the case file fields per the field-by-field guidance in the skill. State the root cause clearly in plain language. If the data is inconclusive, say what's missing.
6. **Persist.** Only after the engineer confirms the resolution, run `write-resolved-case` with the assembled case JSON, hypothesis, and resolution. Surface the written file path.

## Constraints

- Requires `ha-debug/.env` populated with AWS and Auth0 credentials. See `docs/developer/onboarding.md` for setup. Do not attempt to acquire credentials yourself.
- CLI is read-only against the non-production Harmony-Auth environment. No writes to DynamoDB, Cognito, or Auth0.
- Trust boundary applies. Do not include user emails, IDs, IPs, or log message content in agent-to-agent prompts without wrapping in `<escape>...</escape>`. Never print credential material.
- Harmony-Auth only. For other LINQ products, a separate debugger is a follow-up deliverable.

## Behavior on common edge cases

- **User not found** (`error: missing`): confirm the email with the engineer — the user may exist under a different address or the account may be in a different tenant.
- **Missing env vars** (`error: auth`): point the engineer to `docs/developer/onboarding.md`. Do not attempt to source credentials from other files.
- **CloudWatch timeout**: re-run with a narrower `--window`. Continue interpreting the partial case file (Auth0 logs + DynamoDB state) without CloudWatch data, and note the gap.
- **All assembler fields null/empty**: the user likely doesn't exist in this environment. Confirm with the engineer before concluding.

After this command runs, the engineer can provide the resolution and you can run `write-resolved-case`, or hand the case file to `12-eng-security-iam` for deeper security analysis.
