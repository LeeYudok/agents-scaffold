
**javaweb**

- SQL through `PreparedStatement` only — never concatenate user input into SQL
- Always escape JSP output (`<c:out>`/`fn:escapeXml()`) — no direct scriptlet output
- No new unauthenticated entry points — new servlets/JSPs go behind the auth filter
- Never hardcode DB credentials/keys in JSP/web.xml/source → use JNDI or external config
