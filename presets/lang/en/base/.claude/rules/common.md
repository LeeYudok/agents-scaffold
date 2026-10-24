# Common Rules ({{PROJECT_NAME}})

<!-- No `paths` → always loaded at session start -->

## Priority tiers

| Tier | Meaning | On violation |
|------|---------|---------------|
| **P0** | Absolute rules — security, data destruction, secret exposure | Stop immediately, escalate to user |
| **P1** | Required — issue linking, type checks, tests | Blocks PR/MR |
| **P2** | Recommended — CC threshold, file size | Review comment |

## P0 — Absolute rules (no exceptions)

- **Secrets**: never expose `.env`/tokens/passwords in code, logs, issues, or chat. Only use via `source`.
- **Data**: get explicit user consent before `DELETE/DROP/TRUNCATE` in production.
- **git**: confirm before `force push` / `reset --hard`. Never stage `.env`.
- **Auth**: never add a new unauthenticated API endpoint.

## P1 — Required

- **Issue-first**: register an issue in the tracker before starting work → embed its number in the branch/commit/PR-MR. Trivial typos are the only exception.
- **Execute git verbs immediately**: "push/merge/commit/sync/pull/deploy" commands are executed right away. Only destructive git operations require confirmation.
- **Re-check branch right before committing**: automated processes may have checked out `main`.
- **Branch strategy**: `main` (prod) / `develop` (integration) / `feature·fix·chore` (work) / `hotfix` (direct to main).
- **Issue closing**: follow the forge convention (`.claude/rules/forge.md`). GitHub = auto-close via `Closes #N`; GitLab 19 = auto-close works, but verify post-merge and close manually if still open.
- **New features require tests**: at least 1 unit/integration test.
- **Version bump before deploy**: right before a push that deploys, ask how to bump the changed service's version manifest (`package.json`/`pyproject.toml`/`Cargo.toml`/`build.gradle`) — patch/minor/major/no-bump — then reflect it in the same commit/push. Defaults: bugfix→patch, new feature→minor, breaking change→major, infra-only (CI/scripts/docs)→no-bump. An explicit "just push" skips the bump. `[discipline]`

## P2 — Recommended

- Keep per-function cognitive complexity (CC) at or below 15 (`cc-check.py` warns).
- Consider splitting files over 300 lines.
- Tag TODO/FIXME with an issue number.

## Security

- `settings.json` `deny` blocks `.env` reads, `rm -rf`, and force push. Add to `allow` cautiously (self-permission gate).
- No `curl` `-v`/`-sv` — verbose headers can leak secrets. Use `--silent` + status code only.

## Communication

- Conversational replies use a light, casual tone. **Code, commits, issue/PR·MR bodies, and docs stay in a standard/professional tone.**
- Status questions get yes/no + a short rationale. Debug from the actual raw error before acting.
- High-impact actions (DB writes, push, deploy) start only after the user gives an explicit go-ahead.

## Code navigation

- If the repo root has a `.codegraph/` directory (CodeGraph pre-indexed knowledge graph), prefer `codegraph explore "<symbol or question>"` (or the `codegraph` MCP tools) over grep/find/file-reading sweeps when locating or understanding code. No `.codegraph/` → skip; indexing is the user's decision.

## Memory

- SSOT is `.claude/memory/`. Type prefixes: `project_`/`feedback_`/`reference_`/`user_`. See `memory/README.md` for details.
- Only `user_*.md` is personal; everything else is shared with the team.
