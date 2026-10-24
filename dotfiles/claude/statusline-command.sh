#!/bin/bash
# Claude Code statusLine script
# Reads JSON on stdin, prints a two-line status.
#
#   1행: 경로 │ git 브랜치 │ 모델 · 추론 강도 · thinking · fast │ 컨텍스트 막대 · 사용률 (입력/창) · 출력 토큰
#   2행: 세션 비용 │ 소요 시간(전체·API) │ 변경 라인 │ 캐시 적중률 │ 5h·7d 한도(리셋 시각) │ 출력 스타일 │ 버전
#
# 렌더 빈도가 높으므로 jq 는 한 번만 호출해 US(0x1f) 로 이어 붙인 모든 필드를 한 줄로 받는다.
# 없는 필드(구형 CLI·축약 payload)는 해당 구간을 통째로 생략한다.

input=$(cat)

# --- palette (256-color, dim/muted for a quieter look) ---
RESET=$'\033[0m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
SEP="${DIM} \xe2\x94\x82 ${RESET}"   # " │ "

FG_PATH=$'\033[38;5;110m'   # muted steel blue
FG_GIT_CLEAN=$'\033[38;5;108m'   # sage green
FG_GIT_DIRTY=$'\033[38;5;179m'   # muted amber
FG_MODEL=$'\033[38;5;73m'   # dusty teal
FG_OK=$'\033[38;5;108m'
FG_WARN=$'\033[38;5;179m'
FG_CRIT=$'\033[38;5;167m'   # muted red
FG_COST=$'\033[38;5;144m'   # dusty khaki
FG_MUTE=$'\033[38;5;244m'   # gray

# --- 한 번의 jq 호출로 전부 읽기 ---
# 구분자는 US(0x1f). 탭은 IFS 공백류라 빈 필드가 합쳐져 값이 밀린다.
IFS=$'\x1f' read -r cwd model effort thinking fast_mode \
  used_pct in_tok out_tok win_size exceeds \
  cost dur_ms api_ms lines_add lines_del \
  cache_warm cache_hit five five_reset week week_reset \
  style version <<EOF
$(printf '%s' "$input" | jq -r '
  def s: if . == null then "" else tostring end;
  [ ((.workspace.current_dir // .cwd) | s),
    (.model.display_name | s),
    (.effort.level | s),
    (if .thinking.enabled == true then "1" else "" end),
    (if .fast_mode == true then "1" else "" end),
    (.context_window.used_percentage | s),
    (.context_window.total_input_tokens | s),
    (.context_window.total_output_tokens | s),
    (.context_window.context_window_size | s),
    (if .exceeds_200k_tokens == true then "1" else "" end),
    (.cost.total_cost_usd | s),
    (.cost.total_duration_ms | s),
    (.cost.total_api_duration_ms | s),
    (.cost.total_lines_added | s),
    (.cost.total_lines_removed | s),
    (if .prompt_cache.warm == true then "1" else "" end),
    (.prompt_cache.hit_ratio | s),
    (.rate_limits.five_hour.used_percentage | s),
    (.rate_limits.five_hour.resets_at | s),
    (.rate_limits.seven_day.used_percentage | s),
    (.rate_limits.seven_day.resets_at | s),
    (.output_style.name | s),
    (.version | s) ] | join("\u001f")' 2>/dev/null)
EOF

# --- 헬퍼 ---
int() { [ -n "$1" ] && printf '%.0f' "$1" 2>/dev/null; }          # 실수/정수 → 정수 (빈 값은 빈 출력)
k() {                                                             # 토큰 수 → 1000 이상은 k 단위
  local n
  [ -n "$1" ] || return
  n=$(int "$1")
  if [ "$n" -ge 1000 ]; then printf '%dk' $(( n / 1000 )); else printf '%d' "$n"; fi
}
hhmm() {                                                          # epoch → HH:MM (BSD/GNU date 양쪽)
  [ -n "$1" ] || return
  date -r "$1" +%H:%M 2>/dev/null || date -d "@$1" +%H:%M 2>/dev/null
}
dur() {                                                           # ms → 1h02m / 12m / 34s
  local ms="${1:-}" s
  [ -n "$ms" ] || return
  s=$(( $(int "$ms") / 1000 ))
  if   [ "$s" -ge 3600 ]; then printf '%dh%02dm' $(( s / 3600 )) $(( s % 3600 / 60 ))
  elif [ "$s" -ge 60 ];   then printf '%dm' $(( s / 60 ))
  else printf '%ds' "$s"; fi
}

# ── 1행 ─────────────────────────────────────────────────────

# --- path segment ---
dir_name=$(basename "$cwd" 2>/dev/null)
[ -z "$dir_name" ] && dir_name="?"
path_part="${FG_PATH}${BOLD}${dir_name}${RESET}"

# --- git branch ---
git_part=""
if [ -n "$cwd" ] && git -C "$cwd" --no-optional-locks rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short -q HEAD 2>/dev/null)
  if [ -z "$branch" ]; then
    branch=$(git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
  fi
  if [ -n "$branch" ]; then
    if [ -n "$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null)" ]; then
      git_part="${SEP}${FG_GIT_DIRTY}git: ${branch} *${RESET}"
    else
      git_part="${SEP}${FG_GIT_CLEAN}git: ${branch}${RESET}"
    fi
  fi
fi

# --- model + 추론 강도 + thinking + fast ---
model_part=""
if [ -n "$model" ]; then
  flags=""
  [ -n "$effort" ] && flags="${flags} ${effort}"
  [ -n "$thinking" ] && flags="${flags} think"
  [ -n "$fast_mode" ] && flags="${flags} fast"
  model_part="${SEP}${FG_MODEL}${model}${RESET}"
  [ -n "$flags" ] && model_part="${model_part}${FG_MUTE}${flags}${RESET}"
fi

# --- context usage: mini progress bar + colored percentage + 입출력 토큰 ---
ctx_part=""
if [ -n "$used_pct" ]; then
  used_int=$(int "$used_pct")
  [ "$used_int" -gt 100 ] && used_int=100

  if [ "$used_int" -ge 80 ] || [ -n "$exceeds" ]; then
    ctx_color="$FG_CRIT"
  elif [ "$used_int" -ge 60 ]; then
    ctx_color="$FG_WARN"
  else
    ctx_color="$FG_OK"
  fi

  bar_width=10
  filled=$(( used_int * bar_width / 100 ))
  empty=$(( bar_width - filled ))
  bar=""
  for ((i=0; i<filled; i++)); do bar="${bar}\xe2\x96\x88"; done
  for ((i=0; i<empty; i++)); do bar="${bar}\xe2\x96\x91"; done

  ctx_part="${SEP}${ctx_color}${bar} ${used_int}%${RESET} ${FG_MUTE}($(k "$in_tok")/$(k "$win_size"))${RESET}"
  [ -n "$out_tok" ] && ctx_part="${ctx_part}${FG_MUTE} \xe2\x86\x91$(k "$out_tok")${RESET}"
  [ -n "$exceeds" ] && ctx_part="${ctx_part} ${FG_CRIT}>200k${RESET}"
fi

# ── 2행 ─────────────────────────────────────────────────────

# --- 세션 비용 + 소요 시간 ---
cost_part=""
if [ -n "$cost" ]; then
  cost_part="${FG_COST}\$$(printf '%.2f' "$cost")${RESET}"
  t=$(dur "$dur_ms")
  a=$(dur "$api_ms")
  [ -n "$t" ] && cost_part="${cost_part} ${FG_MUTE}${t}${RESET}"
  [ -n "$a" ] && cost_part="${cost_part}${FG_MUTE}(api ${a})${RESET}"
fi

# --- 변경 라인 ---
diff_part=""
if [ -n "$lines_add" ] || [ -n "$lines_del" ]; then
  if [ "$(int "${lines_add:-0}")" -ne 0 ] || [ "$(int "${lines_del:-0}")" -ne 0 ]; then
    diff_part="${FG_OK}+${lines_add:-0}${RESET}${FG_MUTE}/${RESET}${FG_CRIT}-${lines_del:-0}${RESET}"
  fi
fi

# --- 프롬프트 캐시 적중률 ---
cache_part=""
if [ -n "$cache_hit" ]; then
  hit=$(printf '%.0f' "$(echo "$cache_hit" | awk '{print $1*100}')" 2>/dev/null)
  if [ -n "$hit" ]; then
    [ -n "$cache_warm" ] && cache_color="$FG_OK" || cache_color="$FG_MUTE"
    cache_part="${FG_MUTE}cache ${RESET}${cache_color}${hit}%${RESET}"
  fi
fi

# --- claude.ai rate limits (+ 리셋 시각) ---
rate_part=""
if [ -n "$five" ] || [ -n "$week" ]; then
  rl=""
  if [ -n "$five" ]; then
    rl="5h $(int "$five")%"
    r=$(hhmm "$five_reset"); [ -n "$r" ] && rl="${rl}~${r}"
  fi
  if [ -n "$week" ]; then
    w="7d $(int "$week")%"
    r=$(hhmm "$week_reset"); [ -n "$r" ] && w="${w}~${r}"
    [ -n "$rl" ] && rl="${rl}  ${w}" || rl="$w"
  fi
  rate_part="${FG_MUTE}${rl}${RESET}"
fi

# --- 출력 스타일 + 버전 ---
style_part=""
[ -n "$style" ] && style_part="${FG_MUTE}${style}${RESET}"
ver_part=""
[ -n "$version" ] && ver_part="${FG_MUTE}v${version}${RESET}"

# 2행은 값이 있는 구간만 " │ " 로 이어 붙인다
line2=""
for seg in "$cost_part" "$diff_part" "$cache_part" "$rate_part" "$style_part" "$ver_part"; do
  [ -n "$seg" ] || continue
  [ -n "$line2" ] && line2="${line2}${SEP}${seg}" || line2="$seg"
done

printf "%b%b%b%b\n" "$path_part" "$git_part" "$model_part" "$ctx_part"
[ -n "$line2" ] && printf "%b\n" "$line2"
exit 0
