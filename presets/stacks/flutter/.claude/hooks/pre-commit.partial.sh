# --- Flutter format + analyze + test gate ---
if [ -f pubspec.yaml ]; then
  if command -v flutter >/dev/null 2>&1; then
    echo "dart format check..." >&2
    if ! dart format --set-exit-if-changed . >/dev/null 2>&1; then
      echo "Blocked: some files are not formatted. Run 'dart format .' and commit again." >&2
      exit 2
    fi
    echo "flutter analyze..." >&2
    if ! flutter analyze 2>&1; then
      echo "Blocked: flutter analyze failed." >&2
      exit 2
    fi
    if [ -d test ]; then
      echo "flutter test..." >&2
      if ! flutter test 2>&1; then
        echo "Blocked: flutter test failed." >&2
        exit 2
      fi
    fi
  else
    echo "pre-commit: flutter not installed — skipping Flutter checks" >&2
  fi
fi
