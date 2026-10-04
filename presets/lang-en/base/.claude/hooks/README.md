# hooks/ — Automation rules (hook scripts)

The harness runs these automatically on events (before/after tool calls, etc.). "Always/every time do X" automation must live here to be enforced.
The `hooks` block in `settings.json` wires events to scripts.

**Exit code convention**: `exit 2` = block the action, `exit 0` = allow.

Included: `pre-commit.sh` — pre-commit verification skeleton. Stack presets (e.g. springboot) append build verification.
Scripts need execute permission (`chmod +x`).

## instinct-lite (session observation → habit extraction)

A lightweight version of ECC continuous-learning-v2. No background observer — just two hooks:

- `observe-lite.sh` (PostToolUse, Bash|Edit|Write) — compactly logs tool calls to
  `.claude/memory/observations/<session>.jsonl` (secret masking, 2MB cap per session, auto-pruned after 7 days, not committed).
- `stop-memory-remind.sh` (Stop) — reminds once per session to save memory. If the observation log has
  20+ lines, it also prompts extraction of recurring patterns (repeated error fixes, user corrections, repeated workflows)
  into `instinct_*.md` memories.

See [../memory/README.md](../memory/README.md) for the instinct format.

## Codex/agy hook adapters (#65)

`hook-adapter.py` generates Codex `.codex/hooks.json` and agy `.agents/hooks.json` from the hooks in `settings.json`
(`--harness codex|agy|all`), and at run time converts the harness input to Claude format and calls the scripts in this
directory unchanged. Write hooks in Claude format only.

- Carried over: `PostToolUse` (Bash/Edit/Write → Codex `Bash`/`apply_patch`, agy `run_command`/`write_to_file`, ...) and
  `Stop`. Codex also gets `SessionStart` and `UserPromptSubmit`.
- Not carried over: `PreToolUse` (the commit gate lives in `.git/hooks`) and prompt-type hooks.
- Needs `python3`. The project path is provided as `CLAUDE_PROJECT_DIR`.
- Codex runs them only after project trust plus hook-definition trust (`/hooks`). agy runs them without a trust prompt.
