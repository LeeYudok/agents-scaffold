#!/usr/bin/env bash
# Stop hook — once per session, remind whether non-trivial learnings have been saved under .claude/memory/.
set -uo pipefail

input="$(cat)"
sid="$(printf '%s' "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || true)"
[ -z "$sid" ] && sid="nosession"

f="/tmp/claude_memsync_${sid}"
[ -f "$f" ] && exit 0
touch "$f"

reason="Pre-stop check (once per session): confirm whether any non-trivial learning from this session — infra gotchas, root causes of recurring debugging, user preferences, external resource pointers — has been saved as a file under .claude/memory/ with a one-line entry added to the MEMORY.md index. Exclude anything already captured by code, git history, or AGENTS.md. If it's already saved, or there's nothing new worth saving, it's fine to just end."

# instinct-lite: if this session's observation log is substantial enough, also prompt habit (instinct) extraction
# (observe-lite.sh truncates session_id to 32 chars when logging, so look it up truncated the same way)
obs="${CLAUDE_PROJECT_DIR:-.}/.claude/memory/observations/${sid:0:32}.jsonl"
if [ -f "$obs" ] && [ "$(wc -l < "$obs" 2>/dev/null || echo 0)" -ge 20 ]; then
  reason="$reason

Additionally (instinct-lite): scan the observation log at ${obs} for recurring patterns — repeated fixes for the same error, a practice that stuck after a user correction, a repeated workflow — and if found, save one as instinct_<slug>.md (frontmatter with trigger/confidence 0.3~0.9/evidence, one action in the body). If it overlaps an existing instinct, just update its confidence. Skip this if no recurring pattern is found."
fi

python3 -c "
import json, sys
reason = sys.argv[1]
print(json.dumps({'decision': 'block', 'reason': reason}))
" "$reason" 2>/dev/null || printf '{"decision":"block","reason":"Before ending the session: confirm whether any new learning has been saved under .claude/memory/. If not, it is fine to just end."}\n'
