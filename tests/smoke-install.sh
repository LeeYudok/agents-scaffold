#!/usr/bin/env bash
# 설치 스모크 테스트 (#107) — bats 없이 도는 최소 경로. CI 의 macOS(시스템 bash 3.2)·
# Windows(Git Bash) job 과 ubuntu job 이 같은 스크립트를 돌린다.
#
#   bash tests/smoke-install.sh
#
# 확인하는 것:
#   1. 이 스크립트를 실행한 bash 로 설치기가 끝까지 돈다(--stack python,bun)
#   2. 핵심 산출물이 있고, 스택 파셜이 pre-commit.sh 에 스플라이스됐다
#   3. 실제 `git commit` 이 훅을 타고 — 깨끗한 커밋은 통과, .env 는 차단,
#      가짜 ruff 가 실패하면 스택 게이트가 차단하고 통과하면 커밋된다
#
# bash 3.2 호환으로 쓴다(연관 배열·mapfile·${var,,} 금지). 심링크를 가정하지 않는다 —
# Windows 에서는 AGENTS_SCAFFOLD_NO_SYMLINK=1 을 주고 돌린다.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REPO_ROOT/bin/agents-scaffold.sh"
WORK="$(mktemp -d)"
# Windows 에서는 .git 의 읽기 전용 객체 때문에 정리가 실패할 수 있다 — 결과를 뒤집지 않게 한다.
trap 'rm -r "$WORK" 2>/dev/null || true' EXIT

pass=0
ok() { pass=$((pass + 1)); echo "ok $pass - $1"; }
die() {
  echo "not ok - $1" >&2
  [ -z "${2:-}" ] || printf '%s\n' "$2" | sed 's/^/    /' >&2
  exit 1
}

echo "# bash $BASH_VERSION ($BASH), $(uname -s), NO_SYMLINK=${AGENTS_SCAFFOLD_NO_SYMLINK:-0}"

# --- 1) 설치 ---
T="$WORK/proj"
mkdir -p "$T"
git -C "$T" init -q
out="$("$BASH" "$SCRIPT" "$T" --forge github --stack python,bun --name smoke --yes 2>&1)" \
  || die "installer exits 0" "$out"
ok "installer exits 0"

# --- 2) 산출물 ---
for f in AGENTS.md .claude/hooks/pre-commit.sh .claude/rules/python.md .claude/rules/bun.md \
  .claude/skills/handoff/SKILL.md .git/hooks/pre-commit; do
  [ -f "$T/$f" ] || die "installed file exists: $f" "$(ls -la "$T" "$T/.claude" 2>&1)"
done
ok "core files installed"

hook="$T/.claude/hooks/pre-commit.sh"
grep -q 'Python lint + typecheck gate' "$hook" || die "python partial spliced"
grep -q 'bun (TypeScript) typecheck gate' "$hook" || die "bun partial spliced"
marker="$(grep -n '# --- STACK CHECKS' "$hook" | sed -n '1p' | cut -d: -f1)"
gate="$(grep -n 'Python lint + typecheck gate' "$hook" | sed -n '1p' | cut -d: -f1)"
[ "$gate" -gt "$marker" ] || die "partial sits after the STACK CHECKS marker"
! grep -q '{{PROJECT_NAME}}' "$T/AGENTS.md" || die "placeholders substituted in AGENTS.md"
ok "stack partials spliced, placeholders substituted"

# --- 3) 실제 git commit ---
cd "$T"
git config user.name smoke
git config user.email smoke@example.invalid
git config commit.gpgsign false

FAKE="$WORK/fakebin"
mkdir -p "$FAKE"
# 러너에 실제 ruff 가 있어도 결과가 흔들리지 않도록 처음부터 가짜를 PATH 앞에 둔다.
printf '#!/usr/bin/env bash\nexit 0\n' > "$FAKE/ruff"
chmod +x "$FAKE/ruff"
PATH="$FAKE:$PATH"
export PATH

printf 'smoke\n' > notes.txt
git add notes.txt
out="$(git commit -q -m 'clean commit' 2>&1)" || die "clean commit passes the hook" "$out"
ok "clean commit passes the hook"

printf 'X=1\n' > .env
git add -f .env
if out="$(git commit -q -m 'leak' 2>&1)"; then die "staged .env blocks the commit" "$out"; fi
case "$out" in *"Blocked: a .env-type file is staged"*) ;; *) die "staged .env prints the block message" "$out" ;; esac
git rm -q --cached .env
rm .env
ok "staged .env blocks the commit"

mkdir -p app
printf 'import os\n' > app/main.py
git add app/main.py
printf '#!/usr/bin/env bash\n[ "$1" = "check" ] && { echo "app/main.py:1:8: F401 unused import"; exit 1; }\nexit 0\n' > "$FAKE/ruff"
if out="$(git commit -q -m 'lint failure' 2>&1)"; then die "failing ruff blocks the commit" "$out"; fi
case "$out" in *"Blocked: ruff check failed"*) ;; *) die "stack gate prints the block message" "$out" ;; esac
case "$out" in *"F401"*) ;; *) die "stack gate shows the ruff output" "$out" ;; esac
ok "failing stack gate blocks the commit and shows the tool output"

printf '#!/usr/bin/env bash\nexit 0\n' > "$FAKE/ruff"
out="$(git commit -q -m 'lint fixed' 2>&1)" || die "passing ruff lets the commit through" "$out"
[ "$(git rev-list --count HEAD)" -eq 2 ] || die "two commits recorded"
ok "passing stack gate lets the commit through"

cd "$REPO_ROOT"
echo "# smoke: $pass checks passed"
