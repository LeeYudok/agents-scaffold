---
paths:
  - "src/main/java/**/*.java"
  - "src/test/java/**/*.java"
---

# Spring Boot / 백엔드 규칙

## P0

- 시크릿(DB 비밀번호·API 키)을 `application.yml`/소스에 하드코딩 금지 → 환경변수 또는 외부 설정
- JPA 쿼리에 사용자 입력을 문자열 연결로 붙이지 않는다 — 바인딩 파라미터만
- 커밋 전 `./gradlew compileJava` (또는 `mvn -q compile`) 통과 필수
- 인증 없는 엔드포인트 신규 추가 금지 — Spring Security 설정 뒤에만

- **Java {{JAVA_VERSION}} (= Java 8) → Spring Boot 2.7.x 계열** (3.x는 Java 17+ 필요하므로 사용 불가).
  2.7 은 OSS EOL(2023-06, 보안패치 없음)이고 상용 지원도 2026년 말 종료 예정 — Java 8 제약에 따른 의도된 레거시 선택임을 인지하고, 취약점 대응은 의존성 레벨에서 별도 관리.
- 빌드툴 **Gradle** (`./gradlew`).
- 레이어드 아키텍처: `controller` → `service` → `repository`. 컨트롤러에 비즈니스 로직 금지.
- 의존성 주입은 **생성자 주입**(필드 주입 금지), lombok `@RequiredArgsConstructor`.
- 요청 DTO는 Bean Validation(`@Valid`, `@NotNull` 등)으로 검증.
- 시크릿·DB 비번은 `application.yml` 하드코딩 금지 → 환경변수/`.env`.
- 응답에 엔티티 직접 노출 금지 → DTO 변환. 비번/해시/토큰 필드 제외.
