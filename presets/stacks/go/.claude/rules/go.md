---
paths:
  - "**/*.go"
  - "cmd/**/*.go"
  - "internal/**/*.go"
---

# Go 규칙

## 빌드 & 테스트
- `go build ./...` — 에러 없이 커밋.
- `go test -race ./...` — 레이스 컨디션 감지 포함. CI에서 생략 불가.
- `go mod tidy` — 의존성 추가/제거 후 반드시 실행. `go.sum` 커밋 포함.
- `go vet ./...` — 정적 분석 기본.

## 린트
- `golangci-lint run ./...` — `.golangci.yml` 설정 기준.
- 자동 수정: `golangci-lint run --fix ./...`.

## 코드 컨벤션
- **에러 래핑**: `fmt.Errorf("context: %w", err)`. bare `errors.New` 재생성 금지.
- **컨텍스트 전파**: 모든 I/O 함수 첫 번째 인자 `ctx context.Context`.
- **인터페이스**: 구현체 패키지 아닌 사용 패키지에 정의 (인터페이스 소비 측 선언).
- **명명**: 패키지명 소문자 단수. 이니셜리즘은 대문자(`URL`, `HTTP`, `ID`).
- 에러 무시 `_` 금지 — 필요시 `// nolint:errcheck` 주석 + 이유 명시.

## 아키텍처
- **패키지 구조**: `cmd/` (엔트리포인트), `internal/` (비공개), `pkg/` (공개 라이브러리).
- 전역 변수 금지 → 구조체 + 생성자 DI 패턴.
- `init()` 함수 최소화.

## 보안
- 환경변수: `os.Getenv("XXX")`. 하드코딩 금지.
- SQL: 파라미터 바인딩 (`$1`, `?`). 문자열 concat SQL 금지.
- HTTP 응답에 내부 경로/스택 노출 금지.

## P0
- 시크릿 하드코딩 금지
- `go build ./...` + `go vet ./...` 에러 없이 커밋
- `.env` git 스테이징 금지

## P1
- `go.mod` / `go.sum` 반드시 커밋 (재현 가능한 빌드)
- 테스트 파일 동일 패키지 + `_test.go` 접미사
- 레이스 감지 CI에서 `-race` 플래그 필수
