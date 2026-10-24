# --- Flutter format + analyze + test gate ---
if [ -f pubspec.yaml ] && command -v flutter >/dev/null 2>&1; then
  echo "dart format check..." >&2
  if ! dart format --set-exit-if-changed . >/dev/null 2>&1; then
    echo "차단: dart format 미적용 파일이 있음. 'dart format .' 실행 후 커밋." >&2
    exit 2
  fi
  echo "flutter analyze..." >&2
  if ! flutter analyze 2>&1; then
    echo "차단: flutter analyze 실패." >&2
    exit 2
  fi
  if [ -d test ]; then
    echo "flutter test..." >&2
    if ! flutter test 2>&1; then
      echo "차단: flutter test 실패." >&2
      exit 2
    fi
  fi
fi
