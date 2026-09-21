# AGENTS.md — {{PROJECT_NAME}}

이 파일은 이 저장소에서 작업할 때 AI 에이전트(Claude Code·Gemini CLI·Codex 등)가 따르는
**단일 진실원천(SSOT)** 이다. 프로젝트 브레인. 별도의 `CLAUDE.md`·`GEMINI.md` 포인터 파일은 두지 않는다 —
Claude Code(v2.1.277+)·Codex 는 이 파일을 네이티브로 읽고, Gemini CLI 는 `.gemini/settings.json` 의
`context.fileName` 으로 이 파일을 가리킨다.

이 파일은 **자체 완결**이어야 한다 — 아래 P0/P1 은 다른 파일 로딩 없이 여기서 읽힌다.
`@` import 는 메모리 인덱스 한 줄만 허용한다(아래 "메모리 경로 오버라이드") — import 를 확장하는
하네스에서는 인덱스가 자동 로드되고, 확장하지 않는 하네스에는 경로 포인터로 읽힌다.

> `CLAUDE.md`(또는 `CLAUDE.local.md`)를 새로 만들면 Claude Code 는 이 파일을 **더 이상 읽지 않는다**
> (병합이 아니라 폴백). 꼭 필요하면 그 파일 첫 줄에 `@AGENTS.md` 를 넣을 것.

## 메모리 경로 오버라이드

이 프로젝트의 auto-memory SSOT는 `.claude/memory/` 이다.
- 시스템 기본 경로(`~/.claude/projects/.../memory/`)는 사용하지 않는다.
- 모든 메모리 읽기/쓰기는 `.claude/memory/` 하위에서 수행한다.
- `MEMORY.md` 가 인덱스(단일), 타입접두 `project_`/`feedback_`/`reference_`/`user_`.
- `user_*.md` 만 개인(gitignore), 그 외는 팀 공유.

메모리 인덱스:

@.claude/memory/MEMORY.md

## .claude/ 인프라

개요는 [.claude/README.md](.claude/README.md), 각 하위 디렉터리 README 에 작성 골격과
컨벤션이 있다.

| 디렉터리 | 역할 | 상세 |
| :--- | :--- | :--- |
| `agents/` | 서브에이전트 정의 (code-reviewer, security-audit, db-migration, sdlc-*, agent-evolve) | [README](.claude/agents/README.md) |
| `commands/` | 커스텀 슬래시 커맨드 (fix-issue, sdlc-cycle, sonar, knowledge-graph) | [README](.claude/commands/README.md) |
| `hooks/` | 강제 게이트 — pre-commit, 자동 포맷, observe-lite, 메모리 리마인드 | [README](.claude/hooks/README.md) |
| `memory/` | 프로젝트 메모리 SSOT — MEMORY.md 인덱스 + 타입접두 파일 | [README](.claude/memory/README.md) |
| `rules/` | 맥락 인지 룰 — `paths:` 스코프 조건부 로드 | [README](.claude/rules/README.md) |
| `skills/` | 상황별 절차 — review, status, search-first, memory-factcheck, security-precheck, docs-sync, grill-me, handoff 등 | [README](.claude/skills/README.md) |
| `workflows/` | 저장형 Workflow 오케스트레이션 스크립트(`*.js`) — rules-audit 예제 | [README](.claude/workflows/README.md) |
| `scripts/` | 레포 로컬 헬퍼 — knowledge_graph.py(문서 그래프 + 링크 체커) | [README](.claude/scripts/README.md) |

`settings.json` 에 deny 규칙과 훅 바인딩이 있다. 문서 정합성 점검·온보딩은
`/knowledge-graph` 실행.

## 프로젝트 개요

<!-- {{PROJECT_NAME}} 의 한 줄 설명을 여기에. 스택·목표·범위. -->

## 스택

<!-- 예: Next.js 15 (프론트) / Spring Boot 3.x · Java 17 · Gradle (백) -->

## 명령

<!-- 빌드/테스트/실행 명령. 예: ./gradlew build | bun run dev -->

## 컨벤션

- skill/agent 신규 생성 시 `{{PROJECT_NAME}}-` prefix 네임스페이스
- 세부 규약은 `.claude/rules/` 의 paths 스코프 룰 참조
- 스택별 세부 규약 → 아래 우선순위 체계 참조

## 우선순위 체계 (P0/P1/P2)

### P0 — 절대 규칙 (AI/사람 모두, 예외 없음)
P0 위반 시 즉시 작업 중단 + 사용자 에스컬레이션.

- **보안**: 시크릿/토큰/비밀번호를 코드·로그·이슈에 노출 금지
- **데이터**: 프로덕션 DB에 `DELETE/DROP/TRUNCATE` 전 사용자 명시 동의
- **git**: `force push` / `reset --hard` 전 확인. `.env` 스테이징 금지
- **인증**: 인증 없는 API 엔드포인트 신규 추가 금지

#### 스택별 P0

선택한 스택의 P0 는 아래에 **직접 삽입**된다(부트스트랩 시점 생성). 참조 링크에 의존하지
않으므로 `.claude/` 를 로드하지 않는 하네스에서도 도달 가능하다. 상세 규약은
`.claude/rules/<stack>.md` 에 있다.

<!-- STACK P0 -->

### P1 — 필수 (AI 자율 실행 범위, 위반 시 PR 차단)

- 이슈 번호를 브랜치명·커밋·PR/MR 제목에 반드시 포함
- 커밋 전 타입체크·린트 통과 (`.claude/hooks/pre-commit.sh` 자동 게이트)
- 새 기능에 최소 1개 테스트 동반
- `main`/`develop` 직접 커밋 금지 → 항상 feature/fix/chore 브랜치

### P2 — 권장 (리뷰 지적 사항, 예외 협의 가능)

- 함수당 인지 복잡도(CC) 15 이하 (`.claude/hooks/cc-check.py` 경고)
- 파일 1개 = 단일 책임 (300줄 초과 시 분리 검토)
- TODO/FIXME 에 이슈 번호 병기

## 워크플로

1. **이슈 등록** → 2. **브랜치 생성** (`feat/issue-<N>-<slug>`) → 3. **구현** →
4. **pre-commit 자동 게이트 통과** → 5. **PR/MR 생성** → 6. **리뷰** → 7. **머지 + 이슈 클로즈**

이슈 클로즈 규약은 forge 별로 다르다 → `.claude/rules/forge.md` 참조.
GitHub = PR 본문 `Closes #N` 으로 머지 시 자동 클로즈. GitLab 19 = `Closes #N` 자동 클로즈 실측 동작 — 단 머지 후 `glab issue view <N>` 로 확인하고, `opened` 로 남은 경우에만 수동 클로즈.

## 멀티 에이전트 · 병렬 세션

이 레포를 동시에 만지는 모든 워커(세션·서브에이전트·페르소나)는 **각자의 git worktree**
로 격리한다 — 이 섹션은 공유 체크아웃을 쓰던 병렬 세션 두 개가 서로의 작업을
교차오염시킨 사고에서 나왔다.

- 선제 격리: `git worktree add ../{{PROJECT_NAME}}-<slug> -b <type>/issue-<N>` —
  1세션 = 1worktree = 1이슈 = 1브랜치.
- 정식 클론은 default 브랜치 미러로 유지(pull·읽기만 — 거기서 `checkout`/`switch`
  **금지**; 공유 폴더에서 브랜치를 갈아타는 순간 다른 세션의 발밑이 바뀐다).
- `git add` 는 명시 파일만, 디렉터리·`-A` 금지 — 다른 세션의 미커밋 작업을 흡수하지 않기 위함.
- `git status` 에 내가 만들지 않은 변경이 보이면 진행 전에 병렬 세션 여부부터 확인.
- 병렬 서브에이전트가 파일을 동시에 수정하면 `isolation: "worktree"` 필수.
- 머지 후: worktree 제거 + 로컬 브랜치 삭제를 그 자리에서 항상 수행.
- worktree 오케스트레이터(예: Orca) 사용 시: worktree 생성·정리는 해당 도구에 위임 —
  오케스트레이터가 소유한 worktree 를 수동 `git worktree add`/`remove` 로 만지지 않는다
  (도구 상태와 어긋남). 격리 원칙(1세션 = 1worktree = 1이슈 = 1브랜치)은 동일하게
  적용되며, "머지 후 제거" 규칙은 오케스트레이터의 자체 정리로 충족한다.

역할별 에이전트: `.claude/agents/sdlc-*.md` (developer/tester/verifier).
SDLC 자동화: `/sdlc-cycle` 명령 참조.
