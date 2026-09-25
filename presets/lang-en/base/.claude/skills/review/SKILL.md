---
name: review
description: Full review of code changes. A wrapper skill that runs the code-reviewer agent and the security-audit agent in sequence. Use before creating a PR/MR or when a review is requested.
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# Code Review (wrapper)

Runs the code-reviewer + security-audit agents in sequence for a complete review.

## Execution order

### Step 1 — Identify the scope of change
```bash
base=$(for r in origin/HEAD origin/main origin/master main master; do git merge-base HEAD "$r" 2>/dev/null && break; done)  # fork point from the default branch
[ -n "$base" ] || base=$(git rev-parse --verify -q HEAD~1)  # still empty: ask the user for the range and stop
git diff --stat "$base"       # committed + uncommitted changes
git diff --name-only "$base"
```

Stop if there are no changes.

### Step 2 — Code review (code-reviewer agent)

Invoke `Agent(subagent_type: "code-reviewer")`:
- Security: hardcoded keys/tokens, missing input validation
- Performance: N+1 queries, unnecessary synchronous I/O
- Quality: `any` types, functions over 50 lines, duplication, dead code
- Convention: violations of `.claude/rules/` conventions

### Step 3 — Security audit (security-audit agent)

Invoke `Agent(subagent_type: "security-audit")`:
- grep scan of the 12 P0 security items
- weak cryptography, SQL injection, CORS wildcards

### Step 4 — Combined report

```
## Code Review Summary — {{PROJECT_NAME}}

### Code Review
N CRITICAL / M WARNING / K SUGGESTION

### Security Audit
N P0 violations / M P1 violations

### Merge Recommendation
✅ Ready to merge / ❌ Hold for CRITICAL or P0 violations
```

If there is even one CRITICAL or P0 violation, **recommend holding the merge**.

## Quick review (when an argument is given)

`/review quick` — skip security-audit, run code-reviewer only.

## Learned warnings

(Notes discovered during execution accumulate here)
