# 카탈로그 항목 추가 워크플로 (모드 B 전용)

doksam-ui 카탈로그 레포 안에서만 쓰는 계층별 체크리스트다. 각 절차의 마지막은 항상 검증 커맨드다.

공통 검증 (CI 와 같은 순서):

```bash
pnpm typecheck && pnpm lint && pnpm test && pnpm build
# 필요 시: pnpm test:e2e
# 시각 변화가 크면(수동, CI 미포함): pnpm test:vision
```

---

## A. 컴포넌트 추가

1. **구현** — `components/<slug>.tsx`
   - `components/ui/` 의 shadcn 프리미티브를 조합한다. 원본은 건드리지 않는다.
   - className 병합은 `cn()`(`@/lib/utils`), variant 가 여럿이면 CVA.
   - 색은 시맨틱 토큰만. 아이콘은 Phosphor(서버 컴포넌트는 `.../dist/ssr`).

2. **데모** — `components/demos/<slug>.demo.tsx`
   - `demo` / `code` / `dos` / `donts` 4개 export. `demo` 와 `code` 내용 일치.
   - 레퍼런스: `components/demos/badge-extended.demo.tsx`

3. **레지스트리 등록** — `lib/showcase/registry.ts`
   ```ts
   {
     slug: "<slug>",
     title: "<Title>",
     category: "form" | "overlay" | "layout" | "data" | "chat" | "bizinfo" | "finance",
     layer: "primitive" | "composition",
     description: "한 줄 설명(한국어).",
     status: "done",
   }
   ```
   카테고리 블록의 기존 정렬을 유지한다.

4. **데모 로더 등록** — `lib/showcase/demo-loaders.ts`
   ```ts
   "<slug>": () => import("@/components/demos/<slug>.demo"),
   ```
   `status: "done"` 인 항목만 여기 등록되어야 한다(`demo-loaders.test.ts` 가 검사).

5. **수동 항목 화이트리스트** — `components/ui/` 밖의 커스텀이면
   `lib/showcase/registry.test.ts` 의 `MANUAL_ENTRY_SLUGS` 에 slug 추가.
   (이걸 빼면 "레지스트리에만 있고 파일 스캔에 없다"로 테스트가 깨진다.)

6. **i18n** — `lib/i18n/messages/{en,ja,zh,es}.json` **4개 전부**
   - `component.<slug>.description` 필수.
   - 컴포넌트 내부 문구가 있으면 해당 키도 4개 로케일에 추가.
   - `node scripts/i18n/extract.mjs` 로 `scripts/i18n/ko-catalog.json` 재생성.

7. **배포 레지스트리** — 다른 프로젝트가 `npx shadcn add` 로 가져갈 자산이면
   `registry.json` 에 item 추가 (`name`/`type`/`title`/`description`/
   `dependencies`/`registryDependencies`/`files`) 후:
   ```bash
   pnpm registry:build && pnpm gen:llms
   ```
   `public/r`·`public/llms.txt` 는 생성물이므로 직접 편집 금지.

8. **테스트** — 로직이 있는 컴포넌트는 `components/<slug>.test.tsx`,
   데모에 상호작용이 있으면 `components/demos/<slug>.demo.test.tsx`.

---

## B. 패턴 추가

패턴 = 화면 단위 조합 규칙. 컴포넌트 단품이 아니라 "이 상황엔 이렇게 조립한다"를 보여준다.

1. **라우트** — `app/patterns/<slug>/page.tsx` + `loading.tsx` + `error.tsx`
   - `main` 은 상위 layout 이 렌더한다 — 페이지에서 중복 렌더 금지.
   - 에러 UI 는 `div role="alert"`.
2. **레지스트리 등록** — `lib/patterns/registry.ts`
   ```ts
   { slug: "<slug>", title: "...", description: "...", icon: SomeIcon, scope: "common" | "finance" | "srope" }
   ```
   - `scope: "common"` 은 어떤 doksam 프로젝트에서도 재사용 가능한 것만.
     도메인 색이 짙으면 `finance` 또는 `srope`.
   - `icon` 은 `@phosphor-icons/react/dist/ssr` 에서 import.
3. **샘플 데이터** — 목 데이터가 필요하면 `lib/patterns/<name>-data.ts` +
   `<name>-data.test.ts` (기존 `mobile-banking-data`, `stock-order-data` 참고).
4. **i18n** — `pattern.<slug>.title` 과 `pattern.<slug>.description` 을 4개 로케일에.
5. 검증.

---

## C. 템플릿 추가

템플릿 = 완성된 화면 하나. 프로필(테마+폰트)을 지정해 "이 조합이면 이렇게 보인다"를 증명한다.

1. **라우트 디렉터리** — `app/templates/<slug>/`
   - `layout.tsx` 가 컨테이너(`max-w-[1300px] mx-auto`)와 `main` 을 소유한다.
   - `page.tsx` + `loading.tsx` + `error.tsx`.
   - 하위 화면이 있으면 `app/templates/<slug>/<sub>/page.tsx`.
   - 내부 전용 컴포넌트·목 데이터는 `_components/`, `_data/` (언더스코어 = 라우트 제외).
   - 뼈대는 `app/templates/_blueprint/blueprint.tsx` 참고.
2. **레지스트리 등록** — `lib/templates/registry.ts`
   ```ts
   {
     href: "/templates/<slug>",
     title: "...",
     profile: "admin 프로필 · Slate · Geist",   // 사람이 읽는 조합 설명
     description: "...",
     stack: ["app-shell", "table-sortable"],     // 사용한 패턴/자산
     icon: SomeIcon,
   }
   ```
3. **i18n** — `template.<slug>.description` 을 4개 로케일에
   (slug 는 `href` 의 마지막 세그먼트).
4. **폐쇄망** — 템플릿의 데모 데이터도 외부 이미지 URL 금지. 아바타는 `AvatarFallback`.
5. 검증 + 시각 확인(`pnpm dev` 로 라이트/다크 양쪽).

---

## D. 테마 프리셋 추가

1. `themes/<name>.ts` 새 파일 — `ThemePreset` 형태로 토큰 정의.
   **기존 프리셋 파일은 건드리지 않는다.**
2. `themes/index.ts` 의 `THEME_PRESETS` 배열에 등록.
3. `app/globals.css` 에 해당 프리셋 CSS 변수 블록 추가 —
   **다른 프리셋 블록은 수정하지 않는다.**
4. `themes/index.test.ts` 의 프리셋 이름 목록을 갱신한다 — 이 테스트는
   `THEME_PRESETS` 가 **정확히 그 목록과 일치**하는지 단언하므로, 프리셋을
   추가·제거하면 반드시 같이 고쳐야 한다.
5. 같은 테스트가 `THEME_TOKEN_KEYS` 전 키의 light/dark 값 존재도 검사한다 —
   라이트/다크 양쪽 값이 모두 있어야 한다.

## E. 폰트 프리셋 추가

1. woff2 파일을 `assets/fonts/<name>/` 에 커밋 + 해당 폰트 LICENSE 파일 동봉.
2. `fonts/index.ts` 의 `FONT_PRESETS` 에 등록, `next/font/local` 로 연결.
3. `THIRD_PARTY_LICENSES.md` 에 라이선스 항목 추가.
4. npm 폰트 패키지(@fontsource 등)는 파일 취득 도구로만 쓰고 런타임 의존성으로 남기지 않는다.

## F. 브랜드 프로필 추가

1. `profiles/index.ts` 의 `BRAND_PROFILES` 에 항목 추가:
   `{ name, label, description, theme, font, defaultMode, radius, density, shell?, examples }`
2. `theme` 은 `themes/index.ts` 의, `font` 는 `fonts/index.ts` 의 실재하는 `name` 이어야 한다
   — `profiles/index.test.ts` 가 참조 무결성을 강제한다.
3. `density` 는 `compact`(관리·데이터 화면) 또는 `comfortable`(대외 화면).
4. shadcn 레지스트리로 배포하려면 `registry.json` 에 `registry:theme` item 추가
   (`profile-<name>`) 후 `pnpm registry:build && pnpm gen:llms`.
   **폰트는 registry item 으로 자동 설치되지 않는다** — cssVars 는 색·radius 만 담고,
   폰트는 수동 복사 + `next/font/local` 연결이라고 안내 문구에 남긴다.
5. 프로필을 추가·제거해도 소비자 쪽 문서를 고칠 필요는 없다 — 목록의 원천은
   생성물인 `llms.txt` 이고 SKILL.md 는 거기서 읽으라고만 지시한다.

---

## G. 사용 규칙(/rules) 자체를 바꿀 때

`lib/rules-markdown.ts` 의 `RULES_SECTIONS` 만 수정한다.
`/rules` 페이지 렌더링과 AI 프롬프트용 `RULES_MARKDOWN` 이 여기서 파생되므로
다른 곳에 규칙 문장을 복제하지 않는다.

규칙을 추가·변경했으면 `yd-doksam-ui` 스킬(`SKILL.md` §4 다이제스트와 이 파일)이 그와
모순되지 않는지 훑는다 — 모순이 있으면 `lib/rules-markdown.ts` 가 옳고 스킬을 고친다.

---

## 자주 빠뜨리는 것 (제출 전 훑기)

- [ ] 레지스트리 등록했는가 (파일만 만들고 끝내지 않았는가)
- [ ] `status: "done"` ↔ 데모 파일 ↔ 데모 로더 3자가 일치하는가
- [ ] i18n 4개 로케일 전부 넣었는가 (`en` 만 넣지 않았는가)
- [ ] 새 라우트에 `loading.tsx` / `error.tsx` 가 있는가
- [ ] 하드코딩 색·외부 URL 0건인가
- [ ] `registry.json` 을 고쳤으면 `pnpm registry:build && pnpm gen:llms` 를 돌렸는가
- [ ] 라이트/다크 + 다른 테마 프리셋에서 깨지지 않는가
- [ ] 모바일·태블릿·데스크톱 3모드에서 가로 스크롤이 안 생기는가
