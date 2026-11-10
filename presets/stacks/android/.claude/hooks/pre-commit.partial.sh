# --- Android Kotlin lint + typecheck gate ---
# 빌드 산출물·캐시(build/, .gradle/, node_modules/)는 탐색에서 제외한다. `find | head -1` 은
# 큰 트리에서 find 가 SIGPIPE 로 죽어 pipefail 아래 게이트가 조용히 꺼지므로 -quit 을 쓴다.
if [ -x ./gradlew ] && [ -n "$(find . \( -name build -o -name .gradle -o -name node_modules -o -name .git \) -prune -o -name '*.kt' -print -quit 2>/dev/null)" ]; then
  echo "ktlintCheck + detekt..." >&2
  if ! ./gradlew ktlintCheck -q 2>&1; then
    echo "Blocked: ktlint failed. Run './gradlew ktlintFormat' and commit again." >&2
    exit 2
  fi
  if ! ./gradlew detekt -q 2>&1; then
    echo "Blocked: detekt failed." >&2
    exit 2
  fi
fi
