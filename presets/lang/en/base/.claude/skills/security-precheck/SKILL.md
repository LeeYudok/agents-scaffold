---
name: security-precheck
description: Self-run security pre-check ahead of an external security-team code audit. Runs the security-audit agent (plus SonarQube security hotspots when configured), grades findings P0/P1/P2, splits them into issues, and fixes them with parallel subagents. Use on "security check", "security audit prep", "code audit" requests.
user-invocable: true
allowed-tools: Bash, Agent, Read, Edit, Write
---

# Security Pre-check (before an external audit)

Sweep the codebase with the same criteria an external security team would use, and fix
findings ahead of time.

## 1. Scan (parallel)

Run concurrently:

```
Agent(subagent_type: "security-audit") — grep-based scan of the 12 P0 code items
  (hardcoded secrets, missing auth, PII logging, ...) + 8 agent-config items
  (.claude/ hooks, MCP, permissions, prompt injection)
```

```bash
# SonarQube security hotspots (TO_REVIEW only) — skip this step with a note if the
# project has no sonar-project.properties. Never hardcode the host or token:
# use $SONAR_HOST_URL / $SONAR_TOKEN from the environment.
if [ -f sonar-project.properties ]; then
  key=$(grep 'sonar.projectKey' sonar-project.properties | cut -d= -f2-)
  curl -s -u "${SONAR_TOKEN}:" \
    "${SONAR_HOST_URL}/api/hotspots/search?projectKey=$key&status=TO_REVIEW&ps=500" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('TO_REVIEW:', len(d['hotspots'])); [print(h['ruleKey'], h['component'], h.get('line','')) for h in d['hotspots']]"
fi
```

The security-audit agent produces better results when its prompt names this project's
concrete context (auth mechanism, session handling, CORS config, data-access layer,
PII fields). Don't describe these from memory — at run time, grep the repo for its
auth/session/CORS/data-access entry points and include what you actually find.

## 2. Grading + report

- **P0 (critical)**: escalate immediately. Hardcoded secrets, auth bypass, SQL injection, `.env` leaked into git, etc.
- **P1 (recommended fix)**: this skill's main target. Missing rate limits, missing cookie attributes, missing constant-time comparison, overly broad permission allows, PII logging, etc.
- **Pass**: also list items that were checked and found clean (what was checked is the evidence of coverage).

Report as a table: `P0 N / P1 N / pass N`.

## 3. Issue registration (P1 and up, skip trivia)

Group findings by file/topic into one issue each — no issue-per-finding spam.
Example: three findings in the same auth controller (rate limit, cookie attributes,
constant-time comparison) become one issue.

```bash
# forge CLI per rules/forge.md
gh issue create -t "<title>" -b "<pre-check background + concrete findings + files>"   # GitHub
glab issue create -t "<title>" -d "<pre-check background + concrete findings + files>" -y  # GitLab
```

Local-settings fixes (`.claude/settings.local.json` allow-list trimming, MCP permission
review, ...) are handled directly without an issue — local-scope config, not P1 workflow
material.

## 4. Parallel fixing (model tiers)

Split issues by nature and invoke `Agent` concurrently. **Issues touching the same file
go to a single agent** — splitting them causes concurrent-edit conflicts on that file.

| Work type | subagent_type | model |
|---|---|---|
| Backend changes involving security judgment (auth/crypto/session) | sdlc-developer | opus |
| General implementation (logging/validation/config) | sdlc-developer | sonnet |
| Investigate-only review (keep if justified, fix if not) | general-purpose | haiku |

Every Agent call needs `isolation: "worktree"` (prevents parallel edit conflicts). Tell
each agent to create a branch and **commit only — no push, no merge**; the parent session
gates merges sequentially (multiple worktrees hitting main concurrently is a race).

## 5. Sequential merge + close (via PR/MR)

As each agent completes:

1. For security/auth changes, read the diff yourself (constant-time comparison approach, session key choice, rate-limit scope, ... — if these are wrong, the pre-check was pointless)
2. `git push -u origin <branch>` → open a PR/MR (body `Closes #N`). Never merge locally into or
   push directly to the default branch (P1 — no direct commits on `main`/`develop`)
3. Merge once CI and the project's build/test gates (the stack gates in `.claude/hooks/pre-commit.sh`
   are the reference) pass. Merge PRs/MRs **one at a time**; bring the default branch into the next
   one (`git merge origin/<default>`) and re-check its gates first — avoids concurrent-merge races
4. `git worktree remove <path> --force && git branch -d <branch>`
5. Confirm the issue closed per the forge convention (`rules/forge.md`) — close manually only if it did not auto-close

## 6. Memory record

Write `.claude/memory/project_security-precheck.md` with the date, finding counts,
issue numbers handled, and **accepted risks** (e.g. rate-limit keying may be inaccurate
behind a proxy; a specific MCP allow kept with rationale) — so the next pre-check does
not re-litigate items already reviewed and consciously kept.

## Learned warnings

- Keying a rate limit/lockout on the raw client address alone (`request.getRemoteAddr()`
  or equivalent) collapses to the proxy IP behind a reverse proxy, turning it into a
  global lock — verify whether the deployment topology requires `X-Forwarded-For`
  parsing during review.
- Worktrees start without installed dependencies (`node_modules`, venv, ...), so
  frontend/build gates can fail environmentally — for backend-only changes a symlink
  workaround is fine (never commit it); if the issue touches frontend code, tell the
  agent to run the package install (lockfile-frozen) in its worktree first.
- MCP permissions (`mcp__*`) are granted per tool — "read-only only" granularity is not
  possible. If a tool is genuinely needed, don't force-remove it; record the rationale
  in memory and keep it.
