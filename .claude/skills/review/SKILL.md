---
name: review
description: 코드 변경사항 전체 리뷰. code-reviewer 에이전트 + security-audit 에이전트를 순차 실행하는 래퍼 스킬. PR/MR 생성 전 또는 리뷰 요청 시 사용.
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# 코드 리뷰 (래퍼)

code-reviewer + security-audit 에이전트를 순차로 실행해 완전한 리뷰를 수행한다.

## 실행 순서

### Step 1 — 변경 범위 파악
```bash
base=$(for r in origin/HEAD origin/main origin/master main master; do git merge-base HEAD "$r" 2>/dev/null && break; done)  # 기본 브랜치 분기점
[ -n "$base" ] || base=$(git rev-parse --verify -q HEAD~1)  # 그래도 비면 범위를 사용자에게 묻고 중단
git diff --stat "$base"       # 커밋 + 미커밋 변경 전부
git diff --name-only "$base"
```

변경이 없으면 종료.

### Step 2 — 코드 리뷰 (code-reviewer 에이전트)

`Agent(subagent_type: "code-reviewer")` 호출:
- 보안: 하드코딩 키/토큰, 입력 검증 누락
- 성능: N+1 쿼리, 불필요한 동기 I/O
- 품질: any 타입, 50줄 초과 함수, 중복, 죽은 코드
- 컨벤션: `.claude/rules/` 규약 위반

### Step 3 — 보안 감사 (security-audit 에이전트)

`Agent(subagent_type: "security-audit")` 호출:
- P0 보안 12개 항목 grep 스캔
- 취약한 암호화, SQL Injection, CORS 와일드카드

### Step 4 — 종합 보고

```
## 코드 리뷰 종합 — {{PROJECT_NAME}}

### 코드 리뷰
CRITICAL N건 / WARNING M건 / SUGGESTION K건

### 보안 감사
P0 위반 N건 / P1 위반 M건

### 머지 권고
✅ 머지 가능 / ❌ CRITICAL 또는 P0 위반으로 머지 보류
```

CRITICAL 또는 P0 위반이 하나라도 있으면 **머지 보류 권고**.

## 빠른 리뷰 (인자 있으면)

`/review quick` — security-audit 생략, code-reviewer만 실행.

## Learned warnings

(실행 중 발견한 주의사항이 여기에 누적됩니다)
