# --- Python lint + typecheck gate ---
# 프로젝트 가상환경을 우선한다. uv 가 있다는 이유만으로 도구를 내려받거나 동기화하지 않는다 (#104).
python_file="$(find . \( -type d \( -name .git -o -name .venv -o -name venv -o -name __pycache__ -o -name build -o -name dist -o -name node_modules \) -prune \) -o -type f -name '*.py' -print -quit)"
if [ -n "$python_file" ]; then
  ruff_cmd=""
  if [ -x .venv/bin/ruff ]; then ruff_cmd=.venv/bin/ruff
  elif [ -x .venv/Scripts/ruff.exe ]; then ruff_cmd=.venv/Scripts/ruff.exe
  elif command -v ruff >/dev/null 2>&1; then ruff_cmd=ruff; fi
  if [ -n "$ruff_cmd" ]; then
    if ! "$ruff_cmd" check .; then
      echo "차단: ruff check 실패. 'ruff check --fix .' 실행 후 재커밋." >&2
      exit 2
    fi
  fi
  mypy_cmd=""
  if [ -x .venv/bin/mypy ]; then mypy_cmd=.venv/bin/mypy
  elif [ -x .venv/Scripts/mypy.exe ]; then mypy_cmd=.venv/Scripts/mypy.exe
  elif command -v mypy >/dev/null 2>&1; then mypy_cmd=mypy; fi
  if [ -n "$mypy_cmd" ]; then
    if ! "$mypy_cmd" .; then
      echo "차단: mypy 실패. 타입 오류를 수정한 뒤 재커밋." >&2
      exit 2
    fi
  fi
fi
