
**javaweb**

- SQL 은 `PreparedStatement` 만 — 사용자 입력을 문자열 연결로 SQL 에 붙이지 않는다
- JSP 출력은 항상 이스케이프(`<c:out>`/`fn:escapeXml()`) — 스크립틀릿 직접 출력 금지
- 비인증 진입점 신설 금지 — 새 서블릿/JSP 는 인증 필터 뒤에만
- DB 접속 정보·키를 JSP/web.xml/소스에 하드코딩 금지 → JNDI 또는 외부 설정
