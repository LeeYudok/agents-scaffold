#!/usr/bin/env bash
# 스킬별 테스트 러너 (#78) — 각 스킬 폴더의 tests/test_*.py 를 스킬마다 따로 unittest 로 돌린다.
# 원천: .claude/skills/*(기본)·presets/skills-personal/.claude/skills/*(옵트인).
# doksam-skills 의 scripts/run_tests.sh 구조를 이 레포 경로에 맞춘 것. 새 스킬을 추가해도 이 파일은 그대로 둔다.
#   scripts/run-skill-tests.sh            전부
#   scripts/run-skill-tests.sh yd-pg-expert docs-sync   이름으로 고르기
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"
# 바이트코드를 남기지 않는다 — presets 는 find 로 복사되므로 __pycache__ 가 설치 산출물에 섞인다
export PYTHONDONTWRITEBYTECODE=1
failed=0 ran=0

dirs=()
for d in "$REPO_ROOT"/.claude/skills/*/tests/ "$REPO_ROOT"/presets/skills-personal/.claude/skills/*/tests/; do
  [[ -d "$d" ]] || continue
  name="$(basename "$(dirname "$d")")"
  if [[ $# -gt 0 ]]; then
    keep=0; for want in "$@"; do [[ "$want" == "$name" ]] && keep=1; done
    [[ $keep -eq 1 ]] || continue
  fi
  dirs+=("$d")
done

for dir in "${dirs[@]+"${dirs[@]}"}"; do
  # 테스트 파일이 없는 디렉터리는 건너뛴다 — unittest discover 는 0건을 실패(exit 5)로 본다
  compgen -G "$dir/test_*.py" >/dev/null || continue
  name="$(basename "$(dirname "$dir")")"
  echo "=== $name"
  ran=$((ran + 1))
  if (cd "$REPO_ROOT" && "$PY" -m unittest discover -s "$dir" -t "$dir"); then
    echo "--- ok: $name"
  else
    echo "--- FAIL: $name" >&2
    failed=$((failed + 1))
  fi
done

echo "skills tested: $ran, failed: $failed"
[[ $failed -eq 0 ]]
