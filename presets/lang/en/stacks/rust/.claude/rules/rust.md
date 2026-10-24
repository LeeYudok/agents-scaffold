---
paths:
  - "src/**/*.rs"
  - "**/*.rs"
---

# Rust Rules

## Build & test
- `cargo check` — quick compile-error check.
- `cargo build` — full build.
- `cargo test` — run unit/integration tests.
- `cargo clippy -- -D warnings` — treat Clippy warnings as errors. Blocks in CI.

## Code conventions
- No `unsafe` blocks — except for external crate FFI. Requires a `// SAFETY:` comment when used.
- No `unwrap()` / `expect()` — panics in parser/library code are bugs. Use `?` or a match.
- Avoid overusing `clone()` — prefer `&str`, `Cow<str>`, and lifetimes.
- Error types: `thiserror` or `anyhow`. Minimize exposing `Box<dyn Error>` directly.
- Consider `catch_unwind` when calling external crates (defense against panic propagation).

## Formatter / linter
- `rustfmt` — run `cargo fmt` before committing. Follow `rustfmt.toml`.
- `cargo clippy` — `deny(clippy::all)` recommended.

## Architecture
- **Keep versions in sync across 3 places**: `Cargo.toml`, and when using NAPI-RS, `node/Cargo.toml` + `node/package.json`.
- When adding a new parser/format, update magic-byte detection and enum routing together.
- Integration tests: `tests/integration.rs` or the `tests/` directory.

## Security
- Environment variables: `std::env::var("XXX")`. No hardcoding.
- Guard against invalid bytes during encoding conversion → fall back to `\u{FFFD}`.

## P0
- Blocked if `unsafe` is used where an implementation without it is possible
- No `unwrap()`/`expect()` in library code
- `cargo check` must pass with no errors before committing

## P1
- Integration tests required for new parsers
- Commit `Cargo.lock` (binaries/apps). Optional for libraries via .gitignore

## Learned warnings

- When converting `for item in iter` → `while i < len`, every `continue` branch must increment `i += 1` (risk of infinite loop)
