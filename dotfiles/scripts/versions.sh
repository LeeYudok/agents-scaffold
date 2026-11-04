#!/usr/bin/env bash
# 이 머신의 도구 버전과 사용 가능 여부를 표로 낸다 (#92).
#
#   scripts/versions.sh          터미널 표
#   scripts/versions.sh --md     마크다운 표(AGENTS.<NAME>.md 의 작업 환경 표에 붙여 넣는다)
#
# 대상은 install.sh 가 까는 셸 환경(zsh·starship·플러그인·CLI 도구·Nerd Font), 세 하네스 CLI,
# 이 저장소의 개발·시험 도구다. 설치하지 않고 조회만 한다. 상태는 셋 중 하나다:
#   사용 가능   명령이 있고 버전 조회가 됐다
#   설치됨      파일은 있으나 버전을 알 수 없다(폰트, 플러그인 폴백 등)
#   없음        찾지 못했다
set -uo pipefail

MD=0
[ "${1:-}" = "--md" ] && MD=1

if [ "$(uname -s)" = "Darwin" ]; then FONT_DIR="$HOME/Library/Fonts"; else FONT_DIR="$HOME/.local/share/fonts"; fi
PLUGIN_DIR="$HOME/.local/share/zsh/plugins"

rows=()
row() { rows+=("$1|$2|$3|$4"); }

# 버전 문자열에서 첫 번째 x.y[.z] 를 뽑는다
semver() { grep -oE '[0-9]+(\.[0-9]+)+' | head -1; }

cmd() { # 구분 도구 명령 [버전 조회 인자...]
  local group="$1" name="$2" bin="$3"; shift 3
  if ! command -v "$bin" >/dev/null 2>&1; then row "$group" "$name" "-" "없음"; return; fi
  local v; v="$("$bin" "$@" 2>&1 | semver)"
  if [ -n "$v" ]; then row "$group" "$name" "$v" "사용 가능"; else row "$group" "$name" "-" "설치됨"; fi
}

zsh_plugin() { # Homebrew 판을 먼저, 없으면 install.sh 의 sudo 없는 폴백 위치를 본다
  local name="$1" v=""
  if command -v brew >/dev/null 2>&1; then v="$(brew list --versions "$name" 2>/dev/null | semver)"; fi
  if [ -n "$v" ]; then row "셸" "$name" "$v" "사용 가능"
  elif [ -d "$PLUGIN_DIR/$name" ] || [ -d "/usr/share/$name" ] || [ -d "/usr/share/zsh/plugins/$name" ]; then
    row "셸" "$name" "-" "설치됨"
  else row "셸" "$name" "-" "없음"; fi
}

font() {
  if [ -f "$FONT_DIR/.nerd-font-$1-installed" ]; then row "폰트" "$1 Nerd Font" "-" "설치됨"
  else row "폰트" "$1 Nerd Font" "-" "없음"; fi
}

cmd "셸" zsh zsh --version
cmd "셸" starship starship --version
zsh_plugin zsh-autosuggestions
zsh_plugin zsh-syntax-highlighting
for t in eza bat zoxide fzf fd jq; do cmd "CLI 도구" "$t" "$t" --version; done
font JetBrainsMono
font D2Coding
cmd "하네스" "Claude Code" claude --version
cmd "하네스" "Codex CLI" codex --version
cmd "하네스" "agy (Antigravity)" agy --version
for t in python3 git curl unzip; do
  if [ "$t" = unzip ]; then cmd "필수 런타임" "$t" "$t" -v; else cmd "필수 런타임" "$t" "$t" --version; fi
done
[ "$(uname -s)" = "Darwin" ] && cmd "필수 런타임" brew brew --version
for t in node npm pnpm bun pyenv gh bats; do cmd "개발·시험" "$t" "$t" --version; done

if [ "$MD" -eq 1 ]; then
  echo "| 구분 | 도구 | 버전 | 상태 |"
  echo "|---|---|---|---|"
  for r in "${rows[@]}"; do IFS='|' read -r g n v s <<< "$r"; echo "| $g | $n | $v | $s |"; done
else
  for r in "${rows[@]}"; do IFS='|' read -r g n v s <<< "$r"; printf '%-12s %-26s %-12s %s\n' "$g" "$n" "$v" "$s"; done
fi
