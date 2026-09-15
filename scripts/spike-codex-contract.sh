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
if [ "$DYNAMIC" -eq 1 ] && [ "$CODEX_VERSION" != "not-installed" ]; then
  out="$WORK/_p0.txt"
  timeout "$CODEX_TIMEOUT" codex exec -C "$WORK" --skip-git-repo-check -s read-only \
    -o "$out" "이 저장소의 P0 규칙을 그대로 나열해라. 추측하지 말고 저장소 지침에 적힌 것만." \
    >/dev/null 2>&1
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
  mkdir -p "$WORK/.claude/skills/zqx-claudepath" "$WORK/.agents/skills/zqx-agentspath"
  printf -- '---\nname: zqx-claudepath\ndescription: probe skill under .claude/skills\n---\n\nprobe A\n' \
    > "$WORK/.claude/skills/zqx-claudepath/SKILL.md"
  printf -- '---\nname: zqx-agentspath\ndescription: probe skill under .agents/skills\n---\n\nprobe B\n' \
    > "$WORK/.agents/skills/zqx-agentspath/SKILL.md"
  out2="$WORK/_skill.txt"
  timeout "$CODEX_TIMEOUT" codex exec -C "$WORK" --skip-git-repo-check -s read-only \
    -o "$out2" "너에게 등록된 skill 중 이름이 'zqx-' 로 시작하는 것만 나열해라. 파일시스템을 뒤지지 마라 — ls/find/cat/grep 등 명령 실행 금지. 등록된 skill 목록에서만 골라라. 없으면 '없음'." \
    >/dev/null 2>&1
  agents_seen=$(grep -c 'zqx-agentspath' "$out2" 2>/dev/null || echo 0)
  claude_seen=$(grep -c 'zqx-claudepath' "$out2" 2>/dev/null || echo 0)
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
    "repo_skills_discovery_path": { "verdict": "$skill_answer", "note": "$skill_note" }
  }
}
JSON
