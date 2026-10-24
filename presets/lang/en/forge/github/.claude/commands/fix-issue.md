---
name: fix-issue
argument-hint: [issue-number]
---

Handle GitHub issue #$ARGUMENTS (issue-first workflow):

1. `gh issue view $ARGUMENTS` — check the issue content
2. Locate the relevant source files
3. Create a branch: `git checkout -b fix/issue-$ARGUMENTS-<summary>`
4. Implement the minimal fix + write a regression test
5. Confirm the build/tests are green (`./gradlew test` or `npm test`)
6. Commit (referencing `#$ARGUMENTS`) → push → create the PR (`gh pr create --fill --body "Closes #$ARGUMENTS"`) → `gh pr merge --squash`
7. **Automatic close**: merging with `Closes #$ARGUMENTS` in the PR body automatically closes the issue. No manual close needed.
