#!/usr/bin/env bash
# 개인 추가 지침 레이어 AGENTS.<NAME>.md 를 세 하네스에 켜고 끈다 (#92).
#
#   .claude/scripts/personal-layer.sh on <NAME>      켜기(다시 돌리면 사본을 새로 만든다)
#   .claude/scripts/personal-layer.sh off            끄기(이 스크립트가 만든 파일만 지운다)
#   .claude/scripts/personal-layer.sh status         상태와 낡은 사본 여부
#   .claude/scripts/personal-layer.sh use <NAME|none> 이 세션 사용자 확인(#94) — personal-gate 훅이 이 명령을 기다린다.
#                                                    NAME 이면 on, none 이면 레이어 파일만 지운다(게이트 훅은 남긴다)
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
#
# 사용자 확인 게이트(#94): .claude/hooks/personal-gate.sh 가 매 세션 사용자 확인을 강제한다. Claude Code 는
# .claude/settings.json 훅으로 늘 걸려 있다. Codex·agy 는 .codex/hooks.json·.agents/hooks.json 이 필요해서,
# 없으면 on/use 가 게이트만 담은 파일을 만들고(exclude 에 넣는다) off 가 지운다. 설치기가 만든 hooks.json 은
# 이미 게이트를 담고 있으니 건드리지 않는다.
set -euo pipefail

MARK='<!-- personal-layer.sh 생성물: 직접 고치지 말 것 (#92) -->'
EXCL_BEGIN='# personal-layer.sh (#92) begin'
EXCL_END='# personal-layer.sh (#92) end'
CODEX_BUDGET=32768
GATE_STATE=".claude/state/personal-gate"
HOOKS_STATE=".claude/state/personal-layer-hooks"

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
    {
      printf '%s\n/%s\n/%s\n/.agents/rules/personal-*.md\n' "$EXCL_BEGIN" "$claude_file" "$codex_file"
      [ -f "$HOOKS_STATE" ] && sed 's|^|/|' "$HOOKS_STATE"
      printf '%s\n' "$EXCL_END"
    } >> "$tmp"
  fi
  cat "$tmp" > "$ex"; rm -f "$tmp"
}

# Codex·agy 용 게이트 훅 파일이 없으면 게이트만 담아 만든다(#94). 만든 파일은 HOOKS_STATE 에 적는다.
ensure_gate_hooks() {
  local h dst
  grep -qF personal-gate .claude/settings.json 2>/dev/null && [ -f .claude/hooks/hook-adapter.py ] || return 0
  command -v python3 >/dev/null 2>&1 || { echo "personal-layer: python3 가 없어 Codex·agy 게이트 훅을 만들지 못했다" >&2; return 0; }
  mkdir -p "$(dirname "$HOOKS_STATE")"; touch "$HOOKS_STATE"
  for h in codex agy; do
    case "$h" in codex) dst=".codex/hooks.json" ;; agy) dst=".agents/hooks.json" ;; esac
    [ -e "$dst" ] && continue
    mkdir -p "$(dirname "$dst")"
    if python3 .claude/hooks/hook-adapter.py emit "$h" .claude/settings.json --gate-only > "$dst.tmp"; then
      mv "$dst.tmp" "$dst"; grep -qxF "$dst" "$HOOKS_STATE" || echo "$dst" >> "$HOOKS_STATE"
    else
      rm -f "$dst.tmp"
    fi
  done
}

remove_gate_hooks() {
  local f
  [ -f "$HOOKS_STATE" ] || return 0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    # 커밋된 파일이거나 게이트 생성물이 아니면 건드리지 않는다
    if [ -f "$f" ] && grep -qF personal-gate "$f" && ! git ls-files --error-unmatch "$f" >/dev/null 2>&1; then rm -f "$f"; fi
    rmdir "$(dirname "$f")" 2>/dev/null || true
  done < "$HOOKS_STATE"
  rm -f "$HOOKS_STATE"
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
  ensure_gate_hooks
  set_exclude add
  bytes="$(wc -c < "$codex_file" | tr -d ' ')"
  echo "personal-layer: $personal 켬 — $claude_file, $codex_file(${bytes} B), $rule"
  if [ "$bytes" -gt "$CODEX_BUDGET" ]; then
    echo "personal-layer: 경고 — $codex_file 가 Codex 기본 한도 ${CODEX_BUDGET} B 를 넘는다(뒷부분이 잘린다)" >&2
  fi
}

remove_layer_files() {
  local f
  for f in "$claude_file" "$codex_file"; do if ours "$f"; then rm -f "$f"; fi; done
  while IFS= read -r f; do if [ -n "$f" ] && ours "$f"; then rm -f "$f"; fi; done < <(agy_rules)
  rmdir .agents/rules 2>/dev/null || true
}

cmd_off() {
  remove_layer_files
  remove_gate_hooks
  rmdir .agents 2>/dev/null || true
  rm -f "$GATE_STATE/current"
  set_exclude remove
  echo "personal-layer: 꺼짐"
}

# 이 세션 사용자 확인(#94). personal-gate 훅은 current 값이 요청과 같으면 세션을 연다.
cmd_use() {
  local name="${1:-}" upper
  [[ "$name" =~ ^[A-Za-z0-9_-]+$ ]] || die "use <NAME|none>"
  mkdir -p "$GATE_STATE"
  if [ "$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')" = none ]; then
    remove_layer_files
    ensure_gate_hooks
    set_exclude add
    echo none > "$GATE_STATE/current"
    echo "personal-layer: 이 세션 사용자 = 해당 없음 — 개인 지침을 적용하지 않는다"
    return 0
  fi
  upper="$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')"
  [ -f "AGENTS.$upper.md" ] || die "AGENTS.$upper.md 이 없다 — 선택지는 루트의 AGENTS.<NAME>.md 이름이다"
  echo "$upper" > "$GATE_STATE/current"
  # 레이어 파일을 못 만들어도(사용자 파일과 충돌 등) 사용자 확인은 유효하다 — 경고만 낸다
  if ! (cmd_on "$upper"); then
    echo "personal-layer: 경고 — 레이어 파일은 만들지 못했다. 이 세션은 AGENTS.$upper.md 를 직접 읽어 따른다" >&2
  fi
  echo "personal-layer: 이 세션 사용자 = $upper"
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
  use) shift; cmd_use "$@" ;;
  *) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac
