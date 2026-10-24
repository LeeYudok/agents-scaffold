---
paths:
  - "app/**/*.tsx"
  - "app/**/*.ts"
  - "components/**/*.tsx"
  - "components/**/*.ts"
  - "web/app/**/*.tsx"
  - "web/src/**/*.tsx"
---

# Next.js / 프론트 규칙

## 스택
- 함수형 컴포넌트 + hooks만. 클래스 컴포넌트 금지.
- Next.js App Router 기준. Pages Router 신규 추가 금지.
- TypeScript strict, `any` 금지.

## UI 프리미티브
- **shadcn/ui** 사용 — 처음부터 만들지 않는다.
- `components/ui/` 원본 수정 금지 → 필요 시 `components/ui/customs/` 에 작성.
- 클래스 병합: `cn()` 사용 (`tailwind-merge` + `clsx`).
- 아이콘: `@phosphor-icons/react`. 서버 컴포넌트는 `/dist/ssr`.

## 스타일 (Tailwind)
- **Tailwind v4**: `@theme inline` 기반 OKLCH 시맨틱 토큰 사용.
  - 배경 `bg-background`, 카드 `bg-card`, 본문 `text-foreground`
  - 주색 `bg-primary`/`text-primary`, 보조 `bg-secondary`/`bg-muted`
  - 테두리 `border` (= `border-border`), 에러 `text-destructive`
- **하드코딩 색 금지**: `bg-blue-600`, `text-neutral-500`, `bg-white` 등 직접 색상 금지.
  - 검증: `grep -rn 'bg-\(white\|gray\|neutral\|slate\|blue\)-[0-9]' components app`
- dark mode first.

## 상태 관리
- 전역 상태: **Zustand**. prop drilling 금지.
- 서버 상태: **@tanstack/react-query** (`useQuery`, `useMutation`).
- URL 구동 nav: `next/link` + 쿼리파라미터 SSR. Radix Tabs로 대체 금지.

## 클라이언트/서버 분리
- Radix 인터랙티브 ui (tabs/select/dropdown-menu): `"use client"` 필수.
- 순수 표시용 (card/table/button/badge): RSC 가능.
- 데이터 fetch: `lib/api.ts` 중앙화. 컴포넌트 직접 fetch 금지.

## 이미지 & 리소스
- 이미지: `next/image` 전용.
- 폰트: `next/font`.
- 긴 문서/본문: `prose prose-sm dark:prose-invert` (@tailwindcss/typography).

## 빌드 & 타입
- `npx tsc --noEmit` 또는 `next build` — 에러 없이 커밋.
- `next build` 실패 = 커밋 차단.

## P0
- 하드코딩 색(`bg-white`, `text-blue-600` 등) 사용 금지
- `any` 타입 금지
- `.env` git 스테이징 금지

## P1
- 컴포넌트 파일 단일 책임 (50줄 초과 함수는 분리)
- `next/image` 없이 `<img>` 직접 사용 금지
- 새 페이지 추가 시 `loading.tsx` + `error.tsx` 동반
