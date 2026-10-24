# --- Rust cargo check + clippy gate ---
if [ -f Cargo.toml ]; then
  echo "cargo check..." >&2
  if ! cargo check --quiet 2>&1; then
    echo "차단: cargo check 실패." >&2
    exit 2
  fi
  # clippy (있으면, 느릴 수 있어 --quiet)
  if command -v cargo >/dev/null 2>&1; then
    errors="$(cargo clippy --quiet 2>&1 | grep -E '^error' || true)"
    if [ -n "$errors" ]; then
      echo "차단: cargo clippy 에러:" >&2
      printf '%s\n' "$errors" >&2
      exit 2
    fi
  fi
fi
