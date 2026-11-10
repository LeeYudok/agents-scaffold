# --- Python lint + typecheck gate ---
# 추적(스테이징 포함) 중인 .py 가 있을 때만 켠다. find 로 트리를 훑으면 .venv·node_modules 까지 들어간다.
if [ -n "$(git ls-files -- '*.py' 2>/dev/null | sed -n '1p')" ]; then
  # uv 는 프로젝트가 실제로 uv 를 쓸 때만 경유한다(uv.lock 또는 pyproject.toml 의 [tool.uv]).
  # uv 가 PATH 에 있다는 이유만으로 `uv run` 을 쓰면 uv 프로젝트가 아닌 레포에서 ruff 를 못 찾아
  # 멀쩡한 커밋이 막힌다.
  py_uses_uv=0
  if command -v uv >/dev/null 2>&1; then
    if [ -f uv.lock ] || { [ -f pyproject.toml ] && grep -qE '^\[tool\.uv[].]' pyproject.toml; }; then
      py_uses_uv=1
    fi
  fi

  # ruff: uv 프로젝트에서 해석되면 `uv run ruff`, 아니면 PATH 의 ruff, 둘 다 없으면 건너뜀.
  py_ruff=""
  if [ "$py_uses_uv" -eq 1 ] && uv run ruff --version >/dev/null 2>&1; then
    py_ruff="uv run ruff"
  elif command -v ruff >/dev/null 2>&1; then
    py_ruff="ruff"
  fi
  if [ -n "$py_ruff" ]; then
    echo "ruff check..." >&2
    # 출력은 버리지 않는다 — 무엇이 걸렸는지 보여야 고칠 수 있다.
    if ! py_out="$($py_ruff check . 2>&1)"; then
      printf '%s\n' "$py_out" | tail -40 >&2
      echo "Blocked: ruff check failed. Run 'ruff check --fix .' and commit again." >&2
      exit 2
    fi
  else
    echo "pre-commit: ruff not installed — skipping lint" >&2
  fi

  # mypy: 프로젝트가 mypy 를 설정했을 때만 돌리고, 실패하면 차단한다.
  # 설정(mypy.ini / .mypy.ini / pyproject.toml [tool.mypy] / setup.cfg [mypy])이 없으면
  # 기본값 mypy 가 untyped 코드에 오류를 쏟아내므로 게이트로 쓰지 않고 건너뛴다.
  py_mypy_configured=0
  if [ -f mypy.ini ] || [ -f .mypy.ini ]; then
    py_mypy_configured=1
  elif [ -f pyproject.toml ] && grep -qE '^\[tool\.mypy[].]' pyproject.toml; then
    py_mypy_configured=1
  elif [ -f setup.cfg ] && grep -qE '^\[mypy[]-]' setup.cfg; then
    py_mypy_configured=1
  fi
  if [ "$py_mypy_configured" -eq 1 ]; then
    py_mypy=""
    if [ "$py_uses_uv" -eq 1 ] && uv run mypy --version >/dev/null 2>&1; then
      py_mypy="uv run mypy"
    elif command -v mypy >/dev/null 2>&1; then
      py_mypy="mypy"
    fi
    py_target=""
    if [ -d src ]; then py_target="src"; elif [ -d app ]; then py_target="app"; fi
    if [ -z "$py_mypy" ]; then
      echo "pre-commit: mypy is configured but not installed — skipping typecheck" >&2
    elif [ -z "$py_target" ]; then
      echo "pre-commit: no src/ or app/ directory — skipping mypy" >&2
    else
      echo "mypy $py_target..." >&2
      if ! py_out="$($py_mypy "$py_target" 2>&1)"; then
        printf '%s\n' "$py_out" | tail -20 >&2
        echo "Blocked: mypy failed. Fix the type errors above and commit again." >&2
        exit 2
      fi
    fi
  fi
fi
