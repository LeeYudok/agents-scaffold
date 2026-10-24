# --- Python lint + typecheck gate ---
if find . -name "*.py" -path "*/src/*" -o -name "*.py" -path "*/app/*" | head -1 | grep -q py 2>/dev/null \
   || ls *.py 2>/dev/null | head -1 | grep -q py; then
  # ruff check
  if command -v ruff >/dev/null 2>&1 || command -v uv >/dev/null 2>&1; then
    ruff_cmd="ruff"
    command -v uv >/dev/null 2>&1 && ruff_cmd="uv run ruff"
    if ! $ruff_cmd check . >/dev/null 2>&1; then
      echo "차단: ruff check 실패. 'ruff check --fix .' 실행 후 재커밋." >&2
      exit 2
    fi
  fi
  # mypy (있으면)
  if command -v mypy >/dev/null 2>&1 || (command -v uv >/dev/null 2>&1 && uv run mypy --version >/dev/null 2>&1); then
    mypy_cmd="mypy"
    command -v uv >/dev/null 2>&1 && mypy_cmd="uv run mypy"
    target="app"
    [ -d "src" ] && target="src"
    [ -d "$target" ] && $mypy_cmd "$target" --quiet 2>&1 | tail -5 || true
  fi
fi
