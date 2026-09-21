---
name: handoff
description: End a session and hand it off to the next one — write resumable state to HANDOFF.md, and if collaboration infrastructure (GitHub, GitLab, Forgejo, Jira, Plane, Slack) exists, create an issue with the same content so the handoff is a single URL; otherwise the file is the deliverable. At a work-issue boundary, leave a single comment on the next work issue instead of a dedicated handoff issue. The receiving side checks the recorded claims against reality before continuing, then reports results and closes when done. Use when context hits 40-50%, when told "let's stop here / save state / pick up / resume" (Korean: "여기서 끊자 / 상태 남겨 / 이어받아 / 재개"), or when a handoff URL or file path is pasted in.
---

# Session handoff

A handoff is **resumable state, not a summary**. The next session should be able to read it alone
and type the next command from the same spot. The point is not "what was done" but **"where things
stand now and what to type next."**

When context usage hits 40-50%, stop what you're doing and invoke this skill. Compaction is only a
safety net, since the model chooses what to discard on its own.

## Where to leave it — one place per situation

Do not split resumable state across **two locations.** Splitting it means neither location is
resumable on its own, and the next session silently misses whichever half it didn't read
(observed 2026-09-21, issue #152 — gotchas and startup commands were only in the handoff issue,
while newly confirmed patterns were only in the next issue's memo).

| Situation | Where to leave it | What the next session receives |
| --- | --- | --- |
| **Mid-issue** — the work issue is still open (context at 40-50%, etc.) | `HANDOFF.md` + a dedicated handoff issue (see "Two branches" below) | The handoff issue URL |
| **Issue boundary** — the work issue is closed and **the next work issue already exists** | **A single comment on the next work issue** (1-6) — do not create a dedicated handoff issue | The next work issue URL |
| No infrastructure | `HANDOFF.md` | The file path |

At an issue boundary, if the next work issue doesn't exist yet, create it first. If what comes next
hasn't been decided, this isn't a boundary but simply the end of work — don't write a handoff.

## Two branches, the file is always the source of truth

| | What it does | What the next session receives |
| --- | --- | --- |
| **Infrastructure exists** | Write `HANDOFF.md` and **create an issue/ticket/thread with the same content** | **The full URL** |
| **No infrastructure** | `HANDOFF.md` is the deliverable | **The file path** |

When stopping mid-issue, **always** write `HANDOFF.md`. The issue is just the channel that delivers
it to the team and shows status (open/closed); the file is the single source of truth for content.
Missing infrastructure doesn't stall the procedure — if the issue can't be created, fall back to
file mode and finish that way.

## Modes

| Invocation | What it does |
| --- | --- |
| `/handoff` (no arguments) | **Write** — mid-issue: `HANDOFF.md` (+ an issue if infrastructure exists); at an issue boundary: a comment on the next work issue → prints the URL or file path |
| `/handoff <URL · #N · file path>` | **Resume** — reads the content, verifies claims, then continues |
| `/handoff done` | **Close** — leaves the result and closes the issue, or writes it into the file (file mode) |

If the user pastes only a URL or a `HANDOFF.md` path (with no explanation), treat it as resume mode.

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

### 1-2. Write `HANDOFF.md` (repo root, template below)

**Overwrite** it if one already exists. A handoff is always a single "current state" snapshot;
history belongs to the tracker and that repo's own work-log file (e.g. `CURRENT_TASK.md`).

If the repo doesn't track this file (`.gitignore`), announce the **absolute path** instead of
committing it.

### 1-3. Create an issue if infrastructure exists

Pass the body **via a file**, not inline `--body "$(...)"` or `jq --arg` — fenced code, tables, and
backslashes break escaping, and a large body can exceed ARG_MAX and produce an empty request.

```bash
# GitHub
gh issue create --title "Handoff: <one-line summary> (<YYYY-MM-DD>)" \
  --label handoff --body-file HANDOFF.md

# GitLab
glab api --method POST "projects/<owner>%2F<repo>/issues" \
  -F "title=Handoff: <one-line summary> (<YYYY-MM-DD>)" \
  -F "labels=handoff" \
  -F "description=@HANDOFF.md" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['iid'], d['web_url'])"

# Forgejo / Gitea — build the payload as a file first (body contains backticks/tables)
python3 -c "
import json;json.dump({'title':'Handoff: <summary>','body':open('HANDOFF.md').read()}, open('payload.json','w'))"
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
and never add `-v`/`--trace` — verbose metadata lines can bypass masking.

If the `handoff` label (or its Jira/Plane equivalent) doesn't exist, create it first. The label is
what lets the next session find "open handoffs" in one query.

### 1-4. Cross-reference and commit

Put the issue URL on the first line of `HANDOFF.md` (file ↔ issue), and if the repo has a work-log
file, add a line at the top of that too. In file mode, write "no tracker — this file is the source
of truth."

```bash
git add HANDOFF.md && git commit -m "docs: session handoff (<#N or file mode>)"
```

If committing on a branch, **also push** — a new session needs to be able to pick it up from a
different worktree.

### 1-5. One line for the user

Give the **full URL** if infrastructure exists, otherwise the **absolute file path**. Tell them
pasting that alone after `/clear` resumes the session. In file mode, add one more line: "attach a
tracker and it becomes an issue next time."

### 1-6. Issue boundary — a single comment on the next work issue

If you just closed the work issue, follow this procedure instead of 1-2 through 1-4. State
gathering (1-1) and the user-facing line (1-5) are unchanged.

1. **Re-read the previous handoff or startup memo.** The targets are the comments on the work issue
   you just closed, and the handoff issue or `HANDOFF.md` that session picked up from. Sort each
   item into **still valid / expired** — gotchas, verification-environment startup commands, and
   open decisions mostly still hold for the next issue.
2. **Write a comment body that fills every template field into a file** (same `HANDOFF.md` template
   below, just retitled `## Startup notes — <YYYY-MM-DD>`). **Copy over** items still valid — don't
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

`HANDOFF.md` is not used on this branch. If an old one is still in the repo, add `# Closed —
<date>` and the next work issue's URL at the top so it isn't mistaken for the current source of
truth.

---

## 2. Resume

### 2-1. Read the content

```bash
# GitHub
gh issue view <N> --comments
# GitLab
glab issue view <N>
glab api "projects/<owner>%2F<repo>/issues/<N>/notes" | python3 -c "
import json,sys
for n in json.load(sys.stdin): print('---', n['author']['username'], n['created_at']); print(n['body'][:2000])"
# Jira / Plane / Slack — read the body together with comments/thread replies via the MCP tool
# File mode
cat HANDOFF.md
```

**Comments can be newer than the body** — always read both in issue mode. Even if the URL you
received is a **work issue** rather than a handoff issue, the procedure is the same (received via
the issue-boundary branch): the body holds scope and acceptance criteria, and the startup-memo
comment holds resumable state. In file mode, the file is everything, but check **when it was last
updated via git log** too (`git log -1 --format='%ci' -- HANDOFF.md`).

### 2-2. Verify the claims (the body decays too)

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

On a conflict, **trust actual state** and correct it via an issue comment (or the file, in file
mode).

### 2-3. Continue the work

- Use the existing worktree if one remains, otherwise `git worktree add ../<repo>-<n> <branch>`.
- No `checkout`/`switch` in the canonical clone (pull/read only) — it shifts the ground under other
  sessions.
- A handoff is **not the work issue itself** — if an actual work issue number is recorded, pin that
  to the branch/commit/PR. The handoff is only a marker bridging sessions.

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
# Slack — reply in the same thread with the result, following the team's own resolution-emoji convention
```

In file mode, write **`# Closed — <date>`** and the result at the top of `HANDOFF.md` and commit.
If another handoff follows, overwriting the file with the new content is the close.

A session received via the issue-boundary branch has no handoff issue to close — the work issue's
normal close (result comment + close) is the close itself, and if further work follows, leave the
memo on that issue per 1-6.

One line when closing: what finished, and the URL/path of the next handoff if there is one. If two
or more open handoffs pile up, it's unclear which is current — keep **only one open at a time**.

---

## HANDOFF.md template

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
````

---

## Principles

- **The file is the source of truth, the issue is the delivery channel.** A missing or failed
  tracker still leaves a complete handoff.
- **One place per situation.** A handoff issue mid-issue, a single comment on the next work issue
  at an issue boundary. Never both, and whichever one it is must be sufficient to start from alone.
- **Facts only.** Fill dates, issue numbers, and figures from actual measurement; write "unknown"
  when you don't know.
- **Commands must be copy-pasteable.** Include the working directory, never relative paths.
- **Don't paste large tool output** — save it to a file and give the path plus the last few lines.
- Never put `.env` values, tokens, or passwords in the body — key **names** only. If the tracker is
  a public channel, screen internal hostnames and paths once more too.
- One session = one work issue. A handoff is what carries you across that boundary, not a way to
  stretch a single session longer.
</content>
