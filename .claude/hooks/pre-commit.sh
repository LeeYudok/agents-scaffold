#!/usr/bin/env bash
# Pre-commit verification. Exits 2 to block the commit on failure.
# Stack presets append build/test verification to the STACK CHECKS section below.
set -euo pipefail

# --- Common: first line of defense against leaking secrets ---
staged=$(git diff --cached --name-only)
if printf '%s\n' "$staged" | grep -qE '(^|/)\.env($|\.)'; then
  echo "Blocked: a .env-type file is staged. Commit is not allowed." >&2
  exit 2
fi

# --- Common: skills have one source, .agents/skills (#61) ---
# .claude/skills is normally a symlink to it. Where symlinks are unavailable it is a copy, and a
# commit is blocked when the staged copy differs from the staged source. Both the layout and the
# comparison come from the index (and HEAD), not the working tree: untracked caches such as
# __pycache__ do not count, and staging the deletion of either side is caught too.
root=$(git rev-parse --show-toplevel)
staged_tree() {
  git -C "$root" -c core.quotePath=false ls-files -s -- "$1" \
    | awk -F'\t' -v p="$1/" '{ split($1, m, " "); print m[1] " " m[2] "\t" substr($2, length(p) + 1) }'
}
# Entries of a path in the index, or in HEAD when its deletion is staged.
tree_entries() {
  local e
  e=$(git -C "$root" ls-files -s -- "$1")
  if [ -z "$e" ] && git -C "$root" rev-parse -q --verify HEAD >/dev/null; then
    e=$(git -C "$root" ls-tree -r HEAD -- "$1")
  fi
  printf '%s' "$e"
}
# Copy layout = both .agents/skills and .claude/skills are tracked (now or in HEAD) and
# .claude/skills holds regular files — the symlink is a single 120000 entry. Repos that never had
# .agents/skills (the template itself, Claude-only projects) are left alone. Here-strings instead of
# `printf | grep -q`, which can fail on SIGPIPE under pipefail.
is_copy_layout() {
  local copy src
  copy=$(tree_entries .claude/skills)
  src=$(tree_entries .agents/skills)
  [ -n "$copy" ] && [ -n "$src" ] && grep -qv '^120000 ' <<<"$copy"
}
if is_copy_layout; then
  src_tree=$(staged_tree .agents/skills)
  copy_tree=$(staged_tree .claude/skills)
  if [ "$src_tree" != "$copy_tree" ]; then
    differ=$(diff <(printf '%s\n' "$src_tree") <(printf '%s\n' "$copy_tree") \
      | awk -F'\t' '/^[<>] / { print $2 }' | sort -u || true)
    echo "Blocked: the staged .claude/skills (copy) differs from its source .agents/skills:" >&2
    printf '%s\n' "$differ" | sed 's/^/  /' >&2
    echo "  Edit each file in .agents/skills, copy it to the same path under .claude/skills," >&2
    echo "  then stage both files by name: git add -- .agents/skills/<path> .claude/skills/<path>" >&2
    echo "  (dropping one side on purpose? the copy layout needs both — or commit with --no-verify)" >&2
    exit 2
  fi
elif [ -f "$root/.claude/skills" ] && [ ! -L "$root/.claude/skills" ]; then
  echo "Warning: .claude/skills is a plain file — a symlink checked out with core.symlinks=false." >&2
  echo "  Claude Code cannot see the skills. Enable symlinks (git config core.symlinks true) and re-checkout it." >&2
fi

# --- STACK CHECKS (presets append here) ---

echo "pre-commit 통과"
exit 0
