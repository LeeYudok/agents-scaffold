#!/usr/bin/env bash
# LeeYudok/skills(스킬 SSOT)를 이 리포의 같은 경로에 동기화한다 (#183).
# 이 리포의 skills/ 등은 사본이다 — 스킬은 LeeYudok/skills 에서 고친다.
#
# 사용: scripts/sync-skills.sh [--ref <branch|tag|sha>] [--source <로컬 skills 클론>] [--check]
#   --ref     받을 ref (기본 main)
#   --source  네트워크 대신 로컬 클론을 쓴다 (그 클론의 작업 트리가 아니라 --ref 커밋을 쓴다)
#   --check   바꾸지 않고 차이 유무만 종료코드로 알린다 (0=같음, 1=다름)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="https://github.com/LeeYudok/skills.git"
REF="main"
SOURCE=""
CHECK=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)    REF="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --check)  CHECK=1; shift ;;
    -h|--help) sed -n 2,9p "$0"; exit 0 ;;
    *) echo "오류: 알 수 없는 옵션 '$1'" >&2; exit 2 ;;
  esac
done

# 동기화 대상. skills 리포와 이 리포가 같은 상대 경로를 쓴다.
PATHS=(skills .claude/agents presets/skills/personal/.claude/agents
       scripts/install-skills.sh tests/test_install_skills.sh)

tmp="$(mktemp -d "${TMPDIR:-/tmp}/sync-skills.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
if [[ -n "$SOURCE" ]]; then
  git clone -q --no-checkout "$SOURCE" "$tmp/src"
else
  git clone -q --no-checkout --filter=blob:none "$URL" "$tmp/src"
fi
git -C "$tmp/src" checkout -q "$REF"
sha="$(git -C "$tmp/src" rev-parse HEAD)"

changed=0
for p in "${PATHS[@]}"; do
  src="$tmp/src/$p" dst="$ROOT/$p"
  if [[ ! -e "$src" ]]; then
    echo "오류: skills 리포($sha)에 $p 가 없다" >&2
    exit 1
  fi
  if [[ -d "$src" ]]; then
    # .claude/agents 는 이 리포 고유 에이전트(code-reviewer 등)도 담는다 — yd-* 만 맞춘다.
    if [[ "$p" == ".claude/agents" ]]; then
      filter=(--include='yd-*.md' --exclude='*')
    else
      filter=(--exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store')
    fi
    # -c 로 내용만 비교한다. 시각만 다른 줄(.f..T....)은 변경으로 치지 않는다.
    out="$(rsync -rlcni --delete "${filter[@]}" "$src/" "$dst/" | grep -vE '^\.[fdL]\.\.[tT]\.{4,5} ' || true)"
    if [[ -n "$out" ]]; then
      changed=1
      [[ $CHECK -eq 1 ]] && printf '%s\n' "$out" | sed "s|^|$p: |" | head -40
      [[ $CHECK -eq 0 ]] && rsync -rlc --delete "${filter[@]}" "$src/" "$dst/"
    fi
  else
    if ! cmp -s "$src" "$dst"; then
      changed=1
      echo "$p: 다름"
      [[ $CHECK -eq 0 ]] && cp -p "$src" "$dst"
    fi
  fi
done

if [[ $CHECK -eq 1 ]]; then
  if [[ $changed -eq 0 ]]; then echo "같음 — LeeYudok/skills@${sha:0:12}"; exit 0; fi
  echo "다름 — LeeYudok/skills@${sha:0:12} 와 차이가 있다 (scripts/sync-skills.sh 로 반영)" >&2
  exit 1
fi
printf '%s\n' "$sha" > "$ROOT/.skills-upstream"
if [[ $changed -eq 1 ]]; then
  echo "반영 — LeeYudok/skills@${sha:0:12}"
else
  echo "변경 없음 — LeeYudok/skills@${sha:0:12}"
fi
