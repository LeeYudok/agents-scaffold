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
# .claude/skills is normally a symlink to it. Where symlinks are unavailable it is a copy, and
# a commit is blocked when the staged copy differs from the staged source (index, not the
# working tree — untracked caches such as __pycache__ or .DS_Store do not count).
root=$(git rev-parse --show-toplevel)
staged_tree() {
  git -C "$root" -c core.quotePath=false ls-files -s -- "$1" \
    | awk -F'\t' -v p="$1/" '{ split($1, m, " "); print m[1] " " m[2] "\t" substr($2, length(p) + 1) }'
}
if [ -d "$root/.agents/skills" ] && [ -d "$root/.claude/skills" ] && [ ! -L "$root/.claude/skills" ]; then
  if [ "$(staged_tree .agents/skills)" != "$(staged_tree .claude/skills)" ]; then
    echo "Blocked: the staged .claude/skills (copy) differs from its source .agents/skills." >&2
    echo "  Make the edit in .agents/skills, refresh the copy and stage both:" >&2
    echo "  rm -rf .claude/skills && cp -R .agents/skills .claude/skills && git add .agents/skills .claude/skills" >&2
    exit 2
  fi
elif [ -f "$root/.claude/skills" ] && [ ! -L "$root/.claude/skills" ]; then
  echo "Warning: .claude/skills is a plain file — a symlink checked out with core.symlinks=false." >&2
  echo "  Claude Code cannot see the skills. Enable symlinks (git config core.symlinks true) and re-checkout it." >&2
fi

# --- STACK CHECKS (presets append here) ---

echo "pre-commit 통과"
exit 0
