# AGENTS.md — {{PROJECT_NAME}}

This file is the **single source of truth (SSOT)** that AI agents (Claude Code, Gemini CLI, Codex, etc.)
follow when working in this repository. It is the project brain. No separate `CLAUDE.md`/`GEMINI.md` pointer files are shipped —
Claude Code (v2.1.277+) and Codex read this file natively, and Gemini CLI is pointed at it through
`context.fileName` in `.gemini/settings.json`.

This file must be **self-contained** — the P0/P1 tiers below are readable here without loading any
other file. The only `@` import allowed here is the memory index (see "Memory path override" below):
harnesses that expand imports auto-load the index, and the rest read it as a path pointer.

> If you add a `CLAUDE.md` (or `CLAUDE.local.md`), Claude Code **stops reading this file** (fallback,
> not merge). If you really need one, make its first line `@AGENTS.md`.

## Memory path override

This project's auto-memory SSOT is `.claude/memory/`.
- The system default path (`~/.claude/projects/.../memory/`) is not used.
- All memory reads/writes happen under `.claude/memory/`.
- `MEMORY.md` is the (single) index; type prefixes are `project_`/`feedback_`/`reference_`/`user_`.
- Only `user_*.md` is personal; everything else is shared with the team.

Memory index:

@.claude/memory/MEMORY.md

## .claude/ infrastructure

Overview in [.claude/README.md](.claude/README.md); each subdirectory README carries the
authoring skeleton and conventions.

| Directory | Role | Details |
| :--- | :--- | :--- |
| `agents/` | subagent definitions (code-reviewer, security-audit, db-migration, sdlc-*, agent-evolve) | [README](.claude/agents/README.md) |
| `commands/` | custom slash commands (fix-issue, sdlc-cycle, sonar, knowledge-graph) | [README](.claude/commands/README.md) |
| `hooks/` | enforced gates — pre-commit, auto-format, observe-lite, memory reminders | [README](.claude/hooks/README.md) |
| `memory/` | project memory SSOT — MEMORY.md index + type-prefixed files | [README](.claude/memory/README.md) |
| `rules/` | context-aware rules — `paths:`-scoped conditional loading | [README](.claude/rules/README.md) |
| `skills/` | situational procedures — review, status, search-first, memory-factcheck, security-precheck, docs-sync, grill-me, handoff, ... | [README](.claude/skills/README.md) |
| `workflows/` | stored Workflow orchestration scripts (`*.js`) — rules-audit example | [README](.claude/workflows/README.md) |
| `scripts/` | repo-local helpers — knowledge_graph.py (doc graph + link checker) | [README](.claude/scripts/README.md) |

`settings.json` holds the deny rules and hook bindings. For doc-consistency checks and
onboarding, run `/knowledge-graph`.

## Project overview

<!-- Give a one-line description of {{PROJECT_NAME}} here: stack, goal, scope. -->

## Stack

<!-- e.g. Next.js 15 (frontend) / Spring Boot 3.x · Java 17 · Gradle (backend) -->

## Commands

<!-- Build/test/run commands. e.g. ./gradlew build | bun run dev -->

## Conventions

- New skills/agents use the `{{PROJECT_NAME}}-` prefix namespace
- Detailed conventions live in the path-scoped rules under `.claude/rules/`
- Stack-specific conventions → see the priority tiers below

## Priority tiers (P0/P1/P2)

### P0 — Absolute rules (AI and humans, no exceptions)
Stop work immediately and escalate to the user on a P0 violation.

- **Security**: never expose secrets/tokens/passwords in code, logs, or issues
- **Data**: get explicit user consent before `DELETE/DROP/TRUNCATE` in a production DB
- **git**: confirm before `force push` / `reset --hard`. Never stage `.env`
- **Auth**: never add a new unauthenticated API endpoint

#### Stack-specific P0

The P0 rules of the stack you selected are **inlined below** at bootstrap time. They do not depend
on a reference link, so they stay reachable on harnesses that never load `.claude/`. Full
conventions live in `.claude/rules/<stack>.md`.

<!-- STACK P0 -->

### P1 — Required (within AI's autonomous execution scope; blocks PR on violation)

- Always include the issue number in the branch name, commit, and PR/MR title
- Pass type checks and lint before committing (auto-gated by `.claude/hooks/pre-commit.sh`)
- New features must come with at least 1 test
- Never commit directly to `main`/`develop` → always use a feature/fix/chore branch

### P2 — Recommended (review comments, exceptions negotiable)

- Per-function cognitive complexity (CC) at or below 15 (`.claude/hooks/cc-check.py` warns)
- One file = one responsibility (consider splitting over 300 lines)
- Tag TODO/FIXME with an issue number

## Workflow

1. **Register an issue** → 2. **Create a branch** (`feat/issue-<N>-<slug>`) → 3. **Implement** →
4. **Pass the pre-commit gate** → 5. **Create a PR/MR** → 6. **Review** → 7. **Merge + close the issue**

Issue-closing conventions vary by forge → see `.claude/rules/forge.md`.
GitHub = merging a PR with `Closes #N` in the body auto-closes it. GitLab 19 = `Closes #N` auto-close works in practice, but verify with `glab issue view <N>` after merge — close manually only if still `opened`.

## Multi-agent · parallel sessions

Every worker (session, subagent, persona) touching this repo concurrently isolates itself in
its **own git worktree** — this section exists because two parallel sessions sharing one
checkout once cross-contaminated each other's work.

- Preemptive isolation: `git worktree add ../{{PROJECT_NAME}}-<slug> -b <type>/issue-<N>` —
  one session = one worktree = one issue = one branch.
- The primary clone stays a mirror of the default branch (pull/read only — **never**
  `checkout`/`switch` there; switching branches in a shared folder changes the ground under
  other sessions).
- `git add` explicit files only, never directories or `-A` — avoids absorbing another
  session's uncommitted work.
- If `git status` shows changes you didn't make, stop and check for a parallel session before
  proceeding.
- When parallel subagents modify files concurrently, `isolation: "worktree"` is required.
- After merge: always remove the worktree and delete the local branch on the spot.
- Worktree orchestrators (e.g. Orca): when an external tool manages worktrees, delegate
  creation and removal to it — never run `git worktree add`/`remove` by hand on a worktree
  the orchestrator owns (it desyncs the tool's state). The isolation principle (one session
  = one worktree = one issue = one branch) applies unchanged; the "remove after merge" rule
  is then fulfilled through the orchestrator's own cleanup.

Role-based agents: `.claude/agents/sdlc-*.md` (developer/tester/verifier).
SDLC automation: see the `/sdlc-cycle` command.
