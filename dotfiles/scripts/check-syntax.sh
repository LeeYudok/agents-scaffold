#!/usr/bin/env bash
# bash·zsh는 파일마다 문법을 검사하고, Python은 컴파일로 확인한다.
# bash -n에 여러 경로를 넘기면 첫 파일만 검사하므로 각각 실행한다.
set -euo pipefail
cd "$(dirname "$0")/.."

for file in *.sh scripts/*.sh claude/*.sh agy/*.sh gitbash/bashrc gitbash/bash_profile; do
  bash -n "$file"
done
for file in zsh/zshrc.*; do
  zsh -n "$file"
done
python3 -m py_compile codex/*.py agy/*.py
echo '문법 검사 통과'
