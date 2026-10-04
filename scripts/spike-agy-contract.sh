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
agent_answer="unverified"; agent_note="--dynamic 미지정"
hook_answer="unverified"; hook_note="--dynamic 미지정"
rule_answer="unverified"; rule_note="--dynamic 미지정"
emit_answer="unverified"; emit_note="--dynamic 미지정"
adapter_answer="unverified"; adapter_note="--dynamic 미지정"

# 툴 사용을 허용하는 질의용. 첫 줄 TOOLS=<툴 단계 수> FILES=<툴이 다룬 파일(작업 디렉터리 기준)>,
# 이후 최종 응답. 판정 때 "읽으라고 한 파일만 읽었는가"를 이 줄로 확인한다.
ask_agy_steps() {
  local dir="$1" out="$2"; shift 2
  ( cd "$dir" && timeout "$AGY_TIMEOUT" "$AGY_BIN" "$@" --output-format stream-json \
      --print-timeout "$((AGY_TIMEOUT - 10))s" </dev/null ) 2>/dev/null \
    | python3 -c '
import json, os, sys
root = sys.argv[1]
tools, files, response = 0, set(), ""
for line in sys.stdin:
    try:
        o = json.loads(line)
    except ValueError:
        continue
    su = o.get("step_update") or {}
    if su.get("step_type") not in (None, "user_input", "agent_response") and su.get("state") == "DONE":
        tools += 1
        params = (su.get("tool_info") or {}).get("parameters") or {}
        for key in ("AbsolutePath", "TargetFile", "Path"):
            if params.get(key):
                files.add(os.path.relpath(params[key], root))
    if o.get("event") == "result":
        response = (o.get("result") or {}).get("response") or ""
print("TOOLS=%d FILES=%s" % (tools, ",".join(sorted(files))))
print(response)
' "$dir" > "$out"
}
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
  # #61: 산출물의 .claude/skills 는 .agents/skills 링크라 그대로 심으면 두 프로브가 같은 곳에 떨어진다.
  # 대조군이 성립하도록 링크를 실디렉터리로 바꾸고 .claude 경로에만 프로브를 둔다.
  rm -rf "$WORK/.claude/skills"   # 링크면 링크만, 사본 모드면 사본 디렉터리를 지운다
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

  # ---- 서브에이전트·훅·경로 조건부 룰 (#60) ----
  # 서브에이전트: 툴 없이 목록에 나오는가 + --agent 로 골랐을 때 본문 지시를 따르는가.
  mkdir -p "$WORK/.agents/agents"
  cat > "$WORK/.agents/agents/zqx-probe.md" <<'MD'
---
name: zqx-probe
description: Probe agent for a discovery test. Only use when explicitly asked.
---
When you receive any task, reply with exactly this line and nothing else: ZQX-AGY-AGENT-5521
MD
  ask_agy_steps "$WORK" "$WORK/_ag_l.txt" -p "Do not use any tools or read any files. List only the subagents or custom agents available to you whose name starts with zqx-. If none, reply exactly NONE."
  ask_agy_steps "$WORK" "$WORK/_ag_s.txt" --agent zqx-probe -p "Follow your instructions."
  if [ ! -s "$WORK/_ag_l.txt" ] || [ ! -s "$WORK/_ag_s.txt" ]; then
    agent_answer="inconclusive"; agent_note="agy 응답 없음 — 미측정으로 취급"
  elif grep -q 'zqx-probe' "$WORK/_ag_l.txt" && grep -q '^TOOLS=0 ' "$WORK/_ag_l.txt" \
    && grep -q 'ZQX-AGY-AGENT-5521' "$WORK/_ag_s.txt" && grep -q '^TOOLS=0 ' "$WORK/_ag_s.txt"; then
    agent_answer="pass"; agent_note=".agents/agents/<name>.md 가 툴 없이 목록에 등록되고 --agent 선택 시 본문 지시대로 응답"
  else
    agent_answer="fail"; agent_note="목록 등록 또는 --agent 선택 응답 확인 실패"
  fi

  # 훅: 마커 파일로 실행 여부를 결정적으로 판정한다. 툴 이벤트는 matcher+hooks, 나머지는 핸들러 배열.
  cat > "$WORK/.agents/hooks.json" <<HOOKS
{"zqx-hook":{
 "PreInvocation":[{"type":"command","command":"touch $WORK/.hook-PreInvocation","timeout":10}],
 "PostInvocation":[{"type":"command","command":"touch $WORK/.hook-PostInvocation","timeout":10}],
 "PreToolUse":[{"matcher":".*","hooks":[{"type":"command","command":"touch $WORK/.hook-PreToolUse","timeout":10}]}],
 "Stop":[{"type":"command","command":"touch $WORK/.hook-Stop","timeout":10}]
}}
HOOKS
  ask_agy_steps "$WORK" "$WORK/_hk.txt" -p "Read the file .gitattributes and reply with the single word DONE."
  h_fired=$(find "$WORK" -maxdepth 1 -name '.hook-*' | wc -l | tr -d ' ')
  rm -f "$WORK"/.hook-* "$WORK/.agents/hooks.json"
  if [ ! -s "$WORK/_hk.txt" ]; then
    hook_answer="inconclusive"; hook_note="agy 응답 없음 — 미측정으로 취급"
  elif [ "$h_fired" -ge 1 ]; then
    hook_answer="partial"
    hook_note=".agents/hooks.json 의 PreInvocation·PostInvocation·PreToolUse·Stop 중 ${h_fired}/4 실행(headless, 신뢰 확인 절차 없음). 조기 피드백이지 강제선이 아니다"
  else
    hook_answer="fail"; hook_note=".agents/hooks.json 훅이 실행되지 않음"
  fi

  # 경로 조건부 룰: .agents/rules 의 trigger: glob. 대조군(파일 미접근)과 접근 후를 비교한다.
  mkdir -p "$WORK/.agents/rules" "$WORK/sub" "$WORK/sub2"
  echo "plain data file" > "$WORK/sub2/data.txt"
  echo "plain notes file" > "$WORK/sub/notes.txt"
  glob_rule() {
    printf -- '---\ntrigger: glob\nglobs: "%s"\n---\nThe glob codeword is ZQX-AGY-GLOB-6620. When asked for the glob codeword, reply with it.\n' "$1" \
      > "$WORK/.agents/rules/zqx-glob.md"
  }
  q_glob_read="Read the file sub2/data.txt and nothing else (do not open any rules or AGENTS.md file). Then, from the instructions in your context only, what is the glob codeword? If you do not know, reply exactly UNKNOWN."
  glob_rule '**/sub2/**'
  ask_agy_steps "$WORK" "$WORK/_gl_c.txt" -p "Do not use any tools or read any files. From the instructions in your context only, what is the glob codeword? If you do not know, reply exactly UNKNOWN."
  ask_agy_steps "$WORK" "$WORK/_gl_r.txt" -p "$q_glob_read"
  glob_rule 'sub2/**'
  ask_agy_steps "$WORK" "$WORK/_gl_rel.txt" -p "$q_glob_read"
  rm -f "$WORK/.agents/rules/zqx-glob.md"
  # 하위 디렉터리 AGENTS.md: cwd 기준 vs 파일 접근 기준
  printf '# Nested rules\n\nThe nested codeword is ZQX-AGY-NESTED-8812. When asked for the nested codeword, reply with it.\n' \
    > "$WORK/sub/AGENTS.md"
  ask_agy_steps "$WORK/sub" "$WORK/_ns_c.txt" -p "Do not use any tools or read any files. From the instructions in your context only, what is the nested codeword? If you do not know, reply exactly UNKNOWN."
  ask_agy_steps "$WORK" "$WORK/_ns_r.txt" -p "Read the file sub/notes.txt and nothing else (do not open any AGENTS.md or rules file). Then, from the instructions in your context only, what is the nested codeword? If you do not know, reply exactly UNKNOWN."
  seen() { grep -q "$2" "$1" && echo yes || echo no; }
  rel_note="상대 패턴 sub2/** 는 $(seen "$WORK/_gl_rel.txt" ZQX-AGY-GLOB-6620)"
  nested_note="하위 AGENTS.md: cwd=하위 $(seen "$WORK/_ns_c.txt" ZQX-AGY-NESTED-8812), 루트에서 하위 파일 읽기 $(seen "$WORK/_ns_r.txt" ZQX-AGY-NESTED-8812)"
  if [ ! -s "$WORK/_gl_c.txt" ] || [ ! -s "$WORK/_gl_r.txt" ]; then
    rule_answer="inconclusive"; rule_note="agy 응답 없음 — 미측정으로 취급"
  elif grep -q 'ZQX-AGY-GLOB-6620' "$WORK/_gl_c.txt"; then
    rule_answer="fail"; rule_note="glob 룰이 파일 접근 없이도 로드됨(조건부가 아님). $nested_note"
  elif grep -q 'ZQX-AGY-GLOB-6620' "$WORK/_gl_r.txt" && grep -q '^TOOLS=[0-9]* FILES=sub2/data.txt$' "$WORK/_gl_r.txt"; then
    rule_answer="pass"; rule_note="trigger: glob 룰이 sub2/data.txt 접근 뒤에만 로드(대조군 UNKNOWN). 패턴 **/sub2/** 는 yes, $rel_note. $nested_note"
  else
    rule_answer="fail"; rule_note="glob 룰이 일치 파일 접근 뒤에도 로드되지 않음. $rel_note. $nested_note"
  fi

  # 룰 어댑터 e2e (#63): 상대 패턴 paths: 를 가진 .claude/rules 를 --update 로 .agents/rules 에 다시
  # 생성하고, 생성된 룰이 일치 파일 접근 뒤에만 로드되는지 본다.
  mkdir -p "$WORK/sub3"
  echo "plain file" > "$WORK/sub3/data.txt"
  printf -- '---\npaths:\n  - "sub3/**"\n---\nThe emitted codeword is ZQX-AGY-EMIT-2207. When asked for the emitted codeword, reply with it.\n' \
    > "$WORK/.claude/rules/zqx-emit.md"
  bash "$REPO_ROOT/bin/agents-scaffold.sh" "$WORK" --update --yes >/dev/null 2>&1
  ask_agy_steps "$WORK" "$WORK/_em_c.txt" -p "Do not use any tools or read any files. From the instructions in your context only, what is the emitted codeword? If you do not know, reply exactly UNKNOWN."
  ask_agy_steps "$WORK" "$WORK/_em_r.txt" -p "Read the file sub3/data.txt and nothing else (do not open any rules or AGENTS.md file). Then, from the instructions in your context only, what is the emitted codeword? If you do not know, reply exactly UNKNOWN."
  if ! grep -qx 'globs: "\*\*/sub3/\*\*"' "$WORK/.agents/rules/zqx-emit.md" 2>/dev/null; then
    emit_answer="fail"; emit_note="--update 가 .agents/rules/zqx-emit.md 를 생성하지 않았거나 패턴 변환이 다름"
  elif [ ! -s "$WORK/_em_c.txt" ] || [ ! -s "$WORK/_em_r.txt" ]; then
    emit_answer="inconclusive"; emit_note="agy 응답 없음 — 미측정으로 취급"
  elif grep -q 'ZQX-AGY-EMIT-2207' "$WORK/_em_c.txt"; then
    emit_answer="fail"; emit_note="생성된 룰이 파일 접근 없이도 로드됨(조건부가 아님)"
  elif grep -q 'ZQX-AGY-EMIT-2207' "$WORK/_em_r.txt" && grep -q '^TOOLS=[0-9]* FILES=sub3/data.txt$' "$WORK/_em_r.txt"; then
    emit_answer="pass"; emit_note="paths: sub3/** 가 globs: **/sub3/** 로 생성되고, 일치 파일 접근 뒤에만 로드(대조군 미로드)"
  else
    emit_answer="fail"; emit_note="생성된 룰이 일치 파일 접근 뒤에도 로드되지 않음"
  fi

  # 서브에이전트 어댑터 e2e (#64): Claude 형식(tools·model 포함) 프로브를 --update 로 .agents/agents 에
  # 생성하고 --agent 로 고른다. 그대로 복사하면 agy 가 조용히 빼는 형식이라, 생성기가 걸러야 통과한다.
  printf -- '---\nname: zqx-emit-agent\ndescription: Probe agent generated by the scaffold. Only use when explicitly asked.\ntools: Read, Grep\nmodel: sonnet\n---\nWhen invoked, reply with exactly this line and nothing else: ZQX-EMIT-AGENT-3381\n' \
    > "$WORK/.claude/agents/zqx-emit-agent.md"
  bash "$REPO_ROOT/bin/agents-scaffold.sh" "$WORK" --update --yes >/dev/null 2>&1
  ask_agy_steps "$WORK" "$WORK/_ae.txt" --agent zqx-emit-agent -p "Follow your instructions."
  if ! grep -qx "name: 'zqx-emit-agent'" "$WORK/.agents/agents/zqx-emit-agent.md" 2>/dev/null; then
    adapter_answer="fail"; adapter_note="--update 가 .agents/agents/zqx-emit-agent.md 를 생성하지 않음"
  elif [ ! -s "$WORK/_ae.txt" ]; then
    adapter_answer="inconclusive"; adapter_note="agy 응답 없음 — 미측정으로 취급"
  elif grep -q 'ZQX-EMIT-AGENT-3381' "$WORK/_ae.txt" && grep -q '^TOOLS=0 ' "$WORK/_ae.txt"; then
    adapter_answer="pass"; adapter_note="Claude 형식 원본(tools·model 포함)에서 name·description 만 남겨 생성한 에이전트를 --agent 로 고르면 본문 지시대로 응답"
  else
    adapter_answer="fail"; adapter_note="생성한 에이전트를 --agent 로 골라도 본문 지시대로 응답하지 않음"
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
    "repo_skills_discovery_path": { "verdict": "$skill_answer", "note": "$skill_note" },
    "subagents": { "verdict": "$agent_answer", "note": "$agent_note" },
    "lifecycle_hooks": { "verdict": "$hook_answer", "note": "$hook_note" },
    "path_scoped_rules": { "verdict": "$rule_answer", "note": "$rule_note" },
    "rules_adapter": { "verdict": "$emit_answer", "note": "$emit_note" },
    "subagents_adapter": { "verdict": "$adapter_answer", "note": "$adapter_note" }
  }
}
JSON
