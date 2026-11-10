# --- Next.js TypeScript typecheck gate ---
if [ -f tsconfig.json ]; then
  npx_cmd="npx --no-install"
  command -v bunx >/dev/null 2>&1 && npx_cmd="bunx --no-install"
  if $npx_cmd tsc --version >/dev/null 2>&1; then
    errors="$($npx_cmd tsc --noEmit -p tsconfig.json 2>&1 | grep -E 'error TS' || true)"
    if [ -n "$errors" ]; then
      echo "Blocked: TypeScript errors. Fix them before committing:" >&2
      # head 가 아니라 sed 로 자른다 — head 는 먼저 끝나 printf 가 SIGPIPE 로 죽을 수 있다(pipefail).
      printf '%s\n' "$errors" | sed -n '1,20p' >&2
      exit 2
    fi
  else
    echo "pre-commit: tsc unavailable — skipping typecheck" >&2
  fi
fi
