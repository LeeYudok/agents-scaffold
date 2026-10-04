#!/usr/bin/env bash
# PostToolUse(Bash) — 테스트 실행 결과를 터미널 벨 + macOS 알림으로 surfacing.
# bun/npm/pytest/go test/gradle 자동 감지. self-guard 포함.
set -uo pipefail

input="$(cat)"

# 결과를 모르면 알리지 않는다 — 출력이 없는 하네스(agy PostToolUse)에서 실패를 통과로 알리지 않게 (#65)
if ! printf '%s' "$input" | grep -qE '"tool_response"[[:space:]]*:' \
  || printf '%s' "$input" | grep -qE '"tool_response"[[:space:]]*:[[:space:]]*(""|null|\{\})'; then
  exit 0
fi

# 테스트 커맨드 self-guard
if printf '%s' "$input" | grep -qE '"bun test|npm test|pnpm test|yarn test'; then
  runner="js"
elif printf '%s' "$input" | grep -qE '"pytest|python -m pytest'; then
  runner="python"
elif printf '%s' "$input" | grep -qE '"go test'; then
  runner="go"
elif printf '%s' "$input" | grep -qE '"\.\/gradlew test|gradle test'; then
  runner="gradle"
else
  exit 0
fi

# 툴 자체가 에러로 끝났으면(출력 없이 에러만 오는 하네스 포함) 실패로 알린다 (#65)
if printf '%s' "$input" | grep -qE '"is_error"[[:space:]]*:[[:space:]]*true'; then
  msg="Tests failed (${runner}: tool error)"; icon="❌"
else
  case "$runner" in
    js)
      passes="$(printf '%s' "$input" | grep -oE '[0-9]+ pass' | head -1)"
      if printf '%s' "$input" | grep -qE '[1-9][0-9]* fail'; then
        fails="$(printf '%s' "$input" | grep -oE '[1-9][0-9]* fail' | head -1)"
        msg="Tests failed: ${fails:-fail}${passes:+ / $passes}"; icon="❌"
      else
        msg="Tests passed: ${passes:-ok}"; icon="✅"
      fi
      ;;
    python)
      if printf '%s' "$input" | grep -qE 'failed|ERROR'; then
        msg="pytest failed"; icon="❌"
      else
        passed="$(printf '%s' "$input" | grep -oE '[0-9]+ passed' | head -1)"
        msg="pytest passed${passed:+: $passed}"; icon="✅"
      fi
      ;;
    go)
      if printf '%s' "$input" | grep -qE '\bFAIL\b'; then
        msg="go test failed"; icon="❌"
      else
        msg="go test passed"; icon="✅"
      fi
      ;;
    gradle)
      if printf '%s' "$input" | grep -qE 'BUILD FAILED|[1-9][0-9]* test.*fail'; then
        msg="gradle test failed"; icon="❌"
      else
        msg="gradle test passed"; icon="✅"
      fi
      ;;
  esac
fi

printf '\a' >&2
echo "${icon} ${msg}" >&2
command -v osascript >/dev/null 2>&1 \
  && osascript -e "display notification \"${msg//\"/}\" with title \"{{PROJECT_NAME}}\"" >/dev/null 2>&1 || true
exit 0
