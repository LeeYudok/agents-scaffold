---
name: yd-frontend-build
description: pnpm 워크스페이스와 Vite 빌드를 설정·정비하거나, 의존성·락파일·번들 크기·폐쇄망 self-host 문제를 다룰 때 사용한다. 프레임워크 자체의 코드 작성이 아니라 빌드/패키징 층이 대상이다.
---

# yd-frontend-build

빌드·패키징 층을 담당한다. 컴포넌트 코드는 `yd-react-expert` 가 맡는다.

이 문서는 **모델이 이미 아는 일반론을 적지 않는다.** 버전별 함정, 실측으로 확인한 사실,
doksam 고유 규약, 그리고 판단이 갈리는 지점만 담는다.

## 0. 먼저 확정할 것

1. **산출물이 어디로 가는가** — 정적 호스팅 / 다른 언어 바이너리에 내장(`go:embed` 등) /
   컨테이너. 내장이면 §4 를 반드시 읽는다. 뒤늦게 바꾸면 `.gitignore` 와 빌드 순서가 전부 얽힌다.
2. **폐쇄망인가** — 그렇다면 외부 CDN·폰트·원격 이미지가 0건이어야 한다(§3).
3. **패키지 매니저** — 레포에 이미 있는 락파일을 따른다. 섞지 않는다(§1).

## 1. pnpm

### 락파일이 곧 계약이다

- 설치는 CI·재현 환경에서 **`pnpm install --frozen-lockfile`**. 락파일이 어긋나면 조용히
  올려버리는 대신 실패해야 한다.
- 락파일을 지우고 다시 만드는 것은 "고치는" 게 아니라 **의존성 트리 전체를 바꾸는 변경**이다.
  원인 파악 없이 삭제·재생성하지 않는다.
- `package.json` 과 락파일은 **항상 같은 커밋**에 들어간다.

### lifecycle 스크립트는 기본 차단이다

pnpm 10부터 의존성의 install 스크립트가 기본으로 실행되지 않는다. `esbuild`·`sharp` 처럼
네이티브 바이너리를 내려받는 패키지는 **명시 허용**이 필요하다.

```jsonc
// package.json
"pnpm": { "onlyBuiltDependencies": ["esbuild", "sharp"] }
```

증상이 "빌드는 되는데 런타임에 바이너리가 없다"로 나타나므로, 이 계열 오류를 보면
설치 로그의 차단 경고부터 확인한다. **아무거나 허용 목록에 넣지 않는다** — 임의 코드 실행이다.

### 워크스페이스

- `pnpm-workspace.yaml` 이 패키지 경계다. 루트에는 도구만 두고 앱 의존성을 올리지 않는다.
- 패키지 간 참조는 `"workspace:*"`. 버전 번호를 손으로 맞추지 않는다.
- 특정 패키지에서 실행: `pnpm --filter <pkg> build`. 루트에서 `cd` 로 들어가지 않는다.
- 버전을 강제로 맞춰야 하면 `pnpm.overrides`. 단 **왜 필요한지 주석**을 남긴다. 근거 없는
  override 는 다음 업그레이드에서 아무도 못 지운다.

### npx / dlx

일회성 CLI 는 `pnpm dlx <pkg>`. `npx` 는 npm 계열 캐시를 따로 쓰므로 pnpm 레포에서 섞으면
버전이 갈린다. 다만 **shadcn CLI 처럼 `npx` 를 전제로 문서화된 도구**는 그대로 써도 된다 —
설치가 아니라 코드 생성이 목적이라 트리에 영향이 없다.

## 2. Vite

### 반드시 확인하는 설정

```ts
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  build: {
    outDir: "dist",
    sourcemap: false,   // 배포본에 원본 코드를 싣지 않는다
    emptyOutDir: true,  // §4 에 해당하면 false
  },
  server: { proxy: { "/api": "http://localhost:9992" } },
})
```

- **`sourcemap: false`** — 켜두면 배포 산출물에서 원본을 복원할 수 있다. 폐쇄망·사내 도구라도
  기본은 끈다. 필요하면 별도 아티팩트로 빼고 배포물에는 넣지 않는다.
- **`server.proxy`** — 개발 중 백엔드로 넘길 경로. 이걸 안 두면 CORS 를 열게 되고, 그 설정이
  운영까지 따라간다.
- **환경변수는 `VITE_` 접두사만 클라이언트에 노출된다.** 접두사 없는 값은 번들에 안 들어가고,
  반대로 **접두사를 붙이는 순간 공개된다** — 비밀을 넣지 않는다.
- 하위 경로 배포면 `base` 를 지정한다. 안 하면 자산 경로가 루트 기준으로 깨진다.

### TypeScript 5.6+ / 6

`baseUrl` 은 deprecated 다. `paths` 만 두면 tsconfig 위치 기준으로 해석된다.
`baseUrl` 을 남겨두면 TS6 에서 **에러로 빌드가 멈춘다**(경고 아님).

```jsonc
{ "compilerOptions": { "paths": { "@/*": ["./src/*"] } } }
```

Vite 의 `resolve.alias` 와 tsconfig `paths` 는 **둘 다** 필요하다. 하나만 두면
타입은 되는데 번들이 깨지거나, 그 반대가 된다.

`strict: true` 를 확인한다. 스캐폴드 템플릿이 빼놓는 경우가 있다.

## 3. 폐쇄망 — 외부 요청 0건

산출물이 외부로 요청을 보내면 폐쇄망에서 조용히 실패한다. **빌드 후 확인한다.**

- 폰트는 `@font-face` + 로컬 woff2 벤더링. `next/font/google`·Google Fonts CDN 금지.
  **폰트 라이선스 파일을 함께 커밋**한다(OFL 등).
- 이미지·아이콘은 npm 번들 또는 로컬 파일. 원격 URL placeholder 금지.
- 분석·에러수집 SDK 가 딸려오지 않았는지 본다.

`scripts/check_bundle.py` 가 산출물을 훑어 외부 출처·소스맵을 잡아낸다(§6).

## 4. 다른 언어 바이너리에 내장할 때 (go:embed 등)

**빌드 순서가 뒤집힌다.** 프론트 빌드가 백엔드 빌드보다 먼저다. 이걸 문서화하지 않으면
"빌드는 성공했는데 화면이 빈" 상태로 배포된다.

내장 대상이 비어 있으면 컴파일이 실패하므로, 산출물을 커밋하지 않으려면 **자리표시자 하나만
커밋**하고 나머지를 무시한다.

```gitignore
frontend/dist/*
!frontend/dist/.gitkeep
```

이때 두 가지가 동시에 걸린다. **둘 다 처리해야 한다.**

1. **Vite 의 `emptyOutDir: true` 가 `.gitkeep` 을 지운다** → `false` 로 두고, 빌드 스크립트가
   `rm -rf dist/assets dist/index.html` 로 이전 해시 자산만 지운다.
2. **`.gitignore` 의 `dist/` 는 어느 깊이의 `dist` 든 잡는다** → `frontend/dist` 까지 제외되고,
   git 은 제외된 디렉터리로 내려가지 않으므로 **안쪽 negation 이 먹지 않는다.**
   루트만 막으려면 `/dist/` 로 앞에 슬래시를 붙인다. 스캐폴드가 만든 하위 `.gitignore`
   (`frontend/.gitignore` 의 `dist`)도 같이 고쳐야 한다.

빌드하지 않은 채 실행됐을 때 **원인을 알리는 안내 화면**을 서버에 둔다. 빈 화면은 원인 추적에
시간을 잡아먹는다.

검증: `git check-ignore -v <자리표시자>` 로 추적 가능한지, 산출물은 무시되는지 각각 확인한다.

## 5. shadcn / 커스텀 레지스트리

- `shadcn init` 은 프리셋을 **대화형으로 묻고**, 템플릿 인자에 따라 기존 프로젝트를 덮어쓸 수
  있다. 이미 스캐폴드된 프로젝트에서는 **`components.json` 을 직접 작성**하고
  `shadcn add` 만 쓰는 편이 안전하다.
- `components.json` 의 `registries` 에 사설 레지스트리를 등록하면 `@scope/name` 으로 설치된다.
- **`iconLibrary` 를 무엇으로 두든 shadcn 프리미티브 내부는 `lucide-react` 를 import 한다.**
  프로젝트 아이콘 정책이 다르더라도, `components/ui/` 원본 불수정 원칙을 지킬 거면
  `lucide-react` 를 의존성에 남긴다. 자체 코드에서만 정책 아이콘을 쓴다.
- 레지스트리 항목이 그 레포 내부 파일(i18n provider 등)에 의존해 설치 후 컴파일이 깨질 수
  있다. **설치 직후 타입체크**로 확인하고, 안 쓰는 항목이면 지운다.

doksam 프로젝트의 UI 표준·토큰·컴포넌트 선택은 `yd-doksam-ui` 스킬이 단일 진실원천이다.
여기서 중복해 규정하지 않는다.

## 6. 검증

```bash
python3 <스킬경로>/scripts/check_bundle.py <dist 경로>
```

산출물에서 다음을 잡아 `파일:줄` 로 보고하고, 위반이 있으면 exit 1 이다.

- **요청을 유발하는 외부 출처** — `src=`/`href=`/`url()`/`@import`/`fetch()`/`import()` 문맥
- 배포물에 남은 소스맵 (`.map` 파일, `sourceMappingURL`)
- gzip 기준 번들 예산 초과

**URL 이 있다고 요청이 나가는 것은 아니다.** React·react-router·Tailwind 는 에러 메시지에
문서 링크를 심어 두므로, 단순 `grep https://` 는 정상 빌드에서도 여러 건을 뱉는다.
노이즈에 묻히면 "통과"가 아무것도 증명하지 못하므로 **문맥을 보고 판정**한다.
전수 감사가 필요하면 `--strict` 로 문서 링크까지 전부 본다.

번들 예산 기준선. 넘기면 **원인을 지목**해서 보고한다.

| 대상 | 눈여겨볼 선 |
|---|---|
| 초기 JS (gzip) | 200KB |
| 초기 CSS (gzip) | 50KB |
| 폰트 1종 | 한글 서브셋이면 수백 KB 가 정상 — 필요한 굵기만 담는다 |

큰 라이브러리는 동적 `import()` 로 분리한다. 다만 **정적 호스팅이 아닌 내장 배포**에서는
청크를 잘게 쪼개도 실행파일 크기는 그대로다 — 초기 로드 시간만 개선된다.

정당한 예외(자체 도메인 문서 링크 등)는 `--allow-host` 로 넘긴다. 이유 없이 검사 전체를
건너뛰지 않는다 — 면제 수단이 없으면 사람은 검사기를 무시하게 되고, 그 순간 검증이 죽는다.

## 7. 완료 조건

- `pnpm build`(또는 해당 스크립트) 성공, 타입체크 통과
- `check_bundle.py` 통과 (외부 URL·소스맵·예산)
- 내장 배포면: 빌드 순서가 문서·스크립트에 반영됐고, 자리표시자 추적 상태를 확인했다
- 락파일과 `package.json` 이 같은 커밋에 있다
- 예산을 넘겼으면 원인을 지목해 보고한다
