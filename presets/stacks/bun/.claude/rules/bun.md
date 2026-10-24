---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "api/**/*.ts"
  - "src/**/*.ts"
---

# Bun + TypeScript 규칙

## 런타임 & 빌드
- 런타임: **Bun**. `node`/`npm` 직접 실행 금지 → `bun`/`bunx` 사용.
- 타입체크: `bunx tsc --noEmit`. 에러 없이 커밋.
- 테스트: `bun test`. Jest 문법 호환이지만 `bun:test` 임포트 사용.
- 패키지 설치: `bun add <pkg>`. `npm install`/`yarn add` 금지.

## 코드 컨벤션
- `any` / `unknown` 금지 — 정확한 타입 또는 제네릭 사용.
- `console.log` 금지 → 프로젝트 Logger/로깅 유틸 사용.
- 환경변수 하드코딩 금지 → `Bun.env.XXX` 또는 `process.env.XXX`.
- 비동기 I/O는 `async/await` 사용. 콜백 패턴 신규 도입 금지.

## 포매터 / 린터
- Biome 우선 (`biome.json` 있으면). 없으면 Prettier.
- `bunx biome check .` 또는 `bunx prettier --check .` — CI에서 실패 시 차단.

## 아키텍처
- 레이어드 아키텍처: `routes/` → `services/` → `db/`. 라우트에 비즈니스 로직 금지.
- `Bun.file()` / `Bun.write()` — Node fs 대신 Bun native API 우선.
- 환경변수 로드: `Bun.env`로 직접 접근. `dotenv` 불필요.

## P0 (절대 규칙)
- 시크릿(키/토큰/비밀번호) 코드 내 하드코딩 절대 금지
- 커밋 전 `bunx tsc --noEmit` 통과 필수
- `.env` 파일 git 스테이징 금지 (pre-commit 훅이 차단)

## P1 (필수)
- 신규 함수에 JSDoc 또는 타입 시그니처로 목적 명시
- 테스트 파일은 `*.test.ts` 또는 `*.spec.ts` 네이밍
- `bun.lock` 반드시 커밋 (재현 가능한 빌드; Bun 1.2+ 기본 텍스트 락파일 — 구버전 프로젝트의 `bun.lockb` 도 동일)
