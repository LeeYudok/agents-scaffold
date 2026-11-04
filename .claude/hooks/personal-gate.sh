#!/bin/sh
# 개인 레이어 사용자 확인 게이트 실행기 — Claude Code · Codex · agy 공용 (#94).
#
#   sh .claude/hooks/personal-gate.sh <claude|codex|agy> <session-start|prompt|pre-tool|post-tool>
#
# 루트에 AGENTS.<NAME>.md(AGENTS.override.md 제외)가 없으면 python 을 띄우지 않고 바로 통과한다 —
# 개인 레이어를 쓰지 않는 프로젝트에서 툴 호출마다 드는 비용을 없애기 위해서다.
# 레포 루트는 이 스크립트 위치로 찾는다(하네스마다 훅 cwd 가 다르다: Codex 는 세션 cwd, agy 는 .agents/).
ROOT=$(cd "$(dirname "$0")/../.." && pwd)

found=0
for f in "$ROOT"/AGENTS.*.md; do
  [ -f "$f" ] || continue
  case "$(basename "$f")" in AGENTS.override.md|AGENTS.OVERRIDE.md) continue ;; esac
  found=1
  break
done
# agy 1.5.0 은 PreToolUse 출력 {} 를 거부로 읽는다(빈 출력·{"decision":"allow"} 는 허용, 2026-11-04 실측 #94)
allow() { [ "$1" = "agy" ] && [ "$2" = "pre-tool" ] && printf '{"decision":"allow"}'; return 0; }
if [ "$found" -eq 0 ]; then
  allow "$@"
  exit 0
fi

for candidate in "${PERSONAL_GATE_PYTHON:-}" python3 python; do
  [ -n "$candidate" ] || continue
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 8))' 2>/dev/null; then
    exec "$candidate" "$ROOT/.claude/hooks/personal-gate.py" "$@"
  fi
done
echo "[personal-gate] Python 3.8+ 를 찾지 못했다 — 게이트 없이 진행한다. PERSONAL_GATE_PYTHON 으로 경로를 지정한다." >&2
allow "$@"
exit 0
