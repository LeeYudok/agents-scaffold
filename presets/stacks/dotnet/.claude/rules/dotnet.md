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

# .NET 규칙

## SDK & 패키지 관리
- SDK 버전은 `global.json` 으로 고정. 대상 프레임워크(`<TargetFramework>`)는 LTS 를 기본으로 한다.
- 공통 설정(`LangVersion`, `Nullable`, `TreatWarningsAsErrors`)은 `Directory.Build.props` 에 모은다.
- 패키지는 `dotnet add package` 로 추가하고, 버전 고정이 필요하면 `Directory.Packages.props`(중앙 패키지 관리) 사용.
- 재현 가능한 복원이 필요한 레포는 `packages.lock.json` 을 커밋하고 CI 에서 `dotnet restore --locked-mode`.

## 코드 컨벤션
- `.editorconfig` 를 단일 스타일 소스로 삼는다. 커밋 전 `dotnet format`.
- **nullable 참조 타입 활성화**(`<Nullable>enable</Nullable>`) — `!`(null-forgiving) 남용 금지, 쓰면 근거를 주석으로.
- `async` 메서드는 끝까지 async — `.Result`/`.Wait()`/`GetAwaiter().GetResult()` 로 블로킹 금지. 라이브러리 코드는 `ConfigureAwait(false)`.
- 취소 토큰(`CancellationToken`)은 async 공개 API 의 마지막 매개변수로 받아 하위로 전달한다.
- `IDisposable`/`IAsyncDisposable` 자원은 `using` 선언으로 다룬다. `HttpClient` 는 직접 new 하지 말고 `IHttpClientFactory`.
- DI 수명(`Singleton`/`Scoped`/`Transient`)을 명시적으로 결정 — singleton 에 scoped 서비스(예: `DbContext`) 주입 금지.
- 예외는 삼키지 않는다(`catch { }` 금지). 다시 던질 때는 `throw;`(`throw ex;` 금지 — 스택 소실).

## 테스트
- xUnit 기본(`tests/<Project>.Tests/`). 테스트 프로젝트명은 `<Project>.Tests` 규칙.
- 어설션은 사용자 관점 결과로. 외부 의존성은 인터페이스로 추상화 후 대역 사용.
- 새 기능·버그픽스마다 최소 1개 테스트 동반(P1).
- 통합 테스트는 ASP.NET Core `WebApplicationFactory<T>` 사용, DB 는 격리된 인스턴스로.

## 보안
- 시크릿은 개발 시 `dotnet user-secrets`, 운영은 환경변수/시크릿 매니저. `appsettings*.json` 에 연결 문자열 비밀번호·API 키 하드코딩 금지.
- SQL 은 파라미터 바인딩만(`FromSqlInterpolated`/`DbParameter`). `FromSqlRaw` 에 문자열 결합 금지.
- 모델 바인딩 과다 노출 방지 — 엔티티 직접 바인딩 대신 DTO 를 받고 `[Bind]`/`[FromBody]` 대상을 좁힌다.
- 인증이 필요한 컨트롤러·엔드포인트에 `[Authorize]`(또는 `RequireAuthorization()`) 누락 금지.
- 역직렬화는 `System.Text.Json` 기본. `BinaryFormatter` 사용 금지.

## P0
- 시크릿 하드코딩 금지 — `appsettings*.json` 에 비밀번호/키 금지, `secrets.json`·`.env` 스테이징 금지
- SQL 문자열 결합 금지 — 파라미터 바인딩만(`FromSqlRaw` 보간 금지)
- 인증 없는 엔드포인트 신규 추가 금지 — `[Authorize]`/`RequireAuthorization()` 명시

## P1
- `dotnet build` 경고 없이, `dotnet format --verify-no-changes` 통과 상태로 커밋
- 새 기능·버그픽스에 테스트 최소 1개 동반
- async 경로에서 동기 블로킹(`.Result`/`.Wait()`) 금지

## P2
- `var` 는 우변에서 타입이 자명할 때만
- 공개 API 에 XML 문서 주석(`///`) 부여
- 매직 넘버·문자열은 `const`/옵션 클래스(`IOptions<T>`)로
