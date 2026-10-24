#!/usr/bin/env bash
# codex/cost-hook.py 계산 시험과 codex/hooks.py 왕복 시험 — 임시 HOME 에서만 돈다. 실제 홈은 건드리지 않는다.
# 사용법: scripts/test-codex-cost-hook.sh
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
T="$(mktemp -d)"
check() {               # check <이름> <기대값> <실제값>
  if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1"; echo "  기대: $2"; echo "  실제: $3"; fail=1; fi
}

# ── cost-hook.py: 고정 rollout 으로 금액 계산 ────────────────
# 1턴 gpt-5.6-sol: 입력 1,000,000(캐시 800,000) 출력 10,000 → 0.2M×4 + 0.8M×0.4 + 0.01M×20 = $1.32
#   같은 합계가 한 번 더 기록돼도 한 번만 센다
# 2턴 gpt-6-luna: 증분 입력 100,000(캐시 50,000) 출력 10,000 → 0.05M×0.1 + 0.05M×0.01 + 0.01M×0.5 = $0.0105
R="$T/rollout.jsonl"
tc() { printf '{"type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":%s,"cached_input_tokens":%s,"cache_write_input_tokens":0,"output_tokens":%s,"reasoning_output_tokens":0,"total_tokens":0}}}}\n' "$1" "$2" "$3"; }
{
  echo '{"type":"session_meta","payload":{}}'
  echo '{"type":"event_msg","payload":{"type":"task_started"}}'
  echo '{"type":"turn_context","payload":{"model":"gpt-5.6-sol"}}'
  echo '{"type":"event_msg","payload":{"type":"token_count","info":null}}'
  tc 1000000 800000 10000
  tc 1000000 800000 10000
  echo '{"type":"event_msg","payload":{"type":"task_started"}}'
  echo '{"type":"turn_context","payload":{"model":"gpt-6-luna"}}'
  tc 1100000 850000 20000
} > "$R"
hook() { printf '{"transcript_path":"%s"}' "$1" | HOME="$T/h" python3 codex/cost-hook.py; }
mkdir -p "$T/h/.codex"
check standard '{"systemMessage": "API 환산 $1.33 · 이번 턴 +$0.01 · 입력 1.1M(캐시 77%) · 출력 20.0k"}' "$(hook "$R")"

# Fast mode 단가: 0.2M×8 + 0.8M×0.8 + 0.01M×40 = $2.64, 0.05M×0.2 + 0.05M×0.02 + 0.01M×1 = $0.021
printf 'service_tier = "fast"\n\n[tui]\nservice_tier = "flex"\n' > "$T/h/.codex/config.toml"
check fast '{"systemMessage": "API 환산 $2.66 · 이번 턴 +$0.02 · 입력 1.1M(캐시 77%) · 출력 20.0k"}' "$(hook "$R")"
rm "$T/h/.codex/config.toml"

# 단가를 모르는 모델만 쓴 스레드, 없는 파일, 깨진 입력 → 아무것도 출력하지 않고 exit 0
{ echo '{"type":"turn_context","payload":{"model":"qwen-local"}}'; tc 5000 0 100; } > "$T/local.jsonl"
check unknown-model '' "$(hook "$T/local.jsonl")"
check missing-file '' "$(hook "$T/nope.jsonl")"
check bad-stdin '' "$(echo 'not json' | HOME="$T/h" python3 codex/cost-hook.py)"

# ── hooks.py: apply 2회(멱등) → restore ─────────────────────
run() { HOME="$T/$1" python3 codex/hooks.py "$2"; }
want_cmd() { echo "python3 $T/$1/.codex/cost-hook.py"; }
stop_cmds() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("|".join(h["command"] for g in d["hooks"].get("Stop",[]) for h in g["hooks"]))' "$1"; }

# (a) hooks.json 없음 → 생성 → restore 로 삭제
mkdir -p "$T/absent/.codex"
run absent check
run absent apply >/dev/null
check absent-apply "$(want_cmd absent)" "$(stop_cmds "$T/absent/.codex/hooks.json")"
run absent apply | grep -q '이미 최신' || { echo "FAIL absent: 두 번째 apply 가 멱등이 아님"; fail=1; }
run absent restore >/dev/null
[ ! -e "$T/absent/.codex/hooks.json" ] && echo "ok   absent-restore" || { echo "FAIL absent-restore: 설치 전에 없던 hooks.json 이 남음"; fail=1; }

# (b) 다른 도구의 훅이 있음 → 그 훅과 다른 키는 그대로, 비용 훅만 넣고 뺀다
mkdir -p "$T/shared/.codex"
cat > "$T/shared/.codex/hooks.json" <<'JSON'
{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/opt/other/stop.sh", "timeout": 5}]}],
           "SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": "/opt/other/start.sh"}]}]},
 "extra": 1}
JSON
chmod 640 "$T/shared/.codex/hooks.json"
cp "$T/shared/.codex/hooks.json" "$T/shared.expected"
run shared apply >/dev/null
run shared apply >/dev/null
check shared-apply "/opt/other/stop.sh|$(want_cmd shared)" "$(stop_cmds "$T/shared/.codex/hooks.json")"
check shared-mode 640 "$(python3 -c 'import os,sys; print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])' "$T/shared/.codex/hooks.json")"
# 설치 뒤에 다른 도구가 훅을 더 넣어도 restore 는 비용 훅만 뺀다
python3 - "$T/shared/.codex/hooks.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
d["hooks"]["PreToolUse"] = [{"hooks": [{"type": "command", "command": "/opt/other/pre.sh"}]}]
json.dump(d, open(p, "w"))
PY
run shared restore >/dev/null
check shared-restore "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); d["hooks"]["PreToolUse"]=[{"hooks":[{"type":"command","command":"/opt/other/pre.sh"}]}]; print(json.dumps(d,sort_keys=True))' "$T/shared.expected")" \
  "$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])),sort_keys=True))' "$T/shared/.codex/hooks.json")"

# (c) 깨진 JSON·예상 밖 구조 → check·apply 실패, 파일과 백업 디렉터리 불변
reject() {              # reject <이름> <내용>
  mkdir -p "$T/$1/.codex"; printf '%s' "$2" > "$T/$1/.codex/hooks.json"
  if run "$1" check 2>/dev/null; then echo "FAIL $1: check 가 통과함"; fail=1; fi
  if run "$1" apply >/dev/null 2>&1; then echo "FAIL $1: apply 가 통과함"; fail=1; fi
  [ "$(cat "$T/$1/.codex/hooks.json")" = "$2" ] || { echo "FAIL $1: 실패했는데 파일이 바뀜"; fail=1; }
  [ ! -e "$T/$1/.config/dotfiles/backup" ] || { echo "FAIL $1: 실패했는데 백업 디렉터리가 생김"; fail=1; }
  echo "ok   $1 (거부)"
}
reject broken '{"hooks": {'
reject badshape '{"hooks": {"Stop": {"command": "x"}}}'

rm -rf "$T"
[ "$fail" = 0 ] && echo "전체 통과" || { echo "실패 있음"; exit 1; }
