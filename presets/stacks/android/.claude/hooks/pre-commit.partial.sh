# --- Android Kotlin lint + typecheck gate ---
if [ -x ./gradlew ] && (find . -name "*.kt" | head -1 | grep -q kt 2>/dev/null); then
  echo "ktlintCheck + detekt..." >&2
  if ! ./gradlew ktlintCheck -q 2>&1; then
    echo "차단: ktlint 실패. './gradlew ktlintFormat' 실행 후 재커밋." >&2
    exit 2
  fi
  if ! ./gradlew detekt -q 2>&1; then
    echo "차단: detekt 실패." >&2
    exit 2
  fi
fi
