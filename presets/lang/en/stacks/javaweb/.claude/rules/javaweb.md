---
paths:
  - "src/main/java/**/*.java"
  - "src/main/webapp/**/*.jsp"
  - "src/main/webapp/WEB-INF/**"
  - "WebContent/**/*.jsp"
  - "WebContent/WEB-INF/**"
---

# Java + JSP Legacy Web Rules

- Targets **Java {{JAVA_VERSION}}**. For servlet/JSP + Tomcat-family legacy web projects.
- Build tools vary per project (maven/gradle/ant) — the pre-commit gate auto-detects.

## P0 — Absolute rules

- **SQL via `PreparedStatement` only**: never concatenate user input into SQL strings
  (`"... WHERE id='" + id + "'"` is forbidden). When touching existing code, replace
  concatenation with bind variables on sight.
- **Always escape JSP output**: user-derived values go through `<c:out value="..."/>`
  or `fn:escapeXml()` only (XSS). Direct `<%= request.getParameter(...) %>` output is forbidden.
- **No new unauthenticated entry points**: new servlets/JSPs go behind the auth filter
  (web.xml filter-mapping or the shared auth check) only. Escalate to the user if a
  bypass path seems required.
- **No hardcoded secrets**: DB credentials/keys never live in JSP/web.xml/source →
  use a JNDI DataSource or external configuration.

## P1 — Required

- **No new scriptlets (`<% %>`)**: view logic uses EL/JSTL; business logic lives in
  servlets/service classes. Remove existing scriptlets incrementally, within the scope
  you are already touching.
  [auto-enforced: pre-commit — added lines in the staged diff only; directives/comments exempt]
- **UTF-8 everywhere**: JSP `page` directive (`pageEncoding="UTF-8"`) + a request
  encoding filter. Do not patch broken Korean text page-by-page.
- **Release resources**: close `Connection`/`Statement`/`ResultSet` via
  try-with-resources (Java 7+) or a finally block. Connection leaks cause production
  outages.
- **No swallowed exceptions**: empty `catch (Exception e) {}` blocks are forbidden —
  log at minimum, then propagate or translate.

## P2 — Recommended

- Reuse shared markup via taglibs/`<jsp:include>` (no copy-paste).
- Consider splitting any JSP over 300 lines.
- No leftover `System.out.println` debugging in commits — use a logger.
