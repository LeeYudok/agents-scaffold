---
paths:
  - "**/*.kt"
  - "**/*.kts"
  - "app/src/**/*.java"
---

# Android (Kotlin + Gradle) 규칙

## 빌드 & 테스트
- **CI 순서 (빠른 실패 우선)**:
  1. `./gradlew ktlintCheck` — 가장 빠름
  2. `./gradlew detekt` — 정적 분석
  3. `./gradlew lintDebug` — Android Lint (variant 지정 필수, `lint` 단독 금지)
  4. `./gradlew testDebugUnitTest` — 단위 테스트
  5. `./gradlew assembleDebug` — 빌드 성공 확인
- `assembleMinifyDebug` — R8 난독화 테스트 (릴리즈 빌드 전)

## 의존성 관리
- **`gradle/libs.versions.toml` 단일 관리** — 직접 버전 문자열 금지.
- `implementation "com.example:lib:1.0"` 금지 → `libs.example.lib` 사용.
- AGP/Kotlin 버전 업 시 `libs.versions.toml`의 `[versions]` 섹션만 수정.

## 코드 컨벤션
- **ktlint**: `ktlint_official` 스타일. 줄 길이 120. 와일드카드 import 금지.
- **detekt**: `config/detekt.yml` 기준. `buildUponDefaultConfig = true`.
- MVVM 또는 MVI 아키텍처. Activity/Fragment에 비즈니스 로직 금지.
- Jetpack Compose: `@Composable` 함수 side-effect 금지 (LaunchedEffect 사용).

## 테스트 패턴
- **JUnit5 활성화 필수**: `android.testOptions.unitTests.all { it.useJUnitPlatform() }` 없으면 테스트 skip (실패도 아님!).
- MockK + Turbine (Flow 테스트).
- Flow 테스트: `.test { } + cancelAndIgnoreRemainingEvents()` 필수.
- `Dispatchers.setMain(testDispatcher)` + tearDown에서 `resetMain()`.

## 보안
- 키·토큰 `BuildConfig` 또는 코드 내 하드코딩 금지 → `local.properties` + `sealed secrets`.
- `Log.d/e/i` 릴리즈 빌드에서 ProGuard로 제거 또는 빌드 타입별 분기.
- 네트워크: `cleartext` 트래픽 `networkSecurityConfig`으로 명시적 허용만.

## P0
- 시크릿/API키 코드 내 하드코딩 절대 금지
- `ktlintCheck` 에러 없이 커밋
- JUnit5 `useJUnitPlatform()` 설정 없이 테스트 추가 금지

## P1
- 라이브러리 모듈 `isMinifyEnabled = true` 금지 (AGP 8.4+ 불가)
- R8 규칙: `proguard-rules.pro` 또는 `consumerProguardFiles`로 관리
- `lint.xml`로 false positive 억제 (인라인 `@SuppressLint` 남발 금지)
