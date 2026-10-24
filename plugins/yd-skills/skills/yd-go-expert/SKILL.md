---
name: yd-go-expert
description: Go 코드를 작성·리뷰·리팩터링하거나 에러 처리, 동시성, 테스트, net/http 서버, go:embed 를 다룰 때 사용한다. Go 1.22+ 기준.
---

# yd-go-expert

Go 코드가 대상이다. SQL·스키마는 `yd-db-expert` 와 엔진별 스킬(`yd-pg-expert`·`yd-oracle-expert`·`yd-sqlite-expert`),
프론트 산출물 내장의 빌드 순서는 `yd-frontend-build` 가 맡는다.

이 문서는 **일반론을 적지 않는다.** 판단이 갈리는 지점, 자주 틀리는 곳, 최근 버전에서
바뀐 것만 담는다.

## 1. 에러

- **감싸서 올린다.** `fmt.Errorf("%s 열기 실패: %w", path, err)` — `%w` 여야
  `errors.Is`/`errors.As` 가 통한다. `%v` 로 감싸면 사슬이 끊긴다.
- **호출부가 분기해야 하는 실패는 센티널로 노출한다.** `var ErrNotFound = errors.New(...)`.
  문자열 비교로 분기하지 않는다.
- 메시지는 소문자로 시작하고 마침표를 붙이지 않는다. 한국어 메시지도 문장부호 없이 짧게.
- **로그와 반환을 동시에 하지 않는다.** 둘 다 하면 같은 실패가 여러 번 기록된다.
  최상위(핸들러·main)에서 한 번만 기록한다.
- `panic` 은 프로그래머 오류에만. 입력이 잘못된 것은 에러다.
- **error 자리에 nil 포인터를 돌려주지 않는다(typed nil).** `var e *MyErr; return e` 는
  호출부에서 `err != nil` 이 **참**이다. 인터페이스 값에 타입 정보가 남기 때문이다.
  실패가 없으면 리터럴 `nil` 을 반환한다.

```go
if errors.Is(err, chatdb.ErrNotFound) { ... }   // 분기
var perr *fs.PathError
if errors.As(err, &perr) { ... }                 // 타입 정보가 필요할 때
```

Go 1.26+ 는 `errors.AsType` 으로 변수 선언 없이 꺼낸다. `go.mod` 의 `go` 버전이 1.26 미만이면 `errors.As` 를 쓴다.

`go vet` 는 `go.mod` 보다 새로운 표준 라이브러리 API 를 쓰면 `requires go1.26 or later` 로 잡는다. 완료 조건의 `go vet` 가 그 확인을 겸한다.

```go
if perr, ok := errors.AsType[*fs.PathError](err); ok { ... }
```

## 2. 동시성 — 필요할 때만

goroutine 을 띄우기 전에 답한다: **누가 이걸 멈추는가? 결과는 누가 받는가?**
답이 없으면 만들지 않는다.

- **goroutine 의 수명은 호출부가 통제한다.** `context.Context` 를 첫 인자로 받고,
  종료 신호를 존중한다. 구조체 필드에 context 를 넣지 않는다.
- 채널로 소유권을 옮기거나, 뮤텍스로 공유를 보호하거나 — **둘을 섞지 않는다.**
- `sync.WaitGroup` 은 `Add` 를 goroutine **밖에서** 부른다. 안에서 부르면 경합이다.
  Go 1.25+ 는 `wg.Go(func() { ... })` 가 `Add`·`Done` 을 대신해 이 실수가 생기지 않는다.
- **하나가 실패하면 나머지를 멈춰야 하면** `golang.org/x/sync/errgroup` 의
  `errgroup.WithContext` 를 쓴다. `WaitGroup` 은 에러를 모으지도, 취소하지도 않는다.
- **루프 안의 `defer` 는 함수가 끝날 때까지 실행되지 않는다.** 파일을 수백 개 여는 루프에서
  쓰면 핸들이 쌓인다. 반복마다 닫아야 하면 본문을 함수로 빼고 그 안에서 `defer` 한다.
- 루프 변수 캡처는 Go 1.22부터 반복마다 새 변수라 안전하다. **그 이전 버전 코드를
  손볼 때는** 여전히 확인한다.
- **테스트는 `-race` 로 돌린다.** 동시성 코드를 추가·수정했으면 필수다.

## 3. net/http — Go 1.22+ ServeMux

메서드와 경로 변수를 표준 mux 가 지원한다. 서드파티 라우터를 새로 들이기 전에 이걸로
충분한지 본다.

```go
mux.HandleFunc("GET /api/chat/refs/{ref}/rooms", h)
mux.HandleFunc("DELETE /api/chat/dbs/{db}", h)
// 핸들러에서
ref := r.PathValue("ref")
```

- 더 구체적인 패턴이 우선한다 — `/api/...` 를 등록해두면 `/` 폴백이 삼키지 않는다.
- 그 경로에 다른 메서드 패턴만 등록돼 있으면 405 를 돌려준다. 메서드 없는 `/` 나 `/api/` 폴백이 있으면 405 가 아니라 그 폴백이 받는다.
- **경로 변수는 디코딩된 값**이다. 파일명·경로로 쓸 거면 반드시 검증한다(§5).
- 서버에는 최소한 `ReadHeaderTimeout` 을 준다. 없으면 느린 헤더 공격에 매달린다.
- 미들웨어는 핸들러를 감싸는 함수로. 인가처럼 빠뜨리면 안 되는 것은
  **라우팅 등록 지점에서 한 번에 걸리게** 만든다 — 핸들러 안에서 각자 검사하면 언젠가 빠진다.

```go
mux.HandleFunc("GET /api/x", requireAdmin(cfg, "X", handleX))
```

## 4. go:embed

- `//go:embed` 는 **같은 디렉터리 이하만** 가리킨다. `../` 로 못 올라간다.
  상위 폴더의 산출물을 넣으려면 **그 폴더 안에 embed 하는 패키지를 둔다.**
- 기본 패턴은 `.`·`_` 로 시작하는 파일을 건너뛴다. 포함하려면 `all:` 접두사.
- **패턴이 하나도 안 맞으면 컴파일 에러다.** 산출물을 커밋하지 않는 구조라면
  자리표시자를 하나 커밋하고 `//go:embed all:dist` 로 받는다.
- 내장 여부를 런타임에 확인해 안내를 띄운다. 빈 화면보다 원인 추적이 훨씬 빠르다.

```go
//go:embed all:dist
var dist embed.FS

func Built() bool { _, err := fs.Stat(Assets(), "index.html"); return err == nil }
```

SPA 를 서빙한다면 **정적 파일에 없는 경로는 404 가 아니라 index.html** 을 돌려줘야
새로고침·직접 접속이 동작한다.

## 5. 입력 검증

- **Go 1.24+ 는 `os.Root` 로 디렉터리 밖 접근을 막는다.** `os.OpenRoot(dir)` 로 연 루트의
  메서드는 `..` 이나 심볼릭 링크로 루트 밖을 가리키는 경로를 거절한다. 아래 `Base`·
  `EvalSymlinks` 수동 검사보다 빠뜨릴 곳이 적다. `go.mod` 가 1.24 미만일 때만 수동 검사를 쓴다.
- **파일명은 `filepath.Base` 로 정규화**하고, 남은 값에 구분자가 있으면 거절한다.
  경로 조작은 여기서 끊는다.
- 경로를 받는 기능은 절대 경로 여부·확장자·**심볼릭 링크를 푼 뒤**(`filepath.EvalSymlinks`)
  허용 범위를 검사한다. 링크는 검사 우회의 표준 수법이다.
- 업로드는 `io.LimitReader` 로 상한을 두고, 넘으면 지운다. 상한이 없으면 디스크를 채우는
  것만으로 서비스가 멈춘다.
- 형식만 맞고 내용이 아닌 파일을 걸러내려면 **실제로 열어서 판정**한다.
- **사용자가 준 URL 을 서버가 가져오면 SSRF 다.** 호스트를 IP 로 풀어 사설·루프백·링크로컬
  (`169.254.169.254` 같은 메타데이터 주소)을 거절한다. 리다이렉트도 같은 검사를 거친다
  (`http.Client.CheckRedirect`). 이름만 검사하면 DNS 를 바꿔 우회한다.
- 토큰·세션 ID·비밀번호 재설정 코드는 `crypto/rand` 로 만든다. `math/rand` 는 예측된다.

## 6. 테스트

- **테이블 주도**가 기본. 케이스마다 이름을 주고 실패 메시지에 넣는다.
- 실패 메시지는 `got = X, 원하는 값 Y` 형태로 **무엇이 왜 틀렸는지** 드러낸다.
- `t.TempDir()`·`t.Chdir()`·`t.Cleanup()` 을 쓴다. 수동 정리는 실패 경로에서 새어나간다.
- HTTP 는 `httptest.NewServer` + 실제 mux 로 **인가까지 함께** 검증한다.
  핸들러 함수만 직접 부르면 미들웨어가 빠져 "권한 없이도 되는" 회귀를 못 잡는다.
- **보안 요건은 반드시 테스트로 고정한다** — 권한 없는 접근이 403 인지, 주입 시도가 거부되는지,
  민감 자산이 다른 API 로 새지 않는지. 문서에만 적힌 규칙은 다음 리팩터링에서 사라진다.
- 외부 자원이 필요한 통합 테스트는 환경변수로 opt-in 하고 없으면 `t.Skip`.

```go
if got != want {
    t.Errorf("%s: 방 수 = %d, 원하는 값 %d", tc.name, got, want)
}
```

## 7. API 표면

- 반환 타입은 **호출부가 다뤄야 할 만큼만** 노출한다. 내부 구조체를 그대로 JSON 으로
  내보내지 않는다 — 필드가 늘면 조용히 새어나간다. DTO 를 따로 둔다.
- 슬라이스를 돌려줄 때 빈 결과는 `nil` 대신 빈 슬라이스로. JSON 에서 `null` 과 `[]` 는 다르다.
- **`append` 결과는 원본과 배열을 공유할 수 있다.** 용량이 남아 있으면 `b := append(a, x)` 뒤에
  `b` 를 고치면 `a` 도 바뀐다. 받은 슬라이스를 늘려서 돌려줄 때는 `slices.Clone` 으로 먼저 복사한다.
- 인터페이스는 **쓰는 쪽에서** 정의한다. 구현 쪽에 미리 만들어두지 않는다.
- 문서 주석은 이름으로 시작한다: `// Search 는 ...`.

## 8. 완료 조건

- `gofmt -l` 출력 없음, `go vet ./...` 통과
- `go test ./...` 통과 (동시성 변경이 있으면 `-race` 포함)
- 새 엔드포인트·기능에 인가·검증 테스트가 있다
- 에러가 `%w` 로 감싸져 있고, 분기 대상은 센티널로 노출한다
- 외부 입력(파일명·경로·ID)이 검증 후에만 쓰임

## 9. 이 문서의 단언 재현

```bash
python3 .claude/skills/yd-go-expert/scripts/verify_go_claims.py
```

위 단언 가운데 툴체인 동작에 관한 것(typed nil, `%w`/`%v`, 루프 변수, ServeMux, `go:embed`,
`defer`, `append`, `os.Root`, `go vet` 의 버전 검사)을 임시 모듈에서 `go run`·`go build`·`go vet` 으로
재현한다. 하나라도 다르면 exit 1 이고, Go 가 없으면 사유를 찍고 건너뛴다. 언어 의미는 `go.mod`
의 `go` 줄이 정하므로 재현도 그 줄을 단언의 일부로 둔다. Go 를 올린 뒤 돌려 보고, 다르면 문서를 고친다.
단언과 테스트의 대응은 `tests/claims.json` 이 갖는다. CI 는 `.github/workflows/go-claims.yml`.
