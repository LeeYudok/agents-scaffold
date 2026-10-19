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
# AGY_KEEP_WORK=1 이면 작업 디렉터리를 지우지 않고 경로를 stderr 에 남긴다 — 판정이 바뀌었을 때
# 질의별 원문(_*.txt)을 보기 위함 (#73).
#
# 판정 규칙: 응답 전에 툴 호출 단계가 하나라도 있으면 파일을 직접 읽었을 수 있으므로
# 그 질의는 inconclusive 다 — 컨텍스트에 자동 로드된 지침만으로 답했을 때만 판정한다.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DYNAMIC=0
[ "${1:-}" = "--dynamic" ] && DYNAMIC=1
AGY_BIN="${AGY_BIN:-agy}"
AGY_TIMEOUT="${AGY_TIMEOUT:-300}"
# 모든 agy 질의에 덧붙일 인자(공백 구분). 예: AGY_ARGS="--model <이름>" — 기본 모델 할당량이 찼을 때 (#73).
# macOS bash 3.2 + set -u 에서 빈 배열 확장이 죽지 않도록 ${arr[@]+...} 형태로만 쓴다.
AGY_ARGS="${AGY_ARGS:-}"
read -r -a AGY_EXTRA <<< "$AGY_ARGS"

AGY_VERSION="$("$AGY_BIN" --version 2>/dev/null | tr -d '\n' || true)"
[ -n "$AGY_VERSION" ] || AGY_VERSION="not-installed"
TODAY="$(date +%Y-%m-%d)"

WORK="$(mktemp -d)"
if [ "${AGY_KEEP_WORK:-0}" = 1 ]; then
  trap 'echo "spike work dir: $WORK" >&2' EXIT
else
  trap 'rm -rf "$WORK"' EXIT
fi
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

# 툴 호출 판정 (#73): "user_input·agent_response 가 아닌 단계 = 툴" 로 세면, 툴이 아닌 새 단계 종류가
# 생긴 버전(agy 1.4.0)에서 모든 질의가 TOOL_USED 로 오탐된다. 실제 툴 이름(tool_info.name)이 있는
# 단계만 툴로 센다. 버전마다 단계 종류가 바뀌므로 본 종류를 STEPS_LOG 에 모아 결과 JSON 에 싣는다.
STEPS_LOG="$WORK/_steps.log"
: > "$STEPS_LOG"
# error_message 단계 원문 — 빈 응답의 원인(할당량·일시 오류 등)을 결과 JSON 에서 바로 보이게 (#73)
ERRORS_LOG="$WORK/_errors.log"
: > "$ERRORS_LOG"

# agy -p 를 stream-json 으로 돌려 최종 응답만 파일에 남긴다.
# 응답 전 툴 호출 단계가 있으면 응답 대신 TOOL_USED 를 남긴다.
ask_agy() {
  local dir="$1" prompt="$2" out="$3"
  ( cd "$dir" && timeout "$AGY_TIMEOUT" "$AGY_BIN" ${AGY_EXTRA[@]+"${AGY_EXTRA[@]}"} -p "$prompt" \
      --output-format stream-json --print-timeout "$((AGY_TIMEOUT - 10))s" ) 2>/dev/null \
    | python3 -c '
import json, sys
log = open(sys.argv[1], "a")
tool_steps, response = 0, ""
for line in sys.stdin:
    try:
        o = json.loads(line)
    except ValueError:
        continue
    su = o.get("step_update") or {}
    st = su.get("step_type")
    name = (su.get("tool_info") or {}).get("name")
    if st:
        log.write("%s:%s\n" % (st, "tool" if name else "-"))
    if st == "error_message":
        open(sys.argv[2], "a").write(json.dumps(su, ensure_ascii=False)[:300] + "\n")
    if name:
        tool_steps += 1
    if o.get("event") == "result":
        response = (o.get("result") or {}).get("response") or ""
print("TOOL_USED" if tool_steps else response, end="")
' "$STEPS_LOG" "$ERRORS_LOG" > "$out"
}

# ---- 동적 측정 -------------------------------------------------------------
p0_answer="unverified"; p0_note="--dynamic 미지정"
skill_answer="unverified"; skill_note="--dynamic 미지정"
agent_answer="unverified"; agent_note="--dynamic 미지정"
hook_answer="unverified"; hook_note="--dynamic 미지정"
rule_answer="unverified"; rule_note="--dynamic 미지정"
emit_answer="unverified"; emit_note="--dynamic 미지정"
adapter_answer="unverified"; adapter_note="--dynamic 미지정"
hooks_answer="unverified"; hooks_note="--dynamic 미지정"

# 툴 사용을 허용하는 질의용. 첫 줄 TOOLS=<툴 단계 수> FILES=<툴이 다룬 파일(작업 디렉터리 기준)>,
# 이후 최종 응답. 판정 때 "읽으라고 한 파일만 읽었는가"를 이 줄로 확인한다.
ask_agy_steps() {
  local dir="$1" out="$2"; shift 2
  ( cd "$dir" && timeout "$AGY_TIMEOUT" "$AGY_BIN" ${AGY_EXTRA[@]+"${AGY_EXTRA[@]}"} "$@" --output-format stream-json \
      --print-timeout "$((AGY_TIMEOUT - 10))s" </dev/null ) 2>"$out.err" \
    | python3 -c '
import json, os, sys
root, log = sys.argv[1], open(sys.argv[2], "a")
tools, files, response = 0, set(), ""
for line in sys.stdin:
    try:
        o = json.loads(line)
    except ValueError:
        continue
    su = o.get("step_update") or {}
    info = su.get("tool_info") or {}
    if su.get("step_type") and su.get("state") == "DONE":
        log.write("%s:%s\n" % (su["step_type"], "tool" if info.get("name") else "-"))
        if su["step_type"] == "error_message":
            open(sys.argv[3], "a").write(json.dumps(su, ensure_ascii=False)[:300] + "\n")
    if info.get("name") and su.get("state") == "DONE":
        tools += 1
        params = info.get("parameters") or {}
        for key in ("AbsolutePath", "TargetFile", "Path"):
            if params.get(key):
                files.add(os.path.relpath(params[key], root))
    if o.get("event") == "result":
        response = (o.get("result") or {}).get("response") or ""
print("TOOLS=%d FILES=%s" % (tools, ",".join(sorted(files))))
print(response)
' "$dir" "$STEPS_LOG" "$ERRORS_LOG" > "$out"
  # agy 1.3.4+ 는 --agent 이름이 등록 목록에 없으면 응답 없이 exit 1 한다(1.4.2 실측) — 빈 응답(inconclusive)이
  # 아니라 미등록(fail)으로 판정되게 표시를 남긴다 (#73)
  if grep -q 'unknown agent' "$out.err" 2>/dev/null; then echo "AGENT_UNKNOWN" >> "$out"; fi
}
# ask_agy_steps 결과는 TOOLS= 헤더 줄이 항상 있어 [ -s ] 로는 빈 응답을 못 거른다(#73: 빈 응답이
# inconclusive 대신 fail 로 떨어졌다). 헤더 다음 줄부터 공백 아닌 글자가 있는지로 본다.
no_reply() { [ ! -s "$1" ] || [ -z "$(sed -n '2,$p' "$1" | tr -d '[:space:]')" ]; }
if [ "$DYNAMIC" -eq 1 ] && [ "$AGY_VERSION" != "not-installed" ]; then
  # 산출물의 .agents/hooks.json(#65)은 신뢰 확인 없이 돌고, Stop 훅(메모리 리마인드)이 한 턴을 더
  # 돌려 "툴 없이 답했나" 판정을 깨뜨린다. 기능 측정 동안 빼 두고 훅 어댑터 e2e 에서 다시 생성한다.
  rm -f "$WORK/.agents/hooks.json"
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
  if grep -q '^AGENT_UNKNOWN$' "$WORK/_ag_s.txt"; then
    agent_answer="fail"; agent_note="--agent zqx-probe 가 unknown agent 로 거부됨(미등록)"
  elif no_reply "$WORK/_ag_l.txt" || no_reply "$WORK/_ag_s.txt"; then
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
  h_names=$(find "$WORK" -maxdepth 1 -name '.hook-*' -exec basename {} \; | sed 's/^\.hook-//' | sort | paste -sd, -)
  rm -f "$WORK"/.hook-* "$WORK/.agents/hooks.json"
  if no_reply "$WORK/_hk.txt"; then
    hook_answer="inconclusive"; hook_note="agy 응답 없음 — 미측정으로 취급"
  elif [ "$h_fired" -ge 1 ]; then
    hook_answer="partial"
    hook_note=".agents/hooks.json 의 PreInvocation·PostInvocation·PreToolUse·Stop 중 ${h_fired}/4 실행(${h_names}; headless, 신뢰 확인 절차 없음). 조기 피드백이지 강제선이 아니다"
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
  # 읽으라고 한 파일을 읽었고 룰·AGENTS.md 는 직접 열지 않았는가 (#73: 정확 일치 대신 포함 여부 —
  # 버전에 따라 디렉터리 목록 등 다른 툴 단계가 끼어도 판정이 깨지지 않게)
  read_only_target() {
    local files; files=$(sed -n '1s/^TOOLS=[0-9]* FILES=//p' "$1")
    printf ',%s,' "$files" | grep -q ",$2," && ! printf '%s' "$files" | grep -Eq '(^|,)(\.agents/rules/|[^,]*AGENTS\.md)'
  }
  rel_note="상대 패턴 sub2/** 는 $(seen "$WORK/_gl_rel.txt" ZQX-AGY-GLOB-6620)"
  nested_note="하위 AGENTS.md: cwd=하위 $(seen "$WORK/_ns_c.txt" ZQX-AGY-NESTED-8812), 루트에서 하위 파일 읽기 $(seen "$WORK/_ns_r.txt" ZQX-AGY-NESTED-8812)"
  if no_reply "$WORK/_gl_c.txt" || no_reply "$WORK/_gl_r.txt"; then
    rule_answer="inconclusive"; rule_note="agy 응답 없음 — 미측정으로 취급"
  elif grep -q 'ZQX-AGY-GLOB-6620' "$WORK/_gl_c.txt"; then
    rule_answer="fail"; rule_note="glob 룰이 파일 접근 없이도 로드됨(조건부가 아님). $nested_note"
  elif grep -q 'ZQX-AGY-GLOB-6620' "$WORK/_gl_r.txt" && read_only_target "$WORK/_gl_r.txt" sub2/data.txt; then
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
  elif no_reply "$WORK/_em_c.txt" || no_reply "$WORK/_em_r.txt"; then
    emit_answer="inconclusive"; emit_note="agy 응답 없음 — 미측정으로 취급"
  elif grep -q 'ZQX-AGY-EMIT-2207' "$WORK/_em_c.txt"; then
    emit_answer="fail"; emit_note="생성된 룰이 파일 접근 없이도 로드됨(조건부가 아님)"
  elif grep -q 'ZQX-AGY-EMIT-2207' "$WORK/_em_r.txt" && read_only_target "$WORK/_em_r.txt" sub3/data.txt; then
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
  elif grep -q '^AGENT_UNKNOWN$' "$WORK/_ae.txt"; then
    adapter_answer="fail"; adapter_note="생성한 에이전트가 unknown agent 로 거부됨(미등록 — 생성 frontmatter 확인)"
  elif no_reply "$WORK/_ae.txt"; then
    adapter_answer="inconclusive"; adapter_note="agy 응답 없음 — 미측정으로 취급"
  elif grep -q 'ZQX-EMIT-AGENT-3381' "$WORK/_ae.txt" && grep -q '^TOOLS=0 ' "$WORK/_ae.txt"; then
    adapter_answer="pass"; adapter_note="Claude 형식 원본(tools·model 포함)에서 name·description 만 남겨 생성한 에이전트를 --agent 로 고르면 본문 지시대로 응답"
  else
    adapter_answer="fail"; adapter_note="생성한 에이전트를 --agent 로 골라도 본문 지시대로 응답하지 않음"
  fi

  # 훅 어댑터 e2e (#65): settings.json 에서 .agents/hooks.json 을 다시 생성하고 명령을 하나 실행시킨다.
  # headless 에서 run_command 승인 프롬프트가 막지 않도록 임시 작업 디렉터리에서만 권한을 건너뛴다.
  bash "$REPO_ROOT/bin/agents-scaffold.sh" "$WORK" --update --harness agy --yes >/dev/null 2>&1
  hook_gen="$WORK/.agents/hooks.json"
  ask_agy_steps "$WORK" "$WORK/_hk_e2e.txt" --dangerously-skip-permissions \
    -p "Run the shell command: echo zqx-hook-probe — then reply DONE."
  obs=$(grep -l 'zqx-hook-probe' "$WORK"/.claude/memory/observations/*.jsonl 2>/dev/null | head -1)
  if [ -n "$obs" ]; then
    sid_prefix=$(basename "$obs" .jsonl)
    stop_marker=$(ls /tmp/claude_memsync_"$sid_prefix"* 2>/dev/null | head -1)
  else
    stop_marker=""
  fi
  if [ ! -s "$hook_gen" ]; then
    hooks_answer="fail"; hooks_note="--update --harness 가 hooks.json 을 생성하지 않음"
  elif [ -n "$obs" ] && grep -q '"tool": "Bash"' "$obs" && [ -n "$stop_marker" ]; then
    hooks_answer="pass"; hooks_note="생성된 hooks.json → hook-adapter.py → Claude 형식 훅: observe-lite 가 명령을 Bash 로 기록, stop-memory-remind 가 세션 표시를 남김"
  elif [ -n "$obs" ]; then
    hooks_answer="partial"; hooks_note="PostToolUse(observe-lite)는 실행됐으나 Stop(stop-memory-remind) 표시 없음"
  else
    hooks_answer="fail"
    hooks_note="생성된 훅이 실행되지 않음(관찰 로그 없음). 생성된 이벤트: $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(",".join(k for v in d.values() for k in v))' "$hook_gen" 2>/dev/null)"
  fi
fi

cat <<JSON
{
  "measured_at": "$TODAY",
  "agy_version": "$AGY_VERSION",
  "agy_args": "$AGY_ARGS",
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
    "subagents_adapter": { "verdict": "$adapter_answer", "note": "$adapter_note" },
    "hooks_adapter": { "verdict": "$hooks_answer", "note": "$hooks_note" }
  },
  "step_types_seen": "$(sort "$STEPS_LOG" 2>/dev/null | uniq -c | awk '{printf "%s%s=%s", (NR>1?", ":""), $2, $1}')",
  "errors_seen": $(sort -u "$ERRORS_LOG" 2>/dev/null | head -3 | python3 -c 'import json,sys; print(json.dumps([l.rstrip("\n") for l in sys.stdin], ensure_ascii=False))')
}
JSON
