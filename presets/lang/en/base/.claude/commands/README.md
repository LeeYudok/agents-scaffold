# commands/ — custom slash commands

Invoke a repeated task with `/name`. File name = command name (`fix-issue.md` → `/fix-issue`).
Frontmatter `name`/`argument-hint`, body is the prompt. Receives arguments via `$ARGUMENTS`.

Included: `fix-issue.md`, `sdlc-cycle.md`, `sonar.md`, `knowledge-graph.md` (regenerate the
.claude knowledge graph + broken-link check). Add new ones to match the `{{PROJECT_NAME}}` workflow.
