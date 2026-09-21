# agents-scaffold — 내부 구조

생성되는 `.claude/` 트리와 설계 패턴. 개요는 [README](../README.ko.md) 참조.

## 무엇이 들어있나

```
.claude/
  agents/
    security-audit.md   12-item P0/P1 보안 그레프 스캔
    db-migration.md     DDL 안전성 검증 + 롤백 SQL 생성
    sdlc-developer.md   최소 범위 구현 에이전트 (SDLC 역할 분리)
    sdlc-tester.md      AC/TC 테스트 작성 에이전트
    sdlc-verifier.md    파이프라인 실행·리포트 에이전트
    agent-evolve.md     자기개선 메타 에이전트 — 실행 피드백으로 agents/*.md 자동 개선
  commands/            (Claude Code 에서는 레거시 — 슬래시 커맨드가 skills 로 통합됨)
    sonar.md            SonarQube 분석 (CE task 폴링, sqp_/squ_ 구분)
    sdlc-cycle.md       5단계 SDLC 자동화
    knowledge-graph.md  .claude 지식 그래프 재생성 + 깨진 링크 체크
  hooks/
    pre-commit.sh       pre-commit 게이트 골격 (스택 partial 진입점)
    post-edit-format.sh PostToolUse(Edit|Write) → 자동 포맷
    post-test-notify.sh PostToolUse(Bash, *test*) → 터미널 알림
    stop-memory-remind.sh Stop hook → 세션-once 메모리 리마인드
    cc-check.py         PostToolUse(Bash, git commit) → CC > 15 경고
  memory/
    MEMORY.md           auto-memory 인덱스 (SSOT)
    README.md           메모리 타입·운용 규칙
  rules/
    common.md           P0/P1/P2 우선순위 체계 + 공통 워크플로 (항상 로드)
    security.md         시크릿/인증 P0 + 록아웃·관리자 주입 규칙 (paths 스코프)
    testing.md          기능당 1테스트, mock 단위 우선, 사용자 관점 어설션
    data.md             데이터 스크립트 규칙 — 대량 스테이징 금지, 인코딩 명시
    README.md           paths 스코프 로드 + 룰 작성 원칙
  skills/
    skill-evolve/       자기개선 메타 스킬 (Learned warnings 패턴)
    status/             멀티스택 상태 체크
    review/             code-reviewer + security-audit 래퍼
    memory-factcheck/   메모리 사실 검증 — 코드·DB·이슈 대조로 stale 정정
    security-precheck/  감사 대비 보안 사전점검 → 이슈 → 병렬 수정
    docs-sync/          문서 현행화 — 주장별 사실 대조 + 다국어 짝 파일 동시 갱신
    handoff/            세션 핸드오프 — 재개 가능한 상태를 HANDOFF.md/이슈로 넘김
  workflows/            (자동 로드 아님 — 명시 호출로만 실행)
    rules-audit.js      저장형 Workflow 예제 — 스캔/검증/수정, 머지는 사람 게이트
  scripts/              (자동 로드 아님 — 명시 호출로만 실행)
    knowledge_graph.py  .claude 생태계 그래프 + --check 깨진 링크 게이트
  settings.json         hooks 와이어링 + deny 기본값
AGENTS.md               프로젝트 브레인 — 규칙 SSOT (P0/P1/P2 + 워크플로)
.gemini/settings.json   Gemini CLI 가 AGENTS.md 를 읽도록 context.fileName 지정
presets/                프리셋 조각 (복사 덮어쓰기 방식)
  forge-github/         GitHub forge — gh, PR, `Closes #N` 자동 클로즈
  forge-gitlab/         GitLab forge — glab, MR, `Closes #N` 자동 클로즈(머지 후 확인)
  nextjs/ bun/ ...      스택별 조각 (rules + pre-commit.partial.sh + AGENTS.partial.md)
  lang-en/              영어 오버레이 (base/forge-*/stacks/*) — 아래 `--lang` 참조
bin/                    agents-scaffold.sh 부트스트랩 스크립트
```

## 주요 패턴

- **P0/P1/P2 우선순위**: `common.md` + `AGENTS.md` 에 정의. P0 = 보안/시크릿/데이터 파괴, 예외 없음.
- **SDLC 역할 분리**: developer/tester/verifier 에이전트 + `/sdlc-cycle` 자동화 명령.
- **skill-evolve / agent-evolve**: 실수에서 "Learned warnings" 추가하는 자기개선 패턴. skill-evolve는 `.claude/skills/*.md`, agent-evolve는 `.claude/agents/*.md` 대상.
- **메모리 SSOT**: `.claude/memory/`(시스템 기본 경로 미사용). 타입접두 `project_`/`feedback_`/`reference_`/`user_`.
- **paths 스코프 룰**: frontmatter `paths:` 로 해당 파일 작업 시에만 자동 로드.
- **멀티에이전트 격리**: 병렬 서브에이전트 파일 동시수정 → `isolation: "worktree"`.
