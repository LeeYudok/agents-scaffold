# agents/ — AI teammates (subagent definitions)

Task-specialized subagents. Each agent = one markdown file. Frontmatter:

| Field | Purpose |
|---|---|
| `name` | Agent name |
| `description` | When to delegate (auto-selection criteria) |
| `tools` | Accessible tools (comma-separated) |
| `model` | `sonnet`/`opus`/`haiku`/`inherit` (parent session's model) or a full model ID. Match tier to workload — mechanical scans/bulk repetition=haiku, general implementation/review=sonnet, deep judgment/security=opus |
| `memory` | `user`/`project`/`local` — cross-session context learning |
| `maxTurns` | Max turns before stopping |

Recommend the `{{PROJECT_NAME}}-ag-*` prefix for newly created agents. Bundled example: `code-reviewer.md`.

**Generated for Codex and agy (#64)**: with `--harness codex|agy|all`, these files are generated as Codex
`.codex/agents/<name>.toml` (`developer_instructions` = the body) and agy `.agents/agents/<name>.md` (`name` and
`description` only). This directory stays the source — do not edit the generated files. `name` and `description` must be
one-line values, and a body containing `'''` is skipped for Codex. `tools`, `model` and `memory` are Claude Code only
(agy drops an agent that has them, so the generated files leave them out).

When calling agents from a Workflow script, intensity can also be tuned with `effort`
(low~max) in addition to `model` — see `workflows/README.md`.
