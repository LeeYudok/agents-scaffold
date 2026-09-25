---
name: security-precheck
description: 외부 보안팀 코드 검사 전 자체 사전점검. security-audit 에이전트(+ 설정돼 있으면 SonarQube 보안 핫스팟)를 돌려 P0/P1/P2로 정리하고, 발견사항을 이슈로 쪼개 병렬 서브에이전트로 고친다. "보안 검사", "보안 점검", "코드 감사" 언급 시 사용.
user-invocable: true
allowed-tools: Bash, Agent, Read, Edit, Write
---

# 보안 사전점검 (외부 감사 대비)

외부 보안팀이 쓸 기준과 같은 기준으로 먼저 훑어서 고쳐두는 워크플로.

## 1. 스캔 (병렬)

동시 실행:

```
Agent(subagent_type: "security-audit") — P0 코드 규칙 12항목(하드코딩 시크릿·인증누락·PII로깅 등)
  + 에이전트 설정 8항목(.claude/훅·MCP·permissions·프롬프트 인젝션) grep 기반 스캔
```

```bash
# SonarQube 보안 핫스팟 (TO_REVIEW만) — sonar-project.properties 없으면 이 단계는
# 스킵하고 스킵 사실만 보고. 호스트/토큰 하드코딩 금지:
# 환경변수 $SONAR_HOST_URL / $SONAR_TOKEN 사용.
if [ -f sonar-project.properties ]; then
  key=$(grep 'sonar.projectKey' sonar-project.properties | cut -d= -f2-)
  curl -s -u "${SONAR_TOKEN}:" \
    "${SONAR_HOST_URL}/api/hotspots/search?projectKey=$key&status=TO_REVIEW&ps=500" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('TO_REVIEW:', len(d['hotspots'])); [print(h['ruleKey'], h['component'], h.get('line','')) for h in d['hotspots']]"
fi
```

security-audit 프롬프트에는 이 프로젝트의 구체 맥락(인증 방식, 세션 처리, CORS 설정,
데이터 접근 계층, PII 필드)을 짚어주면 결과 품질이 좋아짐 — 기억으로 서술하지 말고
스킬 실행 시점에 레포의 인증/세션/CORS/데이터접근 진입점을 grep 으로 확인해서
실제 발견한 것을 반영.

## 2. 등급 분류 + 보고

- **P0(치명적)**: 즉시 에스컬레이션 대상. 하드코딩 시크릿, 인증 우회, SQL 인젝션, `.env` git 유출 등.
- **P1(권장 개선)**: 이 스킬의 주 타겟. rate-limit 부재, 쿠키 속성 누락, 상수시간 비교 누락, 과도한 permission allow, PII 로깅 등.
- **통과**: 확인했지만 문제없는 항목도 명시(무엇을 확인했는지 신뢰도 근거로).

표 형식으로 보고: `P0 N건 / P1 N건 / 통과 N건`.

## 3. 이슈 등록 (P1 이상만, 트리비얼 제외)

같은 파일/같은 주제끼리 묶어서 이슈 하나로 — 발견사항당 이슈 남발 금지.
예: 같은 인증 컨트롤러에서 발견된 rate-limit·쿠키속성·상수시간비교 3건은 이슈 1개로.

```bash
# forge CLI 는 rules/forge.md 기준
gh issue create -t "<제목>" -b "<사전점검 배경 + 구체적 발견사항 + 관련 파일>"       # GitHub
glab issue create -t "<제목>" -d "<사전점검 배경 + 구체적 발견사항 + 관련 파일>" -y  # GitLab
```

로컬 설정(`.claude/settings.local.json` allow 트림, MCP 권한 재검토 등)은 이슈
없이 바로 처리 — 코드가 아니라 로컬 스코프 설정이라 P1 워크플로 대상이 아님.

## 4. 병렬 처리 (모델 티어 분산)

이슈를 성격별로 나눠 동시에 `Agent` 호출. **같은 파일을 건드리는 이슈는 한
에이전트에 몰아서** — 별도 에이전트로 쪼개면 같은 파일 동시수정 충돌.

| 작업 성격 | subagent_type | model |
|---|---|---|
| 인증/암호/세션 등 보안 판단이 들어가는 백엔드 수정 | sdlc-developer | opus |
| 일반 구현(로깅/검증/설정) | sdlc-developer | sonnet |
| 조사만 하고 근거 있으면 유지, 없으면 수정하는 단순 검토 | general-purpose | haiku |

각 Agent 호출에 `isolation: "worktree"` 필수(병렬 파일 수정 충돌 방지),
브랜치 생성 후 **push/merge는 하지 말고 커밋까지만** 하도록 프롬프트에 명시 —
머지는 부모 세션이 순차로 게이트한다(동시에 여러 worktree가 main을 건드리면
레이스 발생).

## 5. 순차 머지 + 클로즈 (PR/MR 경유)

에이전트 완료 알림 올 때마다:

1. 보안/인증 관련 변경이면 diff를 직접 읽고 검토(상수시간 비교 방식, 세션
   키 선택, rate-limit 스코프 등 — 틀리면 사전점검의 의미가 없어짐)
2. `git push -u origin <branch>` → PR/MR 생성(본문 `Closes #N`). 기본 브랜치에 로컬 merge·직접
   push 금지(P1 — `main`/`develop` 직접 커밋 금지)
3. CI 와 프로젝트 빌드/테스트 게이트(`.claude/hooks/pre-commit.sh` 의 스택 게이트가 기준) 통과 후
   머지. PR/MR 은 **하나씩** 머지하고, 다음 것은 기본 브랜치를 반영(`git merge origin/<default>`)한
   뒤 게이트를 다시 확인 — 동시 머지 레이스 방지
4. `git worktree remove <path> --force && git branch -d <branch>`
5. forge 컨벤션(`rules/forge.md`)대로 이슈 클로즈 확인 — 자동 클로즈 안 된 것만 수동

## 6. 메모리 기록

`.claude/memory/project_security-precheck.md`에 날짜·발견건수·처리 이슈번호·
**받아들이기로 한 리스크**(예: rate-limit 키가 프록시 뒤에서 부정확할 수 있음,
특정 MCP allow 유지 결정 등)를 남긴다. 다음 점검 때 이미 검토하고 유지하기로 한
항목을 또 묻지 않기 위함.

## Learned warnings

- Rate-limit/lockout 키로 원시 클라이언트 주소(`request.getRemoteAddr()` 등)만 쓰면
  리버스프록시 뒤에서 전체 요청이 프록시 IP로 잡혀 전역 잠금이 될 수 있음 — 배포
  토폴로지에 따라 `X-Forwarded-For` 파싱 필요 여부를 검증 단계에서 확인.
- worktree에는 설치된 의존성(`node_modules`, venv 등)이 없어 프론트/빌드 게이트가
  환경적으로 실패하는 경우가 있음 — 백엔드 전용 변경이면 심링크로 우회 가능(커밋
  대상 아님), 프론트 변경이 포함된 이슈라면 해당 worktree에서 패키지 설치
  (lockfile 고정)를 먼저 실행하도록 에이전트 프롬프트에 명시.
- MCP 권한(`mcp__*`)은 툴 단위 grant라 "읽기 전용만 허용" 같은 세분화가
  불가능 — 실사용 필요성이 있으면 무리하게 제거하지 말고 근거를 메모리에
  남기고 유지.
