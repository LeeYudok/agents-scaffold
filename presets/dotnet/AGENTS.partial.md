
**dotnet**

- 시크릿 하드코딩 금지 — `appsettings*.json` 비밀번호/키 금지, `secrets.json`·`.env` 스테이징 금지
- SQL 문자열 결합 금지 — 파라미터 바인딩만
- `dotnet build` + `dotnet format --verify-no-changes` 통과 후 커밋
