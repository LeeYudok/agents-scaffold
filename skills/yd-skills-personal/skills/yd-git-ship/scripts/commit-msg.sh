#!/bin/sh
# commit-msg hook: enforce the agent commit rules from ~/.claude/ref-git-agents.md.
#
# - AI author (<agent>-ai@<domain>): subject must be "[<model>] <type>: <desc> (#N)".
# - Model tag present but author is not an AI account: rejected (forgot -c user.*).
# - Any author: no "Co-Authored-By: Claude" / "Generated with Claude Code" lines.
# Human commits without a tag are not checked.
#
# Installed by yd-git-ship/scripts/install-hook.sh as <repo>/scripts/commit-msg.sh.
# Trivial typo commit without (#N): YD_TRIVIAL=1 git commit ...

msg_file="$1"
subject=$(grep -v '^#' "$msg_file" | sed -n '/[^[:space:]]/{p;q;}')
author=$(git var GIT_AUTHOR_IDENT | sed -n 's/.*<\([^>]*\)>.*/\1/p')

fail() {
  echo "commit-msg: $1" >&2
  echo "  subject: $subject" >&2
  echo "  rules:   ~/.claude/ref-git-agents.md (yd-git-ship)" >&2
  exit 1
}

if grep -v '^#' "$msg_file" | grep -qiE '^co-authored-by:.*(claude|anthropic)|generated with \[?claude code'; then
  fail 'remove the Claude co-author / "Generated with Claude Code" line'
fi

case "$subject" in
  'Merge '*|'Revert "'*|'fixup! '*|'squash! '*|'amend! '*) exit 0 ;;
esac

types='feat|fix|docs|chore|refactor|test|perf|ci|build|style|revert'
tagged=0
echo "$subject" | grep -qE '^\[[^]]+\] ' && tagged=1

case "$author" in
  *-ai@*) ai=1 ;;
  *) ai=0 ;;
esac

if [ "$tagged" -eq 1 ] && [ "$ai" -eq 0 ]; then
  fail "model tag present but author is $author; commit with -c user.name=<agent>-ai -c user.email=<agent>-ai@<domain>"
fi
[ "$ai" -eq 1 ] || exit 0

[ "$tagged" -eq 1 ] || fail 'AI commit needs a leading model tag, e.g. "[Claude Opus 5.5] docs: ... (#11)"'
echo "$subject" | grep -qE "^\[[^]]+\] ($types)(\([^)]+\))?!?: .+" \
  || fail "type must be one of: $types"
if ! echo "$subject" | grep -qE ' \(#[0-9]+\)$'; then
  [ "${YD_TRIVIAL:-0}" = 1 ] || fail 'subject must end with the issue number " (#N)" (trivial typo: YD_TRIVIAL=1)'
fi
exit 0
