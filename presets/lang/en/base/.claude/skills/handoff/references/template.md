# Handoff templates

### Body — scratch file → issue/comment body, or `HANDOFF.md` without infrastructure

````markdown
# HANDOFF — <one-line summary>

- Issue: <URL>  (or "none — this file is the source of truth" if there's no tracker)
- Written: <YYYY-MM-DD HH:MM:SS.mmm>
- Work issue/PR: #<N> · #<M> (<status>)
- Branch: `<branch>`  ·  Worktree: `<path>` (or "none — create one")
- HEAD: `<sha>` (<pushed or not>)

## Where things stand

<Facts about what's done / not done. No "mostly working.">

## Verification results (raw)

```
<Last run of tests/build/gates, verbatim. "Not run" if it wasn't.>
```

## Currently running

| Target | Address | How it was started |
| --- | --- | --- |
| <local server> | <http://127.0.0.1:port> | <command + working directory> |
| <tunnel/proxy> | <127.0.0.1:port> | <script path, pid> |

## Open decisions

<What a human needs to decide. Include the options and the consequence of each.>

## Next command to run

```bash
# Copy-pasteable, including the working directory
cd <absolute-path>
<command>
```

## Gotchas

<What tripped things up this time — tool/platform quirks, signals easy to misread, etc.>

## Machine-readable state

```yaml
schema_version: "1"
meta:
  written_at: "<YYYY-MM-DD HH:MM:SS.mmm>"
  location: "<absolute path of the working directory>"
  issue: "<issue URL or none>"
  branch: "<branch>"
  head: "<sha>"
  read_first: ["<file to read first>"]
state:
  <services, ports, revisions needed to resume — project-specific keys>
last_verification:
  - check: "<what was checked>"
    result: "<raw result, or not run if it wasn't>"
    verified_after_fix: false
next_steps:
  - id: "1"
    do: "<what to do>"
    check: "<command to check against>"
    needs_user_confirmation: false
open_decisions: []
cautions: []
```
````

### Old pointer format — for reading and deciding on deletion (not created from 2026-10-06 on)

```markdown
# HANDOFF (pointer)

The session handoff body lives in a <tracker> issue. This file only points to its location.

- Current handoff: <issue URL>
- Written: <YYYY-MM-DD HH:MM:SS.mmm>
- Summary: <one line — what's blocked and what it's waiting on>
- Full list: <URL of the handoff-labeled issue list>
```
