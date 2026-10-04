#!/usr/bin/env bash
# Codex 계약 실측 spike (#37, a-2)
#
# codex-cli 의 저장소 계약을 실제로 측정한다. 문서 인용이 아니라 실행 결과가 근거다.
# 결과는 stdout 에 JSON 으로 출력한다 — docs/harness-matrix.json 의 입력.
#
#   scripts/spike-codex-contract.sh [--dynamic]
#
# --dynamic 을 주면 codex exec 로 실제 모델 호출까지 수행한다(API 쿼터 소모).
# 생략하면 정적 검사만 하고 동적 항목은 unverified 로 남긴다.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DYNAMIC=0
[ "${1:-}" = "--dynamic" ] && DYNAMIC=1
# codex 호출은 수 분이 걸리고 종종 타임아웃한다. 응답이 없는 것과 "없다고 답한 것"은
# 다른 사실이므로 구분한다 — 응답 없음은 fail 이 아니라 inconclusive 다.
CODEX_TIMEOUT="${CODEX_TIMEOUT:-600}"

CODEX_VERSION="$(codex --version 2>/dev/null | tr -d '\n' || echo 'not-installed')"
TODAY="$(date +%Y-%m-%d)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git -C "$WORK" init -q
git -C "$WORK" config user.email spike@local
git -C "$WORK" config user.name spike
bash "$REPO_ROOT/bin/agents-scaffold.sh" "$WORK" --forge github --stack python \
  --harness codex --name spike-app --yes >/dev/null 2>&1

# ---- 정적 측정 -------------------------------------------------------------
agents_bytes=$(wc -c < "$WORK/AGENTS.md" | tr -d ' ')
has_agents_skills=$([ -d "$WORK/.agents/skills" ] && echo true || echo false)
has_claude_skills=$([ -d "$WORK/.claude/skills" ] && echo true || echo false)
has_codex_dir=$([ -d "$WORK/.codex" ] && echo true || echo false)
has_git_hook=$([ -x "$WORK/.git/hooks/pre-commit" ] && echo true || echo false)

# 게이트가 실제로 .env 를 막는가 (exit code 로 판정)
( cd "$WORK" && echo 'K=v' > .env && git add -f .env >/dev/null 2>&1 )
gate_exit=0
( cd "$WORK" && bash .git/hooks/pre-commit >/dev/null 2>&1 ) || gate_exit=$?
( cd "$WORK" && git reset -q HEAD .env >/dev/null 2>&1; rm -f .env )

# ---- 동적 측정 -------------------------------------------------------------
p0_answer="unverified"; p0_note="--dynamic 미지정"
skill_answer="unverified"; skill_note="--dynamic 미지정"
agent_answer="unverified"; agent_note="--dynamic 미지정"
hook_answer="unverified"; hook_note="--dynamic 미지정"
nested_answer="unverified"; nested_note="--dynamic 미지정"
adapter_answer="unverified"; adapter_note="--dynamic 미지정"
if [ "$DYNAMIC" -eq 1 ] && [ "$CODEX_VERSION" != "not-installed" ]; then
  out="$WORK/_p0.txt"
  timeout "$CODEX_TIMEOUT" codex exec -C "$WORK" --skip-git-repo-check -s read-only \
    -o "$out" "이 저장소의 P0 규칙을 그대로 나열해라. 추측하지 말고 저장소 지침에 적힌 것만." \
    </dev/null >/dev/null 2>&1
  if [ ! -s "$out" ]; then
    p0_answer="inconclusive"; p0_note="codex 응답 없음(타임아웃 또는 빈 출력) — 미측정으로 취급"
  elif grep -qi 'p0' "$out"; then
    if grep -qi 'mypy\|ruff' "$out"; then
      p0_answer="pass"; p0_note="AGENTS.md 자동 로드 + 인라인된 python 스택 P0 까지 응답"
    else
      p0_answer="partial"; p0_note="공통 P0 는 응답했으나 인라인된 스택 P0 는 응답에 없음"
    fi
  else
    p0_answer="fail"; p0_note="응답은 왔으나 P0 를 답하지 못함"
  fi

  # 스킬 발견은 통제 실험으로 잰다. 단순히 "스킬 목록을 말해봐" 라고 물으면
  # 모델이 파일시스템을 읽어서 답하거나 사용자 전역 스킬을 섞어 답하므로 무효다.
  # 레포에만 존재하는 유니크 이름 2개를 서로 다른 경로에 심고 어느 쪽이 등록되는지 본다.
  # #61: 산출물의 .claude/skills 는 .agents/skills 링크라 그대로 심으면 두 프로브가 같은 곳에 떨어진다.
  # 대조군이 성립하도록 링크를 실디렉터리로 바꾸고 .claude 경로에만 프로브를 둔다.
  rm -rf "$WORK/.claude/skills"   # 링크면 링크만, 사본 모드면 사본 디렉터리를 지운다
  mkdir -p "$WORK/.claude/skills/zqx-claudepath" "$WORK/.agents/skills/zqx-agentspath"
  printf -- '---\nname: zqx-claudepath\ndescription: probe skill under .claude/skills\n---\n\nprobe A\n' \
    > "$WORK/.claude/skills/zqx-claudepath/SKILL.md"
  printf -- '---\nname: zqx-agentspath\ndescription: probe skill under .agents/skills\n---\n\nprobe B\n' \
    > "$WORK/.agents/skills/zqx-agentspath/SKILL.md"
  out2="$WORK/_skill.txt"
  timeout "$CODEX_TIMEOUT" codex exec -C "$WORK" --skip-git-repo-check -s read-only \
    -o "$out2" "너에게 등록된 skill 중 이름이 'zqx-' 로 시작하는 것만 나열해라. 파일시스템을 뒤지지 마라 — ls/find/cat/grep 등 명령 실행 금지. 등록된 skill 목록에서만 골라라. 없으면 '없음'." \
    </dev/null >/dev/null 2>&1
  # grep -c 는 0건일 때 "0" 을 찍고 exit 1 이다 — `|| echo 0` 을 붙이면 "0\n0" 이 되어 비교가 깨진다.
  agents_seen=$(grep -c 'zqx-agentspath' "$out2" 2>/dev/null); agents_seen=${agents_seen:-0}
  claude_seen=$(grep -c 'zqx-claudepath' "$out2" 2>/dev/null); claude_seen=${claude_seen:-0}
  if [ ! -s "$out2" ]; then
    skill_answer="inconclusive"; skill_note="codex 응답 없음(타임아웃 또는 빈 출력) — 미측정으로 취급"
  elif [ "$agents_seen" -gt 0 ] && [ "$claude_seen" -eq 0 ]; then
    skill_answer="pass"; skill_note="산출된 .agents/skills 가 등록되고 .claude/skills 는 미등록(통제 실험 확정)"
  elif [ "$agents_seen" -gt 0 ] && [ "$claude_seen" -gt 0 ]; then
    skill_answer="partial"; skill_note="양쪽 경로 모두 등록됨"
  elif [ "$claude_seen" -gt 0 ]; then
    skill_answer="unexpected"; skill_note=".claude/skills 만 등록됨 — 문서와 반대"
  else
    skill_answer="fail"; skill_note="응답은 왔으나 어느 경로도 등록되지 않음"
  fi
  rm -rf "$WORK/.agents" "$WORK/.claude/skills/zqx-claudepath"

  # ---- 서브에이전트·훅·경로별 지침 (#60) ----
  # .codex/ 레이어는 신뢰 프로젝트에서만 로드된다. 사용자 config 를 건드리지 않도록 이번 호출에만
  # 신뢰를 준다(-c projects={...}). 미신뢰 대조군은 같은 질의를 -c 없이 보낸다.
  # codex exec 는 stdin 이 열려 있으면 추가 입력을 기다리므로 </dev/null 로 닫는다.
  # 출력: 첫 줄 CMDS=<셸 명령 실행 수>, 이후 마지막 응답. 명령을 실행했다면 파일을 직접 읽었을 수 있다.
  trust="projects={\"$WORK\"={trust_level=\"trusted\"}}"
  codex_ask() {
    local out="$1"; shift
    timeout "$CODEX_TIMEOUT" codex exec --skip-git-repo-check -s read-only --json "$@" </dev/null 2>/dev/null \
      | python3 -c '
import json, sys
cmds, msg = 0, ""
for line in sys.stdin:
    try:
        o = json.loads(line)
    except ValueError:
        continue
    it = o.get("item") or {}
    if it.get("type") == "command_execution" and o.get("type") == "item.started":
        cmds += 1
    if it.get("type") == "agent_message" and o.get("type") == "item.completed":
        msg = it.get("text") or ""
print("CMDS=%d" % cmds)
print(msg)
' > "$out"
  }
  answered() { [ -s "$1" ] && [ "$(sed -n 2p "$1")" != "" ]; }
  no_cmds() { grep -q '^CMDS=0$' "$1"; }

  # 서브에이전트: 신뢰/미신뢰 목록 + 실제 위임. 암호어는 developer_instructions 에만 있다.
  mkdir -p "$WORK/.codex/agents"
  cat > "$WORK/.codex/agents/zqx_probe_agent.toml" <<'TOML'
name = "zqx_probe_agent"
description = "Probe agent for a discovery test. Only use when explicitly asked."
developer_instructions = """
When invoked, reply with exactly this line and nothing else: ZQX-SUBAGENT-CODEWORD-7319
"""
TOML
  q_list="Do not run any commands or read any files. From the agent/subagent types available to you in this session, list only those whose name starts with zqx_. If none, reply exactly NONE."
  codex_ask "$WORK/_ag_t.txt" -C "$WORK" -c "$trust" "$q_list"
  codex_ask "$WORK/_ag_u.txt" -C "$WORK" "$q_list"
  codex_ask "$WORK/_ag_s.txt" -C "$WORK" -c "$trust" \
    "Spawn a subagent of type zqx_probe_agent with the task 'Follow your instructions.' and wait for it. Then reply with exactly the text it returned. Do not run shell commands or read files yourself."
  if ! answered "$WORK/_ag_t.txt" || ! answered "$WORK/_ag_s.txt"; then
    agent_answer="inconclusive"; agent_note="codex 응답 없음 — 미측정으로 취급"
  elif grep -q 'zqx_probe_agent' "$WORK/_ag_t.txt" && no_cmds "$WORK/_ag_t.txt" \
    && grep -q 'ZQX-SUBAGENT-CODEWORD-7319' "$WORK/_ag_s.txt" && no_cmds "$WORK/_ag_s.txt"; then
    if grep -q 'zqx_probe_agent' "$WORK/_ag_u.txt"; then
      agent_answer="pass"; agent_note=".codex/agents 등록·위임 확인, 미신뢰 프로젝트에서도 등록됨"
    else
      agent_answer="pass"; agent_note=".codex/agents 가 신뢰 프로젝트에서 등록되고 위임 시 developer_instructions 대로 응답(셸 명령 0). 미신뢰 프로젝트에서는 미등록"
    fi
  else
    agent_answer="fail"; agent_note="신뢰 프로젝트에서 등록 또는 위임 응답 확인 실패"
  fi

  # 훅: 마커 파일로 실행 여부를 결정적으로 판정한다.
  cat > "$WORK/.codex/hooks.json" <<HOOKS
{"hooks":{
 "SessionStart":[{"hooks":[{"type":"command","command":"touch $WORK/.hook-SessionStart","timeout":10}]}],
 "UserPromptSubmit":[{"hooks":[{"type":"command","command":"touch $WORK/.hook-UserPromptSubmit","timeout":10}]}],
 "Stop":[{"hooks":[{"type":"command","command":"touch $WORK/.hook-Stop","timeout":10}]}]
}}
HOOKS
  hook_count() { find "$WORK" -maxdepth 1 -name '.hook-*' | wc -l | tr -d ' '; }
  q_done="Reply with the single word DONE."
  codex_ask "$WORK/_hk1.txt" -C "$WORK" -c "$trust" "$q_done"
  h_plain=$(hook_count); rm -f "$WORK"/.hook-*
  codex_ask "$WORK/_hk2.txt" -C "$WORK" -c "$trust" --dangerously-bypass-hook-trust "$q_done"
  h_bypass=$(hook_count); rm -f "$WORK"/.hook-*
  codex_ask "$WORK/_hk3.txt" -C "$WORK" --dangerously-bypass-hook-trust "$q_done"
  h_untrusted=$(hook_count); rm -f "$WORK"/.hook-*
  if ! answered "$WORK/_hk2.txt"; then
    hook_answer="inconclusive"; hook_note="codex 응답 없음 — 미측정으로 취급"
  elif [ "$h_bypass" -ge 3 ]; then
    hook_answer="partial"
    hook_note="SessionStart·UserPromptSubmit·Stop 실행(신뢰 프로젝트 + 훅 신뢰 우회). 훅 정의 신뢰 없이 ${h_plain}/3, 미신뢰 프로젝트는 우회해도 ${h_untrusted}/3 — 신뢰에 묶인 조기 피드백이지 강제선이 아니다"
  else
    hook_answer="fail"; hook_note="신뢰 프로젝트 + 우회에서도 훅 ${h_bypass}/3 실행"
  fi
  rm -f "$WORK/.codex/hooks.json"

  # 경로별 지침: 하위 디렉터리 AGENTS.md 가 cwd 기준으로만 읽히는가, 파일 접근으로도 읽히는가.
  mkdir -p "$WORK/sub"
  printf '# Nested rules\n\nThe nested codeword is ZQX-NESTED-4471. When asked for the nested codeword, reply with it.\n' \
    > "$WORK/sub/AGENTS.md"
  echo "plain notes file" > "$WORK/sub/notes.txt"
  codex_ask "$WORK/_ns1.txt" -C "$WORK/sub" -c "$trust" \
    "Do not run any commands or read any files. Answer only from the instructions already in your context: what is the nested codeword? If you do not know, reply exactly UNKNOWN."
  codex_ask "$WORK/_ns2.txt" -C "$WORK" -c "$trust" \
    "Read the file sub/notes.txt and nothing else (do not open any AGENTS.md). Then, from the instructions in your context only, what is the nested codeword? If you do not know, reply exactly UNKNOWN."
  if ! answered "$WORK/_ns1.txt" || ! answered "$WORK/_ns2.txt"; then
    nested_answer="inconclusive"; nested_note="codex 응답 없음 — 미측정으로 취급"
  elif grep -q 'ZQX-NESTED-4471' "$WORK/_ns1.txt" && no_cmds "$WORK/_ns1.txt"; then
    if grep -q 'ZQX-NESTED-4471' "$WORK/_ns2.txt"; then
      nested_answer="pass"; nested_note="하위 AGENTS.md 가 cwd 기준과 파일 접근 양쪽에서 로드"
    else
      nested_answer="partial"; nested_note="하위 AGENTS.md 는 cwd 가 그 디렉터리일 때만 로드. 루트에서 하위 파일을 읽어도 미로드 — 파일 경로 조건부 로딩 없음"
    fi
  else
    nested_answer="fail"; nested_note="cwd 가 하위 디렉터리여도 하위 AGENTS.md 미로드"
  fi

  # 서브에이전트 어댑터 e2e (#64): Claude 형식(.claude/agents, tools·model 포함) 프로브를 --update 로
  # .codex/agents 에 생성하고, 신뢰 프로젝트에서 위임해 본문 지시대로 응답하는지 본다.
  printf -- '---\nname: zqx-emit-agent\ndescription: Probe agent generated by the scaffold. Only use when explicitly asked.\ntools: Read, Grep\nmodel: sonnet\n---\nWhen invoked, reply with exactly this line and nothing else: ZQX-EMIT-AGENT-3381\n' \
    > "$WORK/.claude/agents/zqx-emit-agent.md"
  bash "$REPO_ROOT/bin/agents-scaffold.sh" "$WORK" --update --yes >/dev/null 2>&1
  codex_ask "$WORK/_ae.txt" -C "$WORK" -c "$trust" \
    "Spawn a subagent of type zqx-emit-agent with the task 'Follow your instructions.' and wait for it. Then reply with exactly the text it returned. Do not run shell commands or read files yourself."
  if ! grep -qx 'name = "zqx-emit-agent"' "$WORK/.codex/agents/zqx-emit-agent.toml" 2>/dev/null; then
    adapter_answer="fail"; adapter_note="--update 가 .codex/agents/zqx-emit-agent.toml 을 생성하지 않음"
  elif ! answered "$WORK/_ae.txt"; then
    adapter_answer="inconclusive"; adapter_note="codex 응답 없음 — 미측정으로 취급"
  elif grep -q 'ZQX-EMIT-AGENT-3381' "$WORK/_ae.txt" && no_cmds "$WORK/_ae.txt"; then
    adapter_answer="pass"; adapter_note=".claude/agents 원본에서 생성한 .codex/agents TOML 을 위임하면 본문 지시대로 응답(셸 명령 0)"
  else
    adapter_answer="fail"; adapter_note="생성한 에이전트를 위임해도 본문 지시대로 응답하지 않음"
  fi
fi

cat <<JSON
{
  "measured_at": "$TODAY",
  "codex_version": "$CODEX_VERSION",
  "dynamic": $([ "$DYNAMIC" -eq 1 ] && echo true || echo false),
  "static": {
    "agents_md_bytes": $agents_bytes,
    "agents_md_budget_bytes": 32768,
    "has_agents_skills_dir": $has_agents_skills,
    "has_claude_skills_dir": $has_claude_skills,
    "has_codex_dir": $has_codex_dir,
    "git_hook_wired": $has_git_hook,
    "gate_exit_on_staged_env": $gate_exit
  },
  "dynamic_results": {
    "instructions_p0": { "verdict": "$p0_answer", "note": "$p0_note" },
    "repo_skills_discovery_path": { "verdict": "$skill_answer", "note": "$skill_note" },
    "subagents": { "verdict": "$agent_answer", "note": "$agent_note" },
    "lifecycle_hooks": { "verdict": "$hook_answer", "note": "$hook_note" },
    "path_scoped_instructions": { "verdict": "$nested_answer", "note": "$nested_note" },
    "subagents_adapter": { "verdict": "$adapter_answer", "note": "$adapter_note" }
  }
}
JSON
