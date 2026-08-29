
**dotnet**

- Never hardcode secrets — no passwords or keys in `appsettings*.json`, never stage `secrets.json` or `.env`
- Never concatenate strings into SQL — bound parameters only
- Commit only with `dotnet build` and `dotnet format --verify-no-changes` clean
