
**springboot**

- 시크릿(DB 비밀번호·API 키)을 `application.yml`/소스에 하드코딩 금지 → 환경변수 또는 외부 설정
- JPA 쿼리에 사용자 입력을 문자열 연결로 붙이지 않는다 — 바인딩 파라미터만
- 커밋 전 `./gradlew compileJava` (또는 `mvn -q compile`) 통과 필수
- 인증 없는 엔드포인트 신규 추가 금지 — Spring Security 설정 뒤에만
