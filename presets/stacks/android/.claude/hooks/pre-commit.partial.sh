# --- Android Kotlin lint + typecheck gate ---
kotlin_file="$(find . \( -type d \( -name .git -o -name .gradle -o -name build -o -name node_modules \) -prune \) -o -type f -name '*.kt' -print -quit)"
if [ -x ./gradlew ] && [ -n "$kotlin_file" ]; then
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
