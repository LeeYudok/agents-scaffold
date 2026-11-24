#!/bin/sh
# Install the yd-git-ship commit-msg hook into the current repo.
#
#   1. copy commit-msg.sh to <repo>/scripts/commit-msg.sh (tracked; commit it)
#   2. write a tiny .git/hooks/commit-msg that runs that script
#
# Does not touch global git config. Re-run to update the repo copy.
# Usage: ~/.claude/skills/yd-git-ship/scripts/install-hook.sh [--check]
set -eu

src="$(cd "$(dirname "$0")" && pwd)/commit-msg.sh"
top=$(git rev-parse --show-toplevel)
hooks=$(git rev-parse --path-format=absolute --git-path hooks)
dst="$top/scripts/commit-msg.sh"
hook="$hooks/commit-msg"
marker='# yd-git-ship'

if [ "${1:-}" = "--check" ]; then
  ok=0
  [ -f "$dst" ] && cmp -s "$src" "$dst" || { echo "scripts/commit-msg.sh missing or differs from the skill copy"; ok=1; }
  grep -q "$marker" "$hook" 2>/dev/null || { echo "hook not installed: $hook"; ok=1; }
  [ "$ok" -eq 0 ] && echo "commit-msg hook OK"
  exit "$ok"
fi

if [ -e "$hook" ] && ! grep -q "$marker" "$hook"; then
  echo "refusing: $hook exists and is not ours; merge it by hand" >&2
  exit 1
fi

mkdir -p "$top/scripts" "$hooks"
if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
  echo "scripts/commit-msg.sh up to date"
else
  cp "$src" "$dst"; chmod +x "$dst"
  echo "wrote scripts/commit-msg.sh (git add + commit it)"
fi

cat > "$hook" <<'HOOK'
#!/bin/sh
# yd-git-ship: run the repo's tracked commit-msg check (works in every worktree).
script="$(git rev-parse --show-toplevel)/scripts/commit-msg.sh"
[ -x "$script" ] || { echo "commit-msg: $script not found, skipping" >&2; exit 0; }
exec "$script" "$@"
HOOK
chmod +x "$hook"
echo "installed $hook"
