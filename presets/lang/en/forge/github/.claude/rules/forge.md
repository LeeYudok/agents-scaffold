# Forge Workflow — GitHub

<!-- No paths → always loaded. Injected by the forge-github preset. -->

This project uses **GitHub** as its issue/PR forge.

- **CLI**: `gh` (issue/pr)
- **Create an issue**: `gh issue create -t "<title>" -b "<body>"`
- **View an issue**: `gh issue view <N>`
- **Create a PR**: `gh pr create --fill --body "Closes #<N>"`
- **Auto-close**: `Closes #N` (or `Fixes`/`Resolves`) in the PR body or commit message **automatically closes the issue on merge** — no manual close needed.
- **Review & merge**: `gh pr merge --squash`
- **Long bodies**: for bodies containing fenced code, tables, or backslashes, write to a file first and use `gh issue create -F body.md` / `gh pr create -F body.md` (avoids inline escaping failures and ARG_MAX limits).
