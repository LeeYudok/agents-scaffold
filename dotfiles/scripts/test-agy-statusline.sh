#!/usr/bin/env bash
# Antigravity CLI(agy) statusline 시험 — 실제 홈은 건드리지 않는다.
#   (1) agy/settings.py: 임시 HOME 에서 apply 2회(멱등) → restore 후 원본과 바이트 비교. 다른 키·사용자 선택 키 보존, 깨진 JSON 거부
#   (2) agy/statusline-command.sh: 고정 payload 렌더 결과 비교, 빈 입력·깨진 입력에서도 exit 0
# 사용법: scripts/test-agy-statusline.sh
set -uo pipefail
cd "$(dirname "$0")/.."
PY=agy/settings.py
fail=0
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
bad() { echo "FAIL $*"; fail=1; }
run() { local h="$T/$1"; shift; HOME="$h" python3 "$PY" "$@"; }
cfg() { echo "$T/$1/.gemini/antigravity-cli/settings.json"; }

# (a) 파일 없음 → apply 가 만들고 restore 가 지운다
mkdir -p "$T/absent/.gemini/antigravity-cli"
run absent apply >/dev/null || bad "absent: apply 실패"
python3 - "$(cfg absent)" "$T/absent" <<'PY' || bad "absent: statusLine 값이 기대와 다름"
import json, sys
d = json.load(open(sys.argv[1]))
assert d == {"statusLine": {"type": "command", "command": f"bash {sys.argv[2]}/.gemini/antigravity-cli/statusline-command.sh", "enabled": True}}, d
PY
cp "$(cfg absent)" "$T/absent.applied"
run absent apply | grep -q '이미 최신' || bad "absent: 두 번째 apply 가 멱등이 아님"
cmp -s "$(cfg absent)" "$T/absent.applied" || bad "absent: 두 번째 apply 가 파일을 바꿈"
run absent restore >/dev/null
[ ! -e "$(cfg absent)" ] || bad "absent: restore 후 파일이 남음"
echo "ok   absent"

# (b) 다른 키 + 사용자 statusLine(선택 키 포함) → 선택 키 보존, restore 는 원본과 바이트까지 같게
mkdir -p "$T/keep/.gemini/antigravity-cli"
cat > "$(cfg keep)" <<'JSON'
{
  "model": "gemini-3.5-pro",
  "statusLine": {
    "type": "command",
    "command": "my-status",
    "padding": 1,
    "stack_with_default": true
  }
}
JSON
chmod 640 "$(cfg keep)"; cp "$(cfg keep)" "$T/keep.expected"
run keep apply >/dev/null || bad "keep: apply 실패"
python3 - "$(cfg keep)" <<'PY' || bad "keep: 다른 키·선택 키가 보존되지 않음"
import json, sys
d = json.load(open(sys.argv[1]))
s = d["statusLine"]
assert d["model"] == "gemini-3.5-pro" and s["padding"] == 1 and s["stack_with_default"] is True, d
assert s["command"].endswith("/.gemini/antigravity-cli/statusline-command.sh") and s["enabled"] is True, d
PY
[ "$(stat -c %a "$(cfg keep)" 2>/dev/null || stat -f %Lp "$(cfg keep)")" = 640 ] || bad "keep: mode 가 보존되지 않음"
run keep restore >/dev/null
cmp -s "$(cfg keep)" "$T/keep.expected" || { bad "keep: restore 결과가 원본과 다름"; diff "$T/keep.expected" "$(cfg keep)"; }
run keep restore >/dev/null
cmp -s "$(cfg keep)" "$T/keep.expected" || bad "keep: 두 번째 restore 가 파일을 바꿈"
echo "ok   keep"

# (c) 깨진 JSON·최상위가 배열 → check/apply 거부, 파일 불변
for case in broken array; do
  mkdir -p "$T/$case/.gemini/antigravity-cli"
  if [ "$case" = broken ]; then printf '{"statusLine": ' > "$(cfg $case)"; else printf '[]\n' > "$(cfg $case)"; fi
  cp "$(cfg $case)" "$T/$case.expected"
  run "$case" check 2>/dev/null && bad "$case: check 가 통과함"
  run "$case" apply 2>/dev/null && bad "$case: apply 가 통과함"
  cmp -s "$(cfg $case)" "$T/$case.expected" || bad "$case: 파일이 바뀜"
done
echo "ok   broken/array (거부)"

# (d) 기록 없는 머신에서 restore 는 아무것도 하지 않는다
mkdir -p "$T/norecord/.gemini/antigravity-cli"; printf '{"statusLine": {"type": "command", "command": "x"}}\n' > "$(cfg norecord)"
cp "$(cfg norecord)" "$T/norecord.expected"
run norecord restore >/dev/null
cmp -s "$(cfg norecord)" "$T/norecord.expected" || bad "norecord: 기록 없이 파일을 바꿈"
echo "ok   norecord"

# (e) 렌더 — ANSI 색을 벗겨 비교. 한도는 남은 비율 → 사용률로 바뀌어야 한다
if command -v jq >/dev/null; then
  payload='{"cwd":"/tmp/proj","model":{"id":"gemini-3.5-flash","display_name":"Gemini 3.5 Flash"},"agent_state":"working",
    "vcs":{"type":"git","branch":"main","dirty":true},
    "context_window":{"context_window_size":1048576,"total_input_tokens":88244,"total_output_tokens":61074,"used_percentage":14.24},
    "quota":{"gemini-5h":{"remaining_fraction":0.85,"reset_in_seconds":3600},"gemini-weekly":{"remaining_fraction":0.1,"reset_in_seconds":90000}},
    "task_count":2,"artifact_count":0,"subagents":["a","b"],"sandbox":{"enabled":true},"version":"1.2.3"}'
  got="$(printf '%s' "$payload" | bash agy/statusline-command.sh | sed 's/\x1b\[[0-9;]*m//g')"
  want="proj │ git: main * │ Gemini 3.5 Flash working │ █░░░░░░░░░ 14% (88k/1048k) ↑61k
G 5h 15%~1h00m  7d 90%~1d1h │ tasks 2 agents 2 │ sandbox │ v1.2.3"
  [ "$got" = "$want" ] || { bad "render: 출력이 기대와 다름"; printf '%s\n---\n%s\n' "$want" "$got"; }
  for input in '{}' 'not json' '{"context_window":{"used_percentage":"error"},"quota":{"gemini-5h":{"remaining_fraction":"x"}}}'; do
    out="$(printf '%s' "$input" | bash agy/statusline-command.sh 2>&1)" || bad "render: '$input' 에서 exit != 0"
    printf '%s' "$out" | grep -q '%' && bad "render: '$input' 에서 잘못된 수치를 표시함"
  done
  echo "ok   render"
else
  echo "skip render (jq 없음)"
fi

[ "$fail" = 0 ] && echo "전체 통과" || echo "실패 있음"
exit "$fail"
