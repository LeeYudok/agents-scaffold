---
paths:
  - "src/main/java/**/*.java"
  - "src/main/webapp/**/*.jsp"
  - "src/main/webapp/WEB-INF/**"
  - "WebContent/**/*.jsp"
  - "WebContent/WEB-INF/**"
---

# Java + JSP 레거시 웹 규칙

- **Java {{JAVA_VERSION}}** 기준. 서블릿/JSP + 톰캣 계열 레거시 웹 프로젝트용.
- 빌드툴은 프로젝트마다 다르다(maven/gradle/ant) — pre-commit 게이트가 자동 감지한다.

## P0 — 절대 규칙

- **SQL 은 `PreparedStatement` 만**: 사용자 입력을 문자열 연결로 SQL 에 붙이지 않는다
  (`"... WHERE id='" + id + "'"` 금지). 기존 코드 수정 시에도 발견 즉시 바인딩 변수로 교체.
- **JSP 출력은 항상 이스케이프**: 사용자 유래 값은 `<c:out value="..."/>` 또는
  `fn:escapeXml()` 경유로만 출력(XSS). `<%= request.getParameter(...) %>` 직접 출력 금지.
- **비인증 진입점 신설 금지**: 새 서블릿/JSP 는 인증 필터(web.xml filter-mapping 또는
  공통 인증 체크) 뒤에만 추가. 인증 우회 경로가 필요하면 사용자 에스컬레이션.
- **시크릿 하드코딩 금지**: DB 접속 정보·키를 JSP/web.xml/소스에 박지 않는다 →
  JNDI DataSource 또는 외부 설정으로.

## P1 — 필수

- **스크립틀릿(`<% %>`) 신규 작성 금지**: 화면 로직은 EL/JSTL, 비즈니스 로직은
  서블릿/서비스 클래스로. 기존 스크립틀릿은 수정 범위에 한해 점진 제거.
  [자동강제: pre-commit — 스테이징 diff 의 추가된 줄만 검사, 지시자/주석 제외]
- **인코딩 UTF-8 고정**: JSP `page` 지시자(`pageEncoding="UTF-8"`) + 요청 인코딩 필터.
  한글 깨짐 수정을 개별 페이지 땜질로 하지 않는다.
- **자원 해제**: `Connection`/`Statement`/`ResultSet` 은 try-with-resources
  (Java 7+) 또는 finally 에서 확실히 close. 커넥션 누수는 운영 장애 직결.
- **예외 삼킴 금지**: `catch (Exception e) {}` 빈 블록 금지 — 최소 로깅 후 전파/변환.

## P2 — 권장

- 공통 마크업은 taglib/`<jsp:include>` 로 재사용(복붙 금지).
- JSP 1개 300줄 초과 시 분리 검토.
- `System.out.println` 디버깅 잔재 커밋 금지 — 로거 사용.
