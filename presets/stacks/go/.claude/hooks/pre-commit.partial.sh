# --- Go build + vet gate ---
if [ -f go.mod ]; then
  if command -v go >/dev/null 2>&1; then
    echo "go build + vet..." >&2
    if ! go build ./... 2>&1; then
      echo "Blocked: go build failed." >&2
      exit 2
    fi
    if ! go vet ./... 2>&1; then
      echo "Blocked: go vet failed." >&2
      exit 2
    fi
    # golangci-lint (있으면) — v1 은 --fast, v2(2025-03+)는 --fast-only 로 플래그가 바뀜
    if command -v golangci-lint >/dev/null 2>&1; then
      fast_flag="--fast"
      golangci-lint run --help 2>/dev/null | grep -q -- '--fast-only' && fast_flag="--fast-only"
      if ! golangci-lint run "$fast_flag" ./... 2>&1; then
        echo "Blocked: golangci-lint failed." >&2
        exit 2
      fi
    fi
  else
    # 툴 미설치는 차단 사유가 아니다(PRESET_SPEC) — "go: command not found" 를 빌드 실패로 오인하지 않는다.
    echo "pre-commit: go not installed — skipping Go checks" >&2
  fi
fi
