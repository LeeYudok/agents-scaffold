# Forge Workflow — GitLab

<!-- No paths → always loaded. Injected by the forge-gitlab preset. -->

This project uses **GitLab** as its issue/MR forge.

- **CLI**: `glab` (issue/mr)
- **Create an issue**: `glab issue create -t "<title>" -d "<body>" -y`
- **View an issue**: `glab issue view <N>`
- **Create an MR**: `glab mr create -t "<title>" -d "Closes #<N>" --fill -y`
- **Verify issue close after merge**: on GitLab 19, `Closes #N` in the MR body does auto-close the issue on merge (verified in practice) — but never assume it. Right after merging, check `glab issue view <N>` → if `state` is still `opened`, close manually with `glab issue note <N>` + `glab issue close <N>`.
- **Verify the merge itself**: `glab mr merge` can fail transiently (405 right after main moves) while appearing to succeed in filtered output — confirm with `glab mr view <N>` → `state: merged` before cleaning up branches/worktrees; retry after a few seconds if not.
- **Review & merge**: `glab mr merge --squash`
- **Long bodies**: for bodies containing fenced code, tables, or backslashes, write to a file first and use `glab issue create -d "$(cat body.md)"` / API `-F description=@body.md` (avoids inline escaping failures and ARG_MAX limits).
