---
name: memory-factcheck
description: An audit skill that checks an agent's persistent memory against ground truth (code, database, issue tracker, filesystem), corrects stale memories, and reports dead ones as archive candidates. Use when memory grows past ~30 files, right after a big stack/infra change (library swap, version upgrade, server migration, schema drop), when two memories seem to contradict each other, or on a "clean up / audit my memory" (메모리 정리해줘 / 감사해줘) request.
---

# Memory Fact-Check

Memory decays. A fact that was true when written becomes false once code, schema and
infrastructure move. **Stale memory is worse than no memory** — an agent reads it and
confidently does the wrong thing.

This skill is **not** a structural cleanup. Orphan files, duplicate entries, index bloat,
broken internal links — those checks compare memory files *to each other*. This skill
compares each memory **to the world it describes**: the code, the database, the issue
tracker, the filesystem. A memory can be perfectly formatted, correctly indexed and recently
modified — and its content completely false.

Automatic deletion is forbidden. Only a source-of-truth comparison can tell what is dead, and
losing a single incident lesson is expensive. Hence semi-automatic: **correct freely, archive
only after approval, never delete.**

## 1. Locate and inventory

Find the memory set. Common locations, in priority order:

- The path declared by the project's agent instructions (`AGENTS.md` / `CLAUDE.md`) — e.g.
  "memory SSOT is `.claude/memory/`". A declared path wins over every default.
- `.claude/memory/` inside the repo (team-shared, committed to the repo)
- The host's per-project memory directory (e.g. `~/.claude/projects/<slug>/memory/`)

For each file, collect the frontmatter (`name`/`description`/`type`) and the last modification
date (`git log -1 --format=%cs -- <file>` for committed memory, `stat` otherwise). If there is
an index file (`MEMORY.md`), note it — it is audited too, but it is an index, not a memory.

**Personal files are out of scope** — anything the project marks as personal (`user_*.md`,
etc.) belongs to its owner. Do not touch it.

**Reading many files**: dumping 50 memories into context at once exceeds the tool output cap
and wastes the budget. Concatenate them into one scratch file with `########## <filename>`
headers, then read it page by page. Do not skim — a stale claim is usually one clause inside an
otherwise sound paragraph.

### Pre-check script

Running the script below once during the inventory step surfaces structural problems and
claim candidates.

```bash
python3 <skill-path>/scripts/memory_audit.py <memory-dir> --repo <repo-root>
```

- There are five kinds of structural problems. A file the index points to is missing, a file is
  missing from the index, and frontmatter is broken. A `[[link]]` pointing to a nonexistent
  memory and a duplicate `name` are counted too. If any one exists, the exit code is 1.
- `type` is accepted both at the top level and under `metadata.type`. Real memories are often
  stored the latter way.
- This script does not create, modify or delete files. Corrections and archiving happen after
  human approval, following the procedure below.
- It extracts file paths, function names and issue numbers as claim candidates and checks them
  against the filesystem of `--repo`. Text inside code blocks, globs, URLs and options are
  excluded from the candidates.
- Claims that could not reach their source come out as unverified. Issue numbers are always
  unverified, since the tracker is not queried. A memory with no claims at all is not fresh
  either.
- If the memory directory or the `--repo` path does not exist, it ends with exit 2.
- This is for narrowing down candidates. Choosing which claims change behavior and checking
  them against the source is still the agent's job.

## 2. Extract load-bearing claims

Per file, pick the **1–3 claims that change what an agent would do (load-bearing claims)**.
Ignore narrative, rationale and background; a memory is only as stale as its actionable
claims.

Load-bearing claims look like: "X lives at path P" · "table T has N rows" · "issue #N is still
open" · "feature F does not exist yet" · "library L is not installed" · "this fix is still
pending" · "run command C to verify".

## 3. Verify against the source of truth

Work **cheapest-and-highest-yield first**. In practice the ranking below holds: issue status is
one API call and catches the largest share of stale claims — because memories are written
mid-work, and when the work finishes nobody goes back to fix the memory.

| Order | Claim type | How to verify |
| --- | --- | --- |
| 1 | **Issue/PR state** ("#N open", "waiting on #N", "decision pending") | forge CLI/API — `gh issue view N --json state` / `glab api projects/<enc>/issues/N`. Batch them in one loop |
| 2 | **Path/URL** (script locations, deploy paths, endpoints) | `ls`, `test -f`, `curl -s -o /dev/null -w '%{http_code}'` |
| 3 | **Code** (a file/class/config exists, a specific behavior) | `grep`/`Read` the current tree — *the source is the code, not the memory* |
| 4 | **Data/schema** (tables, columns, row counts) | Read-only queries via the project's DB tool. Prefer catalog estimates (`pg_class.reltuples`, `information_schema.columns`); exact `count(*)` only when the estimate itself is disputed |
| 5 | **Runtime/host** (cron jobs, services, logs) | `ssh <host> 'ls …; crontab -l; tail <log>'` — a job's last log line dates the claim precisely |

Parallelize independent verifications. If a source is unreachable, state it in the report —
never silently downgrade "couldn't check" to "checked".

## 4. Classify

- **fresh** — every claim holds. Don't touch it.
- **stale** — some claim is outdated (moved path, changed number, closed issue, implemented
  gap). → **Correct the body now, with the measured value and the date.** Corrections are
  within autonomous scope, because they add truth rather than delete anything.
- **dead** — the core premise is gone (library removed, feature retired, wholly superseded).
  → Mark it as an archive **candidate** only.
- **unverified** — the claim could not be confirmed because the source was unreachable (auth
  failure, host unreachable, no permission). → Leave it untouched, but count it separately in
  the report and note what blocked it. Do not count it as fresh.

## 5. Stale patterns worth hunting

Beyond "the number changed", these recur and are easy to miss:

- **Fixed-gap drift** — the memory records a missing capability ("no reconcile on startup",
  "no rate limiting yet") and it has since been implemented. This is the most dangerous class:
  the agent re-implements or re-reports work that has already shipped. Check the linked issue
  *and* grep for the symbol together.
- **Cross-memory contradiction** — two memories say different things (one says script X is the
  canonical way, another says that script was retired). By definition at least one is stale.
  Do not look only file by file; cross-compare claims across files.
- **Scale drift** — "table T has ~8M rows" from a few months ago is now off by 25%. Harmless as
  small talk, harmful when the memory derives advice from that number (batch sizes, timeout
  budgets, "this query takes 19s").
- **Recipe rot** — a command/query the memory saved as a verified recipe no longer works at
  today's data volume or API version. **Re-run saved recipes**; a recipe you did not run is not
  verified.
- **Progress-state drift** — the "current status" section of a long-running job/backfill memory
  falls weeks behind. Sometimes two mutually contradictory status sections pile up. Date each
  section, keep only the newest, and mark the superseded ones.
- **Identity mismatch** — `name`/`description` and the body say opposite things (e.g. a file
  named `*-via-toolX` whose body records that toolX was abandoned). Recall matches on the
  description, so the file gets loaded for the wrong reason or missed entirely.

## 6. Report, then apply

Report as a table before changing anything — file · class · one-line evidence · action:

| File | Class | Evidence | Action |
| --- | --- | --- | --- |
| `reference_x.md` | stale | script moved `scripts/` → `data/` | path corrected |
| `project_y.md` | stale | claims "#302 reconcile missing"; `JobRunHistoryReconciler` exists, #302 closed | rewritten as done |
| `project_z.md` | dead candidate | the feature from #N was removed in #M | awaiting approval |

Then:

1. **Apply corrections to stale bodies** — measured value + date, keeping the original
   observation where it still carries a lesson ("8M as of <date>, 9.9M as of <today>").
2. **Archive dead candidates only after explicit user approval**: `git mv` them into
   `<memory>/archive/` and add `archived: <date> <reason>` to the frontmatter. Never use `rm`.
3. **Sync the index** — reflect the corrections and remove archived entries from `MEMORY.md`.
4. **Commit through the project's normal workflow** (issue → branch/worktree → PR/MR). Memory
   is team-shared content; there are no direct-to-main commits.

## Judgment rules — stay conservative

- **Unverifiable ⇒ unverified.** If the source of truth is unreachable, leave the memory as it
  is and classify it as unverified. Unconfirmed is not dead, but it is not confirmed either. If
  you count it as fresh, the next audit skips that memory.
- **Incident lessons stay fresh even when the code moves.** A memory recording *why something
  broke* exists to prevent recurrence, not as a snapshot of a call site. Correct its stale path
  references, but do not retire the lesson because a file was renamed.
- **Report the drift, don't invent the cause.** If a number inverted or moved without
  explanation, record the measured value and mark it as unexplained. A plausible story written
  into memory becomes tomorrow's false fact.
- **Prefer merge over create.** Two memories on one topic → propose merging into the existing
  one.
- **Non-obvious facts discovered during the audit become new memories** — the audit itself is a
  source of evidence.

## Field notes

- A recent timestamp proves nothing. A file committed this week can carry a claim that was
  already false when written, and a file left untouched for months can still be true. Verify
  the claims — do not sort by date and cut off the tail.
- `count(*)` on a large table can exceed the DB tool's statement timeout — if the memory claims
  "this query is fast", that failure is itself a finding.
- When shelling out from zsh, quote globs (`grep --include="*.java"`). Otherwise the shell eats
  them, the check silently returns an empty result — and you get a false "fresh".
- An issue being closed does not by itself prove that the described work shipped. Confirm
  fixed-gap claims with a grep for the symbol as well.
