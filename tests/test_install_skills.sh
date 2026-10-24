#!/usr/bin/env bash
# scripts/install-skills.sh 동작 테스트 (doksam-skills tests/test_install.sh 이식, agents-scaffold #78).
# 임시 HOME 으로 격리하므로 실제 홈 디렉터리를 건드리지 않는다.
#
# 스킬명을 하드코딩하지 않는다. skills/ 를 훑어 프로브(probe) 스킬을 고르므로
# 스킬이 늘거나 이름이 바뀌어도 이 파일은 그대로 둔다.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL="$REPO_ROOT/scripts/install-skills.sh"
# 설치 원천(.skills-dist)은 install-skills.sh 가 만든다. 스킬·어댑터 경로는 그 안을 본다.
HOME="$(mktemp -d)" "$INSTALL" --list >/dev/null 2>&1 || true
DIST_ROOT="$REPO_ROOT/.skills-dist"

SKILLS=()
for d in "$DIST_ROOT"/skills/*/; do
  [[ -f "$d/SKILL.md" ]] && SKILLS+=("$(basename "$d")")
done
if [[ ${#SKILLS[@]} -eq 0 ]]; then
  echo "오류: skills/ 아래에 SKILL.md 를 가진 스킬이 없다" >&2
  exit 1
fi

# 스킬 설치 동작을 확인할 대표 스킬
SKILL="${SKILLS[0]}"
SRC="$DIST_ROOT/skills/$SKILL"

# agy CLI 스텁 — 실제 agy 를 호출하지 않고 인자만 기록한다 (이슈 #78).
# PATH 맨 앞에 두어 install.sh 의 `command -v agy` 와 호출을 가로챈다.
STUB_BIN="$(mktemp -d)"
AGY_LOG="$STUB_BIN/agy.log"
cat > "$STUB_BIN/agy" <<STUB
#!/usr/bin/env bash
echo "\$@" >> "$AGY_LOG"
exit 0
STUB
chmod +x "$STUB_BIN/agy"
export PATH="$STUB_BIN:$PATH"

# Agent Adapter 동작을 확인할 대표 스킬 (claude.md 를 가진 첫 스킬)
AGENT_SKILL=""
for s in "${SKILLS[@]}"; do
  if [[ -f "$DIST_ROOT/skills/$s/agents/claude.md" ]]; then
    AGENT_SKILL="$s"
    break
  fi
done
if [[ -z "$AGENT_SKILL" ]]; then
  echo "오류: agents/claude.md 를 가진 스킬이 없어 Agent 테스트를 할 수 없다" >&2
  exit 1
fi
CLAUDE_AGENT_SRC="$DIST_ROOT/skills/$AGENT_SKILL/agents/claude.md"
CODEX_AGENT_SRC="$DIST_ROOT/skills/$AGENT_SKILL/agents/codex.toml"
CLAUDE_AGENT_LINK=".claude/agents/$AGENT_SKILL.md"
CODEX_AGENT_LINK=".codex/agents/${AGENT_SKILL//-/_}.toml"

pass=0
fail=0

check() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "  ok   $label"
    pass=$((pass + 1))
  else
    echo "  FAIL $label — expected '$expected', got '$actual'"
    fail=$((fail + 1))
  fi
}

new_sandbox() {
  SANDBOX="$(mktemp -d)"
  export HOME="$SANDBOX"
}

drop_sandbox() {
  rm -rf "$SANDBOX"
}

# 오타나 사라진 헬퍼 호출을 초록불로 통과시키지 않는다. set -e 가 없고 종료
# 코드를 검사하지 않는 줄이 많아, 정의되지 않은 명령은 stderr 한 줄만 남기고
# 묻힌다 (실제로 reset_home 호출 두 곳이 그렇게 방치됐다 — 이슈 #108).
# bash 는 이 훅을 서브셸에서 실행하므로 변수 증가가 부모로 전파되지 않는다.
# 마커 파일에 남기고 마지막에 읽는다.
MISSING_CMD_LOG="$(mktemp)"
trap 'rm -f "$MISSING_CMD_LOG"' EXIT
command_not_found_handle() {
  echo "  FAIL 정의되지 않은 명령 호출: $1"
  echo "$1" >> "$MISSING_CMD_LOG"
  return 127
}

echo "test: --dry-run 은 파일시스템을 바꾸지 않는다"
new_sandbox
"$INSTALL" --dry-run >/dev/null 2>&1
check "exit code" "0" "$?"
check "심링크 미생성" "absent" "$([[ -e "$HOME/.claude/skills/$SKILL" ]] && echo present || echo absent)"
drop_sandbox

echo "test: 기본 설치는 전역 3경로에 모든 스킬 심링크를 만든다"
new_sandbox
"$INSTALL" >/dev/null 2>&1
check "exit code" "0" "$?"
for t in ".agents/skills" ".claude/skills" ".gemini/config/skills"; do
  for s in "${SKILLS[@]}"; do
    check "$t/$s 심링크" "$DIST_ROOT/skills/$s" "$(readlink "$HOME/$t/$s" 2>/dev/null)"
  done
done
drop_sandbox

echo "test: --skill-only 는 기본 설치와 같다"
new_sandbox
"$INSTALL" --skill-only >/dev/null 2>&1
check "exit code" "0" "$?"
check "Skill 설치" "$SRC" "$(readlink "$HOME/.agents/skills/$SKILL" 2>/dev/null)"
check "Claude Agent 미설치" "absent" "$([[ -e "$HOME/$CLAUDE_AGENT_LINK" ]] && echo present || echo absent)"
check "Codex Agent 미설치" "absent" "$([[ -e "$HOME/$CODEX_AGENT_LINK" ]] && echo present || echo absent)"
drop_sandbox

echo "test: --with-agent 는 Skill 과 Claude/Codex Agent 를 설치한다"
new_sandbox
out="$("$INSTALL" --with-agent 2>&1)"
check "exit code" "0" "$?"
check "Claude Agent" "$CLAUDE_AGENT_SRC" "$(readlink "$HOME/$CLAUDE_AGENT_LINK" 2>/dev/null)"
check "Codex Agent" "$CODEX_AGENT_SRC" "$(readlink "$HOME/$CODEX_AGENT_LINK" 2>/dev/null)"
check "Agent 원본은 스킬 소유" "present" "$([[ "$CLAUDE_AGENT_SRC" == "$DIST_ROOT/skills/"* ]] && echo present || echo absent)"
check "agy 스텁이 plugin install 을 받음" "present" "$(grep -q '^plugin install ' "$AGY_LOG" && echo present || echo absent)"
check "런타임별 요약에 Antigravity 등록" "present" "$(grep -q '^런타임별 에이전트: .*Antigravity=플러그인' <<<"$out" && echo present || echo absent)"
drop_sandbox

echo "test: --skill-only 와 --with-agent 를 함께 쓰면 실패한다"
new_sandbox
"$INSTALL" --skill-only --with-agent >/dev/null 2>&1
check "exit code" "1" "$?"
drop_sandbox

echo "test: 재실행은 멱등하다 (skip)"
new_sandbox
"$INSTALL" >/dev/null 2>&1
out="$("$INSTALL" 2>&1)"
check "exit code" "0" "$?"
check "스킬 수 × 3경로 만큼 skip" "$((${#SKILLS[@]} * 3))" "$(grep -c '^skip' <<<"$out")"
drop_sandbox

echo "test: 남의 디렉터리가 있으면 덮어쓰지 않고 실패한다"
new_sandbox
mkdir -p "$HOME/.claude/skills/$SKILL"
touch "$HOME/.claude/skills/$SKILL/SKILL.md"
"$INSTALL" >/dev/null 2>&1
check "exit code" "1" "$?"
check "기존 파일 보존" "present" "$([[ -f "$HOME/.claude/skills/$SKILL/SKILL.md" ]] && echo present || echo absent)"
drop_sandbox

echo "test: 남의 심링크가 있으면 덮어쓰지 않고 실패한다"
new_sandbox
decoy="$SANDBOX/decoy"
mkdir -p "$decoy"
mkdir -p "$HOME/.claude/skills"
ln -s "$decoy" "$HOME/.claude/skills/$SKILL"
"$INSTALL" >/dev/null 2>&1
check "exit code" "1" "$?"
check "기존 심링크 보존" "$decoy" "$(readlink "$HOME/.claude/skills/$SKILL" 2>/dev/null)"
drop_sandbox

echo "test: --force 는 충돌 항목을 교체한다"
new_sandbox
mkdir -p "$HOME/.claude/skills/$SKILL"
"$INSTALL" --force >/dev/null 2>&1
check "exit code" "0" "$?"
check "심링크로 교체" "$SRC" "$(readlink "$HOME/.claude/skills/$SKILL" 2>/dev/null)"
drop_sandbox

echo "test: --copy 는 심링크 대신 복사한다"
new_sandbox
"$INSTALL" --copy >/dev/null 2>&1
check "exit code" "0" "$?"
target="$HOME/.claude/skills/$SKILL"
check "심링크 아님" "notlink" "$([[ -L "$target" ]] && echo link || echo notlink)"
check "SKILL.md 복사됨" "present" "$([[ -f "$target/SKILL.md" ]] && echo present || echo absent)"
check "하위 디렉터리까지 복사됨" "present" \
  "$([[ -f "$HOME/.claude/skills/$AGENT_SKILL/agents/claude.md" ]] && echo present || echo absent)"
drop_sandbox

echo "test: --project 는 프로젝트 스킬 경로에 설치한다"
new_sandbox
proj="$SANDBOX/myrepo"
mkdir -p "$proj"
"$INSTALL" --project "$proj" >/dev/null 2>&1
check "exit code" "0" "$?"
check ".claude/skills" "$SRC" "$(readlink "$proj/.claude/skills/$SKILL" 2>/dev/null)"
check ".agents/skills" "$SRC" "$(readlink "$proj/.agents/skills/$SKILL" 2>/dev/null)"
check "전역 미설치" "absent" "$([[ -e "$HOME/.claude/skills/$SKILL" ]] && echo present || echo absent)"
drop_sandbox

echo "test: --project --with-agent 는 프로젝트 Agent 경로에도 설치한다"
new_sandbox
proj="$SANDBOX/myrepo"
mkdir -p "$proj"
"$INSTALL" --project "$proj" --with-agent >/dev/null 2>&1
check "exit code" "0" "$?"
check "프로젝트 Claude Agent" "$CLAUDE_AGENT_SRC" "$(readlink "$proj/$CLAUDE_AGENT_LINK" 2>/dev/null)"
check "프로젝트 Codex Agent" "$CODEX_AGENT_SRC" "$(readlink "$proj/$CODEX_AGENT_LINK" 2>/dev/null)"
drop_sandbox

echo "test: --project 대상이 디렉터리가 아니면 실패한다"
new_sandbox
"$INSTALL" --project "$SANDBOX/nope" >/dev/null 2>&1
check "exit code" "1" "$?"
drop_sandbox

echo "test: --uninstall 은 우리 심링크만 제거한다"
new_sandbox
"$INSTALL" >/dev/null 2>&1
"$INSTALL" --uninstall >/dev/null 2>&1
check "exit code" "0" "$?"
for t in ".agents/skills" ".claude/skills" ".gemini/config/skills"; do
  for s in "${SKILLS[@]}"; do
    check "$t/$s 제거" "absent" "$([[ -e "$HOME/$t/$s" ]] && echo present || echo absent)"
  done
done
drop_sandbox

echo "test: --uninstall --with-agent 는 Agent 심링크도 제거한다"
new_sandbox
"$INSTALL" --with-agent >/dev/null 2>&1
: > "$AGY_LOG"
"$INSTALL" --uninstall --with-agent >/dev/null 2>&1
check "agy 스텁이 plugin uninstall 을 받음" "present" "$(grep -q '^plugin uninstall ' "$AGY_LOG" && echo present || echo absent)"
check "exit code" "0" "$?"
check "Claude Agent 제거" "absent" "$([[ -e "$HOME/$CLAUDE_AGENT_LINK" ]] && echo present || echo absent)"
check "Codex Agent 제거" "absent" "$([[ -e "$HOME/$CODEX_AGENT_LINK" ]] && echo present || echo absent)"
drop_sandbox

echo "test: --uninstall 은 실제 디렉터리를 삭제하지 않는다"
new_sandbox
"$INSTALL" --copy >/dev/null 2>&1
"$INSTALL" --uninstall >/dev/null 2>&1
check "복사본 보존" "present" "$([[ -f "$HOME/.claude/skills/$SKILL/SKILL.md" ]] && echo present || echo absent)"
drop_sandbox

echo "test: --vendor 는 사본을 파일 단위로 갱신하고 orphan 은 지우지 않는다"
new_sandbox
vproj="$(mktemp -d)"
git -C "$vproj" init -q
mkdir -p "$vproj/.agents/skills/$SKILL"
cp -RL "$SRC/." "$vproj/.agents/skills/$SKILL/"
echo "낡은 내용" > "$vproj/.agents/skills/$SKILL/SKILL.md"          # 뒤처진 파일
echo "로컬 전용" > "$vproj/.agents/skills/$SKILL/local-note.md"      # orphan
mkdir -p "$DIST_ROOT/skills/$SKILL/__pycache__"
echo x > "$DIST_ROOT/skills/$SKILL/__pycache__/t.pyc"                # 제외 대상
"$INSTALL" --vendor "$vproj" --check >/dev/null 2>&1
check "--check 는 뒤처지면 exit 1" "1" "$?"
out="$("$INSTALL" --vendor "$vproj" --dry-run 2>&1)"
check "dry-run 이 update 를 예고" "present" "$(grep -q "^update    $SKILL/SKILL.md" <<<"$out" && echo present || echo absent)"
check "dry-run 후에도 사본은 그대로" "낡은 내용" "$(cat "$vproj/.agents/skills/$SKILL/SKILL.md")"
out="$("$INSTALL" --vendor "$vproj" 2>&1)"
check "vendor 갱신 exit 0" "0" "$?"
check "사본이 원본과 동일해짐" "same" "$(cmp -s "$SRC/SKILL.md" "$vproj/.agents/skills/$SKILL/SKILL.md" && echo same || echo diff)"
check "orphan 보존" "로컬 전용" "$(cat "$vproj/.agents/skills/$SKILL/local-note.md")"
check "orphan 보고" "present" "$(grep -q "^orphan    $SKILL/local-note.md" <<<"$out" && echo present || echo absent)"
check "__pycache__ 미복사" "absent" "$([[ -e "$vproj/.agents/skills/$SKILL/__pycache__" ]] && echo present || echo absent)"
check "git status 요약 출력" "present" "$(grep -q '^-- git status' <<<"$out" && echo present || echo absent)"
"$INSTALL" --vendor "$vproj" --check >/dev/null 2>&1
check "--check 는 최신이면 exit 0" "0" "$?"
rm -rf "$DIST_ROOT/skills/$SKILL/__pycache__" "$vproj"
drop_sandbox

echo "test: --vendor 는 설치 플래그와 배타적이다"
new_sandbox
vproj2="$(mktemp -d)"; mkdir -p "$vproj2/.agents/skills/$SKILL"
"$INSTALL" --vendor "$vproj2" --with-agent >/dev/null 2>&1
check "--vendor --with-agent 거부" "1" "$?"
rm -rf "$vproj2"
drop_sandbox

echo "test: --uninstall 은 남의 심링크를 건드리지 않는다"
new_sandbox
decoy="$SANDBOX/decoy"
mkdir -p "$decoy"
mkdir -p "$HOME/.claude/skills"
ln -s "$decoy" "$HOME/.claude/skills/$SKILL"
"$INSTALL" --uninstall >/dev/null 2>&1
check "exit code" "0" "$?"
check "남의 심링크 보존" "$decoy" "$(readlink "$HOME/.claude/skills/$SKILL" 2>/dev/null)"
drop_sandbox

# ---- --verify (이슈 #129) ----
# 런타임 CLI 스텁을 갈아 끼워 "파일은 있는데 런타임은 모른다" 를 재현한다.
# 그것이 이슈 #110 의 실패 모양이고, --verify 가 존재하는 이유다.
VERIFY_BIN="$(mktemp -d)"
AGY_AGENTS_OUT="$VERIFY_BIN/agy_agents.txt"
CODEX_PROMPT_OUT="$VERIFY_BIN/codex_prompt.txt"
cat > "$VERIFY_BIN/agy" <<STUB
#!/usr/bin/env bash
[[ "\$1" == "agents" ]] && cat "$AGY_AGENTS_OUT"
exit 0
STUB
cat > "$VERIFY_BIN/codex" <<STUB
#!/usr/bin/env bash
cat "$CODEX_PROMPT_OUT"
exit 0
STUB
chmod +x "$VERIFY_BIN/agy" "$VERIFY_BIN/codex"

# 전부 등록된 상태의 스텁 출력
: > "$AGY_AGENTS_OUT"
: > "$CODEX_PROMPT_OUT"
for s in "${SKILLS[@]}"; do
  echo "$s" >> "$AGY_AGENTS_OUT"
  echo "- $s: 설명 (file: /somewhere/$s/SKILL.md)" >> "$CODEX_PROMPT_OUT"
done

ORIG_PATH="$PATH"
export PATH="$VERIFY_BIN:$PATH"

echo "test: --verify 는 전부 등록됐으면 exit 0"
new_sandbox
"$INSTALL" --with-agent >/dev/null 2>&1
out="$("$INSTALL" --verify --with-agent 2>&1)"
check "exit code" "0" "$?"
check "미등록 없음" "absent" "$(grep -q '^missing ' <<<"$out" && echo present || echo absent)"
check "codex 는 CLI 출력으로 판정" "present" "$(grep -q 'codex debug prompt-input$' <<<"$out" && echo present || echo absent)"
check "agy 에이전트는 CLI 출력으로 판정" "present" "$(grep -q "^ok .*agy .*agent $AGENT_SKILL .*agy agents" <<<"$out" && echo present || echo absent)"
drop_sandbox

echo "test: --verify 는 설치하지 않는다"
new_sandbox
"$INSTALL" --verify >/dev/null 2>&1
check "심링크 미생성" "absent" "$([[ -e "$HOME/.claude/skills/$SKILL" ]] && echo present || echo absent)"
drop_sandbox

echo "test: --verify 는 Agent 심링크 누락을 잡는다"
new_sandbox
"$INSTALL" --with-agent >/dev/null 2>&1
rm "$HOME/$CLAUDE_AGENT_LINK"
out="$("$INSTALL" --verify --with-agent 2>&1)"
check "exit code" "1" "$?"
check "누락 지목" "present" "$(grep -q "^missing .*claude .*agent $AGENT_SKILL" <<<"$out" && echo present || echo absent)"
drop_sandbox

echo "test: --verify 는 파일이 있어도 런타임이 모르면 미등록으로 잡는다 (이슈 #110)"
new_sandbox
"$INSTALL" --with-agent >/dev/null 2>&1
grep -v "^$AGENT_SKILL\$" "$AGY_AGENTS_OUT" > "$AGY_AGENTS_OUT.tmp" && mv "$AGY_AGENTS_OUT.tmp" "$AGY_AGENTS_OUT"
out="$("$INSTALL" --verify --with-agent 2>&1)"
check "exit code" "1" "$?"
check "agy 미등록 지목" "present" "$(grep -q "^missing .*agy .*agent $AGENT_SKILL" <<<"$out" && echo present || echo absent)"
check "파일은 그대로 있다" "present" "$([[ -e "$HOME/.claude/agents/$AGENT_SKILL.md" ]] && echo present || echo absent)"
echo "$AGENT_SKILL" >> "$AGY_AGENTS_OUT"
drop_sandbox

echo "test: --verify 는 런타임 CLI 가 없으면 경로로 대신 보고 skip 을 알린다"
new_sandbox
"$INSTALL" >/dev/null 2>&1
# PATH 을 시스템 기본으로 좁혀 런타임 CLI 를 없앤다. bash 가 사는 디렉터리를
# 넣으면 안 된다 — Homebrew bash 옆에 codex 가 같이 살아 CLI 가 되살아난다.
out="$(PATH="/usr/bin:/bin" "$INSTALL" --verify 2>&1)"
check "exit code" "0" "$?"
check "codex skip 보고" "present" "$(grep -q '^skip .*codex' <<<"$out" && echo present || echo absent)"
check "경로로 판정" "present" "$(grep -q "^ok .*codex .*skill $SKILL .*경로:" <<<"$out" && echo present || echo absent)"
drop_sandbox

echo "test: --verify 는 대상이 사라진 심링크를 ok 로 치지 않는다 (#170)"
new_sandbox
"$INSTALL" >/dev/null 2>&1
ln -sfn "/nonexistent/$(basename "$DIST_ROOT")/skills/$SKILL" "$HOME/.claude/skills/$SKILL"
out="$("$INSTALL" --verify 2>&1)"
check "exit code" "1" "$?"
check "끊긴 링크 지목" "present" "$(grep -q "^broken .*claude .*skill $SKILL " <<<"$out" && echo present || echo absent)"
drop_sandbox

echo "test: --verify 는 이름이 바뀐 스킬의 끊긴 링크도 잡는다 (#170)"
new_sandbox
"$INSTALL" >/dev/null 2>&1
ln -s "/old/place/$(basename "$DIST_ROOT")/skills/renamed-away" "$HOME/.claude/skills/renamed-away"
ln -s "/old/place/other-repo/skills/foreign" "$HOME/.claude/skills/foreign"
out="$("$INSTALL" --verify 2>&1)"
check "exit code" "1" "$?"
check "stale 지목" "present" "$(grep -q "^broken .*stale renamed-away" <<<"$out" && echo present || echo absent)"
check "남의 레포 링크는 건드리지 않음" "absent" "$(grep -q "foreign" <<<"$out" && echo present || echo absent)"
drop_sandbox

echo "test: --list 는 설치하지 않고 스킬·에이전트·설치 상태를 표로 보인다 (#177)"
new_sandbox
"$INSTALL" --with-agent >/dev/null 2>&1
rm "$HOME/.claude/skills/$SKILL"
out="$("$INSTALL" --list 2>&1)"
check "exit code" "0" "$?"
check "에이전트 있는 스킬 표시" "present" "$(grep -qE "^$AGENT_SKILL +yes +\\| +ok" <<<"$out" && echo present || echo absent)"
check "빠진 설치는 - 로" "present" "$(grep -qE "^$SKILL +[a-z]+ +\\| +- " <<<"$out" && echo present || echo absent)"
check "설치하지 않는다" "absent" "$([[ -e "$HOME/.claude/skills/$SKILL" ]] && echo present || echo absent)"
drop_sandbox

echo "test: --verify 는 --vendor 와 배타적이다"
new_sandbox
vproj3="$(mktemp -d)"; mkdir -p "$vproj3/.agents/skills/$SKILL"
"$INSTALL" --vendor "$vproj3" --verify >/dev/null 2>&1
check "--vendor --verify 거부" "1" "$?"
rm -rf "$vproj3"
drop_sandbox

export PATH="$ORIG_PATH"
rm -rf "$VERIFY_BIN"

missing=$(wc -l < "$MISSING_CMD_LOG" | tr -d ' ')
fail=$((fail + missing))

echo
echo "pass=$pass fail=$fail"
[[ $fail -eq 0 ]]
