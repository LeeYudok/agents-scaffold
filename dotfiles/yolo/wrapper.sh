#!/bin/sh
# yolo 래퍼 — Claude Code·Antigravity CLI(agy)를 대신 실행하며 `--yolo` 인자만 `--dangerously-skip-permissions` 로 바꾼다 (#109).
# install.sh 가 이 파일을 ~/.local/share/dotfiles/bin/<명령 이름> 으로 복사하고, zshrc 가 그 디렉터리를 PATH 맨 앞에 둔다.
# 셸 함수가 아니라 실행 파일이므로 셸 종류·대화형 여부와 무관하게 동작한다(zsh -c, bash, 스크립트, 터미널 앱 실행 템플릿).
#
# 실제 실행 파일 찾기 — 대상 명령 이름은 이 파일의 이름이다.
#   1. PATH 에서 이 파일이 있는 디렉터리 "뒤"의 항목만 본다. 앞쪽 항목은 이 래퍼로 다시 들어오는 shim 일 수 있다.
#   2. 이 래퍼와 내용이 같은 사본은 건너뛴다(같은 디렉터리가 PATH 에 두 번 있거나 다른 경로로 복사·링크된 경우).
#   3. cmux 의 shim 디렉터리는 건너뛴다. cmux 래퍼는 PATH 에서 처음 만난 shim 이 아닌 파일을 실제 바이너리로 보고 실행하므로,
#      여기서 cmux shim 으로 넘기면 cmux → 이 래퍼 → cmux 로 끝없이 돈다.
#   4. 1 에서 못 찾으면(이 디렉터리가 PATH 에 없거나 실제 실행 파일이 앞쪽에 있으면) PATH 전체를 2·3 규칙으로 본다.
# `--` 뒤의 인자는 프롬프트 같은 위치 인자라 바꾸지 않는다.
#
# 주의: cmux 는 PATH 의 스크립트 앞부분에서 같은 이름을 다시 PATH 로 찾는 구문을 보면 재진입 shim 으로 분류한다.
# 이 파일에는 대상 명령 이름을 소문자 그대로 적지 않는다.
set -f   # PATH 를 : 로 나눌 때 와일드카드가 확장되지 않게 한다

name=${0##*/}
self_dir=$(cd -P -- "$(dirname -- "$0")" && pwd) || exit 127

is_cmux_shim_dir() {
  case $1 in
    */cmux-cli-shims | */cmux-cli-shims/* | */cmux*.app/Contents/Resources/bin) return 0 ;;
  esac
  return 1
}

# find_real <1|0> — 1 이면 이 디렉터리 뒤만, 0 이면 PATH 전체를 본다. 찾으면 경로를 출력한다.
find_real() {
  only_after_self=$1
  seen_self=0
  old_ifs=$IFS
  IFS=:
  for dir in $PATH; do
    IFS=$old_ifs
    [ -n "$dir" ] || continue   # 빈 항목(현재 디렉터리)은 보지 않는다
    if [ "$seen_self" = 0 ] && { [ "$dir" = "$self_dir" ] || [ "$(cd -P -- "$dir" 2>/dev/null && pwd)" = "$self_dir" ]; }; then
      seen_self=1
      continue
    fi
    [ "$only_after_self" = 1 ] && [ "$seen_self" = 0 ] && continue
    is_cmux_shim_dir "$dir" && continue
    cand=$dir/$name
    [ -f "$cand" ] && [ -x "$cand" ] || continue
    cmp -s -- "$cand" "$0" && continue
    printf '%s\n' "$cand"
    return 0
  done
  IFS=$old_ifs
  return 1
}

# 인자를 제자리에서 한 바퀴 돌려 바꾼다 — 공백·따옴표가 든 인자도 그대로 보존된다
n=$#
passthru=0
while [ "$n" -gt 0 ]; do
  arg=$1
  shift
  n=$((n - 1))
  if [ "$passthru" = 0 ]; then
    case $arg in
      --) passthru=1 ;;
      --yolo) arg=--dangerously-skip-permissions ;;
    esac
  fi
  set -- "$@" "$arg"
done

real=$(find_real 1) || real=$(find_real 0) || {
  printf '%s: 실제 실행 파일을 PATH 에서 찾지 못함 (dotfiles yolo 래퍼 %s)\n' "$name" "$0" >&2
  exit 127
}
exec "$real" "$@"
