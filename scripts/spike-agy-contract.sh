#!/usr/bin/env bash
# Antigravity(agy) 계약 실측 spike (#60, a-3)
#
# agy CLI 의 저장소 계약을 실제로 측정한다. 문서 인용이 아니라 실행 결과가 근거다.
# 결과는 stdout 에 JSON 으로 출력한다 — docs/harness-matrix.json 의 입력.
#
#   scripts/spike-agy-contract.sh [--dynamic]
#
# --dynamic 을 주면 agy -p(headless)로 실제 모델 호출까지 수행한다(쿼터 소모).
# 생략하면 정적 검사만 하고 동적 항목은 unverified 로 남긴다.
#
# 판정 규칙: 응답 전에 툴 호출 단계가 하나라도 있으면 파일을 직접 읽었을 수 있으므로
# 그 질의는 inconclusive 다 — 컨텍스트에 자동 로드된 지침만으로 답했을 때만 판정한다.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DYNAMIC=0
[ "${1:-}" = "--dynamic" ] && DYNAMIC=1
AGY_BIN="${AGY_BIN:-agy}"
AGY_TIMEOUT="${AGY_TIMEOUT:-300}"

AGY_VERSION="$("$AGY_BIN" --version 2>/dev/null | tr -d '\n' || true)"
[ -n "$AGY_VERSION" ] || AGY_VERSION="not-installed"
TODAY="$(date +%Y-%m-%d)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git -C "$WORK" init -q
git -C "$WORK" config user.email spike@local
git -C "$WORK" config user.name spike
bash "$REPO_ROOT/bin/agents-scaffold.sh" "$WORK" --forge github --stack python \
  --harness agy --name spike-app --yes >/dev/null 2>&1

# ---- 정적 측정 -------------------------------------------------------------
agents_bytes=$(wc -c < "$WORK/AGENTS.md" | tr -d ' ')
has_agents_skills=$([ -d "$WORK/.agents/skills" ] && echo true || echo false)
has_gemini_dir=$([ -e "$WORK/.gemini" ] && echo true || echo false)
has_git_hook=$([ -x "$WORK/.git/hooks/pre-commit" ] && echo true || echo false)

( cd "$WORK" && echo 'K=v' > .env && git add -f .env >/dev/null 2>&1 )
gate_exit=0
( cd "$WORK" && bash .git/hooks/pre-commit >/dev/null 2>&1 ) || gate_exit=$?
( cd "$WORK" && git reset -q HEAD .env >/dev/null 2>&1; rm -f .env )

# agy -p 를 stream-json 으로 돌려 최종 응답만 파일에 남긴다.
# 응답 전 툴 호출 단계가 있으면 응답 대신 TOOL_USED 를 남긴다.
ask_agy() {
  local dir="$1" prompt="$2" out="$3"
  ( cd "$dir" && timeout "$AGY_TIMEOUT" "$AGY_BIN" -p "$prompt" \
      --output-format stream-json --print-timeout "$((AGY_TIMEOUT - 10))s" ) 2>/dev/null \
    | python3 -c '
import json, sys
tool_steps, response = 0, ""
for line in sys.stdin:
    try:
        o = json.loads(line)
    except ValueError:
        continue
    st = (o.get("step_update") or {}).get("step_type")
    if st and st not in ("user_input", "agent_response"):
        tool_steps += 1
    if o.get("event") == "result":
        response = (o.get("result") or {}).get("response") or ""
print("TOOL_USED" if tool_steps else response, end="")
' > "$out"
}

# ---- 동적 측정 -------------------------------------------------------------
p0_answer="unverified"; p0_note="--dynamic 미지정"
skill_answer="unverified"; skill_note="--dynamic 미지정"
if [ "$DYNAMIC" -eq 1 ] && [ "$AGY_VERSION" != "not-installed" ]; then
  out="$WORK/_p0.txt"
  ask_agy "$WORK" "Do not use any tools or read any files. From the project instructions already in your context only, list this repository's P0 rules verbatim. If none are in your context, reply exactly NONE." "$out"
  if [ ! -s "$out" ]; then
    p0_answer="inconclusive"; p0_note="agy 응답 없음(타임아웃 또는 빈 출력) — 미측정으로 취급"
  elif grep -q 'TOOL_USED' "$out"; then
    p0_answer="inconclusive"; p0_note="응답 전 툴 호출 — 자동 로드 여부 판정 불가"
  elif grep -qi 'p0' "$out" || grep -qi 'force push' "$out"; then
    if grep -qi 'mypy\|ruff' "$out"; then
      p0_answer="pass"; p0_note="AGENTS.md 자동 로드 + 인라인된 python 스택 P0 까지 응답(툴 미사용)"
    else
      p0_answer="partial"; p0_note="공통 P0 는 응답했으나 인라인된 스택 P0 는 응답에 없음"
    fi
  else
    p0_answer="fail"; p0_note="응답은 왔으나 P0 를 답하지 못함"
  fi

  # 스킬 발견은 통제 실험으로 잰다 — 레포에만 있는 유니크 이름 2개를 서로 다른 경로에 심는다.
  mkdir -p "$WORK/.claude/skills/zqx-claudepath" "$WORK/.agents/skills/zqx-agentspath"
  printf -- '---\nname: zqx-claudepath\ndescription: probe skill under .claude/skills\n---\n\nprobe A\n' \
    > "$WORK/.claude/skills/zqx-claudepath/SKILL.md"
  printf -- '---\nname: zqx-agentspath\ndescription: probe skill under .agents/skills\n---\n\nprobe B\n' \
    > "$WORK/.agents/skills/zqx-agentspath/SKILL.md"
  out2="$WORK/_skill.txt"
  ask_agy "$WORK" "Do not use any tools or read any files. List only the skills registered to you whose name starts with 'zqx-'. If none, reply exactly NONE." "$out2"
  agents_seen=$(grep -c 'zqx-agentspath' "$out2" 2>/dev/null); agents_seen=${agents_seen:-0}
  claude_seen=$(grep -c 'zqx-claudepath' "$out2" 2>/dev/null); claude_seen=${claude_seen:-0}
  if [ ! -s "$out2" ]; then
    skill_answer="inconclusive"; skill_note="agy 응답 없음(타임아웃 또는 빈 출력) — 미측정으로 취급"
  elif grep -q 'TOOL_USED' "$out2"; then
    skill_answer="inconclusive"; skill_note="응답 전 툴 호출 — 등록 여부 판정 불가"
  elif [ "$agents_seen" -gt 0 ] && [ "$claude_seen" -eq 0 ]; then
    skill_answer="pass"; skill_note=".agents/skills 가 등록되고 .claude/skills 는 미등록(통제 실험 확정)"
  elif [ "$agents_seen" -gt 0 ] && [ "$claude_seen" -gt 0 ]; then
    skill_answer="partial"; skill_note="양쪽 경로 모두 등록됨"
  elif [ "$claude_seen" -gt 0 ]; then
    skill_answer="unexpected"; skill_note=".claude/skills 만 등록됨 — 문서와 반대"
  else
    skill_answer="fail"; skill_note="응답은 왔으나 어느 경로도 등록되지 않음"
  fi
fi

cat <<JSON
{
  "measured_at": "$TODAY",
  "agy_version": "$AGY_VERSION",
  "dynamic": $([ "$DYNAMIC" -eq 1 ] && echo true || echo false),
  "static": {
    "agents_md_bytes": $agents_bytes,
    "has_agents_skills_dir": $has_agents_skills,
    "has_gemini_dir": $has_gemini_dir,
    "git_hook_wired": $has_git_hook,
    "gate_exit_on_staged_env": $gate_exit
  },
  "dynamic_results": {
    "instructions_p0": { "verdict": "$p0_answer", "note": "$p0_note" },
    "repo_skills_discovery_path": { "verdict": "$skill_answer", "note": "$skill_note" }
  }
}
JSON
