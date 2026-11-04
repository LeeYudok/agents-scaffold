# workflows/ — 저장형 오케스트레이션 워크플로

Claude Code **Workflow 툴**용 결정적(deterministic) 멀티에이전트 오케스트레이션 스크립트.
워크플로 1개 = `.js` 파일 1개. 스킬(모델이 따르는 절차)과 달리 워크플로는 순수 JavaScript
라서 제어 흐름(루프·fan-out·게이트)이 결정적으로 실행되고, 실제 작업은 서브에이전트가 한다.

> Workflow 툴을 제공하는 harness 가 필요. Claude Code 는 `.claude/workflows/*.js` 를 찾아
> `/<name>` 커맨드로 목록에 올린다 — 컨텍스트에는 `meta.description` 한 줄만 들어간다
> (2.1.318 실측, #90). Workflow 툴이 없는 하네스(Codex·agy)에서는 inert 라 동봉 비용이 0이다.

## 파일 형태

모든 스크립트는 순수 리터럴 `meta` 블록으로 시작하고 본문이 이어진다:

```js
export const meta = {
  name: 'my-audit',
  description: '권한 다이얼로그에 표시되는 한 줄',
  whenToUse: '이 워크플로를 고를 상황',
  phases: [{ title: 'Scan', detail: '...' }, { title: 'Verify', detail: '...' }],
}
// 본문 — async 컨텍스트, 순수 JS (TypeScript 문법 불가)
```

본문에 주입되는 프리미티브:

- `agent(prompt, opts)` — 서브에이전트 생성. `opts.schema`(JSON Schema)를 주면 텍스트
  대신 검증된 객체가 반환된다. 그 외 opts: `label`, `phase`, `model`, `effort`,
  `agentType`(예: `sdlc-developer`), `isolation: 'worktree'`.
- `parallel([thunks])` — 동시 실행, 전부 끝날 때까지 배리어. 실패한 thunk 는 `null` —
  사용 전 `.filter(Boolean)`.
- `pipeline(items, stage1, stage2, ...)` — 아이템별로 독립적으로 전 단계 통과,
  단계 사이 배리어 없음. 다단계 작업의 기본 선택.
- `phase(title)` / `log(msg)` — 진행 그룹핑·내레이션.
- `args` — Workflow 툴 호출에 넘긴 값 그대로.

## 베낄 만한 패턴 (`rules-audit.js` 참고 — anthropics/claude-cookbooks 의 orchestrator-workers + evaluator-optimizer 패턴 조합)

- **구조화 반환**: JSON Schema(`FINDINGS`, `VERDICT`)를 한 번 정의해 `opts.schema` 로 —
  출력 파싱 불필요.
- **반박 검증(adversarial verification)**: Scan 에이전트의 발견 하나하나를 별도 검증
  에이전트가 *반박*하게 한다(불확실하면 `real=false`). 비싼 후속 단계 전에 오탐 제거.
  (cookbooks 용어로 evaluator-optimizer — 생성자와 평가자를 분리하는 패턴.)
- **유연한 args 계약**: `배열 | {옵션} | 생략` 을 받고, 호출자가 작업 목록을 안 주면
  첫 에이전트가 직접 발굴.
- **사람 머지 게이트**: 워크플로는 수정·빌드검증·푸시·PR/MR 생성까지 해도
  **절대 머지하지 않는다**. Submit 프롬프트에 명시할 것.
- **worktree 격리**: 수정형 워크플로는 전용 `git worktree` + 이슈 브랜치를 만들고
  그 밖 수정을 금지한다.

## 호출

```
Workflow {name: "rules-audit", args: ["src/pages"]}          # 감사만
Workflow {name: "rules-audit", args: {repair: true}}          # 감사 + 자가 수정
Workflow {scriptPath: ".claude/workflows/rules-audit.js"}     # 경로로
```

## 컨벤션

- 신규 워크플로는 `{{PROJECT_NAME}}-` prefix(프로젝트 네임스페이스) 사용;
  `rules-audit.js` 는 동봉된 범용 예제 — 특화할 때 복사해서 개명.
- 스크립트는 자체 완결 순수 JS; `Date.now()`/`Math.random()` 은 사용 불가
  (resume 을 깨뜨림) — 타임스탬프는 `args` 로 전달.
- 워크플로는 수십 개 에이전트를 띄울 수 있다 — 사용자의 명시적 opt-in 이 있을 때만 실행.
