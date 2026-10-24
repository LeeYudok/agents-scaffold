#!/usr/bin/env bash
# 스킬 전역(또는 프로젝트) 설치 — doksam-skills 의 install.sh 를 이 레포로 옮긴 것 (agents-scaffold #78).
# Claude Code / Codex / Gemini(Antigravity) 가 인식하는 경로에 스킬을 노출한다. 기본은 심링크라
# 이 레포에서 SKILL.md 를 고치면 세 런타임에 바로 반영된다.
#
# 대상: .claude/skills 의 yd-* 와 doksam 출신 4종(handoff·docs-sync·memory-factcheck·skill-evolve).
#       --personal 이면 presets/skills-personal 의 옵트인 yd-* 도. scaffold 베이스 스킬
#       (review·status 등)은 {{PROJECT_NAME}} 치환이 필요해 프로젝트 설치(bin/agents-scaffold.sh) 전용이다.
#
# 설치 원천은 매번 다시 만드는 .skills-dist/skills/<스킬>/ 다(git 무시). 스킬 폴더의 항목은 원본을 가리키는
# 링크이고, agents/ 의 런타임별 어댑터는 에이전트 원본(.claude/agents/<스킬>.md)에서 생성한다 —
# Codex·agy 어댑터를 따로 손으로 두지 않는다(bin/agents-scaffold.sh 의 emit_agents 와 같은 원칙).
# 스킬 폴더에 새 최상위 항목을 추가했으면 이 스크립트를 다시 돌려 링크를 갱신한다.
set -uo pipefail

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PERSONAL=0
_args=()
for _a in "$@"; do
  if [[ "$_a" == "--personal" ]]; then PERSONAL=1; else _args+=("$_a"); fi
done
set -- ${_args[@]+"${_args[@]}"}

DIST="$SRC_ROOT/.skills-dist"
if ! python3 - "$SRC_ROOT" "$DIST" "$PERSONAL" <<'PY'
import os, shutil, sys
src, dist, personal = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
MERGED = ("handoff", "docs-sync", "memory-factcheck", "skill-evolve")
bases = [os.path.join(src, ".claude")]
if personal:
    bases.append(os.path.join(src, "presets", "skills-personal", ".claude"))
skills_out = os.path.join(dist, "skills")
if os.path.isdir(skills_out):
    shutil.rmtree(skills_out)
os.makedirs(skills_out)

def front(path):
    with open(path, encoding="utf-8") as f:
        text = f.read().replace("\r", "")
    lines = text.split("\n")
    end = lines.index("---", 1)
    fm = {}
    for ln in lines[1:end]:
        if ":" in ln and not ln.startswith((" ", "-")):
            k, v = ln.split(":", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            fm[k.strip()] = v
    return fm, "\n".join(lines[end + 1:]).strip("\n") + "\n"

for base in bases:
    sdir = os.path.join(base, "skills")
    for name in sorted(os.listdir(sdir)):
        real = os.path.join(sdir, name)
        if not os.path.isfile(os.path.join(real, "SKILL.md")):
            continue
        if not (name.startswith("yd-") or name in MERGED):
            continue
        out = os.path.join(skills_out, name)
        os.makedirs(out)
        for entry in sorted(os.listdir(real)):
            if entry in ("__pycache__", "agents"):
                continue
            os.symlink(os.path.join(real, entry), os.path.join(out, entry))
        agent = os.path.join(base, "agents", name + ".md")
        if os.path.isfile(agent):
            fm, body = front(agent)
            adir = os.path.join(out, "agents")
            os.makedirs(adir)
            os.symlink(agent, os.path.join(adir, "claude.md"))
            desc = fm.get("description", "")
            esc = desc.replace("\\", "\\\\").replace('"', '\\"')
            if "'''" not in body:
                with open(os.path.join(adir, "codex.toml"), "w", encoding="utf-8") as f:
                    f.write(f'name = "{name.replace("-", "_")}"\ndescription = "{esc}"\n'
                            f"developer_instructions = '''\n{body}'''\n")
            with open(os.path.join(adir, "antigravity.md"), "w", encoding="utf-8") as f:
                q = desc.replace("'", "''")
                f.write(f"---\nname: '{name}'\ndescription: '{q}'\n---\n\n{body}")
PY
then
  echo "오류: 설치 원천(.skills-dist) 생성 실패 — python3 가 필요하다" >&2
  exit 1
fi

REPO_ROOT="$DIST"
SKILL_NAMES=()
for d in "$REPO_ROOT"/skills/*/; do
  [[ -f "$d/SKILL.md" ]] && SKILL_NAMES+=("$(basename "$d")")
done
# Agent Adapter 원본은 각 스킬이 소유한다: skills/<skill>/agents/{claude.md,
# codex.toml, antigravity.md}. 스킬명은 여기서 하드코딩하지 않는다.

MODE="symlink"     # symlink | copy
ACTION="install"   # install | uninstall | verify | list
WITH_AGENT=0
SELECTION=""
DRY_RUN=0
FORCE=0
PROJECT=""
VENDOR=""
VENDOR_CHECK=0
VENDOR_SKILLS=()

ok=0
skipped=0
failed=0

usage() {
  cat <<'USAGE'
사용법: scripts/install-skills.sh [--personal] [옵션]

옵션:
  (없음)              전역 3경로에 심링크를 만든다
                        ~/.agents/skills/                (Codex, Gemini CLI)
                        ~/.claude/skills/                (Claude Code)
                        ~/.gemini/config/skills/         (Antigravity, agy)
  --copy              심링크 대신 복사한다
  --project <dir>     전역 대신 해당 레포의 프로젝트 스킬 경로에 설치한다
                        <dir>/.claude/skills/            (Claude Code)
                        <dir>/.agents/skills/            (Codex, Antigravity)
  --skill-only        Skill 만 설치한다 (기본값)
  --with-agent        Skill 과 이름 있는 Agent Adapter 를 함께 설치한다
                      원본은 skills/<skill>/agents/ 가 소유한다
                        claude.md      -> .claude/agents/<skill>.md
                        codex.toml     -> .codex/agents/<skill_underscored>.toml
                        antigravity.md -> agy 플러그인으로 등록 (전역 설치 시)
  --vendor <dir>      프로젝트에 vendoring 된 스킬 사본(<dir>/.agents/skills/)을
                      리포 최신본으로 파일 단위 갱신한다 — 심링크가 아니라 복사이며,
                      사본에만 있는 파일은 보고만 하고 지우지 않는다.
                      __pycache__/*.pyc/.DS_Store 는 제외한다
    --skill <name>    갱신할 스킬을 지정한다 (반복 가능, 미지정 시 사본에 이미
                      있는 스킬만 갱신)
    --check           갱신 없이 차이 유무만 종료코드로 반환한다 (0=최신, 1=뒤처짐)
  --verify            설치하지 않고, 각 런타임에 실제로 등록됐는지 확인한다
                      런타임 CLI 가 있으면 그 출력에 물어본다 (파일 존재는
                      등록의 증거가 아니다 — 이슈 #110)
                        Codex        codex debug prompt-input 의 스킬 목록
                        Antigravity  agy agents 의 에이전트 목록
                      CLI 가 없는 런타임은 경로 존재로 대신 보고 skip 표시한다.
                      Agent Adapter 는 --with-agent 를 함께 준 경우에만 본다
  --list              설치하지 않고, 스킬마다 에이전트 유무와 런타임별 설치
                      상태를 표로 보여준다 (경로 기준, 이슈 #177)
                        ok      링크·파일이 있다
                        broken  링크는 있는데 대상이 없다
                        -       없다 (에이전트 열은 어댑터가 없으면 비운다)
                      등록 여부를 런타임에 물어보려면 --verify 를 쓴다
  --dry-run           수행할 작업만 출력하고 파일시스템은 바꾸지 않는다
  --uninstall         이 레포를 가리키는 심링크를 제거한다
  --force             충돌하는 기존 항목을 교체한다
  -h, --help          이 도움말

동작 규칙:
  - 이미 이 레포를 가리키는 심링크면 skip 한다 (멱등)
  - 다른 것을 가리키는 심링크나 실제 디렉터리가 있으면 덮어쓰지 않고
    exit 1 한다. --force 를 준 경우에만 교체한다
  - --uninstall 은 이 레포를 가리키는 심링크만 제거한다. 실제 디렉터리
    (--copy 설치분 등)는 경로를 안내하고 손대지 않는다
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --copy)      MODE="copy"; shift ;;
    --skill-only)
      if [[ "$SELECTION" == "agent" ]]; then
        echo "오류: --skill-only 와 --with-agent 는 함께 쓸 수 없다" >&2
        exit 1
      fi
      SELECTION="skill"; WITH_AGENT=0; shift ;;
    --with-agent)
      if [[ "$SELECTION" == "skill" ]]; then
        echo "오류: --skill-only 와 --with-agent 는 함께 쓸 수 없다" >&2
        exit 1
      fi
      SELECTION="agent"; WITH_AGENT=1; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    --verify)    ACTION="verify"; shift ;;
    --list)      ACTION="list"; shift ;;
    --force)     FORCE=1; shift ;;
    --project)
      if [[ $# -lt 2 ]]; then
        echo "오류: --project 에 디렉터리 인자가 필요하다" >&2
        exit 1
      fi
      PROJECT="$2"; shift 2 ;;
    --vendor)
      if [[ $# -lt 2 ]]; then
        echo "오류: --vendor 에 디렉터리 인자가 필요하다" >&2
        exit 1
      fi
      VENDOR="$2"; shift 2 ;;
    --check)     VENDOR_CHECK=1; shift ;;
    --skill)
      if [[ $# -lt 2 ]]; then
        echo "오류: --skill 에 스킬명 인자가 필요하다" >&2
        exit 1
      fi
      VENDOR_SKILLS+=("$2"); shift 2 ;;
    -h|--help)   usage; exit 0 ;;
    *)
      echo "오류: 알 수 없는 옵션 '$1'" >&2
      usage >&2
      exit 1 ;;
  esac
done

if [[ ${#SKILL_NAMES[@]} -eq 0 ]]; then
  echo "오류: skills/ 아래에 SKILL.md 를 가진 스킬이 없다" >&2
  exit 1
fi

# ---- vendoring 사본 갱신 (이슈 #79) ----
# 프로젝트 리포에 커밋된 스킬 사본은 전역 심링크 재설치로는 갱신되지 않는다.
# 여기서 파일 단위로 리포 -> 사본 을 반영한다. 심링크를 만들지 않으며,
# 사본에만 있는 파일(로컬 수정분일 수 있다)은 보고만 하고 지우지 않는다.
vendor_excluded() {
  case "$1" in
    *__pycache__*|*.pyc|*.DS_Store) return 0 ;;
  esac
  return 1
}

if [[ -n "$VENDOR" ]]; then
  if [[ -n "$PROJECT" || "$ACTION" != "install" || $WITH_AGENT -eq 1 ]]; then
    echo "오류: --vendor 는 --project/--uninstall/--verify/--with-agent 와 함께 쓸 수 없다" >&2
    exit 1
  fi
  if [[ ! -d "$VENDOR" ]]; then
    echo "오류: --vendor 대상이 디렉터리가 아니다 — $VENDOR" >&2
    exit 1
  fi
  vendor_root="$(cd "$VENDOR" && pwd)/.agents/skills"

  # 대상 스킬: --skill 지정분, 없으면 사본에 이미 있는 스킬만
  vendor_targets=()
  if [[ ${#VENDOR_SKILLS[@]} -gt 0 ]]; then
    for s in "${VENDOR_SKILLS[@]}"; do
      if [[ ! -d "$REPO_ROOT/skills/$s" ]]; then
        echo "오류: 리포에 없는 스킬 — $s" >&2
        exit 1
      fi
      vendor_targets+=("$s")
    done
  else
    for s in "${SKILL_NAMES[@]}"; do
      [[ -d "$vendor_root/$s" ]] && vendor_targets+=("$s")
    done
    if [[ ${#vendor_targets[@]} -eq 0 ]]; then
      echo "오류: $vendor_root 에 vendoring 된 스킬이 없다 — 새로 넣으려면 --skill <name>" >&2
      exit 1
    fi
  fi

  adds=0; updates=0; orphans=0
  for s in "${vendor_targets[@]}"; do
    src="$REPO_ROOT/skills/$s"
    dst="$vendor_root/$s"
    while IFS= read -r f; do
      rel="${f#"$src"/}"
      vendor_excluded "$rel" && continue
      if [[ ! -f "$dst/$rel" ]]; then
        echo "add       $s/$rel"
        adds=$((adds + 1))
      elif ! cmp -s "$f" "$dst/$rel"; then
        echo "update    $s/$rel"
        updates=$((updates + 1))
      else
        continue
      fi
      if [[ $DRY_RUN -eq 0 && $VENDOR_CHECK -eq 0 ]]; then
        mkdir -p "$(dirname "$dst/$rel")"
        cp -p "$f" "$dst/$rel"
      fi
    done < <(find -L "$src" -type f | sort)   # 원천은 원본을 가리키는 링크 묶음이다(#78)
    if [[ -d "$dst" ]]; then
      while IFS= read -r f; do
        rel="${f#"$dst"/}"
        vendor_excluded "$rel" && continue
        if [[ ! -f "$src/$rel" ]]; then
          echo "orphan    $s/$rel (원본에 없음 — 로컬 수정분일 수 있어 지우지 않는다)"
          orphans=$((orphans + 1))
        fi
      done < <(find "$dst" -type f | sort)
    fi
  done

  echo
  if [[ $VENDOR_CHECK -eq 1 ]]; then
    echo "check: add=$adds update=$updates orphan=$orphans (변경 없음)"
    [[ $((adds + updates)) -eq 0 ]]
    exit $?
  fi
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "dry-run: add=$adds update=$updates orphan=$orphans (변경 없음)"
    exit 0
  fi
  echo "vendor 갱신: add=$adds update=$updates orphan=$orphans -> $vendor_root"
  if git -C "$VENDOR" rev-parse --git-dir >/dev/null 2>&1; then
    echo "-- git status (커밋 대상 확인):"
    git -C "$VENDOR" status --short -- .agents/skills | head -40
  fi
  exit 0
fi

# 타깃 목록 구성
target_bases=()
agent_sources=()
agent_targets=()
if [[ -n "$PROJECT" ]]; then
  if [[ ! -d "$PROJECT" ]]; then
    echo "오류: --project 대상이 디렉터리가 아니다 — $PROJECT" >&2
    exit 1
  fi
  if ! project_abs="$(cd "$PROJECT" && pwd)"; then
    echo "오류: --project 경로로 이동 실패 — $PROJECT" >&2
    exit 1
  fi
  # Antigravity 의 프로젝트 customization root 는 .agents/ 이고 Codex 와 같은
  # 경로이므로, 두 타깃으로 세 런타임을 모두 커버한다.
  target_bases=("$project_abs/.claude/skills" "$project_abs/.agents/skills")
  claude_agents_base="$project_abs/.claude/agents"
  codex_agents_base="$project_abs/.codex/agents"
  claude_skills_base="$project_abs/.claude/skills"
  codex_skills_base="$project_abs/.agents/skills"
  agy_skills_base="$project_abs/.agents/skills"
else
  # Antigravity 의 전역 customization root 는 ~/.gemini/config/ 다.
  # ~/.gemini/antigravity/skills/ 는 agy 가 탐색하지 않는다 (이슈 #5).
  # 문서의 CLI 전역 ~/.gemini/antigravity-cli/skills/ 도 agy 1.2.16 은 읽지 않는다
  # (2026-10-05 프로브 실측, 이슈 #209). 근거 표는 AGENTS.md 에 있다.
  target_bases=("$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.gemini/config/skills")
  claude_agents_base="$HOME/.claude/agents"
  codex_agents_base="$HOME/.codex/agents"
  claude_skills_base="$HOME/.claude/skills"
  codex_skills_base="$HOME/.agents/skills"
  agy_skills_base="$HOME/.gemini/config/skills"
fi

# 스킬별 Agent Adapter 를 런타임이 탐색하는 이름으로 매핑한다.
#   skills/<skill>/agents/claude.md   -> <claude agents>/<skill>.md
#   skills/<skill>/agents/codex.toml  -> <codex agents>/<skill_underscored>.toml
# antigravity.md 는 agy 가 파일시스템 에이전트 디렉터리를 탐색하지 않으므로
# (2026-08-02 agy 1.1.8 실측: ~/.gemini/config/agents/ 의 md 는 CLI 를 행 상태로
# 만든다 — 이슈 #78) 플러그인 메커니즘으로 등록한다: agents/ 를 담은 플러그인을
# 스테이징해 `agy plugin install` → ~/.gemini/config/plugins/<name>/ 에 복사된다.
antigravity_sources=()
if [[ $WITH_AGENT -eq 1 ]]; then
  for skill in "${SKILL_NAMES[@]}"; do
    agents_dir="$REPO_ROOT/skills/$skill/agents"
    if [[ -f "$agents_dir/claude.md" ]]; then
      agent_sources+=("$agents_dir/claude.md")
      agent_targets+=("$claude_agents_base/$skill.md")
    fi
    if [[ -f "$agents_dir/codex.toml" ]]; then
      agent_sources+=("$agents_dir/codex.toml")
      agent_targets+=("$codex_agents_base/${skill//-/_}.toml")
    fi
    if [[ -f "$agents_dir/antigravity.md" ]]; then
      antigravity_sources+=("$agents_dir/antigravity.md")
    fi
  done
  if [[ ${#agent_sources[@]} -eq 0 ]]; then
    echo "오류: --with-agent 를 줬지만 skills/*/agents/ 에 Adapter 가 없다" >&2
    exit 1
  fi
fi

points_at_src() {
  [[ -L "$1" ]] && [[ "$(readlink "$1")" == "$2" ]]
}

# ---- 등록 검증 (이슈 #129) ----
# 파일이 제자리에 있다는 것은 등록의 증거가 아니다. 이슈 #110 이 정확히
# 그 모양이었다 — 플러그인에 어댑터 6개가 복사돼 있는데 agy 는 frontmatter
# 가 없다는 이유로 전부 조용히 무시했고, `agy agents` 에는 안 나왔다.
# 그래서 런타임 CLI 가 있으면 파일이 아니라 CLI 의 출력에 물어본다.
#
# 질의 가능한 표면이 없는 것은 경로 존재로 대신 본다. Claude Code 는 스킬
# 목록을 내주는 CLI 가 없고, Codex 는 커스텀 에이전트를 prompt-input 에
# 싣지 않는다. 그 경우 판정 옆에 근거를 함께 찍어 무엇을 확인한 것인지
# 읽는 사람이 헷갈리지 않게 한다.
verify_missing=0
verify_line() {
  local verdict="$1" runtime="$2" what="$3" how="$4"
  printf '%-9s %-12s %-28s %s\n' "$verdict" "$runtime" "$what" "$how"
  [[ "$verdict" == "missing" ]] && verify_missing=$((verify_missing + 1))
  return 0
}

verify_path() {
  local runtime="$1" what="$2" path="$3"
  # 대상이 사라진 심링크는 -L 은 참이고 -e 는 거짓이다. 레포를 옮기면 전부 이
  # 상태가 되는데, 예전엔 -L 만 보고 ok 로 쳐서 62개가 조용히 끊겨 있었다 (#170).
  if [[ -L "$path" && ! -e "$path" ]]; then
    verify_line "broken" "$runtime" "$what" "끊긴 링크: $path -> $(readlink "$path")"
    verify_missing=$((verify_missing + 1))
  elif [[ -e "$path" ]]; then
    verify_line "ok" "$runtime" "$what" "경로: $path"
  else
    verify_line "missing" "$runtime" "$what" "경로 없음: $path"
  fi
}

# ---- --list (이슈 #177) ----
# 스킬 이름에는 에이전트 유무를 담지 않는다. 대신 여기서 스킬·에이전트·런타임별
# 설치 상태를 한 표로 본다. 런타임 CLI 에 묻지 않고 경로만 보므로 빠르다 —
# 런타임이 실제로 읽었는지는 --verify 가 판정한다.
list_state() {
  local path="$1"
  if [[ -L "$path" && ! -e "$path" ]]; then echo "broken"
  elif [[ -e "$path" ]]; then echo "ok"
  else echo "-"; fi
}

if [[ "$ACTION" == "list" ]]; then
  # 가운데 세 칸은 스킬 설치, 오른쪽 두 칸은 에이전트 설치 상태다
  printf '%-24s %-6s | %-7s %-7s %-7s | %-7s %-7s\n' \
    "skill" "agent" "claude" "codex" "agy" "a:claude" "a:codex"
  for skill in "${SKILL_NAMES[@]}"; do
    if [[ -f "$REPO_ROOT/skills/$skill/agents/claude.md" ]]; then
      has_agent="yes"
      ca="$(list_state "$claude_agents_base/$skill.md")"
      xa="$(list_state "$codex_agents_base/${skill//-/_}.toml")"
    else
      has_agent="no"; ca=""; xa=""
    fi
    printf '%-24s %-6s | %-7s %-7s %-7s | %-7s %-7s\n' "$skill" "$has_agent" \
      "$(list_state "$claude_skills_base/$skill")" \
      "$(list_state "$codex_skills_base/$skill")" \
      "$(list_state "$agy_skills_base/$skill")" "$ca" "$xa"
  done
  echo
  echo "스킬 ${#SKILL_NAMES[@]}개 — Antigravity 에이전트 등록은 'agy agents' 또는 --verify --with-agent 로 확인"
  exit 0
fi

if [[ "$ACTION" == "verify" ]]; then
  echo "(verify — 설치하지 않는다. 런타임 CLI 가 있으면 그 출력에 물어본다)"
  echo

  # Claude Code — 질의 표면 없음. 경로로 본다.
  for skill in "${SKILL_NAMES[@]}"; do
    verify_path "claude" "skill $skill" "$claude_skills_base/$skill"
  done

  # Codex — prompt-input 이 실제로 주입되는 스킬 목록을 담는다.
  #   "- <name>: <description> (file: ...)" 형태로 나열된다.
  if command -v codex >/dev/null 2>&1 &&
     codex_prompt="$(codex debug prompt-input 2>/dev/null)" &&
     [[ -n "$codex_prompt" ]]; then
    for skill in "${SKILL_NAMES[@]}"; do
      if printf '%s' "$codex_prompt" | grep -qF -- "- $skill: "; then
        verify_line "ok" "codex" "skill $skill" "codex debug prompt-input"
      else
        verify_line "missing" "codex" "skill $skill" \
          "codex debug prompt-input 의 스킬 목록에 없음"
      fi
    done
  else
    for skill in "${SKILL_NAMES[@]}"; do
      verify_path "codex" "skill $skill" "$codex_skills_base/$skill"
    done
    verify_line "skip" "codex" "(CLI 질의)" \
      "codex CLI 로 확인하지 못해 경로로 대신 봤다"
  fi

  # Antigravity — 스킬 목록을 내주는 서브커맨드가 없다(agy help: agents/
  # models/plugin/…). 스킬은 경로로, 에이전트는 `agy agents` 로 본다.
  for skill in "${SKILL_NAMES[@]}"; do
    verify_path "agy" "skill $skill" "$agy_skills_base/$skill"
  done

  if [[ $WITH_AGENT -eq 1 ]]; then
    if command -v agy >/dev/null 2>&1 && agy_list="$(agy agents 2>/dev/null)"; then
      have_agy_list=1
    else
      have_agy_list=0
      verify_line "skip" "agy" "(에이전트 목록)" \
        "agy CLI 로 확인하지 못했다 — 등록 여부는 파일로 알 수 없다"
    fi

    for skill in "${SKILL_NAMES[@]}"; do
      agents_dir="$REPO_ROOT/skills/$skill/agents"
      if [[ -f "$agents_dir/claude.md" ]]; then
        verify_path "claude" "agent $skill" "$claude_agents_base/$skill.md"
      fi
      if [[ -f "$agents_dir/codex.toml" ]]; then
        verify_path "codex" "agent $skill" \
          "$codex_agents_base/${skill//-/_}.toml"
      fi
      if [[ -f "$agents_dir/antigravity.md" && $have_agy_list -eq 1 ]]; then
        if printf '%s\n' "$agy_list" | grep -qxF -- "$skill"; then
          verify_line "ok" "agy" "agent $skill" "agy agents"
        else
          verify_line "missing" "agy" "agent $skill" \
            "agy agents 에 없음 — 파일은 있어도 무시된 것이다 (frontmatter 확인)"
        fi
      fi
    done
  fi

  # 이 레포를 가리키던 링크 중 지금은 대상이 없는 것 — 이름이 바뀌었거나 지운
  # 스킬, 또는 레포를 옮기기 전에 만든 링크다. 위 루프는 현재 스킬 이름만 보므로
  # 여기서 따로 훑는다. 레포 경로가 바뀌어도 잡히게 디렉터리 이름으로 맞춘다.
  repo_name="$(basename "$REPO_ROOT")"
  for pair in "claude:$claude_skills_base" "codex:$codex_skills_base" \
              "agy:$agy_skills_base" "claude:$claude_agents_base" \
              "codex:$codex_agents_base"; do
    runtime="${pair%%:*}" base="${pair#*:}"
    [[ -d "$base" ]] || continue
    for link in "$base"/*; do
      [[ -L "$link" && ! -e "$link" ]] || continue
      case "$(readlink "$link")" in
        */"$repo_name"/skills/*) ;;
        *) continue ;;
      esac
      name="$(basename "$link")"
      # 현재 스킬 이름이면 위에서 이미 셌다
      skip=0
      for skill in "${SKILL_NAMES[@]}"; do
        [[ "$name" == "$skill" || "$name" == "$skill.md" || "$name" == "${skill//-/_}.toml" ]] && skip=1
      done
      [[ $skip -eq 1 ]] && continue
      verify_line "broken" "$runtime" "stale $name" "끊긴 링크: $link -> $(readlink "$link")"
      verify_missing=$((verify_missing + 1))
    done
  done

  echo
  if [[ $verify_missing -gt 0 ]]; then
    echo "미등록·끊긴 링크 $verify_missing 건 — scripts/install-skills.sh 로 (재)설치할 것" >&2
    exit 1
  fi
  echo "확인 완료 — 누락 없음"
  exit 0
fi

do_uninstall() {
  local target="$1" source="$2"
  if points_at_src "$target" "$source"; then
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "remove    $target"
    else
      if ! rm "$target"; then
        echo "fail      $target (심링크 제거 실패)" >&2
        failed=$((failed + 1))
        return 0
      fi
      echo "remove    $target"
    fi
    ok=$((ok + 1))
  elif [[ -L "$target" ]]; then
    echo "skip      $target (다른 곳을 가리키는 심링크: $(readlink "$target"))"
    skipped=$((skipped + 1))
  elif [[ -e "$target" ]]; then
    echo "skip      $target (실제 디렉터리 — 직접 확인 후 제거할 것)"
    skipped=$((skipped + 1))
  else
    echo "skip      $target (없음)"
    skipped=$((skipped + 1))
  fi
}

do_install() {
  local target="$1" source="$2"

  if points_at_src "$target" "$source"; then
    echo "skip      $target (이미 설치됨)"
    skipped=$((skipped + 1))
    return 0
  fi

  if [[ -e "$target" || -L "$target" ]]; then
    if [[ $FORCE -eq 0 ]]; then
      local what="실제 디렉터리"
      [[ -L "$target" ]] && what="다른 곳을 가리키는 심링크: $(readlink "$target")"
      echo "conflict  $target ($what) — 덮어쓰지 않는다. 교체하려면 --force" >&2
      failed=$((failed + 1))
      return 0
    fi
    if [[ $DRY_RUN -eq 0 ]]; then
      if ! rm -rf "$target"; then
        echo "fail      $target (기존 항목 제거 실패)" >&2
        failed=$((failed + 1))
        return 0
      fi
    fi
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "$MODE   $target -> $source"
    ok=$((ok + 1))
    return 0
  fi

  if ! mkdir -p "$(dirname "$target")"; then
    echo "fail      $target (부모 디렉토리 생성 실패)" >&2
    failed=$((failed + 1))
    return 0
  fi
  if [[ "$MODE" == "copy" ]]; then
    if ! cp -RL "$source" "$target"; then   # 링크가 아니라 원본 내용을 복사한다(#78)
      echo "fail      $target (복사 실패)" >&2
      failed=$((failed + 1))
      return 0
    fi
    echo "copy      $target"
  else
    if ! ln -s "$source" "$target"; then
      echo "fail      $target (심링크 생성 실패)" >&2
      failed=$((failed + 1))
      return 0
    fi
    echo "symlink   $target -> $source"
  fi
  ok=$((ok + 1))
}

if [[ $DRY_RUN -eq 1 ]]; then
  echo "(dry-run — 파일시스템을 바꾸지 않는다)"
fi

for skill in "${SKILL_NAMES[@]}"; do
  src="$REPO_ROOT/skills/$skill"
  for base in "${target_bases[@]}"; do
    if [[ "$ACTION" == "uninstall" ]]; then
      do_uninstall "$base/$skill" "$src"
    else
      do_install "$base/$skill" "$src"
    fi
  done
done

if [[ $WITH_AGENT -eq 1 ]]; then
  for ((i = 0; i < ${#agent_targets[@]}; i++)); do
    if [[ ! -f "${agent_sources[$i]}" ]]; then
      echo "fail      ${agent_sources[$i]} (Agent 원본 없음)" >&2
      failed=$((failed + 1))
      continue
    fi
    if [[ "$ACTION" == "uninstall" ]]; then
      do_uninstall "${agent_targets[$i]}" "${agent_sources[$i]}"
    else
      do_install "${agent_targets[$i]}" "${agent_sources[$i]}"
    fi
  done
  # ---- Antigravity: 플러그인으로 에이전트 등록 (전역 설치에서만) ----
  # 설치 시점에 ~/.gemini/config/plugins/ 로 복사되므로 antigravity.md 를
  # 고친 뒤에는 --with-agent 재실행이 필요하다.
  AGY_PLUGIN_NAME="agents-scaffold-skills-agents"
  agy_status="원본 없음"
  # bash 3.2 는 set -u 아래에서 빈 배열 전개를 오류로 처리하므로 먼저 센다.
  if [[ ${#antigravity_sources[@]} -gt 0 ]]; then
    if [[ -n "$PROJECT" ]]; then
      agy_status="프로젝트 설치 미지원 — 전역(--project 없이)에서 플러그인으로 등록된다"
      echo "info      Antigravity 에이전트는 전역 플러그인 등록만 지원한다"
    elif ! command -v agy >/dev/null 2>&1; then
      agy_status="건너뜀 — agy CLI 없음"
      echo "info      agy CLI 가 없어 Antigravity 에이전트를 등록하지 못했다."
      echo "info      agy 설치 후 다시 실행하거나, 아래 원본으로 직접 플러그인을 만들면 된다:"
      for src in "${antigravity_sources[@]}"; do
        echo "info        $src"
      done
    elif [[ $DRY_RUN -eq 1 ]]; then
      agy_status="dry-run — 플러그인 '$AGY_PLUGIN_NAME' 등록 예정 (${#antigravity_sources[@]}개)"
      echo "plan      agy plugin install ($AGY_PLUGIN_NAME, 에이전트 ${#antigravity_sources[@]}개)"
    else
      staging="$(mktemp -d "${TMPDIR:-/tmp}/agents-scaffold-agy.XXXXXX")"
      mkdir -p "$staging/agents"
      printf '{"name": "%s", "description": "agents-scaffold Agent Adapter 모음 (scripts/install-skills.sh 가 생성)", "version": "1.0.0"}\n' \
        "$AGY_PLUGIN_NAME" > "$staging/plugin.json"
      for skill in "${SKILL_NAMES[@]}"; do
        adapter="$REPO_ROOT/skills/$skill/agents/antigravity.md"
        [[ -f "$adapter" ]] && cp "$adapter" "$staging/agents/$skill.md"
      done
      if [[ "$ACTION" == "uninstall" ]]; then
        if agy plugin uninstall "$AGY_PLUGIN_NAME" >/dev/null 2>&1; then
          agy_status="플러그인 '$AGY_PLUGIN_NAME' 제거됨"
          echo "remove    agy plugin $AGY_PLUGIN_NAME"
          ok=$((ok + 1))
        else
          agy_status="플러그인 없음 (제거 생략)"
          echo "skip      agy plugin $AGY_PLUGIN_NAME (등록돼 있지 않음)"
          skipped=$((skipped + 1))
        fi
      else
        # 재실행 시 최신 원본으로 갱신되도록 기존 등록을 먼저 지운다.
        agy plugin uninstall "$AGY_PLUGIN_NAME" >/dev/null 2>&1 || true
        if agy plugin install "$staging" >/dev/null 2>&1; then
          agy_status="플러그인 '$AGY_PLUGIN_NAME' 등록 (에이전트 ${#antigravity_sources[@]}개 — 'agy agents' 로 확인)"
          echo "plugin    agy plugin $AGY_PLUGIN_NAME (에이전트 ${#antigravity_sources[@]}개)"
          ok=$((ok + 1))
        else
          agy_status="등록 실패 — 'agy plugin install $staging' 를 직접 실행해 오류를 확인할 것"
          echo "fail      agy plugin install (수동 확인 필요: $staging)" >&2
          failed=$((failed + 1))
        fi
      fi
      [[ "$agy_status" == 등록\ 실패* ]] || rm -rf "$staging"
    fi
  fi
fi

echo
if [[ $WITH_AGENT -eq 1 ]]; then
  echo "런타임별 에이전트: Claude=심링크 · Codex=심링크 · Antigravity=$agy_status"
fi
echo "완료: ok=$ok skip=$skipped conflict=$failed"
[[ $failed -eq 0 ]]
