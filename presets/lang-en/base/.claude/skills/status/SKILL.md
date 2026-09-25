---
name: status
description: See project status at a glance. Checks Git status, build, tests, recent issues, and branch status all at once. Use before starting work or when checking on status.
allowed-tools: Bash, Read
---

# Project Status Check

## Execution order (in parallel)

### 1. Git status
```bash
git status --short
git log --oneline -5
git branch -a | grep -v remotes | head -10
```

### 2. Build status (stack detection)
```bash
# if package.json exists — pick one runner (in `a | tail || b` the exit code is tail's, so the fallback never runs)
if [ -f package.json ]; then
  if command -v bun >/dev/null; then tsc="bunx tsc"; build="bun run build"; else tsc="npx tsc"; build="npm run build"; fi
  echo "=== TypeScript ===" && $tsc --noEmit 2>&1 | tail -5
  echo "=== Build ===" && $build 2>&1 | tail -5
fi

# if go.mod exists
[ -f go.mod ] && { echo "=== Go build ==="; go build ./... 2>&1 | tail -5; }

# if Cargo.toml exists
[ -f Cargo.toml ] && { echo "=== Cargo check ==="; cargo check 2>&1 | tail -5; }

# if build.gradle exists
{ [ -f build.gradle ] || [ -f build.gradle.kts ]; } && { echo "=== Gradle ==="; ./gradlew compileJava 2>&1 | tail -5; }
```

### 3. Test status
```bash
# most recent test results (if any)
find . -path ./node_modules -prune -o -path "*/test-results/*" -name "*.xml" -print 2>/dev/null | head -3
```

### 4. Open issues (forge per `rules/forge.md`)
```bash
command -v gh >/dev/null && gh issue list --state open --limit 5 2>/dev/null || true     # GitHub
command -v glab >/dev/null && glab issue list --per-page 5 2>/dev/null || true         # GitLab (defaults to opened)
```

### 5. Process status (pm2/ports)
```bash
command -v pm2 >/dev/null && pm2 list 2>/dev/null | head -20 || true
```

### 6. Today's usage (optional — only when `ccusage` is present)
```bash
# ccusage reports Claude Code usage. If it isn't installed, skip silently
# (it does not apply to other harnesses such as Codex or agy).
command -v ccusage >/dev/null && ccusage daily --since "$(date +%Y%m%d)" --json 2>/dev/null \
  | python3 -c "import json,sys; d=json.load(sys.stdin).get('daily') or [{}]; r=d[0]; print(f\"today {r.get('totalTokens',0):,} tokens / \${r.get('totalCost',0):.2f}\")" 2>/dev/null || true
```

## Output format

```
## Project Status — {{PROJECT_NAME}} (YYYY-MM-DD HH:MM:SS)

### Git
Branch: feature/issue-42-xxx
Changes: 3 modified, 1 untracked
Recent commit: abc1234 fix: ...

### Build
TypeScript: ✅ no errors / ❌ N errors
Build: ✅ succeeded / ❌ failed

### Issues (open)
#42 [feature] ...
#38 [bug] ...

### Usage (only when ccusage is present)
today 1,207,480,323 tokens / $1227.00

### Next steps
- (remaining TODO comments or outstanding work on the current branch)
```

## Learned warnings

(Notes discovered during execution accumulate here)
