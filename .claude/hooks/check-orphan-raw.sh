#!/usr/bin/env bash
# Stop-hook: surface orphan raw files in knowledge/raw/sources/ that aren't
# referenced by any wiki/sources/<slug>.md. Silent on clean repo / clean wiki.
# Pure bash — no LLM call, no curator dispatch. The full health-check is
# /kb-lint. See knowledge/SCHEMA.md §7.
#
# Stop-hook output convention: emit JSON with a `systemMessage` field on
# stdout to display a one-line message to the user. Anything else stays
# silent. See https://code.claude.com/docs/en/hooks for details.
#
# Portable to bash 3.2 (macOS default) and BSD find — no mapfile, no -printf.

set -o pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
RAW_DIR="$REPO_ROOT/knowledge/raw/sources"
WIKI_DIR="$REPO_ROOT/knowledge/wiki/sources"

# Defensive: skip when the wiki isn't scaffolded yet (fresh clone, branch
# without the knowledge tree, etc.). We don't want to nag in those cases.
[ -d "$RAW_DIR" ] || exit 0
[ -d "$WIKI_DIR" ] || exit 0

# Collect orphans. An orphan = a raw filename that no wiki/sources/*.md
# references (frontmatter `raw_path:` field or any inline link). Grep is
# good enough for this scale. We loop on full paths and derive the basename
# with parameter expansion (portable to BSD find).
orphans=()
first_orphan=""
while IFS= read -r filepath; do
  [ -z "$filepath" ] && continue
  filename="${filepath##*/}"
  case "$filename" in
    README*|.*) continue ;;
  esac
  if ! grep -q -F -r --include='*.md' "$filename" "$WIKI_DIR" 2>/dev/null; then
    orphans+=("$filename")
    [ -z "$first_orphan" ] && first_orphan="$filename"
  fi
done < <(find "$RAW_DIR" -maxdepth 1 -type f 2>/dev/null | sort)

count="${#orphans[@]}"
[ "$count" -eq 0 ] && exit 0

# Emit JSON with systemMessage. Escape any double-quotes in filenames just
# in case (rare, but safer than not).
if [ "$count" -eq 1 ]; then
  msg="⚠️ 1 orphan raw file in knowledge/raw/sources/: ${first_orphan} — run /kb-ingest knowledge/raw/sources/${first_orphan}, or /kb-lint for full health-check."
else
  msg="⚠️ ${count} orphan raw files in knowledge/raw/sources/ (e.g., ${first_orphan}) — run /kb-ingest <path> on each, or /kb-lint for full health-check."
fi

# Escape backslashes and double-quotes for JSON.
msg_json="${msg//\\/\\\\}"
msg_json="${msg_json//\"/\\\"}"
printf '{"systemMessage": "%s"}\n' "$msg_json"
exit 0
