---
name: skill-evolve
description: A meta-skill that turns user feedback or an agent's failure cases into rules in this repository's skill SKILL.md files. Use on requests like "fix the skill" (스킬 고쳐줘), "bake this mistake into the skill" (이 실수 스킬에 박아줘), "put it in the skill so it doesn't happen again" (다음부터 안 그러게 스킬에 반영해), "/skill-evolve <skill-name> <feedback>", or when the same mistake happens twice and the skill document needs fixing. Proceeds in the order issue registration → batch branch → tests → user approval → commit.
---

# Role

You are a **meta-agent** that evolves skills by converting an agent's failures and the user's feedback into structured guidance. You permanently engrave lessons into the skill document (`SKILL.md`) so that a mistake made once is never repeated.
Going beyond simple text edits, you run an expert-grade, safe workflow: **isolated branch creation, enforced convention checks, and apply-after-confirmation**.

# Trigger

`/skill-evolve <skill-name> <feedback>`

# Workflow

Follow the procedure below strictly in order. No step is skipped.

## Phase 1. Diagnose and isolate

1. **Check state**: Confirm the working tree is clean (`git status -s` is empty). `python3 <skill-path>/scripts/evolve_guard.py clean` does the same thing; if the tree is not clean, it exits 1 and shows the list of changes.
2. **Issue first**: Create an issue in the repository tracker. In the body, write the original feedback, the skill to fix, and who makes the call. Use this number in the branch, commit and PR.
3. **Branch**: Do not commit directly to `main`. If there is a batch branch in progress (`batch/<agent>-<YYYYMMDD>-<8-digit hex>`), build on it; otherwise create a new one from `main`. Generate the hex fresh for each batch with `openssl rand -hex 4` (the same rule as yd-git-ship — a sequence suffix like `-2` collides between sessions).
4. **Read the target**: Read the whole `.claude/skills/<skill-name>/SKILL.md` (for opt-in skills, `presets/skills/personal/.claude/skills/<skill-name>/SKILL.md`) to understand its current content. In an installed project, `.agents/skills/<skill-name>/SKILL.md` is the source and `.claude/skills` is a link to it.

## Phase 2. Analyze and define rules

Analyze the feedback and recent execution logs to derive a clear rule: **what went wrong and how to behave from now on**.
- Add a new gotcha (a common mistake) to the `### Learned warnings` section.
- If an existing procedure is flawed, update the process section.
- If there is a wrong command template, fix it.

## Phase 3. Edit the document (strict editing rules)

Edit `SKILL.md` (with tools) following these principles so that the repository's skill conventions (`.claude/skills/README.md`) are not broken.
- **Keep the frontmatter**: Do not add keys that were not there. A new skill uses only `name` and `description` (keys already present in an existing skill, such as `user-invocable`, are kept).
- **No emoji**: Emoji are strictly forbidden in outputs and skill documents.
- **Preserve existing warnings**: Existing warnings in `Learned warnings` are not deleted unless explicitly invalidated; they accumulate. A date tag (`(YYYY-MM-DD)`) is mandatory.
- Apply edits with an exact file-editing tool such as `replace_file_content`.

After editing, check the rules above mechanically with `python3 <skill-path>/scripts/evolve_guard.py check <skill-name>`.

- A `Learned warnings` line must have the form `- (YYYY-MM-DD) ...`; a date that does not exist on the calendar is a violation.
- A warning that existed at the base (`--base`, default `HEAD`) and has disappeared is a violation. If the user explicitly invalidated the warning, add `--allow-removal`.
- When the task adds a new warning, also check that the section exists with `--require-section`.
- If there is a violation, the exit code is 1.
- If the skill name is missing or escapes the path, the exit code is 2.

## Phase 4. Automated verification (core logic)

Right after the document edit lands on disk, **always run the repository tests** to confirm mechanically that the structural conventions (frontmatter, document assertions and claims, layout, etc.) were not broken. In this repository that is `scripts/dev/run-skill-tests.sh` (per-skill tests) and `python3 -m unittest discover -s tests -p 'test_*.py'` (shared conventions); in other repositories it is that repository's runner (`scripts/run_tests.sh`, etc.).
- If the tests fail (exit code > 0), revert **only the file this skill edited** (`git restore -- <path to that skill's SKILL.md>`). A pathless `git restore .` wipes other changes too. `python3 <skill-path>/scripts/evolve_guard.py verify <skill-name>` runs the tests and reverts in one go, and exits 1 on failure. If the tests pass, the edit is left in place. If no test runner can be found, it exits 2 and the edit is also left in place. Then analyze the cause and edit again. Do not move on to the next step in a violating state.
- Separately from structural verification, run a **mini eval**: run the modified skill on the same kind of input that triggered the improvement, and confirm via a before/after comparison that the point that failed before the improvement is actually fixed. (Cherry-picked from the same-named skill in claude-scaffold, 2026-08-16)

## Phase 5. Review and commit

1. After the tests pass, clearly report the **changes (diff summary)** to the user and get approval to commit.
2. When the user approves (`Y`), `git add` only the edited files, naming them explicitly (`git add .` and `-A` are forbidden). The commit title is `[<model-name>] docs(<skill-name>): <improvement summary> (#N)`, and the author is an agent account (`-c user.name=claude-ai`, etc.) unless a human is committing.
3. Push and open a PR (or MR). Put `Closes #N` in the body, and merge with a merge commit (no squash). If the repository has its own rules, follow them.

# Output format

When asking the user for approval after the tests pass, use the format below.

```text
Proposed improvement
Existing: [quote]
Proposed: [revision]

diff summary:
+ summary of added/changed content
- summary of removed content

Repository tests: [passed]

Commit these changes? (Y/n)
```

## Learned warnings

- (2026-06-20) Absorbed the external `skill-evolve` skill: added quoting of existing content and the diff output format.
- (2026-08-01) Adjusted the target file path (`skills/<skill-name>/SKILL.md`) and the frontmatter format (only `name` and `description` allowed) to fit the doksam-skills structure.
- (2026-08-01) **Flawless upgrade**: applied the meta-agent workflow — preventing direct commits, branch isolation, and mandatory tests (`run_tests.sh`).
- (2026-10-04) Renamed to `yd-skill-evolve`. Dropped the `evolve/` branch and `git add .`, and aligned with the global git rules: issue first → batch branch → explicit-file commit → PR with `Closes #N` (#169).
- (2026-10-05) Use an 8-digit hex instead of a batch-branch sequence number (`-2`). Two sessions on the same day picked the same sequence number and collided. Aligned with yd-git-ship (#205).
- (2026-10-24) With doksam-skills merged into agents-scaffold, this skill became the source. The name is `skill-evolve`, the target paths are `.claude/skills/<skill-name>/` and `presets/skills/personal/.claude/skills/<skill-name>/`, and the default test runner is `scripts/dev/run-skill-tests.sh`. Existing skills' frontmatter keys are kept and only new keys are blocked (agents-scaffold #78).
