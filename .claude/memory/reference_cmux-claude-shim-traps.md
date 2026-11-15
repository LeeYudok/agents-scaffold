---
name: reference_cmux-claude-shim-traps
description: cmux 안에서 claude 앞에 래퍼를 끼울 때의 함정 — cmux 가 실제 바이너리를 고르는 규칙, 재진입 shim 판정, 무한 루프, 플래그 수용 실측법
metadata:
  type: reference
---

실측 2026-11-12, macOS, cmux(앱 번들 `Contents/Resources/bin/cmux-claude-wrapper`)·Claude Code 2.1.322. #109 에서 확인했다.

- cmux 는 셸 프롬프트마다 precmd 훅 `_cmux_fix_path` 로 per-surface shim 디렉터리(`~/.cmuxterm/cmux-cli-shims/<surface>`)를 PATH 맨 앞에 다시 넣는다. zshrc 가 PATH 앞에 무엇을 넣어도 대화형 cmux 셸에서는 cmux shim 이 첫 번째다. 중첩 셸(`zsh -i` 를 다시 띄움)에서는 순서가 뒤집힐 수 있다.
- cmux 래퍼의 `find_real_claude` 는 PATH 에서 처음 만난 shim 이 아닌 `claude` 를 실제 바이너리로 보고 exec 한다. 자기 래퍼(사용자 래퍼 포함)가 거기서 다시 PATH 로 `claude` 를 찾아 cmux shim 에 닿으면 cmux → 래퍼 → cmux 로 끝없이 돈다. 래퍼는 cmux shim 디렉터리를 건너뛰어야 한다.
- cmux 는 스크립트 앞 160줄에 `exec claude`·`command claude`·`env claude`·`=claude`·`:-claude}` 같은 문자열이 있으면 재진입 shim 으로 분류해 다르게 다룬다. 래퍼 본문에 대상 명령 이름을 소문자로 적지 않는다. `CMUX_CUSTOM_CLAUDE_PATH`(앱 설정 Claude Binary Path)를 지정하면 PATH 탐색 대신 그 경로를 쓴다.
- 플래그가 먹히는지 실측할 때 `claude <플래그> --version` 은 쓸 수 없다. `--version` 이 먼저 처리돼 모르는 옵션도 통과한다. `claude <플래그> -p '' </dev/null` 을 쓴다. 모르는 옵션이면 `error: unknown option`, 받아들이면 API 호출 전에 `Input must be provided ...` 가 나온다.
- 대화형 zsh 함수로 만든 래퍼는 `zsh -c`·bash·스크립트에서 정의되지 않는다. 비대화형까지 덮으려면 PATH 의 실행 파일이어야 한다(`dotfiles/yolo/wrapper.sh`).

관련: [[reference_harness-config-contracts]]
