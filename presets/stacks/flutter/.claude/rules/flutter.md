---
paths:
  - "**/*.dart"
  - "pubspec.yaml"
  - "analysis_options.yaml"
---

# Flutter (Dart) 규칙

## P0

- 시크릿/API키를 Dart 소스·`pubspec.yaml`·플랫폼 설정에 하드코딩 금지
- 커밋 전 `flutter analyze` 에러 0 (경고는 P2)
- `.env`·`google-services.json`·`GoogleService-Info.plist` git 스테이징 금지

## 빌드 & 테스트
- **CI 순서 (빠른 실패 우선)**:
  1. `dart format --set-exit-if-changed .` — 가장 빠름
  2. `flutter analyze` — 정적 분석 (`analysis_options.yaml` 기준)
  3. `flutter test` — 단위/위젯 테스트
- 릴리즈 검증은 `flutter build apk --release` / `flutter build ios --release --no-codesign` 을 CI 별도 잡으로.

## 의존성 관리
- `pubspec.yaml` 버전은 caret(`^`) 제약 사용, `any` 금지. `pubspec.lock` 은 앱이면 커밋, 패키지면 미커밋.
- 신규 의존성 추가 전 pub.dev 점수(likes/pub points)와 유지보수 상태 확인.
- `flutter_lints` (또는 상위 호환 `very_good_analysis`) 를 `analysis_options.yaml` 에 포함 — 린트 규칙 임의 전면 해제 금지.

## 코드 컨벤션
- 위젯은 가능한 한 `const` 생성자 — `prefer_const_constructors` 린트 준수.
- `build()` 안에서 비즈니스 로직·비동기 호출 금지 — 상태 관리 계층(Riverpod/Bloc 등 프로젝트 채택 라이브러리)으로 분리.
- 상태 관리 라이브러리는 **하나만** 채택하고 혼용 금지.
- `BuildContext` 를 `async` gap 너머로 사용 금지 (`use_build_context_synchronously`) — `mounted` 확인 후 사용.
- 파일명 snake_case, 위젯 1개 = 파일 1개 원칙 (300줄 초과 시 분리 검토).

## 테스트 패턴
- 새 위젯에는 최소 1개 위젯 테스트(`testWidgets`) — 렌더링과 핵심 인터랙션 어설션.
- 상태/서비스 로직은 순수 Dart 단위 테스트로 — 위젯 테스트에 로직 검증을 몰지 말 것.
- 골든 테스트는 플랫폼별 렌더링 차이가 있으므로 CI 러너와 로컬 환경을 일치시킨 뒤에만 도입.

## 금지
- `print()` 디버깅 잔재 커밋 금지 — `debugPrint`/logger 사용, 릴리즈 코드에선 제거.
- `// ignore:` 지시어는 사유 주석 + 이슈 번호 없이 금지.
