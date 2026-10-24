# --- bun (TypeScript) typecheck gate ---
# tsc 가용성은 exit 없이 if 로 감싼다. 다중 스택 적용 시 `exit 0` 으로
# 훅 전체를 끝내면 뒤 스택 게이트가 스킵되므로(차단=exit 2 만 사용).
if [ -f tsconfig.json ]; then
  if bunx --no-install tsc --version >/dev/null 2>&1; then
    errors="$(bunx --no-install tsc --noEmit -p tsconfig.json 2>&1 | grep -E 'error TS' || true)"
    if [ -n "$errors" ]; then
      echo "차단: TypeScript 에러. 커밋 전 수정 필요:" >&2
      printf '%s\n' "$errors" >&2
      exit 2
    fi
  else
    echo "pre-commit: tsc unavailable — skipping typecheck" >&2
  fi
fi
