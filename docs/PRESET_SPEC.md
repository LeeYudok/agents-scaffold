# 스택 프리셋 명세

이 문서는 `bin/agents-scaffold.sh` 가 소비하는 `presets/<stack>/` 하위 스택 프리셋의
필수 레이아웃과 동작을 정의한다. 신규 프리셋을 추가하거나 기존 프리셋을 감사하는
사람을 위한 레퍼런스이며 — 여기를 가리키는 기여 워크플로는 `CONTRIBUTING.md` 참조.

## 디렉터리 구조

```
presets/<stack>/
  .claude/
    rules/
      <stack>.md                 # 필수: paths 스코프 룰 파일
    hooks/
      pre-commit.partial.sh      # 선택: 빌드/린트/테스트 게이트 조각
```

`presets/<stack>/.claude/` 하위의 모든 것은 대상 레포의 `.claude/` 로 그대로
복사된다. 단 하나 예외가 있는데, `pre-commit.partial.sh` 라는 이름의 파일은
독립 파일로 복사되지 않고 대상의 `.claude/hooks/pre-commit.sh` 안으로
스플라이스(삽입)된다(아래 참조).

자동화할 게이트가 없는 프리셋(예: 대부분 lint/scan 툴링이라 보편적으로 설치돼
있지 않은 `ops`)은 룰 파일만 제공하고 `pre-commit.partial.sh` 를 아예 생략해도
된다. `docs/OPTIONS.md`/`docs/OPTIONS.en.md` 는 이를 pre-commit 게이트 열에 `—` 로 표기한다.

## 룰 파일(`<stack>.md`) 요구사항

- **`paths:` 목록을 담은 YAML 프런트매터가 필수**다 — Claude Code 가 룰을 언제
  자동 로드할지 스코프를 지정하는 글롭 목록이다(`paths:` 가 없어 항상 로드되는
  `.claude/rules/common.md` 와 대비된다). `bun.md` 발췌 예시:

  ```yaml
  ---
  paths:
    - "**/*.ts"
    - "**/*.tsx"
    - "api/**/*.ts"
    - "src/**/*.ts"
  ---
  ```

- 글롭은 무관한 파일 타입까지 룰을 로드하지 않도록 충분히 구체적이어야 하되,
  스택의 실제 소스 트리 변형(예: `web/app/**/*.tsx` 같은 대안 루트 레이아웃)을
  커버할 만큼은 넓어야 한다 — 기존 프리셋은 보통 3~6개 패턴을 나열한다.
- 내용은 기존 프리셋과 같은 내부 구조를 따른다. 짧은 스택/툴링 절, 코드
  컨벤션, 그다음 `AGENTS.md`/`.claude/rules/common.md` 에 정의된 우선순위
  등급을 그대로 반영하는 명시적 `## P0` 와 `## P1`(선택적으로 `## P2`) 절
  순서다. P0 항목은 진짜로 협상 불가한 것(시크릿, `.env` 스테이징, 인증)이어야
  한다 — 스타일 취향을 여기 넣지 말 것.
- 프로젝트 고유 값을 하드코딩하는 대신 `{{PROJECT_NAME}}` / `{{JAVA_VERSION}}`
  형태의 플레이스홀더를 사용한다(아래 "플레이스홀더" 참조).

## `pre-commit.partial.sh` 계약

`bin/agents-scaffold.sh` 는 선택된 각 스택의 파셜을 대상의
`.claude/hooks/pre-commit.sh` 안 `# --- STACK CHECKS` 마커 줄 바로 뒤에,
`--stack` 에 전달된 순서대로 삽입한다. 여러 파셜은 하나의 파일 안에 이어
붙어서, 베이스 스크립트의 끝부분 `echo "pre-commit 통과"; exit 0` 이전까지
전부 같은 `bash -euo pipefail` 프로세스에서 실행된다.

### 파셜이 `exit 0` 을 호출하면 안 되는 이유

**파셜은 절대 `exit 0` 을 호출해서는 안 된다.** 파셜이 성공 경로에서
`exit 0` 을 호출하면 셸이 그 자리에서 *스크립트 전체*를 종료시켜버린다 —
그 뒤에 삽입된 다른 모든 스택 파셜과 베이스 스크립트의 최종 성공 줄까지 전부
건너뛴다. 스택이 하나뿐이면 이 문제가 안 보이지만, 레포가 두 개 이상의
스택(예: `bun,python`)을 조합하는 순간 첫 스택의 exit 가 두 번째 스택의
게이트를 조용히 삼켜버린다.

이건 가상의 사례가 아니다 — 이슈 #6(수정 커밋은 `git log --oneline | grep
'#6'` 로 확인, 예: `fix(bun): pre-commit partial exit 0 제거`)이 정확히 이
회귀였다. `bun` 파셜에서 통과한 `bunx tsc` 실행이 `exit 0` 을 호출했고,
이는 `--stack` 에서 `bun` 뒤에 나열된 어떤 스택도 게이트 검사를 전혀 받지
못했다는 뜻이었다.

올바른 패턴:

- **실패 시**: `echo "..." >&2; exit 2`(커밋을 막는다). 파셜이 호출해도 되는
  *유일한* `exit` 이다.
- **성공 또는 "툴 미설치" 시**: 그대로 통과시킨다 — `exit 0` 을 호출하지
  않고, 아예 `exit` 자체를 하지 않는다. 제어 흐름이 파셜 끝에 도달해
  다음(다음 파셜, 또는 베이스 스크립트의 최종 `exit 0`)으로 이어지게
  둔다.
- **툴 미설치 시**(예: `tsc` 미설치): stderr 에 경고를 출력하고 통과시킨다 —
  누락된 툴링 때문에 커밋을 막지 말 것, 그리고 조기에 exit 하지도 말 것.
  레퍼런스 패턴은 `presets/bun/.claude/hooks/pre-commit.partial.sh` 참조
  (`if ... tsc --version >/dev/null 2>&1; then ... else echo "... skipping"
  >&2; fi` — `else` 분기에 `exit` 없음).

### 그 외 파셜 컨벤션

- `set -euo pipefail` 이 이미 활성화돼 있다고 가정한다(베이스 스크립트에서
  상속) — 다시 선언하지 말 것, 그리고 "매치 없음"에 대해 0이 아닌 값을
  반환하는 명령을 조심할 것(예: 기존 파셜들이 `grep -E 'error TS' || true`
  로 하듯 적절히 `|| true` 를 파이프).
- 하드코딩된 전역 바이너리보다 프로젝트에 이미 설정된 런타임/툴체인
  매니저를 우선한다(예: `presets/nextjs/.claude/hooks/pre-commit.partial.sh`
  가 하듯 `npx` 로 폴백하기 전에 `bunx` 를 먼저 시도).
- 실패 출력은 실용적이고 한정된 크기로 유지한다 — 무제한 로그를 그대로
  덤프하지 말고 긴 컴파일러 출력은 `head -20` 등으로 파이프할 것.
- 스택의 설정 파일 존재 여부로 가드한다(예: `if [ -f tsconfig.json ]; then
  ... fi`) — 그래야 스택을 선택했지만 아직 스캐폴딩하지 않은 레포에서
  파셜이 no-op 이 된다.

## 플레이스홀더

`presets/<stack>/.claude/` 하위 모든 파일은 다음 토큰을 쓸 수 있다. 이들은
프리셋 머지 이후 레포 전역(베이스 `.claude/`, `AGENTS.md` 에도)에서 치환된다:

| 토큰 | 치환 값 |
|---|---|
| `{{PROJECT_NAME}}` | `--name` 값, 또는 대상 디렉터리의 basename |
| `{{JAVA_VERSION}}` | `1.8`(현재 유일한 스택 고유 플레이스홀더, `springboot` 가 사용) |

새 프리셋에 스택 고유 플레이스홀더가 필요하면 `bin/agents-scaffold.sh` 3단계의
`sed` 호출에 치환을 추가하고, 여기와 `README.md` 의 플레이스홀더 표에도
문서화한다 — 스크립트가 채울 방법을 모르는 임의 토큰을 만들지 말 것.

## 언어 오버레이 (`presets/lang-en/`)

`--lang en` 은 (한국어) 베이스·forge·스택 프리셋 위에 영어 번역을 얹는다 —
동일한 `merge_preset()` 복사-덮어쓰기 메커니즘을 통해 마지막에 적용되며,
`skip_partial` 이 설정되어 lang 오버레이 안에 딸려 들어온 `pre-commit.partial.sh`
가 있어도 훅에 다시 스플라이스되지 않고 무시된다.

```
presets/lang-en/
  base/.claude/...                      # base .claude/ 트리를 미러
  base/AGENTS.md  # 루트 파일, 직접 복사(.claude/ 하위 아님)
  forge-github/.claude/...              # presets/forge-github/.claude/ 를 미러
  forge-gitlab/.claude/...              # presets/forge-gitlab/.claude/ 를 미러
  stacks/<stack>/.claude/rules/<stack>.md  # presets/<stack>/.claude/rules/<stack>.md 를 미러
```

번역 기여 규칙:

- `presets/lang-en/` 하위의 모든 파일은 그것이 오버레이하는 한국어 트리에
  동일한 이름의 대응 파일이 있어야 한다 — 고아 번역 금지.
- `pre-commit.partial.sh` 는 절대 번역·오버레이하지 않는다 — 이건 산문이
  아니라 셸 코드이며, lang 메커니즘 전체의 바깥에 있다.
- `.claude/scripts/*.py`(예: `knowledge_graph.py`)도 마찬가지로 오버레이하지
  않는다 — 코드 파일은 `--lang` 과 무관하게 영어 메시지를 유지한다(훅과
  같은 선례).
- `.claude/workflows/` 하위 워크플로 `.js` 파일**은** 오버레이 대상이다.
  단 에이전트 프롬프트 문자열, `meta` 설명, 주석만 번역한다 — 스키마와
  코드 구조는 한국어 베이스와 동일해야 한다.
- 구조를 정확히 보존한다: 동일한 헤딩, 동일한 표 행, 동일한
  `{{PROJECT_NAME}}`/`{{JAVA_VERSION}}` 플레이스홀더, 동일한 P0/P1/P2 등급,
  동일한 코드블록(grep 패턴과 명령은 기능적으로 동일하게 유지 — 화면 표시용
  문자열과 산문만 번역한다).
- 새 스택이나 forge 프리셋을 추가할 때는 같은 변경 안에서 한국어 파일과
  그에 대응하는 `presets/lang-en/...` 파일을 함께 추가한다 — 아래 체크리스트
  참조.

## 신규 프리셋 체크리스트

- [ ] `presets/<stack>/.claude/rules/<stack>.md` 가 유효한 `paths:`
      프런트매터와 `## P0`/`## P1` 절을 갖추고 존재한다.
- [ ] 스택에 자동화 가능한 빌드/린트/테스트 단계가 있다면
      `presets/<stack>/.claude/hooks/pre-commit.partial.sh` 가 존재하고
      **어디에도 `exit 0` 이 없다**(실패 시 `exit 2` 만, 또는 `exit` 자체가
      없음).
- [ ] 파셜은 자신의 툴체인이 설치돼 있지 않을 때 깔끔하게 통과한다
      (stderr 에 경고, 막지 않음, 조기 exit 하지 않음).
- [ ] `docs/OPTIONS.md` 와 `docs/OPTIONS.en.md` 양쪽의 스택 프리셋 표에 행이
      추가됐다(룰 파일 설명 + 게이트 열, 게이트가 없으면 `—`).
- [ ] `presets/<stack>/.claude/rules/<stack>.md` 의 영어 대응물로
      `presets/lang-en/stacks/<stack>/.claude/rules/<stack>.md` 가
      추가됐다.
- [ ] `bin/agents-scaffold.sh <dir> --stack <stack> --name scratch` 로 스크래치
      레포를 부트스트랩해 다음을 확인했다:
  - 룰 파일이 플레이스홀더가 치환된 채로 `.claude/rules/<stack>.md` 에
    안착한다,
  - 파셜(있다면)이 `.claude/hooks/pre-commit.sh` 안 `# --- STACK CHECKS`
    마커 뒤에 스플라이스되어 나타난다,
  - 의도적인 lint/build 실패가 `git commit` 을 exit 2 로 실패시키고,
    고치면 커밋이 통과한다,
  - 적어도 하나의 기존 스택과 조합했을 때(예: `<stack>,bun`) 양쪽 게이트가
    모두 실행된다 — 이것이 이슈 #6 의 회귀 클래스다.
- [ ] 워크플로 자체를 갱신해야 한다면 `CONTRIBUTING.md` 의 "신규 스택
      프리셋 기여하기" 절에서도 신규 프리셋을 참조한다.
