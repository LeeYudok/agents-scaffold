---
paths:
  - "**/*.cs"
  - "src/**/*.cs"
  - "tests/**/*.cs"
  - "**/*.csproj"
  - "**/*.sln"
  - "**/*.razor"
  - "**/appsettings*.json"
---

# .NET Rules

## SDK & package management
- Pin the SDK version in `global.json`. Default `<TargetFramework>` to an LTS release.
- Keep shared settings (`LangVersion`, `Nullable`, `TreatWarningsAsErrors`) in `Directory.Build.props`.
- Add packages with `dotnet add package`; use `Directory.Packages.props` (central package management) when versions must be pinned in one place.
- Repos that need reproducible restores commit `packages.lock.json` and run `dotnet restore --locked-mode` in CI.

## Code conventions
- `.editorconfig` is the single style source. Run `dotnet format` before committing.
- **Enable nullable reference types** (`<Nullable>enable</Nullable>`) — do not lean on `!` (null-forgiving); when you use it, justify it in a comment.
- Keep `async` all the way down — never block with `.Result`/`.Wait()`/`GetAwaiter().GetResult()`. Library code uses `ConfigureAwait(false)`.
- Take a `CancellationToken` as the last parameter of public async APIs and flow it downstream.
- Handle `IDisposable`/`IAsyncDisposable` resources with `using` declarations. Never `new` an `HttpClient` — use `IHttpClientFactory`.
- Decide DI lifetimes (`Singleton`/`Scoped`/`Transient`) deliberately — never inject a scoped service (e.g. `DbContext`) into a singleton.
- Never swallow exceptions (no `catch { }`). Rethrow with `throw;`, never `throw ex;` (it loses the stack trace).

## Testing
- xUnit by default (`tests/<Project>.Tests/`). Name test projects `<Project>.Tests`.
- Assert on user-visible outcomes. Abstract external dependencies behind interfaces and substitute them.
- Every feature and bug fix ships with at least one test (P1).
- Use ASP.NET Core's `WebApplicationFactory<T>` for integration tests, against an isolated database instance.

## Security
- Secrets go in `dotnet user-secrets` for development and environment variables / a secret manager in production. Never hardcode connection-string passwords or API keys in `appsettings*.json`.
- Bind SQL parameters only (`FromSqlInterpolated`/`DbParameter`). Never concatenate strings into `FromSqlRaw`.
- Avoid over-posting — bind a DTO instead of the entity and narrow the `[Bind]`/`[FromBody]` surface.
- Never add a controller or endpoint that needs authentication without `[Authorize]` (or `RequireAuthorization()`).
- Deserialize with `System.Text.Json`. `BinaryFormatter` is forbidden.

## P0
- Never hardcode secrets — no passwords or keys in `appsettings*.json`, never stage `secrets.json` or `.env`
- Never concatenate strings into SQL — bound parameters only (no interpolation into `FromSqlRaw`)
- Never add an unauthenticated endpoint — declare `[Authorize]`/`RequireAuthorization()`

## P1
- Commit only with `dotnet build` warning-free and `dotnet format --verify-no-changes` clean
- Ship at least one test with every feature and bug fix
- No synchronous blocking (`.Result`/`.Wait()`) on async paths

## P2
- Use `var` only when the right-hand side makes the type obvious
- Document public APIs with XML comments (`///`)
- Move magic numbers and strings into `const` or an options class (`IOptions<T>`)
