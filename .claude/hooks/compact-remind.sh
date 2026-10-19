#!/usr/bin/env bash
# SessionStart(matcher: compact) hook — 컨텍스트 압축 직후 재진입 정리를 유도한다 (#72).
# PreCompact 는 prompt 타입 훅을 지원하지 않아 예전 PreCompact prompt 훅은 실행된 적이 없다.
# SessionStart 훅의 stdout 은 모델 컨텍스트에 들어간다.
set -uo pipefail
cat >/dev/null 2>&1 || true

cat <<'MSG'
컨텍스트가 방금 압축됐다. 이어서 작업하기 전에 재진입에 필요한 사실(완료/진행/다음 단계, 주요 결정과 근거, 차단 요소, 관련 이슈·브랜치·파일)이 요약에 남아 있는지 확인하라.

- 세션 간 지속이 필요한 비자명 사실은 `.claude/memory/` 에 타입접두(project_/feedback_/reference_) 메모리로 기록하고 `MEMORY.md` 인덱스에 한 줄 추가.
- 코드/git 으로 드러나는 사실은 기록하지 말 것(중복).
MSG
