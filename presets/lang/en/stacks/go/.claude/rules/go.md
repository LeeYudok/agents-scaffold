---
paths:
  - "**/*.go"
  - "cmd/**/*.go"
  - "internal/**/*.go"
---

# Go Rules

## Build & test
- `go build ./...` — no errors before committing.
- `go test -race ./...` — includes race-condition detection. Cannot be skipped in CI.
- `go mod tidy` — always run after adding/removing dependencies. Include `go.sum` in the commit.
- `go vet ./...` — baseline static analysis.

## Linting
- `golangci-lint run ./...` — per `.golangci.yml` settings.
- Auto-fix: `golangci-lint run --fix ./...`.

## Code conventions
- **Error wrapping**: `fmt.Errorf("context: %w", err)`. Do not re-create bare `errors.New`.
- **Context propagation**: every I/O function takes `ctx context.Context` as its first argument.
- **Interfaces**: define in the consuming package, not the implementing package (interface consumer declares it).
- **Naming**: lowercase singular package names. Initialisms are uppercase (`URL`, `HTTP`, `ID`).
- No ignoring errors with `_` — if necessary, add a `// nolint:errcheck` comment with a reason.

## Architecture
- **Package layout**: `cmd/` (entry points), `internal/` (private), `pkg/` (public library).
- No global variables → use struct + constructor DI pattern.
- Minimize `init()` functions.

## Security
- Environment variables: `os.Getenv("XXX")`. No hardcoding.
- SQL: parameter binding (`$1`, `?`). No string-concatenated SQL.
- Do not expose internal paths/stack traces in HTTP responses.

## P0
- No hardcoded secrets
- `go build ./...` + `go vet ./...` must pass with no errors before committing
- No `.env` staged into git

## P1
- Always commit `go.mod` / `go.sum` (reproducible builds)
- Test files in the same package with a `_test.go` suffix
- `-race` flag required for race detection in CI
