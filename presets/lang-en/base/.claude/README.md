# `.claude/` — Claude Code collaboration assets

Works together with the root `AGENTS.md` (the project brain, loaded natively by the harness).

```
.claude/
├── agents/        AI teammates — subagent definitions
├── commands/      custom slash commands
├── hooks/         rules Claude must follow — hook scripts (exit 2 = block)
├── memory/        project memory SSOT — MEMORY.md index + type-prefixed files
├── rules/         context-aware rules — conditional auto-load via paths frontmatter (native)
├── skills/        situational intelligence — <name>/SKILL.md
├── workflows/     stored Workflow orchestration scripts (*.js)
├── scripts/       repo-local helper scripts (knowledge_graph.py, ...)
└── settings.json  control center — permissions/hooks/model
```

- **memory/** is the auto-memory SSOT. The system default path is not used (`memory/README.md`).
- **rules/** auto-load when working on files matching their `paths:` frontmatter; without paths they load at session start.
- New skills/agents use the project prefix namespace to avoid global collisions.
- Run `/knowledge-graph` to render this ecosystem as a graph and check for broken links.

Each subdirectory `README.md` carries its purpose and authoring skeleton.
