#!/usr/bin/env bash
# 개인 추가 지침 레이어 AGENTS.<NAME>.md 를 세 하네스에 켜고 끈다 (#92).
#
#   .claude/scripts/personal-layer.sh on <NAME>      켜기(다시 돌리면 사본을 새로 만든다)
#   .claude/scripts/personal-layer.sh off            끄기(이 스크립트가 만든 파일만 지운다)
#   .claude/scripts/personal-layer.sh status         상태와 낡은 사본 여부
#
# AGENTS.md 는 모두가 공유하는 기본 지침이고, AGENTS.<NAME>.md 는 그 위에 얹는 개인 지침이다.
# 하네스마다 지침 파일을 하나 더 읽게 하는 방법이 달라서 아래 생성물을 만든다.
# 생성물은 .git/info/exclude 에 넣어 커밋되지 않게 한다 — 켜고 끄는 일은 그 사람 클론에서만 일어난다.
#
#   Claude Code  CLAUDE.local.md              "@AGENTS.md" + "@AGENTS.<NAME>.md"
#                CLAUDE.local.md 가 있으면 Claude Code 는 AGENTS.md 를 건너뛰므로 둘 다 import 한다.
#   Codex        AGENTS.override.md           AGENTS.md + AGENTS.<NAME>.md 를 이어 붙인 사본
#                같은 폴더에선 override 가 AGENTS.md 를 대신한다(import 없음). 원본을 고치면 on 을 다시 돌린다.
#   agy          .agents/rules/personal-<name>.md   trigger: always_on 룰로 AGENTS.<NAME>.md 내용
#
# 실측(2026-11-04, #92): claude 2.1.318·codex-cli 0.166.0(debug prompt-input, 신뢰 무관)·agy 1.5.0
# 모두 기본 암호어와 개인 암호어를 함께 읽었다.
set -euo pipefail

MARK='<!-- personal-layer.sh 생성물: 직접 고치지 말 것 (#92) -->'
EXCL_BEGIN='# personal-layer.sh (#92) begin'
EXCL_END='# personal-layer.sh (#92) end'
CODEX_BUDGET=32768

die() { echo "personal-layer: $*" >&2; exit 1; }

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "git 저장소 안에서 실행한다"
cd "$ROOT"

claude_file="CLAUDE.local.md"
codex_file="AGENTS.override.md"

ours() { [ -f "$1" ] && grep -qF -- "$MARK" "$1"; }

# 사용자가 직접 만든 파일은 덮어쓰지 않는다.
guard() {
  if [ -e "$1" ] && ! ours "$1"; then
    die "$1 이 이미 있고 이 스크립트가 만든 파일이 아니다 — 건드리지 않는다. 직접 합치거나 옮긴 뒤 다시 실행한다"
  fi
}

agy_rules() { find .agents/rules -maxdepth 1 -name 'personal-*.md' 2>/dev/null || true; }

claude_body() { printf '@AGENTS.md\n@%s\n%s\n' "$1" "$MARK"; }
codex_body() { printf '%s\n' "$MARK"; cat AGENTS.md; printf '\n'; cat "$1"; }
agy_body() { printf -- '---\ntrigger: always_on\n---\n%s\n' "$MARK"; cat "$1"; }

exclude_file() { git rev-parse --git-path info/exclude; }

set_exclude() {
  local ex tmp; ex="$(exclude_file)"; mkdir -p "$(dirname "$ex")"; touch "$ex"
  tmp="$(mktemp)"
  awk -v b="$EXCL_BEGIN" -v e="$EXCL_END" '$0==b{skip=1;next} $0==e{skip=0;next} !skip' "$ex" > "$tmp"
  if [ "${1:-}" = add ]; then
    printf '%s\n/%s\n/%s\n/.agents/rules/personal-*.md\n%s\n' "$EXCL_BEGIN" "$claude_file" "$codex_file" "$EXCL_END" >> "$tmp"
  fi
  cat "$tmp" > "$ex"; rm -f "$tmp"
}

cmd_on() {
  local name="${1:-}" upper lower personal rule bytes
  [[ "$name" =~ ^[A-Za-z0-9_-]+$ ]] || die "이름은 영문·숫자·_·- 만 쓴다: on <NAME>"
  upper="$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')"
  lower="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')"
  personal="AGENTS.$upper.md"; rule=".agents/rules/personal-$lower.md"
  [ -f AGENTS.md ] || die "AGENTS.md 가 없다"
  [ -f "$personal" ] || die "$personal 이 없다 — 먼저 만든다"
  guard "$claude_file"; guard "$codex_file"; guard "$rule"
  # 이전에 켠 다른 이름의 agy 룰은 지운다(한 번에 한 사람)
  while IFS= read -r f; do [ -n "$f" ] && ours "$f" && rm -f "$f"; done < <(agy_rules)
  claude_body "$personal" > "$claude_file"
  codex_body "$personal" > "$codex_file"
  mkdir -p .agents/rules; agy_body "$personal" > "$rule"
  set_exclude add
  bytes="$(wc -c < "$codex_file" | tr -d ' ')"
  echo "personal-layer: $personal 켬 — $claude_file, $codex_file(${bytes} B), $rule"
  if [ "$bytes" -gt "$CODEX_BUDGET" ]; then
    echo "personal-layer: 경고 — $codex_file 가 Codex 기본 한도 ${CODEX_BUDGET} B 를 넘는다(뒷부분이 잘린다)" >&2
  fi
}

cmd_off() {
  local f
  for f in "$claude_file" "$codex_file"; do ours "$f" && rm -f "$f"; done
  while IFS= read -r f; do [ -n "$f" ] && ours "$f" && rm -f "$f"; done < <(agy_rules)
  rmdir .agents/rules .agents 2>/dev/null || true
  set_exclude remove
  echo "personal-layer: 꺼짐"
}

state() {
  if [ ! -e "$1" ]; then echo "없음"; elif ours "$1"; then echo "생성물"; else echo "사용자 파일(건드리지 않음)"; fi
}

cmd_status() {
  local personal="" rule
  if ours "$claude_file"; then personal="$(sed -n '2s/^@//p' "$claude_file")"; fi
  echo "개인 레이어: ${personal:-꺼짐}"
  echo "  Claude Code  $claude_file: $(state "$claude_file")"
  echo "  Codex        $codex_file: $(state "$codex_file")"
  rule="$(agy_rules | head -1)"
  echo "  agy          ${rule:-.agents/rules/personal-*.md}: $(state "${rule:-/nonexistent}")"
  [ -n "$personal" ] && [ -f "$personal" ] || return 0
  local stale=""
  if ours "$codex_file" && ! codex_body "$personal" | cmp -s - "$codex_file"; then stale="$codex_file"; fi
  if [ -n "$rule" ] && ours "$rule" && ! agy_body "$personal" | cmp -s - "$rule"; then stale="${stale:+$stale, }$rule"; fi
  if [ -n "$stale" ]; then
    echo "  사본이 낡았다($stale) — AGENTS.md 나 $personal 이 바뀌었다. on 을 다시 돌린다"
    return 3
  fi
  echo "  사본은 최신이다"
}

case "${1:-}" in
  on) shift; cmd_on "$@" ;;
  off) cmd_off ;;
  status) cmd_status ;;
  *) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac
