#!/usr/bin/env bash
# yolo 래퍼(yolo/wrapper.sh) 시험 — 가짜 CLI·가짜 cmux shim 만 쓰며 실제 claude·agy 는 실행하지 않는다 (#109).
#   - `--yolo` 치환, 공백 든 인자 보존, `--` 뒤 인자 보존
#   - 비대화형 bash·sh·zsh(있으면)에서 동작
#   - cmux shim 이 래퍼 앞·뒤 어디에 있어도 루프 없이 실제 파일에 도달
#   - 래퍼 사본 중복, PATH 밖에서 절대 경로로 실행, 실제 파일 없음(127)
# 사용법: scripts/test-yolo-wrapper.sh
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
bad() { echo "FAIL $*"; fail=1; }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
T="$(cd -P "$T" && pwd)"
SYS=/usr/bin:/bin
mkdir -p "$T/real" "$T/wrap" "$T/copy" "$T/cmux-cli-shims/S1"
for n in claude agy; do
  # 가짜 CLI: 받은 인자를 [ ] 로 감싸 한 줄씩 출력한다
  printf '#!/bin/sh\nfor a; do printf "[%%s]\\n" "$a"; done\n' > "$T/real/$n"
  cp yolo/wrapper.sh "$T/wrap/$n"
  cp yolo/wrapper.sh "$T/copy/$n"
done
# 가짜 cmux shim: cmux 래퍼처럼 shim 을 뺀 PATH 에서 처음 만난 같은 이름을 원래 PATH 그대로 실행한다. 다섯 번 넘게 들어오면 루프로 본다.
cat > "$T/cmux-cli-shims/S1/claude" <<'EOF'
#!/bin/sh
echo hop >> "$HOPS"
[ "$(wc -l < "$HOPS")" -le 5 ] || { echo loop >&2; exit 99; }
IFS=:
for d in $PATH; do
  case $d in */cmux-cli-shims|*/cmux-cli-shims/*) continue ;; esac
  [ -x "$d/claude" ] && exec "$d/claude" "$@"
done
exit 98
EOF
chmod +x "$T"/real/* "$T"/wrap/* "$T"/copy/* "$T/cmux-cli-shims/S1/claude"
export HOPS="$T/hops"

expect='[--dangerously-skip-permissions]
[-p]
[a b]
[--]
[--yolo]'
# check <설명> <PATH> <기대 hop 수> <명령...>
check() {
  local desc=$1 path=$2 hops=$3 out
  shift 3
  : > "$HOPS"
  out="$(PATH="$path" "$@" 2>&1)" || { bad "$desc: 종료 코드 $? — $out"; return; }
  [ "$out" = "$expect" ] || bad "$desc: 출력이 다름 — $out"
  [ "$(wc -l < "$HOPS" | tr -d ' ')" = "$hops" ] || bad "$desc: cmux shim 진입 $(wc -l < "$HOPS" | tr -d ' ')회 (기대 $hops)"
}
args=(--yolo -p 'a b' -- --yolo)

check "직접 실행" "$T/wrap:$T/real:$SYS" 0 "$T/wrap/claude" "${args[@]}"
check "bash -c" "$T/wrap:$T/real:$SYS" 0 bash -c 'claude "$@"' _ "${args[@]}"
check "sh -c (agy)" "$T/wrap:$T/real:$SYS" 0 sh -c 'agy "$@"' _ "${args[@]}"
if command -v zsh >/dev/null; then
  check "zsh -c" "$T/wrap:$T/real:$SYS" 0 "$(command -v zsh)" -fc 'claude "$@"' _ "${args[@]}"
else
  echo "skip zsh -c (zsh 없음)"
fi
check "cmux shim 이 앞" "$T/cmux-cli-shims/S1:$T/wrap:$T/real:$SYS" 1 bash -c 'claude "$@"' _ "${args[@]}"
check "cmux shim 이 뒤" "$T/wrap:$T/cmux-cli-shims/S1:$T/real:$SYS" 0 bash -c 'claude "$@"' _ "${args[@]}"
check "래퍼 사본 중복" "$T/wrap:$T/copy:$T/wrap:$T/real:$SYS" 0 bash -c 'claude "$@"' _ "${args[@]}"
check "실제 파일이 래퍼보다 앞" "$T/real:$T/wrap:$SYS" 0 "$T/wrap/claude" "${args[@]}"
check "PATH 밖에서 절대 경로" "$T/real:$SYS" 0 "$T/wrap/claude" "${args[@]}"

out="$(PATH="$T/wrap:$T/copy:$SYS" "$T/wrap/claude" --yolo 2>&1)"; rc=$?
[ "$rc" = 127 ] || bad "실제 파일 없음: 종료 코드 $rc (기대 127)"
case $out in *"실제 실행 파일을 PATH 에서 찾지 못함"*) ;; *) bad "실제 파일 없음: 안내 없음 — $out" ;; esac

# Git Bash 는 래퍼 대신 gitbash/bashrc 의 함수를 export -f 로 자식 bash 에 넘긴다
out="$(env -u GIT_CONFIG_COUNT HOME="$T" PATH="$T/real:$SYS" bash --norc -ic \
  '. gitbash/bashrc && bash -c '"'"'claude "$@"'"'"' _ "$@"' _ "${args[@]}" </dev/null 2>/dev/null)"
[ "$out" = "$expect" ] || bad "gitbash/bashrc: 자식 bash 에서 치환되지 않음 — $out"
out="$(env -u GIT_CONFIG_COUNT HOME="$T" PATH="$SYS" bash --norc -ic '. gitbash/bashrc && type -t agy' </dev/null 2>/dev/null)"
[ -z "$out" ] || bad "gitbash/bashrc: PATH 에 없는 agy 를 함수로 정의함"

# cmux 는 스크립트 앞부분에 같은 이름을 PATH 로 다시 찾는 구문이 있으면 재진입 shim 으로 분류한다 — 래퍼가 그 패턴을 피하는지 본다
grep -nE '(exec|command|env) +["'"'"']?claude|=claude|:-claude' yolo/wrapper.sh && bad "yolo/wrapper.sh: cmux 재진입 shim 패턴 포함"

[ "$fail" = 0 ] && echo "ok   yolo-wrapper"
exit "$fail"
