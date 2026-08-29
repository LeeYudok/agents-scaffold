#!/usr/bin/env bash
# agents-scaffold — .claude/ 부트스트랩.
# P2 300줄 규칙 예외(#37): curl|bash 원커맨드 설치가 단일 파일을 요구해 분리하지 않는다.
set -euo pipefail

print_help() {
  cat <<'EOF'
Usage:
  bin/agents-scaffold.sh [<target-dir>] [--forge github|gitlab] [--stack nextjs,springboot] [--lang en|ko] [--name <project>] [--yes]
  bin/agents-scaffold.sh --update [<target-dir>] [--name <project>]
  curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- [--stack nextjs] [--name <project>] [--yes]

  <target-dir>   Default "." (current directory). In-place (=repo itself) for the GitLab template path.
  --forge        Issue/PR forge. github (default) or gitlab. Interactive prompt if unset (default github).
  --stack        Comma-separated stack presets. Interactive prompt if unset.
  --lang         Output language overlay. ko (default) or en. Interactive prompt if unset.
                 en overlays presets/lang-en/ (base + forge + selected stacks) on top of the
                 English base, after base copy + forge merge + stack merge.
  --name         {{PROJECT_NAME}} substitution value. Default = target directory name.
  --harness      Target agent harness: claude (default), codex, or all.
                 codex keeps AGENTS.md + rules/skills/hooks/memory (harness-neutral),
                 drops Claude Code-only layers (settings.json, agents/, commands/,
                 workflows/, CLAUDE.md/GEMINI.md pointers), and wires the pre-commit
                 gate as a real .git/hooks/pre-commit. all installs everything and
                 also wires the git hook.
  --yes          Skip interactive prompts (non-interactive mode).
  --update       Refresh the base .claude/·AGENTS.md etc. of an already-bootstrapped project.
                 .claude/hooks/pre-commit.sh has stack partials inserted, so it is skipped
                 (manual merge required). Out of scope: --lang — --update only touches the
                 Korean base regardless of the project's language overlay.
                 Other base files are skipped if identical to the target, otherwise the
                 existing file is preserved and the new version is saved as <file>.new.
                 A summary of added/updated/skipped files is printed at the end.

Remote install (no clone): if the local BASH_SOURCE-relative path is not a valid template
root (e.g. running via curl pipe), a $AGENTS_SCAFFOLD_REPO tarball is downloaded to a temp
directory and used as the template source.
  AGENTS_SCAFFOLD_REPO  Defaults to the official GitHub repo URL (override via env).
  AGENTS_SCAFFOLD_REF   Branch/tag. Default "main".

Flow: copy base (.claude/ + CLAUDE.md) -> merge forge preset -> merge selected stack presets
      -> merge lang-en overlay (if --lang en) -> substitute {{PLACEHOLDER}} -> chmod +x
      -> in-place: self-clean bin/·presets/·scripts/·docs/superpowers/·docs/harness-matrix.json.
EOF
}

# 이슈 #10/#21: 원격 설치 기본 소스 레포
AGENTS_SCAFFOLD_REPO_OWNER_DEFAULT="leeyudok"
AGENTS_SCAFFOLD_REPO="${AGENTS_SCAFFOLD_REPO:-https://github.com/${AGENTS_SCAFFOLD_REPO_OWNER_DEFAULT}/agents-scaffold}"
AGENTS_SCAFFOLD_REF="${AGENTS_SCAFFOLD_REF:-main}"

TARGET="."
STACKS=""
FORGE=""
LANG_OPT=""
NAME=""
ASSUME_YES=0
UPDATE=0
HARNESS="claude"

while [ $# -gt 0 ]; do
  case "$1" in
    --stack) STACKS="$2"; shift 2 ;;
    --forge) FORGE="$2"; shift 2 ;;
    --lang)  LANG_OPT="$2"; shift 2 ;;
    --name)  NAME="$2";  shift 2 ;;
    --harness) HARNESS="$2"; shift 2 ;;
    --yes)   ASSUME_YES=1; shift ;;
    --update) UPDATE=1; shift ;;
    -h|--help) print_help; exit 0 ;;
    --*) echo "Unknown option: $1" >&2; exit 1 ;;
    *)   TARGET="$1"; shift ;;
  esac
done

TARGET="$(cd "$TARGET" && pwd)"
[ -z "$NAME" ] && NAME="$(basename "$TARGET")"

case "$HARNESS" in
  claude|codex|all) ;;
  *) echo "Unknown --harness '$HARNESS' (claude|codex|all)" >&2; exit 1 ;;
esac

# --- 이슈 #10: SRC 결정. 로컬 clone 이면 BASH_SOURCE 기준, curl 파이프 등으로
#     로컬 템플릿이 없으면 tarball 을 받아 임시 디렉터리를 SRC 로 쓴다.
REMOTE_TMPDIR=""
cleanup_remote_tmpdir() {
  # EXIT trap 의 마지막 명령 상태가 스크립트 exit code 를 오염시키지 않도록 if 문 사용
  # ([ -n ] && ... 형태면 로컬 설치(빈 REMOTE_TMPDIR)에서 항상 exit 1 이 됨)
  if [ -n "$REMOTE_TMPDIR" ]; then
    rm -rf "$REMOTE_TMPDIR"
  fi
}
trap cleanup_remote_tmpdir EXIT

fetch_remote_src() {
  REMOTE_TMPDIR="$(mktemp -d)"
  local tarball="$REMOTE_TMPDIR/agents-scaffold.tar.gz"
  local url="${AGENTS_SCAFFOLD_REPO}/archive/refs/heads/${AGENTS_SCAFFOLD_REF}.tar.gz"
  echo "== Local template not found — remote install: downloading $url ==" >&2
  if ! curl -fsSL "$url" -o "$tarball"; then
    echo "Error: template download failed ($url). Check AGENTS_SCAFFOLD_REPO/AGENTS_SCAFFOLD_REF." >&2
    exit 1
  fi
  tar -xzf "$tarball" -C "$REMOTE_TMPDIR"
  local extracted
  extracted="$(find "$REMOTE_TMPDIR" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  if [ -z "$extracted" ] || [ ! -d "$extracted/.claude" ]; then
    echo "Error: downloaded template structure is invalid" >&2
    exit 1
  fi
  echo "$extracted"
}

SRC_LOCAL=""
if SRC_LOCAL="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")/.." 2>/dev/null && pwd)"; then
  :
fi
if [ -n "$SRC_LOCAL" ] && [ -d "$SRC_LOCAL/.claude" ] && [ -d "$SRC_LOCAL/presets" ]; then
  SRC="$SRC_LOCAL"
else
  SRC="$(fetch_remote_src)"
fi

INPLACE=0
[ "$TARGET" = "$SRC" ] && INPLACE=1

JAVA_VERSION="1.8"

# sed 치환문에 들어갈 값의 메타문자(\ & / 개행) 이스케이프 — 미처리 시 조용히 산출물 오염
sed_escape_replacement() {
  printf '%s' "$1" | sed -e 's/[&/\]/\\&/g' | awk 'NR>1{printf "\\n"} {printf "%s", $0}'
}
NAME_SED="$(sed_escape_replacement "$NAME")"

substitute_placeholders() {
  # 인자로 받은 파일들에 {{PLACEHOLDER}} 치환 적용
  local f
  for f in "$@"; do
    [ -f "$f" ] || continue
    # 바이너리는 건너뜀 — macOS sed 가 illegal byte sequence 로 전체를 죽인다 (#37/#39 일반화)
    LC_ALL=C grep -Iq . "$f" || continue
    # LC_ALL=C: 한국어 베이스(UTF-8 멀티바이트)를 C 로케일 sed 에서도 바이트 단위로 안전 처리
    LC_ALL=C sed -i.bak -e "s/{{PROJECT_NAME}}/$NAME_SED/g" -e "s/{{JAVA_VERSION}}/$JAVA_VERSION/g" "$f"
    rm -f "$f.bak"
  done
}

# --- 이슈 #13: --update 모드. 이미 부트스트랩된 프로젝트의 베이스 파일을 최신화한다.
run_update() {
  echo "== agents-scaffold --update: target=$TARGET name=$NAME ==" >&2
  echo "note: --lang is out of scope for --update; only the Korean base is refreshed" >&2

  local hook_rel=".claude/hooks/pre-commit.sh"
  local added=() updated=() skipped=() unchanged=()

  # git 소스면 tracked 만 대상(#39) — find 는 untracked 로컬 산출물(observations 등)까지
  # Added 로 실어 나른다. tarball 폴백은 아카이브가 이미 tracked 만 담으므로 find 유지.
  local base_files=()
  if git -C "$SRC" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    while IFS= read -r -d '' f; do base_files+=("$SRC/$f"); done \
      < <(git -C "$SRC" ls-files -z -- .claude)
  else
    while IFS= read -r f; do base_files+=("$f"); done < <(find "$SRC/.claude" -type f)
  fi
  base_files+=("$SRC/AGENTS.md" "$SRC/CLAUDE.md" "$SRC/GEMINI.md")

  local f rel tgt
  for f in "${base_files[@]:-}"; do
    [ -n "$f" ] || continue
    rel="${f#"$SRC"/}"
    tgt="$TARGET/$rel"

    if [ "$rel" = "$hook_rel" ]; then
      if [ -f "$tgt" ]; then
        skipped+=("$rel (stack partial inserted file — manual merge required, skipped)")
      fi
      continue
    fi

    if [ ! -f "$tgt" ]; then
      mkdir -p "$(dirname "$tgt")"
      cp "$f" "$tgt"
      substitute_placeholders "$tgt"
      added+=("$rel")
      continue
    fi

    # 치환 "적용 후" 사본과 비교(#39) — 원본과 비교하면 {{PROJECT_NAME}} 든
    # 파일이 no-op 업데이트에도 전부 "변경됨"으로 잡혀 .new 를 쏟아낸다.
    subbed="$(mktemp)"
    cp "$f" "$subbed"
    substitute_placeholders "$subbed"
    if diff -q "$subbed" "$tgt" >/dev/null 2>&1; then
      rm -f "$subbed"
      unchanged+=("$rel")
      continue
    fi

    mkdir -p "$(dirname "$tgt")"
    mv "$subbed" "$tgt.new"
    updated+=("$rel")
  done

  chmod +x "$TARGET/.claude/hooks/"*.sh 2>/dev/null || true

  echo "== --update summary ==" >&2
  echo "Added: ${#added[@]}" >&2
  if [ "${#added[@]}" -gt 0 ]; then
    for rel in "${added[@]}"; do echo "  + $rel" >&2; done
  fi
  echo "Pending update (.new created, apply manually after diff): ${#updated[@]}" >&2
  if [ "${#updated[@]}" -gt 0 ]; then
    for rel in "${updated[@]}"; do echo "  * $rel -> $rel.new" >&2; done
  fi
  echo "Skipped: ${#skipped[@]}" >&2
  if [ "${#skipped[@]}" -gt 0 ]; then
    for rel in "${skipped[@]}"; do echo "  - $rel" >&2; done
  fi
  echo "Unchanged: ${#unchanged[@]}" >&2
  echo "== Done. Review .new files with diff and apply manually. ==" >&2
}

if [ "$UPDATE" -eq 1 ]; then
  run_update
  exit 0
fi

# forge 미지정 + 대화형이면 묻는다 (기본 github)
if [ -z "$FORGE" ] && [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
  echo "Select issue/PR forge [github|gitlab] (blank=github):" >&2
  printf "forge> " >&2
  read -r FORGE || FORGE=""
fi
[ -z "$FORGE" ] && FORGE="github"
FORGE="$(echo "$FORGE" | tr -d '[:space:]')"
case "$FORGE" in
  github|gitlab) : ;;
  *) echo "Unknown forge '$FORGE' (only github|gitlab supported)" >&2; exit 1 ;;
esac

# lang 미지정 + 대화형이면 묻는다 (기본 ko), --yes 면 기본 ko
if [ -z "$LANG_OPT" ] && [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
  echo "Select output language [ko|en] (blank=ko):" >&2
  printf "lang> " >&2
  read -r LANG_OPT || LANG_OPT=""
fi
[ -z "$LANG_OPT" ] && LANG_OPT="ko"
LANG_OPT="$(echo "$LANG_OPT" | tr -d '[:space:]')"
case "$LANG_OPT" in
  en|ko) : ;;
  *) echo "Unknown lang '$LANG_OPT' (only en|ko supported)" >&2; exit 1 ;;
esac

# 스택 미지정 + 대화형이면 묻는다
AVAILABLE_STACKS="nextjs, springboot, javaweb, bun, python, go, rust, ruby-rails, android, flutter, ops"
if [ -z "$STACKS" ] && [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
  echo "Select stack presets (comma-separated, blank=common only): $AVAILABLE_STACKS" >&2
  printf "stack> " >&2
  read -r STACKS || STACKS=""
fi

echo "== agents-scaffold: target=$TARGET name=$NAME forge=$FORGE stacks=[${STACKS:-none}] lang=$LANG_OPT inplace=$INPLACE ==" >&2

# 1) 베이스 복사 (in-place 면 이미 있으므로 스킵)
# git 소스면 tracked 파일만 복사(#39) — cp -R 은 untracked 로컬 산출물
# (memory/observations 세션로그, __pycache__, 에이전트 메모리)까지 실어 나른다.
# tarball 원격 설치는 git 메타가 없지만 아카이브 자체가 tracked 만 담으므로 cp -R 유지.
if [ "$INPLACE" -eq 0 ]; then
  if git -C "$SRC" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$SRC" ls-files -z -- .claude | while IFS= read -r -d '' bf; do
      # 기존 파일은 보존 — 커스텀 base 를 가진 프로젝트 위에 덮어쓰지 않는다(갱신은 --update 소관)
      [ -e "$TARGET/$bf" ] && continue
      mkdir -p "$TARGET/$(dirname "$bf")"
      cp "$SRC/$bf" "$TARGET/$bf"
    done
  else
    cp -R "$SRC/.claude" "$TARGET/.claude"
  fi
  # AGENTS.md = SSOT, CLAUDE.md/GEMINI.md = @AGENTS.md 포인터
  cp "$SRC/AGENTS.md" "$SRC/CLAUDE.md" "$SRC/GEMINI.md" "$TARGET/"
fi

# 프리셋 머지 헬퍼 — 프리셋 디렉터리의 .claude/ 하위 파일을 타깃에 복사(덮어쓰기).
# pre-commit.partial.sh 만 특수: 베이스 pre-commit.sh 의 STACK CHECKS 마커 뒤에 삽입.
# skip_partial=1 이면 pre-commit.partial.sh 를 통째로 무시한다(lang 오버레이 등
# 파셜을 두지 않기로 약속된 디렉터리에서, 실수로 들어와도 방어).
merge_preset() {
  local pdir="$1"
  local skip_partial="${2:-0}"
  [ -d "$pdir/.claude" ] || return 0
  while IFS= read -r f; do
    local rel="${f#"$pdir"/}"
    if [ "$(basename "$f")" = "pre-commit.partial.sh" ]; then
      if [ "$skip_partial" -eq 1 ]; then
        continue
      fi
      # 훅 partial 은 베이스 pre-commit.sh 의 STACK CHECKS 마커 "바로 뒤"에 삽입한다.
      # (끝에 append 하면 base 의 `exit 0` 뒤로 떨어져 죽은 코드가 됨)
      local hook="$TARGET/.claude/hooks/pre-commit.sh"
      local marker='# --- STACK CHECKS'
      if grep -qF "$marker" "$hook"; then
        local tmp
        tmp="$(mktemp)"
        awk -v partial="$f" '
          { print }
          /# --- STACK CHECKS/ && !ins {
            while ((getline line < partial) > 0) print line
            close(partial); ins = 1
          }
        ' "$hook" > "$tmp" && mv "$tmp" "$hook"
      else
        # 마커가 없으면(커스텀 base) 안전하게 끝에 붙인다.
        cat "$f" >> "$hook"
      fi
    else
      mkdir -p "$TARGET/$(dirname "$rel")"
      cp "$f" "$TARGET/$rel"
    fi
  done < <(find "$pdir/.claude" -type f)
}

# 2a) forge 프리셋 머지 (스택보다 먼저 — forge 워크플로 규약을 베이스에 얹는다)
fdir="$SRC/presets/forge-$FORGE"
if [ -d "$fdir" ]; then
  merge_preset "$fdir"
else
  echo "Warning: forge preset '$fdir' not found — using base as-is" >&2
fi

# 2b) 스택 프리셋 머지
IFS=',' read -r -a STACK_ARR <<< "$STACKS"
# bash 3.2(macOS 기본)의 set -u 는 0-원소 배열의 "${arr[@]}" 를 unbound 로 취급(4.4+ 에서 수정됨).
# STACKS 가 빈 문자열이면 STACK_ARR 이 0-원소가 되어 크래시하므로 ":-" 로 가드한다.
for s in "${STACK_ARR[@]:-}"; do
  s="$(echo "$s" | tr -d '[:space:]')"
  [ -z "$s" ] && continue
  pdir="$SRC/presets/$s"
  [ -d "$pdir" ] || { echo "Warning: unknown stack '$s' — skipping" >&2; continue; }
  merge_preset "$pdir"
done

# 2c) 이슈 #22: 한국어 오버레이 머지. base/forge/stack 머지가 모두 끝난 뒤,
#     LANG_OPT=en 이면 presets/lang-en/ 아래 대응 디렉터리로 덮어쓴다 (#36 반전:
#     베이스 = 한국어 원본, 영어가 오버레이). lang-en/base 는 .claude/ 뿐 아니라
#     루트 파일(AGENTS.md 등)도 base/ 바로 아래
#     두므로 merge_preset (=.claude/ 전용) 이 못 다루는 루트 파일은 별도 복사한다.
if [ "$LANG_OPT" = "en" ]; then
  lang_dir="$SRC/presets/lang-en"
  if [ -d "$lang_dir" ]; then
    lang_base="$lang_dir/base"
    if [ -d "$lang_base" ]; then
      merge_preset "$lang_base" 1
      for rf in "$lang_base"/*.md; do
        [ -f "$rf" ] || continue
        cp "$rf" "$TARGET/$(basename "$rf")"
      done
    else
      echo "Warning: presets/lang-en/base not found — skipping English base overlay" >&2
    fi

    lang_forge="$lang_dir/forge-$FORGE"
    if [ -d "$lang_forge" ]; then
      merge_preset "$lang_forge" 1
    else
      echo "Warning: presets/lang-en/forge-$FORGE not found — skipping English forge overlay" >&2
    fi

    for s in "${STACK_ARR[@]:-}"; do
      s="$(echo "$s" | tr -d '[:space:]')"
      [ -z "$s" ] && continue
      lang_stack="$lang_dir/stacks/$s"
      if [ -d "$lang_stack" ]; then
        merge_preset "$lang_stack" 1
      else
        echo "Warning: presets/lang-en/stacks/$s not found — skipping English stack overlay" >&2
      fi
    done
  else
    echo "Warning: presets/lang-en not found — skipping English overlay entirely" >&2
  fi
fi

# 2d) 스택별 P0 를 AGENTS.md 본문에 인라인 (#21)
#   AGENTS.md 는 모든 하네스가 읽는 유일한 상시 로드 면이다. 스택 P0 를
#   `.claude/rules/<stack>.md` 참조로만 두면 .claude/ 를 로드하지 않는 하네스에서
#   해당 P0 가 도달 불가가 된다 → 선택한 스택의 P0 만 본문에 삽입한다.
#   전 스택을 인라인하지 않는 이유: Codex 의 instruction 합산 기본 한도는 32KiB
#   (project_doc_max_bytes) 이고 상시 로드 면을 무제한 키우면 context flooding 이 된다.
#   lang 오버레이가 AGENTS.md 를 통째로 덮어쓰므로 반드시 그 뒤에 실행한다.
agents_md="$TARGET/AGENTS.md"
p0_marker='<!-- STACK P0 -->'
if [ -f "$agents_md" ] && grep -qF "$p0_marker" "$agents_md"; then
  for s in "${STACK_ARR[@]:-}"; do
    s="$(echo "$s" | tr -d '[:space:]')"
    [ -z "$s" ] && continue
    partial="$SRC/presets/$s/AGENTS.partial.md"
    if [ "$LANG_OPT" = "en" ] && [ -f "$SRC/presets/lang-en/stacks/$s/AGENTS.partial.md" ]; then
      partial="$SRC/presets/lang-en/stacks/$s/AGENTS.partial.md"
    fi
    [ -f "$partial" ] || { echo "Warning: $partial not found — stack P0 not inlined for '$s'" >&2; continue; }
    tmp="$(mktemp)"
    awk -v partial="$partial" -v marker="$p0_marker" '
      { print }
      index($0, marker) && !ins {
        while ((getline line < partial) > 0) print line
        close(partial); ins = 1
      }
    ' "$agents_md" > "$tmp" && mv "$tmp" "$agents_md"
  done
fi

# 3) 플레이스홀더 치환
find "$TARGET/.claude" "$TARGET/AGENTS.md" "$TARGET/CLAUDE.md" "$TARGET/GEMINI.md" -type f 2>/dev/null | while IFS= read -r f; do
  substitute_placeholders "$f"
done

# 4) 실행권한
chmod +x "$TARGET/.claude/hooks/"*.sh 2>/dev/null || true

# 4.5) 하네스 조정 (#16)
#   codex: Claude Code 전용 계층 제거 — AGENTS.md 는 Codex 가 네이티브로 읽고,
#          rules/skills/hooks/memory 는 하네스 중립 문서·스크립트라 유지한다.
#   전 하네스 공통: pre-commit 게이트를 진짜 git hook 으로 배선 (#21).
if [ "$HARNESS" = "codex" ]; then
  echo "== harness=codex: removing Claude Code-only layers ==" >&2
  rm -rf "$TARGET/.claude/agents" "$TARGET/.claude/commands" "$TARGET/.claude/workflows"
  rm -f "$TARGET/.claude/settings.json" "$TARGET/CLAUDE.md" "$TARGET/GEMINI.md"
fi
# git hook 은 하네스와 무관하게 항상 배선한다 (#21).
#   Claude Code 의 PreToolUse 훅(settings.json)은 그 세션이 Bash 툴로 커밋할 때만 발동하므로,
#   사람이 터미널에서 직접 커밋하거나 다른 하네스가 커밋하면 게이트를 타지 않는다.
#   결정적 강제선은 하네스 밖(.git/hooks + CI)에 두고, 하네스 훅은 조기 피드백 계층으로 남긴다.
if true; then
  if [ -d "$TARGET/.git" ]; then
    githook="$TARGET/.git/hooks/pre-commit"
    if [ -e "$githook" ]; then
      echo "Warning: .git/hooks/pre-commit already exists — not overwriting. Chain .claude/hooks/pre-commit.sh manually." >&2
    else
      printf '%s\n' '#!/usr/bin/env bash' 'exec "$(git rev-parse --show-toplevel)/.claude/hooks/pre-commit.sh"' > "$githook"
      chmod +x "$githook"
      echo "== git pre-commit hook wired to .claude/hooks/pre-commit.sh ==" >&2
    fi
  else
    echo "Note: target is not a git repo yet — after 'git init', wire the gate with:" >&2
    echo "  printf '%s\n' '#!/usr/bin/env bash' 'exec \"\$(git rev-parse --show-toplevel)/.claude/hooks/pre-commit.sh\"' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit" >&2
  fi
fi

# 5) in-place self-clean (템플릿 흔적 제거)
if [ "$INPLACE" -eq 1 ]; then
  echo "== self-clean: removing bin/ presets/ scripts/ docs/superpowers/ docs/harness-matrix.json ==" >&2
  rm -rf "$TARGET/bin" "$TARGET/presets" "$TARGET/scripts" "$TARGET/docs/superpowers"
  # scripts/ 와 harness-matrix.json 은 이 저장소의 유지보수 자산이지 사용자 산출물이 아니다 (#37)
  rm -f "$TARGET/docs/harness-matrix.json"
fi

echo "== Done. Fill in CLAUDE.md and .claude/ for your project. ==" >&2
