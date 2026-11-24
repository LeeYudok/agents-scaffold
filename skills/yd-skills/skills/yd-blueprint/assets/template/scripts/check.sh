#!/bin/sh
# 청사진 검사기를 bun 이 있으면 bun 으로, 없으면 node 로 돌린다.
# package.json 의 check 가 이 파일을 부르므로 bun·pnpm·npm 어느 쪽이든 수정 없이 같다.
cd "$(dirname "$0")/.." || exit 1
if command -v bun >/dev/null 2>&1; then
  exec bun scripts/check.mjs "$@"
elif command -v node >/dev/null 2>&1; then
  exec node scripts/check.mjs "$@"
fi
echo "[FAIL] bun 또는 node(22.6 이상) 가 필요합니다" >&2
exit 1
