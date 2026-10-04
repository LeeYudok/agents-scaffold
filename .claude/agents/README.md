# agents/ — AI 팀원 (서브에이전트 정의)

작업 특화 서브에이전트. 각 에이전트 = 마크다운 1파일. frontmatter:

| 필드 | 용도 |
|---|---|
| `name` | 에이전트 이름 |
| `description` | 언제 위임할지(자동 선택 기준) |
| `tools` | 접근 가능 도구(쉼표 구분) |
| `model` | `sonnet`/`opus`/`haiku`/`inherit`(부모 세션 상속) 또는 전체 모델 ID. 작업 강도별 차등 — 기계적 스캔·대량 반복=haiku, 일반 구현·리뷰=sonnet, 심층 판단·보안=opus |
| `memory` | `user`/`project`/`local` — 세션 간 컨텍스트 학습 |
| `maxTurns` | 중단 전 최대 턴 |

신규 생성 시 `{{PROJECT_NAME}}-ag-*` prefix 권장. 동봉 예시: `code-reviewer.md`.

**Codex·agy 용 생성물 (#64)**: `--harness codex|agy|all` 이면 이 파일들을 Codex `.codex/agents/<이름>.toml`
(`developer_instructions` = 본문)과 agy `.agents/agents/<이름>.md`(`name`·`description` 만)로 생성한다. 원본은 여기
하나다 — 생성물은 고치지 않는다. `name`·`description` 은 한 줄 값이어야 하고, 본문에 `'''` 가 있으면 Codex 용은 건너뛴다.
`tools`·`model`·`memory` 는 Claude Code 전용이다(agy 는 이 필드가 있으면 에이전트를 빼므로 생성물에 넣지 않는다).

Workflow 스크립트에서 에이전트를 부를 땐 `model` 외에 `effort`(low~max)로도 강도를
조절할 수 있다 — `workflows/README.md` 참조.
