---
name: yd-doksam-ui
description: doksam 프로젝트의 UI 를 만들거나 수정할 때, 사용자가 "ui.doksam.com 참고" / "doksam-ui" / "독삼 표준 UI" 라고 말할 때, 프론트엔드 작업이 doksam 인프라를 대상으로 할 때 사용한다. ui.doksam.com 을 디자인 단일 진실원천(SSOT)으로 강제한다 — shadcn/ui 시맨틱 토큰(색상 하드코딩 금지), 브랜드 프로필, 자체 호스팅 shadcn 커스텀 레지스트리(npx shadcn add https://ui.doksam.com/r/<name>.json), Phosphor 아이콘 우선, 폐쇄망 셀프호스팅, 기계적 표준 준수 검증. 카탈로그 레포(doksam-ui) 자체를 확장할 때 — 컴포넌트·패턴·템플릿 추가, 데모 작성, 토큰·테마·폰트·프로필 변경, shadcn registry.json / llms.txt 갱신 — 도 이 스킬을 쓴다.
---

# Role

당신은 doksam 프로젝트의 UI 를 **ui.doksam.com 표준에 맞춰** 구현하는, 어떤 예외도 허용하지 않는 수석 프론트엔드 개발자다.
ui.doksam.com(doksam-ui)은 shadcn/ui 기반 디자인 토큰, 브랜드 프로필, 컴포넌트 레지스트리, 사용 규칙을 한곳에 모은 **단일 진실원천(SSOT)** 이다.

**가장 중요한 임무는 환각(Hallucination)을 막는 것이다.** 카탈로그에 없는 UI 를 Tailwind 유틸리티로 임의 창작하지 않으며, 작업 후 스스로 코드를 검증해 규칙 위반이 없음을 기계적으로 증명한다.

---

# 0. 두 가지 모드 — 먼저 어느 쪽인지 정한다

| | 모드 A — 소비자 | 모드 B — 생산자 |
|---|---|---|
| 상황 | 다른 doksam 프로젝트의 화면을 만든다 | **카탈로그 레포(doksam-ui) 자체**를 확장한다 |
| 판별 | 작업 대상 레포에 `lib/showcase/registry.ts` 가 **없다** | 작업 대상 레포에 `lib/showcase/registry.ts` 가 **있다** |
| 원천 | ui.doksam.com 의 `/llms.txt`·`/rules.md` (live fetch) | 레포 안의 `lib/rules-markdown.ts` (파일 원문) |
| 판단 기준 | "이 화면이 표준을 지키는가" | "표준으로서 일관되고 재사용 가능한가" |
| 본문 | → 2장 | → 3장 |

§1(SSOT)·§4(규칙 다이제스트)·§5(자가 검증)는 **두 모드 공통**이다.

---

# 1. SSOT 원칙 및 네트워크 처리 (Fallback)

**이 문서는 요약이고 원본은 따로 있다.** 카탈로그와 규칙은 계속 갱신되므로 작업 시작 시 반드시 원본을 확인한다.

| 원천 | 용도 | 모드 |
|---|---|---|
| `https://ui.doksam.com/llms.txt` | 기계 판독 카탈로그 — 설치 가능한 전 항목·install 명령·의존성·브랜드 프로필 목록 | A |
| `https://ui.doksam.com/rules.md` | 사용 규칙 markdown 원문 (`curl -s https://ui.doksam.com/rules.md`) | A |
| `https://ui.doksam.com/components` 등 | 라이브 데모 + 코드 스니펫 | A |
| 레포의 `lib/rules-markdown.ts` (`RULES_SECTIONS`) | 규칙 조항의 **진짜 원본** — 위 `rules.md` 가 여기서 파생된다 | B |

**Fallback 규칙 (모드 A):** `curl` 이 실패하거나 폐쇄망이라 접근할 수 없으면 조용히 넘어가지 말고 **즉시 사용자에게 네트워크 차단 사실을 보고**한 뒤, §4 다이제스트만으로 보수적으로 진행한다. 없는 컴포넌트를 지어내지 말고 기본 HTML/CSS 로 대체한다.

**규칙을 바꿔야 하면 `lib/rules-markdown.ts` 만 고친다** (모드 B). `/rules` 페이지 렌더링과 AI 프롬프트용 `RULES_MARKDOWN` 이 모두 거기서 파생된다. 이 스킬을 포함해 어디에도 규칙 문장을 복제하지 않는다 — 복제본과 원문이 어긋나면 **원문이 옳고 이 스킬이 틀린 것이다.**

---

# 2. 모드 A — 소비자 워크플로

1. **카탈로그 확인** — `curl -s https://ui.doksam.com/llms.txt` 로 현재 설치 가능한 목록을 읽는다.
2. **브랜드 프로필 확정** — 프로필은 테마·폰트·`defaultMode`·`radius`·`density` 를 미리 고정해 둔 층이고, **프로젝트가 고르는 단위는 프로필 하나**다. 사용 가능한 프로필 목록은 위 `llms.txt` 의 `registry:theme` 항목(`profile-*`)에서 읽는다 — 이 문서에 목록을 박아두지 않는다(프로필이 추가되면 낡는다). 사용자가 지정하지 않았으면 프로젝트 성격 기준으로 제안하고 합의한다. **프로필이 고정한 radius·density 는 임의로 덮어쓰지 않는다** — 바꿀 필요가 생기면 카탈로그 레포에 프로필을 추가·수정한다(모드 B).
3. **레지스트리 연결** — `components.json` 이 없으면 `npx shadcn@latest init` 먼저. 이후 `registries` 에 `"@doksam-ui": "https://ui.doksam.com/r/{name}.json"` 을 등록해 `@doksam-ui/<name>` 으로 설치한다. 단건 설치는 `npx shadcn add https://ui.doksam.com/r/<name>.json`.
4. **재발명·환각 금지** — 필요한 UI 가 생기면 **만들기 전에 카탈로그를 무조건 먼저 찾는다.** 이미 있는 자산은 코드를 복붙하거나 Tailwind 로 재구현하지 않고 레지스트리로 설치한다.
5. **규칙 준수 구현** — §4 다이제스트를 지키며 구현한다.
6. **기계적 자가 검증** — §5.
7. **최종 보고** — §5.3 형식으로 제출한다.

---

# 3. 모드 B — 생산자 워크플로 (카탈로그 확장)

doksam-ui 는 개별 화면을 만드는 앱이 아니라 **다른 프로젝트가 가져다 쓰는 표준을 정의하는 레포**다. 모든 변경은 "한 화면이 예뻐지는가"가 아니라 **"표준으로서 일관되고 재사용 가능한가"** 로 판단한다.

## 3.1 3계층 카탈로그

| 계층 | 라우트 | 레지스트리(단일 진실원천) | 성격 |
|---|---|---|---|
| 컴포넌트 | `/components/<slug>` | `lib/showcase/registry.ts` (+ `lib/showcase/demo-loaders.ts`) | "무엇을 쓰는가" |
| 패턴 | `/patterns/<slug>` | `lib/patterns/registry.ts` | "어떻게 조합하는가" |
| 템플릿 | `/templates/<slug>` | `lib/templates/registry.ts` | "화면 하나가 어떻게 완성되는가" |

그 외 파운데이션: `/tokens`, `/profiles`, `/icons`, `/rules`.
테마 `themes/index.ts` · 폰트 `fonts/index.ts` · 프로필 `profiles/index.ts` · shadcn 배포 `registry.json`(루트).

**레지스트리에 등록하지 않으면 페이지·사이드바에 나타나지 않는다.** 파일만 추가하고 끝내는 것이 가장 흔한 실수다.

## 3.2 컴포넌트 계층 구분

`ComponentLayer`(`lib/showcase/types.ts`)는 출처가 아니라 **조립 수준**으로 나눈다.

- `primitive` — shadcn CLI 가 `components/ui/` 에 설치한 저수준 빌딩블록. **수정 금지.**
- `composition` — 프리미티브를 조합한 상위 컴포넌트. `components/<name>.tsx` (kebab-case).

카테고리(`ComponentCategory`)는 `form` · `overlay` · `layout` · `data` · `chat` · `bizinfo`(프로젝트 확장) · `finance`(금융 도메인 확장). 도메인 색이 짙은 것을 공통 카테고리에 넣지 않는다 — 확장 카테고리가 그 용도다.

### 새 컴포넌트를 만들 기준

만든다: 같은 시각 패턴이 2곳 이상 반복될 때 / 도메인 규칙을 코드로 굳혀야 할 때(등락색, 사업자번호 포맷, 상태 뱃지) / 다른 프로젝트가 `npx shadcn add` 로 가져갈 가치가 있을 때.

만들지 않는다: 한 템플릿에서만 쓰는 일회성 레이아웃 / className 조합만 하는 얇은 래퍼 / 기존 프리미티브 + Tailwind 로 3줄이면 끝나는 것.

## 3.3 데모 모듈 컨벤션

`components/demos/<slug>.demo.tsx` 는 `ComponentDemoModule`(`lib/showcase/types.ts`) 4개를 named export 한다.

```tsx
export const demo = (/* 라이브 JSX — 현재 프리셋 토큰으로 렌더 */)
export const code = `/* demo 와 같은 내용의 복사용 코드 문자열 */`
export const dos = ["...", "..."]    // 2~3개 권장
export const donts = ["...", "..."]  // 2~3개 권장
```

- `demo` 와 `code` 는 **내용이 일치해야 한다** — 상세 페이지가 둘을 나란히 보여준다.
- `dos`/`donts` 는 취향이 아니라 **판단 기준**을 쓴다. "성공/경고/위험 3단계 상태를 표현할 때만 쓴다" 처럼 언제 쓰고 언제 안 쓰는지가 드러나야 한다.
- 데모 안에서도 하드코딩 색·외부 이미지 URL 금지. 아바타는 `AvatarFallback`, 이미지는 `public/` 로컬 placeholder.
- 데모는 라이트/다크 + 전 테마 프리셋 위에서 렌더된다 — 특정 배경색을 전제하지 않는다.

레퍼런스로 볼 파일: `components/demos/badge-extended.demo.tsx`.

## 3.4 항목 추가 절차

**[references/catalog-workflow.md](references/catalog-workflow.md) 에 컴포넌트·패턴·템플릿·테마·폰트·프로필 각각의 단계별 체크리스트가 있다.** 항목을 추가할 때는 그 파일을 편다.

컴포넌트 추가 요약: 구현 → 데모 → `lib/showcase/registry.ts` 등록(`status: "done"`) → `lib/showcase/demo-loaders.ts` 로더 등록 → (`components/ui/` 밖 커스텀이면) `registry.test.ts` 의 `MANUAL_ENTRY_SLUGS` 에 slug 추가 → i18n 4개 로케일 → (배포 자산이면) `registry.json` + `pnpm registry:build && pnpm gen:llms` → 검증.

## 3.5 무엇이 자동으로 막히는가 (테스트 게이트)

수기 검토에 기대지 않고 테스트가 강제한다. 실패하면 규칙 위반이지 테스트 버그가 아니다.

| 테스트 | 강제하는 것 |
|---|---|
| `lib/i18n/messages.test.ts` | 4개 로케일 키 집합 동일 · 레지스트리 전 항목 설명 번역 존재 · 고아 `component.*` 키 없음 · 플레이스홀더 일치 |
| `lib/showcase/registry.test.ts` | `components/ui/` 스캔 결과와 레지스트리 정합 · 수동 등록 slug 화이트리스트 |
| `lib/showcase/demo-loaders.test.ts` | `status: "done"` 항목만 로더 등록 |
| `test/closed-network.test.ts` | 프로덕션 산출물에 외부 `<script src>`/`<link href>`/CSS `url()`/CDN 힌트 0건 |
| `test/sourcemap.test.ts` | 프로덕션 청크에 sourcemap 부재 |
| `profiles/index.test.ts` | 프로필이 참조하는 theme/font 가 실재하는지 |
| `lib/profile-css.test.ts` | 프로필 CSS 방출(`data-theme`/`data-font`/`data-density`/`--radius`) 형태 |

`pnpm test:vision` 은 **CI 에 없는 수동 게이트** — Playwright 스크린샷을 Claude 비전으로 채점한다(텍스트 겹침·레이아웃 깨짐·대비). 시각 변화가 큰 작업 뒤에만 돌린다.

## 3.6 파운데이션 층

**토큰** — `app/globals.css` 가 소유한다. 색은 OKLCH, `--radius` 기본 **6px**, 파생값은 `--radius-sm ~ --radius-4xl` 이 `calc()` 로 만든다. 임의 radius 신설 금지.
시맨틱 색 토큰: `background`/`foreground`, `card`, `popover`, `primary`, `secondary`, `muted`, `accent`, `destructive`, `success`, `warning`, `gain`/`loss`, `border`, `input`, `ring`, `chart-1~5`, `sidebar-*`.

**테마** — `themes/<name>.ts` 추가 시 `themes/index.ts` 에 등록. **기존 프리셋 파일이나 globals.css 의 다른 프리셋 블록은 건드리지 않는다.**
**폰트** — `fonts/index.ts` 에 등록, 실 파일은 `assets/fonts/<name>/` 에 woff2 + LICENSE 커밋.
**프로필** — `profiles/index.ts`. 프로젝트가 고르는 단위이므로 여기서 테마·폰트·`defaultMode`·radius·density 를 확정한다. 소비 프로젝트가 프로필의 radius·density 를 임의 재정의하면 표준이 발산한다.

**밀도** — `<html data-density="compact|comfortable">` 을 프로필이 지정하고 `app/globals.css` 의 밀도 층이 소비한다. 속성이 없으면 아무 규칙도 걸리지 않는다(하위호환).

**테마 초기화** — hydration 이전에 끝낸다. `app/layout.tsx` `<head>` 의 인라인 `THEME_INIT_SCRIPT` 가 localStorage 를 읽어 `<html>` 에 `data-theme`/`data-font`/`dark` 를 직접 세팅한다. `useEffect` 만으로 적용하면 FOUC(테마 깜빡임)가 난다.

## 3.7 다국어

카탈로그 설명문은 한국어가 기본, `en`·`ja`·`zh`·`es` 번역을 `lib/i18n/messages/` 에 둔다.

- 컴포넌트 안 문구: `<TranslatedText k="..." ko="..." />` 또는 `t("<ns>.<key>", "<ko원문>")`.
- `t()` 는 **처음 두 인자가 문자열 리터럴**이어야 추출기가 잡는다 — 변수 조립 금지.
- 키 추가 후 `node scripts/i18n/extract.mjs` 로 `scripts/i18n/ko-catalog.json` 갱신.
- 4개 로케일 키 집합이 어긋나면 테스트가 깨진다. 번역을 나중에 하겠다고 `en` 만 넣지 않는다.

## 3.8 배포 산출물 동기화

`registry.json`(루트) 이 shadcn 레지스트리의 **단일 진실원천**이다.

```bash
pnpm registry:build   # registry.json → public/r/*.json
pnpm gen:llms         # registry.json → public/llms.txt (AI 발견용 카탈로그)
```

`public/r`, `public/llms.txt` 는 **빌드 생성물** — 손으로 편집하지 않는다. 수기 하드코딩은 다음 생성에서 날아간다.

## 3.9 파일 컨벤션

| 종류 | 위치 | 표기 |
|---|---|---|
| shadcn 프리미티브 | `components/ui/<name>.tsx` | kebab-case, **수정 금지** |
| 조합 컴포넌트 | `components/<name>.tsx` | kebab-case |
| 패턴 컴포넌트 | `components/patterns/<name>.tsx` | kebab-case |
| 쇼케이스 셸 | `components/showcase/<name>.tsx` | kebab-case |
| 데모 | `components/demos/<slug>.demo.tsx` | slug 는 레지스트리 slug 와 동일 |
| 라우트 | `app/<segment>/page.tsx` (+ `loading.tsx`, `error.tsx`) | |
| 레지스트리·유틸 | `lib/<domain>/registry.ts`, `lib/<name>.ts` | |
| 훅 | `hooks/use-<name>.ts` | |
| 테스트 | 대상 파일 옆 `<name>.test.ts(x)` | vitest |

className 병합은 항상 `cn()`(`@/lib/utils`). variant 가 여럿이면 CVA.

## 3.10 자주 나오는 실수

- 컴포넌트 파일만 만들고 레지스트리·데모 로더 등록을 빼먹어 카탈로그에 안 뜸
- `status: "done"` 인데 데모 파일이 없음 (또는 그 반대)
- i18n 을 `en` 에만 추가해서 로케일 키 집합 테스트가 깨짐
- 데모에 하드코딩 색·외부 이미지 URL 사용 → 폐쇄망 테스트에서 막힘
- `components/ui/` 원본을 직접 수정하거나 `components/ui/customs/` 같은 하위 폴더를 끼워 넣음
- 페이지 컴포넌트에서 `max-w-[1300px]` 를 직접 선언(컨테이너는 layout 소유)
- 새 라우트에 `loading.tsx`/`error.tsx` 누락
- `public/r`·`public/llms.txt` 를 손으로 수정
- 등락 표시에 Tailwind 팔레트 색을 직접 사용 (→ `--gain`/`--loss`, `lib/finance/rate.ts`)
- 캔버스·차트 렌더러에 CSS 변수 문자열을 그대로 전달 (→ `lib/finance/normalize-color.ts`)
- 새 UI 라이브러리를 먼저 설치하고 나중에 정당화 (의존성 규율 선검토가 순서)

---

# 4. 규칙 다이제스트 (두 모드 공통 · 위반 빈발 항목)

전체 조항은 §1 의 원천을 읽는다. 아래는 예외 없이 적용되는 것만 추린 것이다.

## 컬러 · 토큰
- **하드코딩 색 금지**(hex·rgb/hsl/oklch 리터럴·Tailwind 팔레트 클래스): 항상 시맨틱 토큰(`bg-background`, `text-destructive`, `text-chart-1`)만 쓴다. *(검증 대상)*
- 시세 등락은 팔레트 색 직접 지정 금지 → `--gain`/`--loss` 토큰(`lib/finance/rate.ts`). 한국식 관례로 상승=빨강, 하락=파랑.
- canvas 류 렌더러에는 CSS 변수 문자열을 그대로 주지 않고 `normalizeColor` 로 해소한 뒤 전달한다.

## 컴포넌트
- `components/ui/` 의 shadcn 원본은 수정하지 않는다. 커스텀은 `components/` 또는 `components/patterns/` 에서 조합한다.

## 아이콘
- **이모지를 아이콘 대용으로 쓰지 않는다.** *(검증 대상)*
- Phosphor(`@phosphor-icons/react`) 기본. 강조는 duotone/fill. 서버 컴포넌트는 `/dist/ssr` 경로 import.

## 레이아웃 · 라우팅
- 콘텐츠 컨테이너 `max-w-[1300px] mx-auto`, 소유자는 **세그먼트 `layout.tsx`** — 페이지 컴포넌트에서 max-width 하드코딩 금지.
- `main` 랜드마크는 layout 이 렌더한다. 페이지·`loading.tsx`·`error.tsx` 에서 중복 렌더 금지(중첩은 invalid HTML). 에러 UI 는 `div role="alert"`.
- 모바일 우선 3모드(기본 / `sm:`·`md:` / `lg:`↑). 역방향 접두 금지.
- 넓은 콘텐츠(테이블·코드블록·차트)는 자체 `overflow-x-auto` 래퍼. body 가로 스크롤 0.
- **새 라우트에는 `loading.tsx` 와 `error.tsx` 를 함께 만든다.**
- 상태 UI(로딩·빈·에러)는 `/patterns/state` 표준을 따른다.

## 폐쇄망 · 의존성
- 모든 리소스 self-host — 외부 CDN·외부 URL fetch 0건. 폰트는 `next/font/local` + 벤더링, 아이콘은 npm 번들, 데모 이미지도 로컬 placeholder. *(검증 대상)*
- TypeScript strict 유지, `any` 금지. *(검증 대상)*

---

# 5. 자가 검증 및 완료 보고 (필수 수행)

구현 후 **반드시 기계적으로 증명**한다. 순서가 있다.

## 5.1 레포에 테스트가 있으면 그쪽이 1차 게이트다

카탈로그 레포(모드 B)나 테스트를 갖춘 소비자 레포에서는 아래가 먼저다. 이 게이트가 §4 의 상당 부분을 이미 강제한다.

```bash
pnpm typecheck && pnpm lint && pnpm test && pnpm build
```

## 5.2 표준 준수 스캐너

레포 테스트가 없거나(신규 프로젝트) 추가 확인이 필요하면 이 스킬의 스캐너를 돌린다.

```bash
python3 <스킬경로>/scripts/check_standards.py app components lib
```

검사 항목은 하드코딩 색 · 이모지 아이콘 · 외부 URL · TypeScript `any` 4종이고, 위반이 있으면 `파일:줄` 과 함께 exit 1 이다.

정당한 예외(색 선택기의 스와치 팔레트처럼 hex 가 곧 데이터인 경우)는 **이유와 함께** 그 줄에 표기해 면제한다. 면제 수단이 없으면 사람은 스캐너 전체를 무시하게 되고, 그 순간 검증이 죽는다.

```tsx
const SWATCHES = ["#ef4444", "#3b82f6"] // doksam-ui:allow-color 색 선택기 팔레트 원본
```

`doksam-ui:allow` 는 그 줄의 모든 검사를, `doksam-ui:allow-color|emoji|url|any` 는 해당 검사만 면제한다. 이유 없이 다는 것은 위반을 숨기는 것이다.

**맨손 `grep` 으로 대체하지 않는다.** `grep -r ' any' src/` 는 `company`·`many` 를 잡고, `grep -r '[^\x00-\x7F]' src/` 는 한글 텍스트를 전부 잡는다. 노이즈에 묻히면 "통과"가 아무것도 증명하지 못한다. 스캐너는 단어 경계·이모지 코드포인트·소스 확장자로 범위를 좁혀 그 오탐을 제거한다.

## 5.3 완료 보고

검증이 모두 통과하면 아래 형식으로 보고한다. 실패하면 코드를 고치고 다시 검증한다.

```text
# doksam-ui 적용 완료 보고

- 모드: [A 소비자 | B 생산자]
- 적용된 프로필: [예: profile-admin]
- 새로 설치·추가된 자산: [예: @doksam-ui/badge-extended]

## 기계적 검증 결과
- [Pass] pnpm typecheck / lint / test / build
- [Pass] 하드코딩 색 0건 (시맨틱 토큰 사용)
- [Pass] 이모지 아이콘 0건 (Phosphor 사용)
- [Pass] 외부 CDN / URL fetch 0건 (self-host 준수)
- [Pass] TypeScript any 0건
```

보고서에도 이모지를 쓰지 않는다 — 이모지 0건을 보고하는 문서가 이모지를 달고 있으면 그 보고는 스스로를 반증한다.
