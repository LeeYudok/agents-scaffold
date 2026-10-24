---
paths:
  - "app/**/*.tsx"
  - "app/**/*.ts"
  - "components/**/*.tsx"
  - "components/**/*.ts"
  - "web/app/**/*.tsx"
  - "web/src/**/*.tsx"
---

# Next.js / Frontend Rules

## Stack
- Functional components + hooks only. No class components.
- Based on the Next.js App Router. Do not add new Pages Router code.
- TypeScript strict; `any` forbidden.

## UI primitives
- Use **shadcn/ui** — do not build from scratch.
- Do not modify `components/ui/` originals → write custom variants under `components/ui/customs/`.
- Class merging: use `cn()` (`tailwind-merge` + `clsx`).
- Icons: `@phosphor-icons/react`. Server components use `/dist/ssr`.

## Styling (Tailwind)
- **Tailwind v4**: use OKLCH semantic tokens based on `@theme inline`.
  - Background `bg-background`, card `bg-card`, body text `text-foreground`
  - Primary `bg-primary`/`text-primary`, secondary `bg-secondary`/`bg-muted`
  - Border `border` (= `border-border`), error `text-destructive`
- **No hardcoded colors**: forbid direct colors like `bg-blue-600`, `text-neutral-500`, `bg-white`.
  - Check with: `grep -rn 'bg-\(white\|gray\|neutral\|slate\|blue\)-[0-9]' components app`
- Dark mode first.

## State management
- Global state: **Zustand**. No prop drilling.
- Server state: **@tanstack/react-query** (`useQuery`, `useMutation`).
- URL-driven navigation: `next/link` + query params with SSR. Do not replace with Radix Tabs.

## Client/server separation
- Interactive Radix UI (tabs/select/dropdown-menu): `"use client"` required.
- Pure display components (card/table/button/badge): can be RSC.
- Data fetching: centralize in `lib/api.ts`. No direct fetch calls in components.

## Images & assets
- Images: `next/image` only.
- Fonts: `next/font`.
- Long documents/prose: `prose prose-sm dark:prose-invert` (@tailwindcss/typography).

## Build & types
- `npx tsc --noEmit` or `next build` — no errors before committing.
- `next build` failure blocks the commit.

## P0
- No hardcoded colors (`bg-white`, `text-blue-600`, etc.)
- No `any` type
- No `.env` staged into git

## P1
- Single responsibility per component file (split functions over 50 lines)
- No direct `<img>` usage without `next/image`
- New pages must ship with `loading.tsx` + `error.tsx`
