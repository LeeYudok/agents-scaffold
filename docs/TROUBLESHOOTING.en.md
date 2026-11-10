# agents-scaffold — troubleshooting

What to do when the gate, the installer or a harness does not behave as expected. Start at the
[README](../README.md). 한국어: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Commands below assume a clone of agents-scaffold next to your project and are run from the project root.

| Symptom | Section |
|---|---|
| A commit was blocked and you think it should pass | [The gate blocked a commit](#the-gate-blocked-a-commit) |
| A commit that should be blocked goes through | [The gate does not run](#the-gate-does-not-run) |
| Claude Code does not follow `AGENTS.md` | [Claude Code ignores AGENTS.md](#claude-code-ignores-agentsmd) |
| `Warning: ... pre-commit already exists` | [An existing pre-commit hook or husky](#an-existing-pre-commit-hook-or-husky) |
| `Warning: python3 not found` | [python3 is missing](#python3-is-missing) |
| `*.new` files after `--update` | [.new files after --update](#new-files-after---update) |
| An `AGENTS.md.bak-<timestamp>` file appeared | [AGENTS.md.bak files](#agentsmdbak-files) |
| `Warning: symlink unavailable` | [Symlinks are unavailable (Windows)](#symlinks-are-unavailable-windows) |
| `Error: unknown stack` | [Unknown stack](#unknown-stack) |
| Codex or Antigravity misses rules, subagents or hooks | [Codex and Antigravity limits](#codex-and-antigravity-limits) |
| You want it gone | [Uninstalling](#uninstalling) |

## The gate blocked a commit

The gate is `.claude/hooks/pre-commit.sh`, run by git through `.git/hooks/pre-commit`. When it blocks, it prints a
line that starts with `Blocked:` (stack gates from before 1.0.0 print `차단:`) and exits 2, and git aborts the commit.
Read that line first — it names the check that failed.

| Message | Meaning | Fix |
|---|---|---|
| `Blocked: a .env-type file is staged.` | A staged path is `.env`, `.env.<something>`, or one of those in a subdirectory | `git rm --cached <file>` and add it to `.gitignore`. A template such as `.env.example` matches too — rename it (for example `env.example`) or commit that one file consciously with `--no-verify` |
| `Blocked: the staged .claude/skills (copy) differs from its source .agents/skills` | Copy mode (no symlink): only one side of a skill was staged | Edit the file under `.agents/skills`, copy it to the same path under `.claude/skills`, and `git add` both paths |
| A stack message (`tsc`, `ruff`, `gradlew`, ...) | The selected stack's build, type or lint check failed | Run the named tool yourself, fix what it reports, commit again |

To see the whole output without committing, run the gate directly:

```bash
.claude/hooks/pre-commit.sh; echo "exit=$?"
```

Bypassing is possible and is your decision: `git commit --no-verify` skips every local hook for that one commit.
Nothing in the scaffold prevents it, which is why CI should run the same checks. If a check is wrong for your
project, edit `.claude/hooks/pre-commit.sh` — it is your file, and `--update` will not overwrite your edit (see
[.new files](#new-files-after---update)).

## The gate does not run

`.git/hooks/` is not part of a commit, so the hook exists only in the clone where the installer ran. Every other
clone has to wire it once. Check:

```bash
cat "$(git rev-parse --git-path hooks)/pre-commit"
```

It should contain a line that runs `.claude/hooks/pre-commit.sh`. If the file is missing, either run `--update`
(it wires a missing hook) or write the hook by hand:

```bash
../agents-scaffold/bin/agents-scaffold.sh --update .
# or, without the scaffold:
printf '%s\n' '#!/usr/bin/env bash' 'exec "$(git rev-parse --show-toplevel)/.claude/hooks/pre-commit.sh"' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

Other causes:

- The installer ran before `git init`. It prints `Note: target is not the root of a git repo yet` with the command
  above. Run it after `git init`.
- The scaffold was installed in a subdirectory of a repository. The installer does not touch the parent
  repository's hooks (it prints the same `Note`); call `<subdir>/.claude/hooks/pre-commit.sh` from the parent
  repository's pre-commit hook yourself.
- The commit was made with `--no-verify`.

Worktrees, submodules and `core.hooksPath` are handled: the hook is written where git actually looks for it.

## Claude Code ignores AGENTS.md

Claude Code reads `AGENTS.md` natively (v2.1.277 and later), but **only when there is no `CLAUDE.md`**. If the
project has a `CLAUDE.md` or a `CLAUDE.local.md`, Claude Code reads that file and skips `AGENTS.md` — it is a
fallback, not a merge. The installer neither creates nor edits those files.

Fix: make this the first line of the `CLAUDE.md` (or `CLAUDE.local.md`) you want to keep:

```markdown
@AGENTS.md
```

Or delete `CLAUDE.md` after moving its content into `AGENTS.md`. On a Claude Code older than 2.1.277, upgrade or
use the same one-line `CLAUDE.md`.

## An existing pre-commit hook or husky

The installer never overwrites a pre-commit hook it did not write. It prints:

```console
Warning: .git/hooks/pre-commit already exists — not overwriting. Add this line to it to run the gate:
  "$(git rev-parse --show-toplevel)/.claude/hooks/pre-commit.sh" || exit $?
```

Add that line to your hook, before any final `exec` or `exit`. With husky (`core.hooksPath` set to `.husky`) the
warning names `.husky/pre-commit`, and the same line goes there:

```bash
# .husky/pre-commit
"$(git rev-parse --show-toplevel)/.claude/hooks/pre-commit.sh" || exit $?
npx lint-staged
```

Once the hook mentions `.claude/hooks/pre-commit.sh`, the installer and `--update` stay quiet about it. Other hook
managers (pre-commit, lefthook) work the same way: add a local hook that runs that script.

## python3 is missing

```console
Warning: python3 not found — codex hook adapter (.codex/hooks.json) not generated.
```

Only the Codex and Antigravity **hook adapters** (`.codex/hooks.json`, `.agents/hooks.json`) need `python3`, both to
be generated and to run. Without it the rest of the install is complete: `AGENTS.md`, rules, skills, generated
subagents, Antigravity rules and the git pre-commit gate (a bash script).

Fix: install Python 3 so that `python3` is on `PATH`, then run `--update` — it generates the missing adapters for
the recorded harness. On Windows see [step 5 of OFFLINE_INSTALL.en.md](OFFLINE_INSTALL.en.md#5-python3-on-windows).
Claude Code's own helper hooks written in Python (`cc-check.py`) need it as well.

## .new files after --update

`--update` rebuilds what your recorded choices would install today and compares file by file. An identical file is
skipped, a missing one is added, and **a file that differs is left alone** — the new version is written beside it as
`<file>.new`. It cannot tell your edit from an upstream change, so both cases produce a `.new`.

```bash
../agents-scaffold/bin/agents-scaffold.sh --update . --dry-run   # list what would be added or staged as .new
find . -name '*.new' -not -path './.git/*'                       # after a real run
diff -u .claude/rules/common.md .claude/rules/common.md.new
```

For each one:

- You never edited the file → take the new version: `mv <file>.new <file>`.
- You edited it → merge the parts of the diff you want into your file, then delete the `.new`.
- You want to keep yours as is → delete the `.new`. The next `--update` writes it again while the two differ.

`AGENTS.md` always differs once you have filled in its empty sections, so expect `AGENTS.md.new` on every update;
diff it for new rules and delete it. `.claude/hooks/pre-commit.sh` is compared too, against a gate rebuilt with
your recorded stacks. `.claude/memory/MEMORY.md` is yours and never gets a `.new`.

The choices come from `.claude/.scaffold.json`. If that file is missing (an install made before 1.0.0, or the file
was deleted), `--update` infers forge, stacks, language and harness from the project and prints `(inferred)` in its
first line; check that line, and pass the options explicitly if a guess is wrong — they are then recorded.

## AGENTS.md.bak files

Running the **installer** again (not `--update`) over a project regenerates `AGENTS.md`. If your `AGENTS.md`
differed from the regenerated one, the old file is saved first:

```console
== your previous AGENTS.md differed from the generated one — saved as AGENTS.md.bak-20261110-154053 (merge what you need back) ==
```

Copy your sections (project overview, stack, commands, anything you added) back from the `.bak` file into
`AGENTS.md`, then delete the `.bak`. To refresh an existing install without regenerating `AGENTS.md`, use
`--update` instead. `--dry-run` on a normal install lists the files that exist and differ before anything is written.

## Symlinks are unavailable (Windows)

```console
Warning: symlink unavailable — .claude/skills is a copy of .agents/skills.
  Edit .agents/skills only; the pre-commit gate blocks a commit whose staged copy drifts.
```

Skills live in `.agents/skills`, and Claude Code reads them through the symlink `.claude/skills`. Where a symlink
cannot be created — the default for Git Bash on Windows — the installer makes a copy instead. Everything works, with
one rule: change skills in `.agents/skills`, copy the file to the same path under `.claude/skills`, and stage both.
The gate blocks a commit in which the two differ.

To get the symlink back, make symlinks available (on Windows: Developer Mode, `git config core.symlinks true` and
`export MSYS=winsymlinks:nativestrict` in Git Bash), then run `--update`: it replaces the copy with the link when a
link can be made.
To force copy mode on any system, install with `AGENTS_SCAFFOLD_NO_SYMLINK=1`.

A related case: a clone made with `core.symlinks=false` checks the link out as a small plain file. Claude Code then
sees no skills and the gate prints `Warning: .claude/skills is a plain file`. Enable `core.symlinks` and check the
path out again. More in [OFFLINE_INSTALL.en.md](OFFLINE_INSTALL.en.md).

## Unknown stack

```console
Error: unknown stack 'nextj'. Available: android, bun, dotnet, flutter, go, javaweb, nextjs, ops, php-laravel, python, ruby-rails, rust, springboot
```

A misspelt `--stack` stops the install with exit 1 and nothing is written (earlier versions warned and carried on
without that stack's gate). `--list-stacks` prints the valid names, one per line. Several stacks are separated by
commas with no spaces: `--stack nextjs,python`.

## Codex and Antigravity limits

These are measured limits of the harnesses, recorded in [harness-matrix.json](harness-matrix.json), not install
failures. On both, `AGENTS.md` and the git gate hold.

- **Codex loads `.codex/` only for a trusted project**, and runs hooks only after the hook definitions are
  reviewed (`/hooks`). Generated subagents and hooks are inactive until then.
- **Codex has no file-path-scoped instructions**, so `paths:` rules in `.claude/rules` do not reach it. The P0 rules
  of the selected stacks are inlined into `AGENTS.md` for that reason.
- **Antigravity 1.5.0 does not load `trigger: glob` rules** from `.agents/rules`, even after a matching file is
  read (`always_on` rules load). This is why Antigravity is at the baseline tier.
- **Antigravity runs a repository's `.agents/hooks.json` without a trust prompt.** Read that file before running
  agy in a repository you did not write.

## Uninstalling

```bash
../agents-scaffold/bin/agents-scaffold.sh --uninstall . --dry-run   # list what would be removed and kept
../agents-scaffold/bin/agents-scaffold.sh --uninstall . --yes
```

`--uninstall` rebuilds what your recorded choices installed and removes the files that are still identical to it.
Without `--yes` it asks for confirmation, and refuses when there is no terminal to ask on.

What it leaves for you to decide:

- Files you changed — they are listed as kept. Delete them by hand if you do not want them.
- `.claude/memory/` — project memory is never removed.
- `AGENTS.md.bak-*` and `*.new` files, and the hook lines added to `.gitattributes`.
- A pre-commit hook that contains anything besides the scaffold's own line. If you chained the gate into your own
  hook or husky, remove that line yourself, or the next commit fails on the missing script.

The scaffold's own `.git/hooks/pre-commit` is removed, so the gate stops running in this clone. Other clones still
have their hook file until they remove it.
