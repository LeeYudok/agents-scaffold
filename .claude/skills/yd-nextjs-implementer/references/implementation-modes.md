# 구현 모드별 실행 계약

`SKILL.md`에서 구현 프로필을 정한 뒤 선택한 절만 적용한다. 기존 프로젝트에는
새 스캐폴드를 덮지 않고 현재 package manager와 명령을 따른다.

## Next.js App Router

새 프로젝트는 TypeScript, App Router, ESLint를 켠 `create-next-app`으로 만든다.
기본 확인 명령은 프로젝트 scripts에 맞춰 다음 의미를 모두 충족해야 한다.

```sh
pnpm lint
pnpm test
pnpm build
pnpm dev
```

기본 URL은 `http://localhost:3000`이지만 실제 포트를 기록한다. Next.js 풀스택은
Server Actions/Route Handlers를 사용하고, Java 모드는 타입 있는 API client와
rewrite를 사용한다.

## Vite + React SPA

새 프로젝트는 pnpm + Vite + React + TypeScript로 만들고 `react-router`를
추가한다. 기존 프로젝트의 router major를 보존한다.

### react-router 패키지 함정

**어느 패키지에서 import 하는지가 major마다 다르다.** 2026-08-23 npm 레지스트리
실측 기준이다.

| major | 설치·import | 비고 |
|---|---|---|
| v8 (`react-router` 8.x) | `react-router` | `react-router-dom` 은 8.x가 없다. peer가 react·react-dom **>=19.2.7** 이라 React를 못 올리면 v8도 못 쓴다 |
| v7 (`react-router` 7.x) | `react-router` (권장) 또는 `react-router-dom` 7.x | `react-router-dom` 7.x는 `react-router` 7.x를 그대로 재수출하는 얇은 래퍼다 |
| v6 (`react-router-dom` 6.x) | `react-router-dom` | dist-tag `version-6` 로 유지된다 |

기존 프로젝트는 설치된 버전을 먼저 확인하고 그 major의 표기를 따른다. **v6/v7
API를 한 파일 안에서 섞지 않는다.** React 버전을 올리는 결정은 이 스킬이
임의로 하지 않는다 — 필요하면 근거와 함께 사용자에게 묻는다.

### 화면 ID → 라우트 매핑

`화면`은 route object에, `팝업`·`바텀시트`는 부모 route의 오버레이 상태에
매핑한다. 오버레이는 라우트를 갖지 않으므로 `traceability.json`에 `route`를
쓰지 않고 부모 화면의 구현 파일을 가리킨다.

```tsx
// src/routes.tsx — 화면 ID를 주석이 아니라 매핑표(traceability.json)로 추적한다
export const routes = [
  { path: "/", element: <Home /> },              // DTC-MAIN-001
  { path: "/board", element: <BoardList /> },    // DTC-BOARD-001
  { path: "/board/:boardId", element: <BoardDetail /> }, // DTC-BOARD-002
  { path: "*", element: <NotFound /> },
];
```

라우터에 등록하지 않은 화면은 **빌드도 타입 검사도 통과한다** — 그 URL로
들어갔을 때만 빈 화면이 된다. 그래서 기계로 대조한다.

```sh
python3 <스킬경로>/scripts/validate_traceability.py \
  docs/traceability.json docs/<프로젝트>_business-rules.md --repo-root . \
  --routes src/routes.tsx
```

문서에만 있는 라우트와 라우터에만 있는 라우트를 양방향으로 보고한다. `*`와
index는 화면 ID를 갖지 않으므로 대조 대상이 아니다.

### 직접 진입과 새로고침

SPA는 서버가 모든 경로를 `index.html`로 돌려주지 않으면 **직접 URL 진입과
새로고침이 404가 된다.** `vite dev`는 자동으로 처리하므로 개발 중에는 드러나지
않는다 — 배포 환경(nginx `try_files`, 정적 호스팅의 SPA fallback 설정)에서
반드시 확인한다. 확인하지 못했으면 그 사실을 잔여 위험으로 보고한다.

### mock ↔ 실제 API 전환

데이터 계층 인터페이스는 하나, 어댑터는 둘이다. 컴포넌트는 어느 쪽인지 모른다.

- 전환은 **빌드 타임 플래그**(`import.meta.env.VITE_USE_MOCK` 등)로 하고,
  컴포넌트 안에서 분기하지 않는다.
- mock 어댑터는 동적 import로 분리해 프로덕션 번들에 들어가지 않게 한다.
  들어갔는지는 `yd-frontend-build/scripts/check_bundle.py <dist>`로 확인한다.
- `VITE_` 로 시작하는 값은 전부 번들에 그대로 박히는 **공개 값**이다. API 키·
  토큰을 넣지 않는다. 비밀이 필요하면 그 호출은 프론트가 할 일이 아니다.
- mock으로 끝난 구현은 영속성·인증·권한을 검증했다고 보고하지 않는다.

```sh
pnpm lint
pnpm exec tsc --noEmit
pnpm test
pnpm build
python3 <yd-frontend-build-스킬>/scripts/check_bundle.py dist
pnpm dev
```

기본 URL은 `http://localhost:5173`이지만 실제 포트를 기록한다. SPA fallback은
호스팅 환경에도 설정해 직접 URL 진입이 404가 되지 않게 한다. API가 있으면
`server.proxy`를 사용하고, 배포 시 API base URL은 공개 설정과 비밀 설정을
분리한다.

## traceability.json

저장소의 `docs/traceability.json`을 기본 경로로 쓰되 기존 문서 디렉터리 규약이
있으면 따른다. JSON은 기계가 읽을 수 있어야 하며 주석을 넣지 않는다.

```json
{
  "documentVersion": "1.0.0",
  "frontendMode": "vite-react-spa",
  "screens": [
    {
      "screenId": "DTC-BOARD-001",
      "route": "/board",
      "implementation": ["src/routes/board.tsx"],
      "rules": [
        {
          "ruleId": "DTC-BOARD-001.IN-01",
          "tests": ["src/routes/board.test.tsx"]
        }
      ]
    }
  ]
}
```

규칙 ID 형식은 `<화면ID>.<구분>-<2자리 번호>`다. 구분은 `IN`(입력 검증),
`OUT`(출력 규칙), `INT`(인터랙션), `EDGE`(엣지케이스)다. 같은 ID를 두 번 쓰지
않고, 한 규칙이 여러 파일에 걸리면 배열에 모두 기록한다. 구문서의 임시 키는
원문을 수정하지 않고 manifest에만 `legacy: true`로 표시한다.

규칙 ID가 있는 최신 문서는 구현 완료 전에 다음을 실행한다.

```sh
python3 <스킬경로>/scripts/validate_traceability.py \
  docs/traceability.json docs/<프로젝트>_business-rules.md --repo-root .
```

화면·규칙 ID의 누락/중복/잘못된 연결, 구현·테스트 파일의 부재를 모두
검사하며 위반이 있으면 exit 1이다.
