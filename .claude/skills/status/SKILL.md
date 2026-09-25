---
name: status
description: 프로젝트 상태 한눈에 보기. Git 상태·빌드·테스트·최근 이슈·브랜치 현황을 한 번에 조회. 작업 시작 전 또는 상태 점검 시 사용.
allowed-tools: Bash, Read
---

# 프로젝트 상태 조회

## 실행 순서 (병렬로)

### 1. Git 상태
```bash
git status --short
git log --oneline -5
git branch -a | grep -v remotes | head -10
```

### 2. 빌드 상태 (스택 감지)
```bash
# package.json 있으면 — 러너는 하나만 고른다(`a | tail || b` 는 tail 의 종료코드라 폴백이 돌지 않는다)
if [ -f package.json ]; then
  if command -v bun >/dev/null; then tsc="bunx tsc"; build="bun run build"; else tsc="npx tsc"; build="npm run build"; fi
  echo "=== TypeScript ===" && $tsc --noEmit 2>&1 | tail -5
  echo "=== 빌드 ===" && $build 2>&1 | tail -5
fi

# go.mod 있으면
if [ -f go.mod ]; then echo "=== Go build ==="; go build ./... 2>&1 | tail -5; fi

# Cargo.toml 있으면
if [ -f Cargo.toml ]; then echo "=== Cargo check ==="; cargo check 2>&1 | tail -5; fi

# build.gradle 있으면
if [ -f build.gradle ] || [ -f build.gradle.kts ]; then echo "=== Gradle ==="; ./gradlew compileJava 2>&1 | tail -5; fi
```

### 3. 테스트 현황
```bash
# 가장 최근 테스트 결과 (있으면)
find . -path ./node_modules -prune -o -path "*/test-results/*" -name "*.xml" -print 2>/dev/null | head -3
```

### 4. 미완료 이슈 (forge 는 `rules/forge.md` 기준)
```bash
command -v gh >/dev/null && gh issue list --state open --limit 5 2>/dev/null || true     # GitHub
command -v glab >/dev/null && glab issue list --per-page 5 2>/dev/null || true         # GitLab (기본값이 opened)
```

### 5. 프로세스 상태 (pm2/포트)
```bash
command -v pm2 >/dev/null && pm2 list 2>/dev/null | head -20 || true
```

### 6. 오늘 사용량 (옵션 — `ccusage` 가 있을 때만)
```bash
# ccusage 는 Claude Code 전용 사용량 도구다. 설치돼 있지 않으면 조용히 건너뛴다
# (Codex·agy 등 다른 하네스에서는 해당 없음).
command -v ccusage >/dev/null && ccusage daily --since "$(date +%Y%m%d)" --json 2>/dev/null \
  | python3 -c "import json,sys; d=json.load(sys.stdin).get('daily') or [{}]; r=d[0]; print(f\"오늘 {r.get('totalTokens',0):,} 토큰 / \${r.get('totalCost',0):.2f}\")" 2>/dev/null || true
```

## 출력 형식

```
## 프로젝트 상태 — {{PROJECT_NAME}} (YYYY-MM-DD HH:MM:SS)

### Git
브랜치: feature/issue-42-xxx
변경: 3 modified, 1 untracked
최근 커밋: abc1234 fix: ...

### 빌드
TypeScript: ✅ 에러 없음 / ❌ N개 에러
빌드: ✅ 성공 / ❌ 실패

### 이슈 (오픈)
#42 [feature] ...
#38 [bug] ...

### 사용량 (ccusage 있을 때만)
오늘 1,207,480,323 토큰 / $1227.00

### 다음 할 일
- (현재 브랜치 기준 TODO 코멘트나 남은 작업)
```

## Learned warnings

(실행 중 발견한 주의사항이 여기에 누적됩니다)
