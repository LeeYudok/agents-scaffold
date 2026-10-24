# --- springboot (Gradle) 빌드 검증: STACK CHECKS 구획에 append 됨 ---
if [ -x ./gradlew ]; then
  echo "gradle compileJava + test..." >&2
  ./gradlew -q compileJava test || { echo "차단: gradle 빌드/테스트 실패." >&2; exit 2; }
fi
