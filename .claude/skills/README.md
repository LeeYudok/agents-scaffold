# skills/ — 상황별 지능 (스킬)

특정 상황에서 발동하는 절차적 지식. 각 스킬 = 디렉터리 1개 + `SKILL.md`
(frontmatter `name`/`description`(+`user-invocable`) + 본문 절차). description 트리거에
맞으면 Claude가 로드해 그대로 따른다. `user-invocable: true` 면 수동 호출도 가능.

```
skills/
└── <name>/
    ├── SKILL.md      # 본문은 짧게 — 트리거·핵심 절차만
    ├── scripts/      # (옵션) 스킬이 실행하는 스크립트
    └── resources/    # (옵션) 무거운 참조 자료 — 본문에서 링크, 필요할 때만 로드
```

원칙은 progressive disclosure(점진적 공개): SKILL.md 는 항상 로드되므로 짧게 유지하고,
긴 원문·표·예시는 `resources/` 파일로 빼서 필요할 때만 읽게 한다.

동봉: `example-skill/`, `review/`, `status/`, `search-first/`, `skill-evolve/`,
`memory-factcheck/`(메모리 사실 검증), `security-precheck/`(감사 대비 보안 사전점검),
`docs-sync/`(문서 현행화 — 주장별 사실 대조 + 다국어 짝 파일 동시 갱신),
`handoff/`(세션 핸드오프 — 트래커가 있으면 이슈 본문, 없으면 `HANDOFF.md` 로 넘기고 이어받기),
`grill-me/`(적대적 요구사항 심문 — 대화 안에서 끝나는 가장 가벼운 선택지. 더 무거운
superpowers `brainstorming`·Ouroboros 와 작업마다 택일하며, 비교는 README 의
"요구사항 다지기 도구 고르기" 참조).
신규는 `{{PROJECT_NAME}}-sk-*` prefix 권장.

## `yd-*` 스킬 (#78)

[LeeYudok/doksam-skills](https://github.com/LeeYudok/doksam-skills) 에서 옮겨 왔고, 이제 이 레포가 원본이다.
`yd-*` 스킬은 **한국어 전용**이다(`--lang en` 오버레이 없음). 설치할 때 `{{PROJECT_NAME}}` 치환도 하지 않는다.
에이전트 열이 ○ 인 스킬은 `agents/yd-<이름>.md` 가 있어 이름 있는 에이전트로도 부를 수 있다.

**기본 설치 14개**

| 스킬 | 에이전트 | 언제 쓰나 |
|---|---|---|
| [yd-mobile-web-planner](yd-mobile-web-planner/SKILL.md) | ○ | 모바일 웹·앱의 IA·화면설계서(HTML 슬라이드)·Business Rules 를 만들 때 |
| [yd-nextjs-implementer](yd-nextjs-implementer/SKILL.md) | ○ | 화면설계서를 Next.js 또는 Vite + React 코드로 옮길 때 |
| [yd-blueprint](yd-blueprint/SKILL.md) | ○ | 구조·구현 현황·남은 작업을 JSONL 로 적고 청사진 화면으로 띄울 때 |
| [yd-frontend-build](yd-frontend-build/SKILL.md) | ○ | pnpm·Vite 빌드, 의존성, 번들 크기, 폐쇄망 self-host |
| [yd-typescript](yd-typescript/SKILL.md) | — | 타입 경계·비동기 UI·DOM 접근 점검 |
| [yd-react-expert](yd-react-expert/SKILL.md) | ○ | React 19 컴포넌트·상태·effect·접근성·렌더 성능 |
| [yd-go-expert](yd-go-expert/SKILL.md) | ○ | Go 1.22+ 코드 작성·리뷰(에러·동시성·`net/http`·`go:embed`) |
| [yd-db-expert](yd-db-expert/SKILL.md) | ○ | 엔진 무관 관계형 설계(정규화·키·제약·인덱스·트랜잭션·마이그레이션) |
| [yd-pg-expert](yd-pg-expert/SKILL.md) | ○ | PostgreSQL 고유 동작(잠금을 잡는 ALTER·`CONCURRENTLY`·VACUUM·실행계획) |
| [yd-oracle-expert](yd-oracle-expert/SKILL.md) | ○ | Oracle 고유 문제(빈 문자열 NULL·DATE 시각·VARCHAR2 바이트·ROWNUM) |
| [yd-sqlite-expert](yd-sqlite-expert/SKILL.md) | ○ | SQLite 고유 문제(읽기 전용 조회·WAL·잠금·동적 테이블명) |
| [yd-agents-yaml](yd-agents-yaml/SKILL.md) | — | `AGENTS.md` + `AGENTS.yaml` + 검증기 세팅·갱신 |
| [yd-writer-kr](yd-writer-kr/SKILL.md) | ○ | 이슈·PR·문서·공지를 한국어로 쓰거나 고칠 때 |
| [yd-cve-check](yd-cve-check/SKILL.md) | ○ | pnpm 의존성 CVE·GHSA·악성 패키지 점검과 보완(온라인 `pnpm audit`·폐쇄망 OSV 덤프, #79) |

doksam-skills 의 `yd-handoff`·`yd-doc-sync`·`yd-memory-factcheck`·`yd-skill-evolve` 는 같은 역할의
`handoff`·`docs-sync`·`memory-factcheck`·`skill-evolve` 에 합쳤다.

**옵트인 9개** — 메인테이너 환경(특정 GitLab·호스트·ui.doksam.com·FinGuard)을 전제한다. 원본은 이 레포의
`presets/skills-personal/.claude/skills/` 이고, 설치할 때 `--with-personal-skills` 를 줘야 들어간다.
`yd-sdlc-orchestrator`·`yd-finguard`·`yd-doksam-ui`·`yd-script-editor`(에이전트 동봉), `yd-agents-mem`·
`yd-git-ship`·`yd-git-sync`·`yd-claude-auth-sync`·`yd-session-recording`.

## 작성 규약

- frontmatter 는 `name`(폴더명과 같게)과 `description`(트리거 조건을 구체적으로) 필수.
- 테스트 가능한 단언은 `tests/claims.json` 에 `{id, kind, rule, test}` 로 적는다. `rule` 은 SKILL.md 나
  `references/*.md` 에 **글자 그대로** 있어야 하고, `test` 는 unittest 가 실제로 수집하는 테스트여야 한다.
- 스킬 테스트는 `tests/test_*.py`. 레포 루트에서 `scripts/run-skill-tests.sh [스킬명]` 으로 돌린다.
- `tests/test_skill_contracts.py` 가 claims 형식, 문서가 말한 스크립트 경로의 존재, 스킬 간 description 트리거
  중복을 검사한다. 트리거가 겹치면 description 에 경계("X 는 Y 가 맡는다")를 적어 가른다.

설치된 프로젝트에서 스킬 원본은 `.agents/skills/`(Codex·agy 네이티브 경로)이고, `.claude/skills` 는
그 디렉터리를 가리키는 심볼릭 링크다(#61) — 어느 경로로 고쳐도 같은 파일이다. 링크를 만들 수 없는
환경(Windows Git Bash 기본값 등)에서는 `.claude/skills` 가 사본이므로 `.agents/skills` 만 고치고
같은 파일을 사본에도 복사해 두 경로를 파일 단위로 스테이징한다(`git add -- .agents/skills/<경로> .claude/skills/<경로>`).
스테이징된 사본이 원본과 다르면 pre-commit 게이트가 다른 파일을 나열하며 차단한다.
