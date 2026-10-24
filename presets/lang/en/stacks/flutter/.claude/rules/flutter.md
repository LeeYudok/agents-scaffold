---
paths:
  - "**/*.dart"
  - "pubspec.yaml"
  - "analysis_options.yaml"
---

# Flutter (Dart) Rules

## P0

- Never hardcode secrets/API keys in Dart sources, `pubspec.yaml`, or platform config
- `flutter analyze` must report zero errors before commit (warnings are P2)
- Never stage `.env`, `google-services.json`, or `GoogleService-Info.plist`

## Build & test
- **CI order (fail fast)**:
  1. `dart format --set-exit-if-changed .` — fastest
  2. `flutter analyze` — static analysis (per `analysis_options.yaml`)
  3. `flutter test` — unit/widget tests
- Release verification (`flutter build apk --release` / `flutter build ios --release --no-codesign`) belongs in a separate CI job.

## Dependency management
- Use caret (`^`) constraints in `pubspec.yaml`, never `any`. Commit `pubspec.lock` for apps; don't for packages.
- Before adding a dependency, check its pub.dev score (likes/pub points) and maintenance status.
- Include `flutter_lints` (or the stricter `very_good_analysis`) in `analysis_options.yaml` — no blanket lint disabling.

## Code conventions
- Prefer `const` widget constructors — honor `prefer_const_constructors`.
- No business logic or async calls inside `build()` — push them into the state-management layer (Riverpod/Bloc, whichever the project adopted).
- Adopt **one** state-management library; do not mix.
- Never use `BuildContext` across an `async` gap (`use_build_context_synchronously`) — check `mounted` first.
- snake_case file names; one widget per file (consider splitting past 300 lines).

## Test patterns
- Every new widget gets at least one widget test (`testWidgets`) asserting rendering and the key interaction.
- Test state/service logic as pure Dart unit tests — don't cram logic assertions into widget tests.
- Introduce golden tests only after pinning CI runner and local environments — platform rendering differs.

## Forbidden
- No leftover `print()` debugging — use `debugPrint`/a logger, strip from release code.
- No `// ignore:` directives without a reason comment and an issue number.
