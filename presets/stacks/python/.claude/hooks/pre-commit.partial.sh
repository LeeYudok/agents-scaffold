# --- Python lint + typecheck gate ---
# 프로젝트 가상환경을 우선한다. uv 가 있다는 이유만으로 도구를 내려받거나 동기화하지 않는다 (#104).
python_file="$(find . \( -type d \( -name .git -o -name .claude -o -name .agents -o -name .codex -o -name .venv -o -name venv -o -name __pycache__ -o -name build -o -name dist -o -name node_modules \) -prune \) -o -type f -name '*.py' -print -quit)"
if [ -n "$python_file" ]; then
  ruff_cmd=""
  if [ -x .venv/bin/ruff ]; then ruff_cmd=.venv/bin/ruff
  elif [ -x .venv/Scripts/ruff.exe ]; then ruff_cmd=.venv/Scripts/ruff.exe
  elif command -v ruff >/dev/null 2>&1; then ruff_cmd=ruff; fi
  if [ -n "$ruff_cmd" ]; then
    if ! "$ruff_cmd" check .; then
      echo "Blocked: ruff check failed. Run 'ruff check --fix .' before committing." >&2
      exit 2
    fi
  else
    echo "pre-commit: ruff not installed — skipping lint" >&2
  fi
  mypy_configured=0
  if [ -f mypy.ini ] || [ -f .mypy.ini ] \
    || { [ -f pyproject.toml ] && grep -qE '^\[tool\.mypy[].]' pyproject.toml; } \
    || { [ -f setup.cfg ] && grep -qE '^\[mypy[]-]' setup.cfg; }; then
    mypy_configured=1
  fi
  mypy_cmd=""
  if [ -x .venv/bin/mypy ]; then mypy_cmd=.venv/bin/mypy
  elif [ -x .venv/Scripts/mypy.exe ]; then mypy_cmd=.venv/Scripts/mypy.exe
  elif command -v mypy >/dev/null 2>&1; then mypy_cmd=mypy; fi
  if [ "$mypy_configured" -eq 1 ] && [ -n "$mypy_cmd" ]; then
    if ! "$mypy_cmd" .; then
      echo "Blocked: mypy failed. Fix the type errors before committing." >&2
      exit 2
    fi
  elif [ "$mypy_configured" -eq 1 ]; then
    echo "pre-commit: mypy is configured but not installed — skipping typecheck" >&2
  fi
fi
