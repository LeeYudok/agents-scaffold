#!/usr/bin/env bash
# Windows 경로 시험 — (1) Git Bash 등에서는 0 단계에서 중단하고 홈에 아무것도 만들지 않는다 (어느 OS 에서나 시험 가능)
#                     (2) WSL 로 감지되면 Nerd Font 단계를 건너뛴다 (Linux 에서만 시험. 패키지가 없으면 install.sh 가 설치한다)
# 실제 홈은 건드리지 않는다. 사용법: scripts/test-windows-paths.sh
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
T="$(mktemp -d)"

# (1) uname 을 흉내 내 MINGW 로 보이게 한다
mkdir -p "$T/bin" "$T/mingw"
printf '#!/bin/sh\necho MINGW64_NT-10.0-26100\n' > "$T/bin/uname"; chmod +x "$T/bin/uname"
out="$(HOME="$T/mingw" PATH="$T/bin:$PATH" ./install.sh 2>&1)" && { echo "FAIL mingw: install.sh 가 통과함"; fail=1; }
printf '%s\n' "$out" | grep -q 'WSL2' || { echo "FAIL mingw: WSL2 안내 없음"; fail=1; }
[ -z "$(find "$T/mingw" -mindepth 1)" ] || { echo "FAIL mingw: 홈에 파일이 생김"; find "$T/mingw" -mindepth 1; fail=1; }
echo "ok   mingw (거부)"

# (2) WSL 흉내 — /proc/version 대신 읽을 파일을 바꾼다
if [ "$(uname -s)" = "Linux" ]; then
  mkdir -p "$T/wsl"
  echo 'Linux version 6.6.0-microsoft-standard-WSL2 (test)' > "$T/proc-version"
  run() { HOME="$T/wsl" DOTFILES_PROC_VERSION="$T/proc-version" "$@"; }
  out="$(run ./install.sh 2>&1)" || { echo "FAIL wsl: install.sh 실패"; printf '%s\n' "$out" | tail -5; fail=1; }
  printf '%s\n' "$out" | grep -q 'WSL 감지' || { echo "FAIL wsl: 폰트 건너뜀 안내 없음"; fail=1; }
  [ ! -e "$T/wsl/.local/share/fonts" ] || { echo "FAIL wsl: 폰트 디렉터리가 생김"; fail=1; }
  [ -f "$T/wsl/.zshrc" ] || { echo "FAIL wsl: .zshrc 미배치"; fail=1; }
  run ./install.sh >/dev/null 2>&1 || { echo "FAIL wsl: 두 번째 install.sh 실패"; fail=1; }
  [ -z "$(find "$T/wsl" -name '*.bak')" ] || { echo "FAIL wsl: 두 번째 실행에서 .bak 이 생김 (멱등 아님)"; fail=1; }
  # 일반 uninstall 은 설치한 바이너리(~/.local/bin)를 남긴다 — manifest 를 남겨 두고 --purge 로 이어서 지운다
  run ./uninstall.sh --keep-backup >/dev/null 2>&1 || { echo "FAIL wsl: uninstall.sh 실패"; fail=1; }
  left="$(find "$T/wsl" -type f -not -path "$T/wsl/.config/dotfiles/backup/*" -not -path "$T/wsl/.local/bin/*")"
  [ -z "$left" ] || { echo "FAIL wsl: uninstall 후 남은 파일"; printf '%s\n' "$left"; fail=1; }
  run ./uninstall.sh --purge >/dev/null 2>&1 || { echo "FAIL wsl: uninstall.sh --purge 실패"; fail=1; }
  left="$(find "$T/wsl" -type f)"
  [ -z "$left" ] || { echo "FAIL wsl: uninstall --purge 후 남은 파일"; printf '%s\n' "$left"; fail=1; }
  echo "ok   wsl"
else
  echo "skip wsl (Linux 에서만 시험 — 컨테이너에서 실행)"
fi

rm -rf "$T"
[ "$fail" = 0 ] && echo "전체 통과" || { echo "실패 있음"; exit 1; }
