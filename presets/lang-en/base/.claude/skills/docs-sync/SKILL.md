---
name: docs-sync
description: Documentation sync (docs-sync) — after code or configuration changes (a directory deleted or moved, a port, command or dependency changed, a large refactor merged), find and fix the places where agent instructions (AGENTS.md, CLAUDE.md), READMEs, rules (.claude/rules), skills and docs no longer match reality. Extracts references to deleted or moved paths with a script, separates current instructions from point-in-time records, and fixes only the current ones. Use on "sync the docs" (문서 현행화), "update the docs" (문서 최신화), "refresh the README" (README 갱신), "check for doc drift" (문서 드리프트 확인), "docs-sync", "clean up leftover references" (남은 참조 정리), and right before opening a PR that changed behavior, paths, versions or numbers. Checks each documented claim against reality and updates the parallel-language files together. Memory audits belong to memory-factcheck, AGENTS.yaml setup to yd-agents-yaml.
---

# docs-sync

Builds and tests protect code, but nothing protects documentation. When you delete or move a
directory, the instructions, READMEs and rules that pointed at that path quietly become false.
An agent reads those docs, then goes looking for files that no longer exist or reruns commands
that were removed.

This skill **brings the documentation in line with the changed reality**. The yardstick is
always the code, the configuration, the filesystem and actual execution results — not other
documents.

## Principles

- **Verify claim by claim.** Do not read a document to see whether it "reads naturally".
  Extract the **checkable claims** a sentence makes (paths, versions, numbers, behavior,
  defaults) and check each against reality.
- **Never edit without evidence.** You need a `file:line`, a command's output, or an
  official-docs URL. What you could not confirm is not deleted but **explicitly marked
  "unverified"** — a silent deletion destroys the information.
- **No optimistic wording.** If something only partly works, do not write that it "works".
  Write what works and what does not, separately.

## Boundaries

| Target | Owning skill |
|---|---|
| Fact audit of the agent's persistent memory | `memory-factcheck` (this skill only fixes path references along the way) |
| First-time `AGENTS.yaml` setup or structural change | `yd-agents-yaml` (this skill only checks whether existing values match reality) |
| Project-specific mapping table | If the repo has a project skill such as `*-doc-sync`, follow **its mapping table first** |
| Polishing the edited sentences, reports and issue/MR bodies | `yd-writer-kr` (this skill decides what to fix; the sentences are written by that skill's rules) |
| Issues, commits, MRs | The repo workflow (AGENTS.md). If you use a GitLab agent account, the opt-in `yd-git-ship` |

## Workflow

### 1. Set the scope

First pin down what changed. Do not widen the scope on guesses.

```bash
git log --oneline -15                          # find the baseline
git diff --name-status -M <baseline> HEAD | head    # what was deleted and moved
```

- The baseline is the commit or MR the user named; failing that, the commit just before the
  merge that last brought the docs in line.
- If the repo's project skills, `AGENTS.md` or `.claude/rules/` contain doc-update rules (which
  docs to fix when which code changes), read them and follow them as written.

### 2. Extract drift — script first

The script comes before a hand grep. A hand-written regex mistakes a same-named path in a
subproject (`web/src` pointing at `ews-v3/web/src`) for a deleted path.

```bash
S=<this skill>/scripts/find_stale_refs.py
python3 $S --removed-since <baseline>            # lines pointing at deleted or moved paths
python3 $S                                  # full existence check (only paths whose first segment exists in the repo)
python3 $S --exclude 'model-source/*' --json  # exclude preserved copies, for machine processing
```

- Only tracked documents (`*.md`, `*.yaml`, `*.toml`, `AGENTS*`, `CLAUDE*`, etc.) are scanned.
  Path strings in code are the job of builds and tests.
- The full existence check only looks at tokens whose first path segment exists in the repo
  right now (to cut noise from other repos' paths). If you deleted a whole top-level folder,
  you must catch it with `--removed-since`.
- Paths that actually exist somewhere in the repo (paths relative to a subproject, numbered
  shorthands like `docs/12`) are excluded from the report. Moved paths are reported as
  `renamed -> new path`.
- The exit code is 1 if there is any `current`, 0 if only `history` remains, and 2 for git or
  argument errors. A 1 does not mean the script is broken; it means there are lines to fix.
  `--strict` counts `history` as 1 too.
- Check separately the drift the script cannot catch. Each kind of statement has a fixed
  evidence source, and **documents are never reconciled against each other**.

  | Statement | Evidence source |
  |---|---|
  | Environment variable names | The code that reads the config (`os.Getenv`, config loader), `.env.example` |
  | Ports, containers, health checks | Quadlet `*.container`, compose `HealthCmd`/`PublishPort`, actual `podman ps`/`docker ps` |
  | Run commands, CI jobs | `package.json` scripts, `Makefile`, CI config files |
  | Dependencies, versions | `go.mod`, `package.json`, lock files |
  | Counts and numbers ("37 tables") | Actual query results and their date (DB query, `find`, `grep -c`) |
  | Tracker behavior (auto-close, etc.) | The actual state of the most recent issue/MR |
  | CLI flags, defaults | The output of running `<cmd> --help` (never quote a doc) |
  | Tool versions | Measured with `<cmd> --version` + **record the measurement date** |
  | Behavior ("auto-loads") | The tool's **official-docs URL**. If there is none, mark it "no documented basis" |
  | Gate behavior | Actually run it and check the exit code |

  What goes stale most easily: **directory-tree blocks** (new artifacts missing — they are text
  inside a code block rather than links, so even the link checker misses them), **version
  strings**, **"it automatically ..." behavior claims**, **support matrices**.

- For every statement you fix, search the whole repo for the same statement again
  (`git grep`). When using `grep --include` in zsh, quote the glob (`--include='*.md'`) —
  otherwise it stops with `no matches found`.
- If there is an `AGENTS.yaml`, run the repo's validator (`scripts/check-agents-yaml.sh`).

#### Per-repo scope — `x-doc-sync` in `AGENTS.yaml`

Each repo differs in which "point-in-time records are never fixed" and which "paths are never
scanned". Write them in the repo-root `AGENTS.yaml` and the script reads them (an `x-` section
under the `yd-agents-yaml` convention).

```yaml
x-doc-sync:
  history:              # counted only as history even when found — records that are never fixed
    - CHANGELOG.md
    - docs/superpowers/{plans,specs}/**
    - .claude/memory/archive/**
  exclude:              # not scanned — original copies, generated data
    - data/manual/**
```

Use `*`, `**` (both cross `/`) and `{a,b}`. Without the section, the defaults apply (CHANGELOG
and `archive/` are history; lock files, `node_modules` and the like are excluded). When you
first add this section to a repo, also add one line to `AGENTS.md`: "Use `docs-sync` for
documentation sync." Even without PyYAML, the shapes above (block lists, flow lists) are read.
A broken `AGENTS.yaml` only produces a warning and the defaults apply.

### 3. Classify — separate current instructions from point-in-time records

Sort the lines you found into three groups. The script's `current`/`history` is a word-based
guess, so **read each line yourself** and decide.

| Class | Examples | Handling |
|---|---|---|
| Current instruction | "Start the server with `backend/cmd/server`", a rule file's `paths:` | Fix it to match reality. If the target is gone, delete the sentence or point it at the new location |
| Point-in-time record | CHANGELOG, "as of commit `e59d98b` on 2026-09-21", decision records carrying an issue number, past plans/specs (`plans/`, `specs/`), run logs (`runs/`), memory `archive/`, preserved original copies | **Do not fix it.** If it reads like a current instruction and invites confusion, only attach a marker such as "(removed in #N)" |
| Generated output | HTML, SVG or code produced by a script | Do not edit it directly. Fix the generator (template, script) and rerun it |

- In a repo with design decision records (ADRs, D-entries), if the structure changed, add one
  more decision entry and mark the old statements as pointing to it. Do not rewrite the body
  of an old decision.
- In memory files, fix only path references; hand off staleness of the facts themselves to
  `memory-factcheck`.

### 4. Fix

- **Fix only what you confirmed with evidence.** Write a new path, command or value only after
  opening the actual file or running the command to confirm it. Do not fix a line you could
  not confirm; put it under "Needs confirmation" in the report.
- Delete a whole section that described a removed feature. Do not leave hollow sentences
  ("there is no ...") in several places; record a vanished fact in one place only (README or a
  decision record).
- For files with doc-update rules (rule tables, skill lists, indexes), align the table and the
  actual file list together.
- **Always polish the edited sentences with `yd-writer-kr`.** Changing only a path easily
  leaves the surrounding sentences out of joint. Reread the edited line and its paragraph
  under that skill's rules and tidy them. Follow the document's own style, and do not touch
  paragraphs you did not edit.
- **Update parallel-language and counterpart files in the same commit (required).** Fixing one
  side leaves the rest stale, and no gate catches it. Use `ls README*.md` to find every
  language edition, and if there is a language overlay such as `presets/lang-en/`, fix the
  corresponding files too. These are not translations but **per-language editions of the same
  facts**, so numbers, versions, paths and table structure stay identical. The source text
  differs per language and blanket replacement breaks, so `grep -n` the replacement target in
  each file first.
- If many files need fixing, you may split them across subagents with non-overlapping file
  ranges. When a fact update arrives (e.g. a production teardown completed), relay it to all
  subagents immediately.

### 5. Verify

```bash
python3 $S --removed-since <baseline>   # current is 0, or every remaining line has a reason to stay
<repo validators>                      # AGENTS.yaml validator, link check (python3 .claude/scripts/knowledge_graph.py --check), etc.
<repo build and tests>                   # if scripts or config changed along with the docs
```

For every remaining `current`, write one line on why it stays (another repo's path, an
intentional record).

### 6. Report

Keep it short in chat; put the details in the issue/MR body. Write the report and the issue/MR
body with `yd-writer-kr` as well.

```
## Documentation sync — <baseline>..HEAD
- Fixed: <N files> — for each claim, `before → after + evidence` (do not leave only a summary like "updated the README")
- Kept as records: <file, line> — <reason>
- Needs confirmation: <line> — <what has to be confirmed>
- Not checked: <folder, doc type> — <reason (no access, no evidence source, time)>
- Verification: find_stale_refs current <n> (reasons stated), <validator> passed
```

Commits and MRs go through the repo workflow (issue → branch → PR/MR). As a rule, the
documentation sync goes into the same MR as the code change (the MR that changed the code also
fixes the docs). Open a separate issue only when catching up with a change that has already
been merged.

## Done when

- `current` from `find_stale_refs.py --removed-since <baseline>` is 0, or the report gives a
  reason for every remaining line.
- For every statement fixed, the evidence file or command result was checked.
- Point-in-time records and generated output were not edited directly.
- The edited sentences and the report and issue/MR bodies were polished with `yd-writer-kr`.
- The parallel-language and language-overlay counterpart files are in the same commit.
- The repo's doc validators (including 0 broken from the link checker) and the tests of any
  scripts changed alongside pass.
- The report or MR body lists the scope that could not be checked ("none" if there is none). A
  missed folder becomes the next drift.

## Learned warnings

- (2026-10-24) Merged agents-scaffold's `docs-sync` and doksam-skills' `yd-doc-sync` into one. Drift extraction (`find_stale_refs.py`) and current/record classification came from yd-doc-sync; claim-by-claim checking, the "unverified" marker, updating parallel-language files together and the link-checker gate came from docs-sync (agents-scaffold #78).
- (2026-10-24) Handling a stale statement by **deleting** it breaks the trail of "why it disappeared" — it is better to keep it marked "unverified" with the measurement date.
