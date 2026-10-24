# --- javaweb (Java+JSP 레거시) 컴파일 게이트: 빌드툴 자동 감지 ---
# 레거시 프로젝트는 빌드툴이 제각각이라 maven → gradle → ant 순으로 감지한다.
# 도구가 없으면 경고만 하고 통과(fall-through) — exit 0 금지(#6), 차단은 exit 2 만.
if [ -f pom.xml ]; then
  javaweb_mvn=""
  if [ -x ./mvnw ]; then javaweb_mvn="./mvnw"; elif command -v mvn >/dev/null 2>&1; then javaweb_mvn="mvn"; fi
  if [ -n "$javaweb_mvn" ]; then
    echo "javaweb: maven compile..." >&2
    "$javaweb_mvn" -q -DskipTests compile || { echo "차단: maven 컴파일 실패. 커밋 전 수정 필요." >&2; exit 2; }
  else
    echo "pre-commit: maven 미설치 — javaweb 컴파일 게이트 skip" >&2
  fi
elif [ -f build.gradle ] || [ -f build.gradle.kts ]; then
  if [ -x ./gradlew ]; then
    echo "javaweb: gradle compileJava..." >&2
    ./gradlew -q compileJava || { echo "차단: gradle 컴파일 실패. 커밋 전 수정 필요." >&2; exit 2; }
  else
    echo "pre-commit: gradlew 없음 — javaweb 컴파일 게이트 skip" >&2
  fi
elif [ -f build.xml ]; then
  if command -v ant >/dev/null 2>&1; then
    echo "javaweb: ant compile..." >&2
    ant -q compile || { echo "차단: ant compile 실패. 커밋 전 수정 필요." >&2; exit 2; }
  else
    echo "pre-commit: ant 미설치 — javaweb 컴파일 게이트 skip" >&2
  fi
fi

# --- javaweb JSP 게이트(#40): 추가된 줄의 신규 스크립틀릿 차단 ---
# 기존 레거시 스크립틀릿은 건드리지 않는다(P1 점진 제거) — 이번 커밋에서 "추가되는" 줄만 검사.
# 지시자(<%@)·주석(<%--)은 허용, 스크립틀릿(<%)·표현식(<%=)·선언(<%!)은 차단.
javaweb_staged_jsp="$(git diff --cached --name-only --diff-filter=ACM -- '*.jsp' 2>/dev/null || true)"
if [ -n "$javaweb_staged_jsp" ]; then
  javaweb_new_scriptlets="$(git diff --cached -U0 -- '*.jsp' | grep -E '^\+[^+]' | grep -E '<%([^@-]|$)' | head -5 || true)"
  if [ -n "$javaweb_new_scriptlets" ]; then
    echo "차단: 신규 JSP 스크립틀릿 감지 — EL/JSTL 로 작성할 것 (.claude/rules/javaweb.md P1):" >&2
    printf '%s\n' "$javaweb_new_scriptlets" >&2
    exit 2
  fi
fi
