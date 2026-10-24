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

**`yd-*` agents (#78)**: entry points to the `yd-*` skills of the same name — the behavior rules live only in the
skill's `SKILL.md`, and the agent body just tells the agent to follow that skill. The 11 default agents
(`yd-blueprint`, `yd-db-expert`, `yd-frontend-build`, `yd-go-expert`, `yd-mobile-web-planner`, `yd-nextjs-implementer`,
`yd-oracle-expert`, `yd-pg-expert`, `yd-react-expert`, `yd-sqlite-expert`, `yd-writer-kr`) live here; the 4 opt-in ones
(`yd-doksam-ui`, `yd-finguard`, `yd-script-editor`, `yd-sdlc-orchestrator`) live in `presets/skills-personal/.claude/agents/`
and are added with `--with-personal-skills`. Both sets are real source files, not symlinks, and the Codex/agy
versions are generated from them by the rules below.

**Generated for Codex and agy (#64)**: with `--harness codex|agy|all`, these files are generated as Codex
`.codex/agents/<name>.toml` (`developer_instructions` = the body) and agy `.agents/agents/<name>.md` (`name` and
`description` only). This directory stays the source — do not edit the generated files. `name` and `description` must be
one-line values, and a body containing `'''` is skipped for Codex. `tools`, `model` and `memory` are Claude Code only
(agy drops an agent that has them, so the generated files leave them out).

When calling agents from a Workflow script, intensity can also be tuned with `effort`
(low~max) in addition to `model` — see `workflows/README.md`.
