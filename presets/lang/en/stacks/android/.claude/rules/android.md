---
paths:
  - "**/*.kt"
  - "**/*.kts"
  - "app/src/**/*.java"
---

# Android (Kotlin + Gradle) Rules

## Build & test
- **CI order (fail fast first)**:
  1. `./gradlew ktlintCheck` — fastest
  2. `./gradlew detekt` — static analysis
  3. `./gradlew lintDebug` — Android Lint (variant must be specified; do not run bare `lint`)
  4. `./gradlew testDebugUnitTest` — unit tests
  5. `./gradlew assembleDebug` — confirm the build succeeds
- `assembleMinifyDebug` — R8 obfuscation test (before release builds)

## Dependency management
- **Manage centrally in `gradle/libs.versions.toml`** — no direct version strings.
- No `implementation "com.example:lib:1.0"` → use `libs.example.lib`.
- When bumping AGP/Kotlin versions, edit only the `[versions]` section of `libs.versions.toml`.

## Code conventions
- **ktlint**: `ktlint_official` style. Line length 120. No wildcard imports.
- **detekt**: per `config/detekt.yml`. `buildUponDefaultConfig = true`.
- MVVM or MVI architecture. No business logic in Activity/Fragment.
- Jetpack Compose: no side effects in `@Composable` functions (use LaunchedEffect).

## Test patterns
- **JUnit5 must be enabled**: without `android.testOptions.unitTests.all { it.useJUnitPlatform() }`, tests are skipped (not even failed!).
- MockK + Turbine (Flow testing).
- Flow tests: `.test { } + cancelAndIgnoreRemainingEvents()` required.
- `Dispatchers.setMain(testDispatcher)` + call `resetMain()` in tearDown.

## Security
- No hardcoding keys/tokens in `BuildConfig` or code → use `local.properties` + sealed secrets.
- Strip `Log.d/e/i` in release builds via ProGuard or branch by build type.
- Network: allow cleartext traffic only via explicit `networkSecurityConfig`.

## P0
- Never hardcode secrets/API keys in code
- `ktlintCheck` must pass with no errors before committing
- Do not add tests without JUnit5 `useJUnitPlatform()` configured

## P1
- No `isMinifyEnabled = true` on library modules (not possible on AGP 8.4+)
- Manage R8 rules via `proguard-rules.pro` or `consumerProguardFiles`
- Suppress false positives via `lint.xml` (avoid excessive inline `@SuppressLint`)
