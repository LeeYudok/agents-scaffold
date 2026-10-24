---
paths:
  - "src/**/*.rs"
  - "**/*.rs"
---

# Rust 규칙

## 빌드 & 테스트
- `cargo check` — 빠른 컴파일 에러 확인.
- `cargo build` — 전체 빌드.
- `cargo test` — 단위·통합 테스트 실행.
- `cargo clippy -- -D warnings` — Clippy 경고를 에러로 처리. CI에서 차단.

## 코드 컨벤션
- `unsafe` 블록 금지 — 외부 크레이트 FFI 제외. 사용 시 `// SAFETY:` 주석 필수.
- `unwrap()` / `expect()` 금지 — 파서/라이브러리 코드에서 패닉은 버그. `?` 또는 match 사용.
- `clone()` 남발 금지 — `&str`, `Cow<str>`, 라이프타임 우선.
- 에러 타입: `thiserror` 또는 `anyhow`. `Box<dyn Error>` 직접 노출 최소화.
- 외부 크레이트 호출 시 `catch_unwind` 고려 (패닉 전파 방어).

## 포매터 / 린터
- `rustfmt` — `cargo fmt` 후 커밋. `rustfmt.toml` 기준.
- `cargo clippy` — `deny(clippy::all)` 권장.

## 아키텍처
- **버전 3곳 동기화**: `Cargo.toml`, NAPI-RS 사용 시 `node/Cargo.toml` + `node/package.json`.
- 새 파서/포맷 추가 시 매직바이트 감지 + enum 라우팅 동시 수정.
- 통합 테스트: `tests/integration.rs` 또는 `tests/` 디렉터리.

## 보안
- 환경변수: `std::env::var("XXX")`. 하드코딩 금지.
- 인코딩 변환 시 유효하지 않은 바이트 → `\u{FFFD}` 방어.

## P0
- `unsafe` 없이 구현 가능한데 `unsafe` 쓰면 차단
- `unwrap()`/`expect()` 라이브러리 코드에 사용 금지
- `cargo check` 에러 없이 커밋

## P1
- 새 파서에 통합 테스트 필수
- `Cargo.lock` 커밋 (바이너리/앱). 라이브러리는 .gitignore 선택적

## Learned warnings

- for item in iter → while i < len 변환 시 모든 continue 분기에 i += 1 필수 (무한루프 위험)
