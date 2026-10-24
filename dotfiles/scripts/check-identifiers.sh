#!/usr/bin/env bash
# 스테이징된 파일의 식별자 패턴을 검사한다. 검출 값 대신 파일명만 출력한다.
# git add 후 실행한다. 모든 시크릿을 탐지하는 검사는 아니므로 diff도 직접 검토한다.
set -euo pipefail
cd "$(dirname "$0")/.."

pattern='([0-9]{1,3}\.){3}[0-9]{1,3}|/Users/[[:alnum:]_][[:alnum:]_.-]*|/home/[[:alnum:]_][[:alnum:]_.-]*|glpat-|ghp_|BEGIN [A-Z ]*PRIVATE KEY'
if git grep --cached -lIE "$pattern" -- . ':!scripts/check-identifiers.sh'; then
  echo '식별자 패턴을 발견했습니다. 위 파일의 스테이징된 내용을 확인하십시오.' >&2
  exit 1
else
  status=$?
  if [ "$status" -ne 1 ]; then
    echo '식별자 검사를 실행하지 못했습니다.' >&2
    exit "$status"
  fi
fi
echo '식별자 검사 통과'
