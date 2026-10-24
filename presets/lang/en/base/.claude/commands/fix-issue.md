---
name: fix-issue
argument-hint: [issue-number]
---

Handle issue #$ARGUMENTS (issue-first workflow):

1. Check the issue content (forge CLI — GitHub `gh issue view`, GitLab `glab issue view`)
2. Locate the relevant source files
3. Create a branch: `git checkout -b fix/issue-$ARGUMENTS-<summary>`
4. Implement the minimal fix + write a regression test
5. Confirm the build/tests are green (`./gradlew test` or `npm test`)
6. Commit (referencing `#$ARGUMENTS`) → push → create a PR/MR → merge
7. Close the issue — follow forge convention (see `.claude/rules/forge.md`)

> Forge-specific concrete commands are overridden by the forge preset for this file. Select with `--forge`.
