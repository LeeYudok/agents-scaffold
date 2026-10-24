---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "api/**/*.ts"
  - "src/**/*.ts"
---

# Bun + TypeScript Rules

## Runtime & build
- Runtime: **Bun**. Do not run `node`/`npm` directly → use `bun`/`bunx`.
- Type check: `bunx tsc --noEmit`. No errors before committing.
- Tests: `bun test`. Jest-syntax compatible, but import from `bun:test`.
- Package install: `bun add <pkg>`. No `npm install`/`yarn add`.

## Code conventions
- No `any` / `unknown` — use precise types or generics.
- No `console.log` → use the project's Logger/logging utility.
- No hardcoded environment variables → use `Bun.env.XXX` or `process.env.XXX`.
- Use `async/await` for async I/O. Do not introduce new callback patterns.

## Formatter / linter
- Biome first (if `biome.json` exists). Otherwise Prettier.
- `bunx biome check .` or `bunx prettier --check .` — CI blocks on failure.

## Architecture
- Layered architecture: `routes/` → `services/` → `db/`. No business logic in routes.
- Prefer `Bun.file()` / `Bun.write()` — native Bun APIs over Node fs.
- Load environment variables directly via `Bun.env`. `dotenv` is unnecessary.

## P0 (absolute rules)
- Never hardcode secrets (keys/tokens/passwords) in code
- `bunx tsc --noEmit` must pass before committing
- No `.env` files staged into git (blocked by the pre-commit hook)

## P1 (required)
- Document new functions' purpose with JSDoc or type signatures
- Test files named `*.test.ts` or `*.spec.ts`
- Always commit `bun.lock` (reproducible builds; the default text lockfile since Bun 1.2 — same rule applies to legacy `bun.lockb`)
