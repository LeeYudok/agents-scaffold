---
name: sdlc-cycle
description: Automatically runs one SDLC cycle (issue → development → testing → verification → PR/MR) based on an issue or spec, without human intervention.
argument-hint: "<issue-number or spec-path.md> [--no-mr] [--no-issue]"
---

# One SDLC Cycle

Takes an issue number or spec path via `$ARGUMENTS` and runs one cycle of
**issue → development → testing → verification → PR/MR**.
Each phase is a gate: on failure, it stops or rolls back to a previous phase.
Options: `--no-mr` (skip PR/MR), `--no-issue` (skip issue creation).

> Before starting, check: if the argument is a file path, Read it. If not, stop and ask for a path.
> Follow global rules: issue-first, re-confirm the branch right before committing, issue-close convention (`.claude/rules/forge.md`).
> Forge-specific concrete commands (`gh`/`glab`) are overridden by the forge preset for this file.

## Phase 0 — Intake & issue

1. If an issue number, understand the content via the forge CLI (GitHub `gh issue view $N` / GitLab `glab issue view $N`). If a spec, Read it.
2. (Unless `--no-issue`) Create the issue (forge CLI — `gh issue create` / `glab issue create`).
   → Obtain issue number N.
3. Create the branch (if currently on main):
   ```bash
   git checkout -b feature/issue-N-<slug>
   ```

## Phase 1 — Development → subagent `sdlc-developer`

Hand off the issue/spec content and delegate a **minimal-scope implementation**.
Receive the deliverable (list of changed files, requirements met, items not implemented).

## Phase 2 — Testing → subagent `sdlc-tester`

Delegate writing test code based on the AC/TC. Do not execute — writing only.

## Phase 3 — Verification → subagent `sdlc-verifier`

Run the build+test pipeline and report the result.
- **PASS**: proceed to Phase 4
- **FAIL**: receive the failing phase and a root-cause hypothesis → roll back to Phase 1 (or 2) to fix and re-verify. **Maximum 2 retries.** After 2 failures, stop and report the failure in Phase 4.

## Phase 4 — PR/MR (skip if `--no-mr`)

```bash
# Re-confirm the branch right before committing
git branch --show-current

git add -p  # or git add <files>
git commit -m "feat(#N): <feature name>"
git push -u origin feature/issue-N-<slug>
# Create the PR/MR via forge CLI (body includes Closes #N) — see .claude/rules/forge.md for the concrete command
#   GitHub: gh pr create --fill --body "Closes #N"
#   GitLab: glab mr create -t "feat(#N): <feature name>" -d "Closes #N" --fill -y
```

## Phase 5 — Report

| Item | Value |
|------|-----|
| Issue | #N |
| Branch | feature/N-slug |
| Files changed | n |
| Verification | lint/build/test PASS/FAIL, pass count, retry count |
| PR/MR | URL or reason for omission |

Suggest the next action (merge, further fixes, deployment).

---

### Running a single phase standalone

- Development only: hand issue content to `Agent sdlc-developer`
- Testing only: `Agent sdlc-tester`
- Verification only: `Agent sdlc-verifier`
