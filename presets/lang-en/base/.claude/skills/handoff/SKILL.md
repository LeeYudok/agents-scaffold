---
name: handoff
description: "End a session and hand it off to the next one — if collaboration infrastructure (GitHub, GitLab, Forgejo, Jira, Plane, Slack) exists, write resumable state as the body of an issue in that tracker and hand over a single issue URL — in that case do not create HANDOFF.md in the repo (no pointer file either). Only in a folder with no tracker, write the full content into HANDOFF.md itself and finish with that file. At a boundary where the work issue was closed, leave a single comment on the next work issue instead of a dedicated issue. The receiving side reads the issue URL or file, checks the recorded claims against reality, then continues the work, and when done leaves the result and closes. Use when context hits 40-50%, when told \"let's stop here / save state / pick up / resume\" (Korean: \"여기서 끊자 / 상태 남겨 / 이어받아 / 재개\"), or when a handoff URL or file path is pasted in."
---

# Session handoff

A handoff is **resumable state, not a summary**. The next session should be able to read it alone
and type the next command from the same spot. The point is not "what was done" but **"where things
stand now and what to type next."**

When context usage hits 40-50%, stop what you're doing and invoke this skill. Compaction is only a
safety net, since the model chooses what to discard on its own.

## Where to leave it — one place per situation

Do not split resumable state across **two locations.** Splitting it means neither location is
resumable on its own, and the next time it's written one half silently goes missing (observed
2026-09-21, issue #152 — gotchas and startup commands were only in the handoff issue, while newly
confirmed patterns were only in the next issue's memo).

| Situation | Where to leave it | What the next session receives |
| --- | --- | --- |
| **Mid-issue** — the work issue is still open (context at 40-50%, etc.) | A dedicated handoff issue (no `HANDOFF.md` is created in the repo; see "Two branches" below) | The handoff issue URL |
| **Issue boundary** — the work issue is closed and **the next work issue already exists** | **A single comment on the next work issue** (1-6) — do not create a dedicated handoff issue | The next work issue URL |
| No infrastructure (folder without a tracker) | `HANDOFF.md` | The file path |

At an issue boundary, if the next work issue doesn't exist yet, create it first. If what comes next
hasn't been decided, this isn't a boundary but simply the end of work — don't write a handoff.

## Two branches; with infrastructure, the issue is the source of truth

| | What it does | `HANDOFF.md` | What the next session receives |
| --- | --- | --- | --- |
| **Infrastructure exists** | Write the body to a scratch file and **create an issue/ticket/thread from that content** | **Not created** (no pointer file either) | **The full URL** |
| **No infrastructure** | Write the full content into `HANDOFF.md` | **The body itself = the source of truth** | **The file path** |

When stopping mid-issue, **always** write the body. With infrastructure, that body goes into the
issue and no file is left in the repo — resumable state is not left in the repo as plain text, and
the next session knows where to go from the single issue URL the user pastes (or from the list of
`handoff`-labeled issues). Without infrastructure there is nowhere else for it to go, so the body
itself stays in `HANDOFF.md` (file mode) — the procedure doesn't stall.

Before 2026-10-06, `HANDOFF.md` was left in the repo even when infrastructure existed.
It held **only a pointer** (issue URL, time written, summary, list link). It is no longer created. If such a pointer file is still in a repo, read it per 2-1,
confirm that the issue it points to holds all the content, then delete the file via that repo's issue/MR.

## `HANDOFF.yaml` — the machine-readable pair

The body reads well for humans, but for the next session to extract service addresses, revisions,
verification results and next commands, it would have to parse markdown every time. Write
`HANDOFF.yaml`, which records the same state as keys, **together with the body**.
Both point at the same facts, so update them together. If only one is changed, the checker (`--pair`) catches the mismatch.

| Situation | Where the yaml goes |
| --- | --- |
| No infrastructure (file mode) | `HANDOFF.yaml` at the repo root — next to `HANDOFF.md` |
| Infrastructure exists | A single ```yaml block inside the `## Machine-readable state` section at the end of the issue body. Do not create `HANDOFF.yaml` in the repo |

The reason it goes inside the body rather than as an attachment when infrastructure exists is that
attachment support differs per tracker (Jira, Plane, Slack), so using attachments would split the
source of truth in two. The principle that the one body is the source of truth stays intact.

- The schema's source of truth is `## Machine-readable state` in the body template below. Add project-specific keys under `state`.
- Required keys are `schema_version`, `meta`, `state`, `last_verification` and `next_steps`.
- **Always quote dates, times and versions.** Without quotes, YAML silently turns `2026-10-05` into a date, `1.10` into `1.1`, and `yes` into a boolean.
  For decimals, only values whose key name contains `version`, `release`, `revision` or `tag` require quotes. Genuine decimal values (`progress: 0.5`) are written as-is.
- Write lists in block style (`- `). Don't write the same key twice. The checker is lexical, so it can't count items in a one-line flow-style list, and the parser uses the last value of a duplicate key.
- If a `## Machine-readable state` section exists, it must contain a closed ```yaml block. The yaml inside the body is cross-checked against that same body's `Written`, `Branch` and `HEAD`.
- For each `next_steps` item, write a command to check it against (`check`).
- Never put secrets in values. Write key names and paths only.
- The checker looks at the lexical level (required keys, type-coercion risks, tabs), and if PyYAML is available it actually parses the file.

## Modes

| Invocation | What it does |
| --- | --- |
| `/handoff` (no arguments) | **Write** — mid-issue: with infrastructure, only create the issue (no repo file); without infrastructure, full content in `HANDOFF.md`; at an issue boundary: a comment on the next work issue → prints the URL or file path |
| `/handoff <URL · #N · file path>` | **Resume** — reads the content, verifies claims, then continues |
| `/handoff done` | **Close** — leaves the result and closes it (issue) / writes it into the file (file mode) |

If the user pastes only a URL or a `HANDOFF.md` path (with no explanation), treat it as resume mode. The same applies when you receive an old pointer file left in a repo.

---

## 0. Identify the tracker (do this first, never guess)

**Do not pick commands from assumptions like "this repo is on GitLab."** Check the following in
order and use the first one that resolves.

```bash
# 1) Does repo documentation name a tracker? (strongest signal)
grep -riE 'jira|plane|linear|이슈는|트래커' AGENTS.md CLAUDE.md README.md 2>/dev/null | head -5

# 2) Git forge
git remote get-url origin

# 3) Is auth actually working (installed != usable)
gh auth status 2>&1 | tail -2
glab auth status 2>&1 | tail -2

# 4) Are there credentials for a non-forge tracker — check names only, never print values
env | grep -oE '^(JIRA|PLANE|SLACK|LINEAR)_[A-Z_]+' | sort -u
```

If Jira/Plane/Slack tools appear in the MCP tool list, use those **before** the CLI (no need to
pull credentials into the shell).

| Result | Use | Project scoping |
| --- | --- | --- |
| `github.com/<owner>/<repo>` | `gh` | `--repo <owner>/<repo>` |
| GitLab (including self-hosted) | `glab` | `projects/<owner>%2F<repo>` (slash as `%2F`) |
| Forgejo / Gitea | `curl` + token | `/api/v1/repos/<owner>/<repo>/issues` |
| Jira | MCP tool or REST | `/rest/api/3/issue` · project key required |
| Plane | MCP tool or REST | `/api/v1/workspaces/<ws>/projects/<id>/issues/` |
| Slack (channel-based collaboration, no tickets) | MCP tool or `curl` | Channel ID · thread permalink is the URL |
| Nothing | **File mode** | The `HANDOFF.md` path is the address |

**When in doubt, fall back to file mode.** Leaving one accurate file and telling the user "let me
know if you want a tracker" beats filing an issue in the wrong tracker. The same applies when issue
creation fails due to missing permissions — don't swallow the failure, finish in file mode and
**report the failure and its cause in one line**.

---

## 1. Write

### 1-1. Gather state (never guess, measure everything)

```bash
git branch --show-current && git status --short
git log --oneline -5
git worktree list

# open work — only what matches this tracker
gh pr list && gh issue list --label handoff --state open      # GitHub
glab mr list -P 10 && glab issue list --label handoff -P 5    # GitLab

# locally running servers — swap the port for this repo's own
lsof -nP -iTCP -sTCP:LISTEN | grep -E '<app-name>|<port>' || true
```

If a verification gate was run, copy the **raw result** (pass/fail lines) verbatim. If it wasn't
run, write "not run" — pretending it was run is the most dangerous thing you can do here.

### 1-2. Write the body to a scratch file (template below)

Don't write straight into the repo's `HANDOFF.md` — with infrastructure, this body goes into an
issue and no file at all is left in the repo. Write a temporary file in the session scratch
directory (or `/tmp`), filling in every field of the "Body template" below.

Only when there is no infrastructure at all (step 0 result "Nothing") write this body as-is to
`HANDOFF.md` at the repo root — if one already exists, **overwrite** it. A handoff is always a
single "current state" snapshot; history belongs to the tracker and that repo's own work-log file
(e.g. `CURRENT_TASK.md`). If the repo doesn't track this file (`.gitignore`), announce the
**absolute path** instead of committing it.

Once the body is written, **run the checker before posting.** Post only on `exit 0`. It catches
empty fields, leftover placeholders, ISO 8601 timestamps and secret-shaped strings, and for secrets
it reports only the line number. `exit 2` means the input or git could not be used — it is not a pass.

```bash
python3 <skill-path>/scripts/check_handoff.py <body-file>.md
```

In file mode, `HANDOFF.yaml` is checked together with its paired `HANDOFF.md`. A yaml block inside
an issue body is checked by the body check above.

```bash
python3 <skill-path>/scripts/check_handoff.py HANDOFF.yaml --yaml --pair HANDOFF.md
```

### 1-3. Create an issue if infrastructure exists

Pass the body **via a file**, not inline `--body "$(...)"` or `jq --arg` — fenced code, tables, and
backslashes break escaping, and a large body can exceed ARG_MAX and produce an empty request.
The `<body-file>` below is the scratch file written in 1-2 (not the repo's `HANDOFF.md`).

```bash
# GitHub
gh issue create --title "Handoff: <one-line summary> (<YYYY-MM-DD>)" \
  --label handoff --body-file <body-file>.md

# GitLab
glab api --method POST "projects/<owner>%2F<repo>/issues" \
  -F "title=Handoff: <one-line summary> (<YYYY-MM-DD>)" \
  -F "labels=handoff" \
  -F "description=@<body-file>.md" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['iid'], d['web_url'])"

# Forgejo / Gitea — build the payload as a file first, then pass it (the body contains backticks/tables)
python3 -c "
import json;json.dump({'title':'Handoff: <summary>','body':open('<body-file>.md').read()}, open('payload.json','w'))"
curl -s -X POST "$FORGEJO_URL/api/v1/repos/<owner>/<repo>/issues" \
  -H "Authorization: token $FORGEJO_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['number'], d['html_url'])"
```

**For Jira / Plane / Slack, use the MCP tool if one is available.** Fall back to REST only when
there isn't one:

```bash
# Jira — description defaults to ADF but most instances also accept wiki/plain. Project key is required.
curl -s -X POST "$JIRA_URL/rest/api/3/issue" \
  -H "Authorization: Bearer $JIRA_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['key'])"
# → URL is $JIRA_URL/browse/<KEY>

# Plane
curl -s -X POST "$PLANE_URL/api/v1/workspaces/$PLANE_WS/projects/$PLANE_PROJECT/issues/" \
  -H "X-API-Key: $PLANE_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['id'], d.get('sequence_id'))"

# Slack — for teams that collaborate over channel threads instead of tickets. If the body is long, an uploaded snippet works better.
#   Send one message → use its permalink as the URL (chat.getPermalink).
```

Never inline the payload into the shell — build it as a **file, then pass it with `--data-binary
@`** (the `payload.json` in both commands above). Use tokens only as a variable on the same line,
and never add `-v`/`--trace` — verbose metadata lines bypass masking.

If the `handoff` label (or its Jira/Plane equivalent) doesn't exist, create it first. The label is
what lets the next session find "open handoffs" in one query.

### 1-4. Leave no file in the repo (commit only in file mode)

With infrastructure, do not create `HANDOFF.md` in the repo — no pointer file either. Resumable
state lives only in the issue from 1-3, and the next session finds it by that URL or by the list of
`handoff`-labeled issues. If the repo already has a work-log file (e.g. `CURRENT_TASK.md`), it's
fine to leave one line with the issue URL at its top (within that file's original purpose).

If an old pointer `HANDOFF.md` is still in the repo, don't copy the scratch file's body into it —
confirm that the issue it points to holds all the content, then delete the file via that repo's
issue/MR. To inspect its state before deleting, use `python3 <skill-path>/scripts/check_handoff.py HANDOFF.md --as-file`.
If a tracker issue exists but a body is still left in `HANDOFF.md`, this check fails.

In file mode (no infrastructure), the full body was already written to `HANDOFF.md` in 1-2. Write
"no tracker — this file is the source of truth" at the top of the file. If that folder is a git
repo, commit it.

```bash
git add HANDOFF.md && git commit -m "docs: session handoff (file mode)"
```

If committing on a branch, **also push** — a new session needs to be able to pick it up from a
different worktree.

### 1-5. One line for the user

Give the **full URL** if infrastructure exists, otherwise the **absolute file path**. Tell them
pasting that alone after `/clear` resumes the session. In file mode, add one more line: "attach a
tracker and it becomes an issue from next time."

### 1-6. Issue boundary — a single comment on the next work issue

If you just closed the work issue, follow this procedure instead of 1-2 through 1-4. State
gathering (1-1) and the user-facing line (1-5) are unchanged.

1. **Re-read the previous handoff or startup memo.** The targets are the comments on the work issue
   you just closed, and the handoff issue or `HANDOFF.md` that session picked up from. Sort each
   item into **still valid / expired** — gotchas, verification-environment startup commands, and
   open decisions mostly still hold for the next issue.
2. **Write a comment body that fills every template field into a file** (the "Body template" below
   as-is, just retitled `## Startup notes — <YYYY-MM-DD>`). **Copy over** items still valid — don't
   defer to "see the previous issue/MR"; a link is only a citation, not a substitute for content.
   Distinguishing what's newly confirmed this session from what's inherited makes it easier to sort
   again at the next boundary.
3. **Self-containment check.** Before posting, ask: is there anything here that can only be known by
   opening some other issue or MR outside this comment? If so, copy it in. Don't repeat what's
   already in the next work issue's **body** (scope, design, acceptance criteria) — the body plus
   the comment together should be one complete page.
4. **Post as a single comment** (body via file — same reasoning as 1-3).

```bash
# GitHub
gh issue comment <next-N> --body-file <memo-file>.md
# GitLab
glab api --method POST "projects/<owner>%2F<repo>/issues/<next-N>/notes" -F "body=@<memo-file>.md"
# Jira / Plane / Slack — comment on the corresponding ticket/thread via the MCP tool
```

If you find something missing after posting, **edit that comment rather than adding another one**
— the moment there are two places to read, the same problem recurs. If the handoff issue this
session picked up from is still open, close it per section 3, and put the next work issue's URL in
the closing comment.

`HANDOFF.md` is not used on this branch. If an old pointer is still in the repo, don't write over
it — delete it per 1-4. A stale file gets mistaken for the latest one.

---

## 2. Resume

### 2-1. Read the content

With infrastructure, open the **issue URL** the user gave (if there is none, find the open one in
the list of `handoff`-labeled issues). If the repo has an old pointer `HANDOFF.md`, take only the
issue URL written in it and don't use the file itself as resumable state — once you've read
everything, delete it per 1-4. Without infrastructure, the file itself is the entire body.

```bash
cat HANDOFF.md   # file mode: this file is the entire body (if it's an old pointer in a repo with infrastructure, take only the issue URL)

# GitHub
gh issue view <N> --comments
# GitLab
glab issue view <N>
glab api "projects/<owner>%2F<repo>/issues/<N>/notes" | python3 -c "
import json,sys
for n in json.load(sys.stdin): print('---', n['author']['username'], n['created_at']); print(n['body'])"   # don't truncate — the next command to run and the gotchas are usually near the end
# Jira / Plane / Slack — read the body together with comments/thread replies via the MCP tool
```

**Comments can be newer than the body** — always read both in issue mode. Even if the URL you
received is a **work issue** rather than a handoff issue, the procedure is the same (received via
the issue-boundary branch): the body holds scope and acceptance criteria, and the startup-memo
comment holds resumable state. In file mode, one file is everything, but for that very reason also
check **when it was last updated via git log** (`git log -1 --format='%ci' -- HANDOFF.md`).

If there is a yaml pair, read it first — `HANDOFF.yaml` in file mode, or the `## Machine-readable state`
block at the end of the body when infrastructure exists. Old handoffs without yaml (md only) are read as they are.

### 2-2. Verify the claims (the body decays too)

If there is yaml, check `next_steps[0].check` and `meta.branch`/`meta.head` against reality as in
the table below; if they diverge, report it before starting.

Before acting, check **1-2 claims that would change your behavior** against reality. In practice, a
PR recorded as "open" has already been merged before.

| Recorded item | How to check |
| --- | --- |
| Branch/worktree | `git worktree list`, `git branch -a --contains <sha>` |
| PR/MR status | `gh pr view <N>` / `glab mr view <N>` — may already be merged |
| Issue/ticket status | `gh issue view <N>` / `glab issue view <N>` / Jira·Plane lookup — may already be closed |
| A server left running | `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:<port>/` |
| Deployed version | Hit the service's `/version` or `/healthz` directly |
| Next command | Whether the path/script still exists (`ls`, `git show --stat`) |

The checker verifies the branch and HEAD claims read-only. Save the body (or `HANDOFF.md` in file
mode) to a file and run it. If the branch is ahead of the recorded HEAD, it warns; if the recorded
HEAD is not an ancestor of the branch, it's a violation.

```bash
python3 <skill-path>/scripts/check_handoff.py <body-file>.md --verify-git <repo-path>
```

On a conflict, **trust actual state** and correct it via an issue comment (or the file, in file
mode).

### 2-3. Continue the work

- Use the existing worktree if one remains, otherwise `git worktree add ../<repo>-<n> <branch>`.
- No `checkout`/`switch` in the canonical clone (pull/read only) — it shifts the ground under other
  sessions.
- A handoff is **not a work issue** — if an actual work issue number is recorded, pin that to the
  branch/commit/PR. The handoff is only a marker bridging sessions.

---

## 3. Close

Once the picked-up work is done (including when it produces yet another handoff), close the
handoff.

```bash
# GitHub
gh issue comment <N> --body-file <result-file>.md && gh issue close <N>
# GitLab
glab api --method POST "projects/<owner>%2F<repo>/issues/<N>/notes" -F "body=@<result-file>.md"
glab issue close <N>
# Jira / Plane — comment via the MCP tool and set status to Done/Completed
# Slack — reply in the same thread with the result, following the team's convention (resolution emoji, etc.)
```

In file mode, write **`# Closed — <date>`** and the result at the top of `HANDOFF.md` and commit.
If another handoff follows, overwriting the file with the new content is the close.

A session received via the issue-boundary branch has no handoff issue to close — the work issue's
normal close (result comment + close) is the close itself, and if further work follows, leave the
memo on that issue per 1-6.

One line when closing: what finished, and the URL/path of the next handoff if there is one.
If two or more open handoffs pile up, it's unclear which is current — keep **only one open at a time**.

---

## Templates

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

---

## When using doksam GitLab

doksam's self-hosted GitLab has a separate account for each agent. Leave handoff issues and
comments under **your own account**. Read the token only on the same line as the command that uses
your own section of `~/workspace/.env.toml`, and never print it separately.

| Agent | Section |
|---|---|
| Claude Code | `gitlab_claude_ai` |
| Codex | `gitlab_codex_ai` |
| Antigravity | `gitlab_agy_ai` |

```bash
export GITLAB_TOKEN=$(python3 -c 'import tomllib,os;print(tomllib.load(open(os.path.expanduser("~/workspace/.env.toml"),"rb"))["gitlab_claude_ai"]["token"])')
glab api -X POST "projects/<ns>%2F<repo>/labels" -f name=handoff -f color='#6699cc' >/dev/null 2>&1   # create the label if it doesn't exist
```

- `glab issue create -R <ns>/<repo>` can return 404. Run it inside the repo folder without `-R`.
- Write times as `YYYY-MM-DD HH:MM:SS.mmm` (KST). Don't use ISO 8601's `T` or `+09:00`.
- Before writing a handoff, first record any facts worth keeping in the repo memory and push. An issue body decays, but memory is read automatically by the next session.
- The receiving side first leaves a `재개: <agent>` ("resumed: <agent>") comment on the issue. This prevents two agents from picking up the same handoff at the same time.

---

## Principles

- **With infrastructure, the issue is the source of truth and no `HANDOFF.md` is created in the repo. Without infrastructure, the file is the source of truth.**
  Even with no tracker, or a failed one, the handoff is complete.
- **One place per situation.** A handoff issue mid-issue, a single comment on the next work issue
  at an issue boundary. Never both, and whichever one it is must be sufficient to start from alone.
- **The yaml is the body's pair.** It records the same facts as keys and is updated together. With infrastructure it goes inside the issue body; without, next to `HANDOFF.md`.
- **Facts only.** Fill dates, issue numbers, and figures from actual measurement; write "unknown"
  when you don't know.
- **Commands must be copy-pasteable.** Include the working directory, never relative paths.
- **Don't paste large tool output** — save it to a file and give the path plus the last few lines.
- Never put `.env` values, tokens, or passwords in the body — key **names** only. If the tracker is
  a public channel, screen internal hostnames and paths once more too.
- One session = one work issue. A handoff is what carries you across that boundary, not a way to
  stretch a single session longer.

## Learned warnings

- (2026-10-06) Do not commit a `HANDOFF.md` pointer to a repo that has a tracker. The user's instruction was "HANDOFF.md 는 삭제해 깃없을때만 이용이라" ("delete HANDOFF.md — it's only for when there's no git"). So in jbb/ews#250 the files at the root and in `newtech/` were deleted. Hand off via the handoff issue URL or a comment on the next work issue. Use the file only in folders without a tracker (#217).
