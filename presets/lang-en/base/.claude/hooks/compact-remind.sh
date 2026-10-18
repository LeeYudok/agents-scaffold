#!/usr/bin/env bash
# SessionStart(matcher: compact) hook — prompts a re-entry check right after context compaction (#72).
# PreCompact does not support prompt-type hooks, so the old PreCompact prompt hook never ran.
# A SessionStart hook's stdout is added to the model's context.
set -uo pipefail
cat >/dev/null 2>&1 || true

cat <<'MSG'
The context was just compacted. Before continuing, check that the summary still holds the facts needed to re-enter the work (done/in-progress/next steps, key decisions and their rationale, blockers, related issues/branches/files).

- Any non-trivial fact that needs to persist across sessions should be written to `.claude/memory/` as a type-prefixed memory (project_/feedback_/reference_), with a one-line entry added to the `MEMORY.md` index.
- Do not record facts already evident from code/git (that would be duplication).
MSG
