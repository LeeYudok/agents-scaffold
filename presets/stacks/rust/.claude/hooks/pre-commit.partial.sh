# --- Rust cargo check + clippy gate ---
if [ -f Cargo.toml ]; then
  if command -v cargo >/dev/null 2>&1; then
    echo "cargo check..." >&2
    if ! cargo check --quiet 2>&1; then
      echo "Blocked: cargo check failed." >&2
      exit 2
    fi
    # clippy (컴포넌트가 설치돼 있을 때만, 느릴 수 있어 --quiet)
    if cargo clippy --version >/dev/null 2>&1; then
      errors="$(cargo clippy --quiet 2>&1 | grep -E '^error' || true)"
      if [ -n "$errors" ]; then
        echo "Blocked: cargo clippy errors:" >&2
        printf '%s\n' "$errors" | sed -n '1,20p' >&2
        exit 2
      fi
    else
      echo "pre-commit: clippy not installed — skipping lint" >&2
    fi
  else
    # 툴 미설치는 차단 사유가 아니다(PRESET_SPEC).
    echo "pre-commit: cargo not installed — skipping Rust checks" >&2
  fi
fi
