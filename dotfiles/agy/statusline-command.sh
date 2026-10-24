#!/bin/bash
# Antigravity CLI (agy) statusLine script
# Reads the status JSON on stdin, prints a two-line status. claude/statusline-command.sh 와 같은 모양·색을 쓴다.
#
#   1행: 경로 │ git 브랜치 │ 모델 · 에이전트 상태 │ 컨텍스트 막대 · 사용률 (입력/창) · 출력 토큰
#   2행: Gemini 5h·7d 사용률(리셋까지) │ 3P(타사 모델) 5h·7d │ 작업·산출물·서브에이전트 수 │ sandbox │ vim 모드 │ 버전
#
# 입력 필드(Antigravity CLI 가 상태가 바뀔 때마다 stdin 으로 넘긴다):
#   cwd, workspace.current_dir, model.display_name|id, agent_state, vcs.{branch,dirty},
#   context_window.{used_percentage,total_input_tokens,total_output_tokens,context_window_size},
#   quota["gemini-5h"|"gemini-weekly"|"3p-5h"|"3p-weekly"].{remaining_fraction,reset_in_seconds},
#   task_count, artifact_count, subagents[], sandbox.{enabled,allow_network}, vim.mode, version
# 한도는 남은 비율(remaining_fraction)로 오지만 Claude statusline 과 맞추려고 사용률(100 - 남은 %)로 보여준다.
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
IFS=$'\x1f' read -r cwd model state vcs_type branch dirty \
  used_pct in_tok out_tok win_size \
  g5 g5_reset gw gw_reset p5 p5_reset pw pw_reset \
  tasks artifacts subagents sandbox sandbox_net vim_mode version <<EOF
$(printf '%s' "$input" | jq -r '
  def s: if . == null then "" else tostring end;
  def n: if type == "number" then tostring else "" end;            # 숫자가 아닌 값(문자열·null)은 빈 값
  def used: if type == "number" then (100 - . * 100) | tostring else "" end;
  def q($k): (.quota // {})[$k] // {};
  [ ((.workspace.current_dir // .cwd) | s),
    ((.model | if type == "object" then (.display_name // .id) else . end) | s),
    (.agent_state | s),
    (.vcs.type | s),
    (.vcs.branch | s),
    (if .vcs.dirty == true then "1" else "" end),
    (.context_window.used_percentage | n),
    (.context_window.total_input_tokens | n),
    (.context_window.total_output_tokens | n),
    (.context_window.context_window_size | n),
    (q("gemini-5h").remaining_fraction | used),
    (q("gemini-5h").reset_in_seconds | n),
    (q("gemini-weekly").remaining_fraction | used),
    (q("gemini-weekly").reset_in_seconds | n),
    (q("3p-5h").remaining_fraction | used),
    (q("3p-5h").reset_in_seconds | n),
    (q("3p-weekly").remaining_fraction | used),
    (q("3p-weekly").reset_in_seconds | n),
    (.task_count | n),
    (.artifact_count | n),
    (if (.subagents | type) == "array" then (.subagents | length | tostring) else "" end),
    (if .sandbox.enabled == true then "1" else "" end),
    (if .sandbox.allow_network == true then "1" else "" end),
    (.vim.mode | s),
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
left() {                                                          # 초 → 2d3h / 1h02m / 12m / 34s (리셋까지 남은 시간)
  local s
  [ -n "$1" ] || return
  s=$(int "$1")
  if   [ "$s" -ge 86400 ]; then printf '%dd%dh' $(( s / 86400 )) $(( s % 86400 / 3600 ))
  elif [ "$s" -ge 3600 ];  then printf '%dh%02dm' $(( s / 3600 )) $(( s % 3600 / 60 ))
  elif [ "$s" -ge 60 ];    then printf '%dm' $(( s / 60 ))
  else printf '%ds' "$s"; fi
}
nz() { [ -n "$1" ] && [ "$(int "$1")" != 0 ]; }                   # 비어 있지 않고 0 이 아님

# ── 1행 ─────────────────────────────────────────────────────

# --- path segment ---
dir_name=$(basename "$cwd" 2>/dev/null)
[ -z "$dir_name" ] && dir_name="?"
path_part="${FG_PATH}${BOLD}${dir_name}${RESET}"

# --- git branch: payload 의 vcs 를 쓰고, 없으면 git 으로 직접 확인 ---
git_part=""
if [ -z "$branch" ] && [ -z "$vcs_type" ] && [ -n "$cwd" ] \
    && git -C "$cwd" --no-optional-locks rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short -q HEAD 2>/dev/null)
  [ -z "$branch" ] && branch=$(git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
  [ -n "$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null)" ] && dirty=1
fi
if [ -n "$branch" ]; then
  if [ -n "$dirty" ]; then
    git_part="${SEP}${FG_GIT_DIRTY}git: ${branch} *${RESET}"
  else
    git_part="${SEP}${FG_GIT_CLEAN}git: ${branch}${RESET}"
  fi
fi

# --- model + 에이전트 상태 (idle 은 생략) ---
model_part=""
if [ -n "$model" ]; then
  model_part="${SEP}${FG_MODEL}${model}${RESET}"
  [ -n "$state" ] && [ "$state" != "idle" ] && model_part="${model_part}${FG_MUTE} ${state}${RESET}"
fi

# --- context usage: mini progress bar + colored percentage + 입출력 토큰 ---
ctx_part=""
if [ -n "$used_pct" ]; then
  used_int=$(int "$used_pct")
  [ "$used_int" -gt 100 ] && used_int=100

  if [ "$used_int" -ge 80 ]; then
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

  ctx_part="${SEP}${ctx_color}${bar} ${used_int}%${RESET}"
  [ -n "$in_tok" ] && [ -n "$win_size" ] && ctx_part="${ctx_part} ${FG_MUTE}($(k "$in_tok")/$(k "$win_size"))${RESET}"
  [ -n "$out_tok" ] && ctx_part="${ctx_part}${FG_MUTE} \xe2\x86\x91$(k "$out_tok")${RESET}"
fi

# ── 2행 ─────────────────────────────────────────────────────

# --- 사용 한도: <라벨> 5h 사용률↺리셋까지  7d 사용률↺리셋까지 (80% 이상 경고색) ---
quota() {     # quota <라벨> <5h 사용률> <5h 리셋초> <주간 사용률> <주간 리셋초>
  local out="" seg r u color
  for pair in "5h:$2:$3" "7d:$4:$5"; do
    IFS=: read -r name u r <<<"$pair"
    [ -n "$u" ] || continue
    u=$(int "$u"); [ "$u" -lt 0 ] && u=0
    if [ "$u" -ge 80 ]; then color="$FG_CRIT"; elif [ "$u" -ge 60 ]; then color="$FG_WARN"; else color="$FG_MUTE"; fi
    seg="${color}${name} ${u}%${RESET}"
    r=$(left "$r"); [ -n "$r" ] && seg="${seg}${FG_MUTE}~${r}${RESET}"
    [ -n "$out" ] && out="${out}  ${seg}" || out="$seg"
  done
  [ -n "$out" ] && printf '%s' "${FG_MUTE}$1 ${RESET}${out}"
}
gem_part=$(quota "G" "$g5" "$g5_reset" "$gw" "$gw_reset")
tp_part=$(quota "3P" "$p5" "$p5_reset" "$pw" "$pw_reset")

# --- 작업·산출물·서브에이전트 (0 이면 생략) ---
work_part=""
for pair in "tasks:$tasks" "artifacts:$artifacts" "agents:$subagents"; do
  name=${pair%%:*}; n=${pair#*:}
  nz "$n" || continue
  [ -n "$work_part" ] && work_part="${work_part} "
  work_part="${work_part}${name} $(int "$n")"
done
[ -n "$work_part" ] && work_part="${FG_MUTE}${work_part}${RESET}"

# --- sandbox · vim · 버전 ---
sandbox_part=""
if [ -n "$sandbox" ]; then
  sandbox_part="${FG_OK}sandbox${RESET}"
  [ -n "$sandbox_net" ] && sandbox_part="${sandbox_part}${FG_MUTE}+net${RESET}"
fi
vim_part=""
[ -n "$vim_mode" ] && vim_part="${FG_MUTE}${vim_mode}${RESET}"
ver_part=""
[ -n "$version" ] && ver_part="${FG_MUTE}v${version}${RESET}"

# 2행은 값이 있는 구간만 " │ " 로 이어 붙인다
line2=""
for seg in "$gem_part" "$tp_part" "$work_part" "$sandbox_part" "$vim_part" "$ver_part"; do
  [ -n "$seg" ] || continue
  [ -n "$line2" ] && line2="${line2}${SEP}${seg}" || line2="$seg"
done

printf "%b%b%b%b\n" "$path_part" "$git_part" "$model_part" "$ctx_part"
[ -n "$line2" ] && printf "%b\n" "$line2"
exit 0
