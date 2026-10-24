#!/usr/bin/env bash
# Windows 폐쇄망 Git 설치 스크립트(windows/)와 Git Bash 설정(gitbash/)의 정적 시험 — Windows 없이 어느 OS 에서나 돈다.
#   - .ps1 은 UTF-8 BOM (Windows PowerShell 5.1 이 한글을 cp949 로 읽지 않게), .cmd 는 ASCII (cmd.exe 는 OEM 코드 페이지로 읽는다)
#   - .ps1/.cmd 는 CRLF, gitbash/ 는 LF (CRLF 면 bash 가 읽지 못한다)
#   - gitbash/ 문법, 대화형 bash 에서 source 가능, pwsh 가 있으면 .ps1 구문 분석
# 사용법: scripts/test-windows-git.sh
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
bad() { echo "FAIL $*"; fail=1; }

for f in windows/*.ps1; do
  [ "$(head -c3 "$f" | od -An -tx1 | tr -d ' ')" = "efbbbf" ] || bad "$f: UTF-8 BOM 없음"
done
for f in windows/*.cmd; do
  LC_ALL=C grep -q '[^[:print:][:space:]]' "$f" && bad "$f: ASCII 외 문자"
done
for f in windows/*.ps1 windows/*.cmd; do
  [ "$(grep -c $'\r$' "$f")" = "$(wc -l < "$f")" ] || bad "$f: CRLF 가 아닌 줄이 있음"
done
for f in gitbash/*; do
  grep -q $'\r' "$f" && bad "$f: CR 포함 (LF 여야 함)"
  bash -n "$f" || bad "$f: 문법 오류"
done
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
env -u GIT_CONFIG_COUNT HOME="$T" bash --norc -ic '. gitbash/bashrc && alias gs >/dev/null && [ "$GIT_CONFIG_KEY_0" = core.quotepath ]' </dev/null >/dev/null 2>&1 \
  || bad "gitbash/bashrc: 대화형 bash 에서 source 실패"
[ -z "$(HOME="$T" bash --norc -c '. gitbash/bashrc; alias')" ] || bad "gitbash/bashrc: 비대화형 셸에서 alias 를 정의함"
if command -v pwsh >/dev/null; then
  for f in windows/*.ps1; do
    PS1_FILE="$f" pwsh -NoProfile -c '$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $env:PS1_FILE),[ref]$null,[ref]$e); $e | % { $_.ToString() }; exit $e.Count' \
      || bad "$f: PowerShell 구문 오류"
  done
else
  echo "skip pwsh 구문 분석 (pwsh 없음)"
fi
[ "$fail" = 0 ] && echo "ok   windows-git"
exit "$fail"
