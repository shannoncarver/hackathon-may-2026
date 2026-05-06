---
status: Accepted
date: 2026-05-06
category: skills-management
---

# Decision 0023 — `ha-debug` skill bundle layout

**Status:** Accepted (2026-05-06).

## Context

[Decision 0018](0018-ts-debugger-architecture.md) created the `ha-debug` TypeScript CLI at the repo root (`hackathon-may-2026/ha-debug/`) and a paired skill protocol at `.claude/skills/ha-debug/SKILL.md`. The skill's bash invocations resolved the CLI via `cd "$(git rev-parse --show-toplevel)"`, which only works when the operator's cwd is somewhere inside a `hackathon-may-2026` worktree.

Operators who hit auth tickets while working in a different repo (notably `Harmony-Auth`, the system this debugger targets) could not invoke the skill — the slash-command bash failed before discovery even started. This is a real ergonomics tax and contradicts the "default skill for any LINQ authentication problem" framing in [Decision 0022](0022-ha-debug-ssm-discovery.md).

The repo already has an established self-contained-skill pattern: [`skills/verify-user-authorization/`](../../skills/verify-user-authorization/SKILL.md) ships SKILL.md and `scripts/` together inside the skill folder, and `.claude/skills/verify-user-authorization` is a relative symlink into it. The skill resolves its own scripts via the `${CLAUDE_SKILL_DIR}` environment variable Claude Code injects when the skill runs — making the skill cwd-independent and trivially symlinkable to `~/.claude/skills/` for global use.

## Decision

Relocate `ha-debug` to the same self-contained-bundle layout. Three rules.

### Rule 1 — Bundle layout

```
hackathon-may-2026/
├── skills/
│   └── ha-debug/
│       ├── SKILL.md           ← canonical operational protocol
│       └── cli/               ← canonical TypeScript CLI
│           ├── package.json
│           ├── tsconfig.json
│           ├── package-lock.json
│           └── src/
│               ├── cli.ts
│               ├── auth.ts
│               ├── audit.ts
│               ├── aws-session.ts
│               ├── discovery.ts
│               ├── errors.ts
│               ├── types.ts
│               ├── resolve-subject.ts
│               ├── assemblers/
│               └── clients/
└── .claude/
    └── skills/
        └── ha-debug → ../../skills/ha-debug   ← relative symlink
```

The CLI's npm dependencies install at `skills/ha-debug/cli/node_modules/` (gitignored). Per-clone dep install is `npm install --prefix "${CLAUDE_SKILL_DIR}/cli"`.

### Rule 2 — Use `${CLAUDE_SKILL_DIR}` for every CLI invocation

The skill's bash never references `git rev-parse --show-toplevel` or any cwd-relative path. Every CLI invocation in `SKILL.md` and `.claude/commands/ha-debug.md` resolves through `${CLAUDE_SKILL_DIR}`:

```bash
# CLI dependency check (Step 0a)
test -d "${CLAUDE_SKILL_DIR}/cli/node_modules" && \
test -f "${CLAUDE_SKILL_DIR}/cli/node_modules/tsx/package.json" && \
echo "DEPS_OK" || echo "DEPS_MISSING"

# One-time install
npm install --prefix "${CLAUDE_SKILL_DIR}/cli"

# Doctor (Step 0b)
npx --prefix "${CLAUDE_SKILL_DIR}/cli" tsx "${CLAUDE_SKILL_DIR}/cli/src/cli.ts" doctor --environment dev

# Any subcommand
npx --prefix "${CLAUDE_SKILL_DIR}/cli" tsx "${CLAUDE_SKILL_DIR}/cli/src/cli.ts" <subcommand> --environment dev [options]
```

Result: the skill works from any cwd — a `hackathon-may-2026` worktree, a Harmony-Auth worktree, the user's home directory, anywhere Claude Code is running.

### Rule 3 — Global symlink for cross-repo use

To use `ha-debug` from a non-`hackathon-may-2026` directory, the operator runs once:

```bash
ln -s "$(pwd)/skills/ha-debug" ~/.claude/skills/ha-debug
```

(Run from the `hackathon-may-2026` repo root.) After that, Claude Code auto-loads the skill on any session, regardless of which repo or directory the operator is in. Per-clone `npm install --prefix "${CLAUDE_SKILL_DIR}/cli"` still runs once.

This mirrors the install instructions in [`skills/verify-user-authorization/SKILL.md`](../../skills/verify-user-authorization/SKILL.md). Eventually a publishable npm package may obviate this step, but the symlink is the right primitive for the demo and for repo-quality reference.

## Alternatives Considered

### Alternative A — Keep `ha-debug/` at repo root, point the skill at it via relative path

Less moving. SKILL.md would compute the CLI path as `${CLAUDE_SKILL_DIR}/../../ha-debug` (skill at `.claude/skills/ha-debug` → `../../ha-debug`).

**Rejected.** Two problems: (a) `${CLAUDE_SKILL_DIR}/../../ha-debug` only works when the skill is symlinked from inside this repo's `.claude/skills/`. If the operator symlinks it into `~/.claude/skills/ha-debug`, the relative path resolves to `~/.claude/ha-debug` which does not exist. (b) The bundle is no longer self-contained — `verify-user-authorization`'s install instructions don't apply.

### Alternative B — Publish the CLI as an npm package (`@linq/ha-debug-cli`)

Operators run `npx -y @linq/ha-debug-cli doctor` from anywhere, no checkout needed.

**Rejected for this PR; potential follow-up.** Requires npm registry publishing, version management, and CI wiring. The bundle layout is reversible to this if the demo grows into a real product; not worth blocking the demo on.

### Alternative C — Vendor the CLI as a single-file bundle (`esbuild --bundle`)

Ship a pre-bundled `dist/ha-debug.js` and skip the per-clone `npm install`.

**Rejected.** The CLI is small enough that one `npm install` is fine, and bundling adds a build step the demo doesn't need.

## Consequences

- **No more `cd "$(git rev-parse --show-toplevel)"` in any skill bash.** Cwd is irrelevant; `${CLAUDE_SKILL_DIR}` carries the skill's own path.
- **Per-clone npm install moves** from `npm install --prefix ha-debug` (run from repo root) to `npm install --prefix "${CLAUDE_SKILL_DIR}/cli"` (works from any cwd). Stale `ha-debug/node_modules/` on existing clones is now orphaned; a one-line `rm -rf ha-debug` cleans up.
- **Global use is one symlink command away.** `ln -s "$(pwd)/skills/ha-debug" ~/.claude/skills/ha-debug` makes the skill available in any Claude Code session.
- **Decisions 0018, 0021, 0022 historical references** to `ha-debug/` and `ha-debug/.env` describe the state-of-the-world at the time those decisions were made; they remain accurate as historical context. New work points to `skills/ha-debug/cli/`.
- **`.claude/settings.local.json`** on existing clones contains stale Bash permission grants for the old paths. Harmless; operators can prune at leisure.
- **The `package.json` `bin` entry (`./dist/cli.js`)** is now a relative path inside `skills/ha-debug/cli/`. Unaffected by the move — the build/bin shape didn't change.

## References

- [Decision 0018](0018-ts-debugger-architecture.md) — original `ha-debug` architecture.
- [Decision 0021](0021-ha-debug-credential-migration.md) — credential migration + setup preflight.
- [Decision 0022](0022-ha-debug-ssm-discovery.md) — SSM-driven resource discovery.
- [`skills/verify-user-authorization/SKILL.md`](../../skills/verify-user-authorization/SKILL.md) — reference layout for self-contained skills (the pattern this decision adopts for `ha-debug`).
- [`skills/ha-debug/SKILL.md`](../../skills/ha-debug/SKILL.md) — the operational protocol after relocation.
- [`skills/ha-debug/cli/`](../../skills/ha-debug/cli/) — the relocated TypeScript CLI.
