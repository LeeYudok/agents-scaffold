# --- springboot (Gradle/Maven) 컴파일 게이트: STACK CHECKS 구획에 append 됨 ---
# 빌드 파일이 없으면 no-op, 빌드 도구가 없으면 경고만 하고 통과한다(dotnet·php-laravel 과 같은 기준).
# 커밋마다 전체 테스트 스위트를 돌리지 않는다 — Spring 컨텍스트를 띄우는 테스트는 분 단위라
# 게이트를 --no-verify 로 우회하게 만든다. 기본은 main+test 소스 컴파일까지만 확인하고
# (gradle testClasses / maven test-compile), 테스트 실행은 CI 에 맡긴다.
# 커밋 때도 테스트를 돌리려면 SPRINGBOOT_GATE_TESTS=1 을 설정한다.
if [ -f build.gradle ] || [ -f build.gradle.kts ] || [ -f settings.gradle ] || [ -f settings.gradle.kts ]; then
  if [ -x ./gradlew ]; then
    sb_task="testClasses"
    [ "${SPRINGBOOT_GATE_TESTS:-0}" = "1" ] && sb_task="test"
    echo "springboot: gradle $sb_task..." >&2
    if ! ./gradlew -q "$sb_task" 2>&1 | tail -40; then
      echo "Blocked: gradle $sb_task failed. Fix it before committing." >&2
      exit 2
    fi
  else
    echo "pre-commit: no executable ./gradlew — skipping springboot compile check" >&2
  fi
elif [ -f pom.xml ]; then
  sb_mvn=""
  if [ -x ./mvnw ]; then sb_mvn="./mvnw"; elif command -v mvn >/dev/null 2>&1; then sb_mvn="mvn"; fi
  if [ -n "$sb_mvn" ]; then
    sb_goal="test-compile"
    [ "${SPRINGBOOT_GATE_TESTS:-0}" = "1" ] && sb_goal="test"
    echo "springboot: maven $sb_goal..." >&2
    if ! "$sb_mvn" -q "$sb_goal" 2>&1 | tail -40; then
      echo "Blocked: maven $sb_goal failed. Fix it before committing." >&2
      exit 2
    fi
  else
    echo "pre-commit: maven not installed — skipping springboot compile check" >&2
  fi
fi
