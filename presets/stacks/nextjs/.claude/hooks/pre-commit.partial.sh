# --- Next.js TypeScript typecheck gate ---
if [ -f tsconfig.json ]; then
  npx_cmd="npx --no-install"
  command -v bunx >/dev/null 2>&1 && npx_cmd="bunx --no-install"
  if $npx_cmd tsc --version >/dev/null 2>&1; then
    errors="$($npx_cmd tsc --noEmit -p tsconfig.json 2>&1 | grep -E 'error TS' || true)"
    if [ -n "$errors" ]; then
      echo "차단: TypeScript 에러. 커밋 전 수정 필요:" >&2
      printf '%s\n' "$errors" | head -20 >&2
      exit 2
    fi
  fi
fi
