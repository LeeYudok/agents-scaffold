#!/usr/bin/env bats
# agents-scaffold.sh 회귀 테스트 (이슈 #12)
#
# 실행: bats tests/agents-scaffold.bats
# 로컬 설치: brew install bats-core (또는 https://github.com/bats-core/bats-core)
#
# 각 테스트는 REPO_ROOT/bin/agents-scaffold.sh 를 BATS_TEST_TMPDIR 안의
# 격리된 타겟에 대해 실행한다. 원본 레포는 절대 건드리지 않는다
# (in-place self-clean 테스트만 예외 — 반드시 레포를 임시 복사한 사본을 대상으로 함).
#
# ⚠️ 알려진 환경 이슈 (이슈 #12 조사 중 발견, bin/agents-scaffold.sh 는 수정하지 않음
#    — #10/#13 병렬 작업 범위): macOS 기본 시스템 bash(/bin/bash, 3.2, set -u 하에서
#    "IFS=',' read -a arr <<< \"\"" 로 만든 빈 배열 참조 시 "unbound variable" 로 죽는
#    구버전 버그 있음) 로 bin/agents-scaffold.sh 를 실행하면 --stack 을 지정하지 않은
#    호출(예: base copy 전용 실행)이 90번째 줄 `for s in "${STACK_ARR[@]}"` 에서
#    실패한다. bash>=4 (CI ubuntu 기본, 또는 `brew install bash` 후 PATH 우선순위 조정)
#    에서는 재현되지 않는다. 이 테스트 스위트는 CI/최신 bash 기준으로 통과하도록
#    작성했다 — 로컬에서 실행 전 `PATH="/opt/homebrew/bin:$PATH"` 로 brew bash 를
#    우선시킬 것. 근본 수정(예: `"${STACK_ARR[@]:-}"` 가드)은 별도 이슈로 보고.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  SCRIPT="$REPO_ROOT/bin/agents-scaffold.sh"
}

# --- 1) 베이스 복사 ---

# 테스트 이름은 ASCII 로 유지한다 — bats-core 가 비-ASCII(한글) 테스트명에서
# 로케일/CI 환경에 따라 내부 이름 인코딩이 어긋나 "unknown test name" 으로
# 깨지는 사례가 있어(로컬 macOS ko_KR.UTF-8 환경에서 실측 재현) 회피한다.

@test "base copy creates .claude AGENTS.md and no CLAUDE.md/GEMINI.md/.gemini shims (#54, #60)" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --yes
  [ "$status" -eq 0 ]
  [ -d "$BATS_TEST_TMPDIR/.claude" ]
  [ -f "$BATS_TEST_TMPDIR/AGENTS.md" ]
  # #54: CLAUDE.md 가 있으면 Claude Code 가 AGENTS.md 를 건너뛰므로 셤을 만들지 않는다
  [ ! -e "$BATS_TEST_TMPDIR/CLAUDE.md" ]
  [ ! -e "$BATS_TEST_TMPDIR/GEMINI.md" ]
  # #60: agy 가 AGENTS.md 를 네이티브로 읽으므로 Gemini CLI 용 context.fileName 셤도 두지 않는다
  [ ! -e "$BATS_TEST_TMPDIR/.gemini" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/skills/handoff/SKILL.md" ]
}

# --- 2) 스택 1개 머지 ---

@test "one stack (bun) merge: rules copied + partial inserted right after marker" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack bun --yes
  [ "$status" -eq 0 ]
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/bun.md" ]

  hook="$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh"
  [ -f "$hook" ]

  marker_line="$(grep -n '# --- STACK CHECKS' "$hook" | head -1 | cut -d: -f1)"
  [ -n "$marker_line" ]
  next_line="$((marker_line + 1))"
  next_content="$(sed -n "${next_line}p" "$hook")"
  # bun partial 의 첫 줄(주석 헤더)이 마커 바로 다음 줄이어야 함
  first_partial_line="$(head -1 "$REPO_ROOT/presets/bun/.claude/hooks/pre-commit.partial.sh")"
  [ "$next_content" = "$first_partial_line" ]
}

# --- 3) 스택 2개 머지 (#6 회귀) ---

@test "two stacks (bun,python) merge: both gates exist before exit 0 (#6 regression)" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack bun,python --yes
  [ "$status" -eq 0 ]

  hook="$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh"
  [ -f "$hook" ]

  exit0_line="$(grep -n '^exit 0$' "$hook" | tail -1 | cut -d: -f1)"
  [ -n "$exit0_line" ]

  bun_line="$(grep -n 'bun (TypeScript) typecheck gate' "$hook" | head -1 | cut -d: -f1)"
  python_line="$(grep -n 'Python lint + typecheck gate' "$hook" | head -1 | cut -d: -f1)"

  [ -n "$bun_line" ]
  [ -n "$python_line" ]
  [ "$bun_line" -lt "$exit0_line" ]
  [ "$python_line" -lt "$exit0_line" ]

  # 두 partial 모두 exit 2 (차단) 만 쓰고 exit 0 으로 훅을 조기 종료하지 않는지 확인
  # (partial 자체는 exit 0 을 포함하지 않아야 함 — #6 재발 방지)
  ! grep -q '^exit 0$' "$REPO_ROOT/presets/bun/.claude/hooks/pre-commit.partial.sh"
  ! grep -q '^exit 0$' "$REPO_ROOT/presets/python/.claude/hooks/pre-commit.partial.sh"
}

# --- 4) 마커 없는 커스텀 base -> append fallback ---

@test "custom base without marker: partial appended at end (fallback)" {
  mkdir -p "$BATS_TEST_TMPDIR/.claude/hooks"
  cat > "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh" <<'EOF'
#!/usr/bin/env bash
# 커스텀 base — STACK CHECKS 마커 없음
set -euo pipefail
echo "custom pre-commit"
exit 0
EOF

  # cp -R "$SRC/.claude" "$TARGET/.claude" 는 대상 .claude 가 이미 있으면
  # 그 안에 중첩(target/.claude/.claude/...)되므로, 스택 머지 단계가 참조하는
  # target/.claude/hooks/pre-commit.sh 는 위에서 만든 커스텀 파일 그대로 남는다.
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack bun --yes
  [ "$status" -eq 0 ]

  hook="$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh"
  [ -f "$hook" ]
  # 마커가 여전히 없고, bun 게이트 헤더가 파일에 존재(append 됨)
  ! grep -qF '# --- STACK CHECKS' "$hook"
  grep -q 'bun (TypeScript) typecheck gate' "$hook"
  # append 이므로 커스텀 원본 내용도 그대로 유지
  grep -q 'custom pre-commit' "$hook"
}

# --- 5) {{PROJECT_NAME}} 치환 ---

@test "PROJECT_NAME placeholder substitution via --name, no .bak left" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --name my-cool-project --yes
  [ "$status" -eq 0 ]

  grep -q 'my-cool-project' "$BATS_TEST_TMPDIR/AGENTS.md"
  ! grep -q '{{PROJECT_NAME}}' "$BATS_TEST_TMPDIR/AGENTS.md"

  # .bak 파일이 하나도 남지 않아야 함
  bak_count="$(find "$BATS_TEST_TMPDIR" -name '*.bak' | wc -l | tr -d ' ')"
  [ "$bak_count" -eq 0 ]
}

@test "--name with sed metacharacters (& / \\) substitutes literally (#32)" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --name 'foo&bar/baz\qux' --yes
  [ "$status" -eq 0 ]

  grep -qF 'foo&bar/baz\qux' "$BATS_TEST_TMPDIR/AGENTS.md"
  ! grep -q '{{PROJECT_NAME}}' "$BATS_TEST_TMPDIR/AGENTS.md"
  # '&' 가 매치 원문({{PROJECT_NAME}})으로 재확장되지 않아야 함
  ! grep -qF 'foo{{PROJECT_NAME}}bar' "$BATS_TEST_TMPDIR/AGENTS.md"
}

# --- 6) 알 수 없는 스택 ---

@test "unknown stack prints warning and continues (no abort)" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack totally-unknown-stack --yes
  [ "$status" -eq 0 ]
  [[ "$output" == *"Warning"* ]]
  [[ "$output" == *"totally-unknown-stack"* ]]
  # 베이스는 정상적으로 완료됨
  [ -d "$BATS_TEST_TMPDIR/.claude" ]
  [ -f "$BATS_TEST_TMPDIR/AGENTS.md" ]
}

# --- 7) --yes 비대화 모드 ---

@test "--yes non-interactive mode succeeds without stdin prompt" {
  run bash -c "\"$SCRIPT\" \"$BATS_TEST_TMPDIR\" --yes < /dev/null"
  [ "$status" -eq 0 ]
  [[ "$output" != *"stack>"* ]]
  [ -d "$BATS_TEST_TMPDIR/.claude" ]
}

# --- 8) in-place self-clean ---

@test "harness matrix manifest passes its own checker (#37)" {
  run python3 "$REPO_ROOT/scripts/check-harness-matrix.py"
  [ "$status" -eq 0 ]
}

@test "harness matrix checker actually fails an expired full tier (#37)" {
  # 게이트가 실제로 막는지 확인한다 — 통과만 보면 무용지물인 검사기를 못 잡는다.
  run python3 "$REPO_ROOT/scripts/check-harness-matrix.py" --today 2099-01-01
  [ "$status" -eq 1 ]
  [[ "$output" == *"tier=full"* ]]
}

@test "in-place self-clean removes bin presets docs/superpowers (run against repo copy)" {
  copy="$BATS_TEST_TMPDIR/repo-copy"
  cp -R "$REPO_ROOT" "$copy"

  # 원본 레포는 훼손되지 않아야 하므로 사본 경로로만 실행
  run "$copy/bin/agents-scaffold.sh" "$copy" --yes
  [ "$status" -eq 0 ]

  [ ! -d "$copy/bin" ]
  [ ! -d "$copy/presets" ]
  [ ! -d "$copy/docs/superpowers" ]
  # #61: in-place install also moves the template's skills to the .agents/skills source
  [ -L "$copy/.claude/skills" ]
  [ -f "$copy/.agents/skills/review/SKILL.md" ]

  # 원본은 그대로 존재해야 함
  [ -d "$REPO_ROOT/bin" ]
  [ -d "$REPO_ROOT/presets" ]
  [ -d "$REPO_ROOT/docs/superpowers" ]
}

# --- 9) 실행권한 ---

@test "hooks/*.sh get executable permission" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack bun --yes
  [ "$status" -eq 0 ]

  for f in "$BATS_TEST_TMPDIR/.claude/hooks/"*.sh; do
    [ -x "$f" ]
  done
}

# --- 10) --lang en / ko / invalid (이슈 #22, #36 반전: 베이스=한국어, en=오버레이) ---
#
# fixture 사본으로 오버레이 동작 자체만 검증한다 (실콘텐츠와 독립).

@test "--lang en overlays presets/lang-en/base onto target (fixture)" {
  copy="$BATS_TEST_TMPDIR/repo-copy-lang-en"
  cp -R "$REPO_ROOT" "$copy"

  mkdir -p "$copy/presets/lang-en/base/.claude/rules"
  echo "ENGLISH DUMMY COMMON RULES" > "$copy/presets/lang-en/base/.claude/rules/common.md"

  target="$BATS_TEST_TMPDIR/lang-en-target"
  mkdir -p "$target"
  run "$copy/bin/agents-scaffold.sh" "$target" --lang en --yes
  [ "$status" -eq 0 ]

  [ -f "$target/.claude/rules/common.md" ]
  grep -q "ENGLISH DUMMY COMMON RULES" "$target/.claude/rules/common.md"
}

@test "--lang ko (default) does not apply lang-en overlay (fixture)" {
  copy="$BATS_TEST_TMPDIR/repo-copy-lang-default"
  cp -R "$REPO_ROOT" "$copy"

  mkdir -p "$copy/presets/lang-en/base/.claude/rules"
  echo "ENGLISH DUMMY COMMON RULES" > "$copy/presets/lang-en/base/.claude/rules/common.md"

  target="$BATS_TEST_TMPDIR/lang-default-target"
  mkdir -p "$target"
  run "$copy/bin/agents-scaffold.sh" "$target" --yes
  [ "$status" -eq 0 ]

  [ -f "$target/.claude/rules/common.md" ]
  ! grep -q "ENGLISH DUMMY COMMON RULES" "$target/.claude/rules/common.md"
}

@test "--lang fr is rejected with exit 1" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --lang fr --yes
  [ "$status" -eq 1 ]
}

# --- 11) ported assets (issue #24) ---

@test "base copy includes ported skills, workflows, scripts, commands, rules" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --yes
  [ "$status" -eq 0 ]

  [ -f "$BATS_TEST_TMPDIR/.claude/skills/memory-factcheck/SKILL.md" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/skills/security-precheck/SKILL.md" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/skills/docs-sync/SKILL.md" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/workflows/README.md" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/workflows/rules-audit.js" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/scripts/knowledge_graph.py" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/commands/knowledge-graph.md" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/security.md" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/testing.md" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/data.md" ]
}

@test "PROJECT_NAME is substituted inside workflow js and script py" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --name graphproj --yes
  [ "$status" -eq 0 ]

  ! grep -rq '{{PROJECT_NAME}}' "$BATS_TEST_TMPDIR/.claude"
  grep -q 'graphproj' "$BATS_TEST_TMPDIR/.claude/scripts/knowledge_graph.py"
  grep -q 'graphproj' "$BATS_TEST_TMPDIR/.claude/workflows/rules-audit.js"
}

@test "docs-sync skill ships in both languages (#29)" {
  t="$BATS_TEST_TMPDIR/dsko"
  mkdir -p "$t"
  run bash "$SCRIPT" "$t" --forge github --name ds-ko --yes
  [ "$status" -eq 0 ]
  grep -q '^name: docs-sync$' "$t/.claude/skills/docs-sync/SKILL.md"
  grep -q '다국어' "$t/.claude/skills/docs-sync/SKILL.md"

  t2="$BATS_TEST_TMPDIR/dsen"
  mkdir -p "$t2"
  run bash "$SCRIPT" "$t2" --forge github --lang en --name ds-en --yes
  [ "$status" -eq 0 ]
  grep -q '^name: docs-sync$' "$t2/.claude/skills/docs-sync/SKILL.md"
  grep -q 'parallel-language' "$t2/.claude/skills/docs-sync/SKILL.md"
}

@test "--lang en overlays ported files with real English content" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --lang en --yes
  [ "$status" -eq 0 ]

  # en overlay must differ from the Korean base file
  ! diff -q "$REPO_ROOT/.claude/skills/memory-factcheck/SKILL.md" \
      "$BATS_TEST_TMPDIR/.claude/skills/memory-factcheck/SKILL.md" >/dev/null
  ! diff -q "$REPO_ROOT/.claude/workflows/rules-audit.js" \
      "$BATS_TEST_TMPDIR/.claude/workflows/rules-audit.js" >/dev/null
  ! diff -q "$REPO_ROOT/.claude/skills/grill-me/SKILL.md" \
      "$BATS_TEST_TMPDIR/.claude/skills/grill-me/SKILL.md" >/dev/null
  # knowledge_graph.py is a code file — never overlaid (no en counterpart may exist)
  [ ! -f "$REPO_ROOT/presets/lang-en/base/.claude/scripts/knowledge_graph.py" ]
}

# --- 12) knowledge-graph link gate (issue #24) ---
# Forces every relative link in AGENTS.md / rules/README / SKILL.md files to
# resolve on a freshly bootstrapped target, in both languages.

@test "knowledge_graph.py --check exits 0 on a fresh en scaffold" {
  command -v python3 >/dev/null || skip "python3 not installed"
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --name scratch --lang en --yes
  [ "$status" -eq 0 ]

  run python3 "$BATS_TEST_TMPDIR/.claude/scripts/knowledge_graph.py" --check
  [ "$status" -eq 0 ]
}

@test "knowledge_graph.py --check exits 0 on a fresh ko (default) scaffold" {
  command -v python3 >/dev/null || skip "python3 not installed"
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --name scratch --yes
  [ "$status" -eq 0 ]

  run python3 "$BATS_TEST_TMPDIR/.claude/scripts/knowledge_graph.py" --check
  [ "$status" -eq 0 ]
}

# --- publish-github.sh (#26) ---
# The publish script must produce a fresh-history tree without internal-only
# files (.gitlab-ci.yml) and abort when internal references remain.

# Copies the current working tree (tracked state) into an isolated scratch repo
# committed as main, so the script under test never touches the real repo.
setup_publish_repo() {
  PUB_REPO="$BATS_TEST_TMPDIR/pubrepo"
  mkdir -p "$PUB_REPO"
  (cd "$REPO_ROOT" && tar -cf - --exclude='.git' --exclude='./.git' .) | tar -xf - -C "$PUB_REPO"
  git -C "$PUB_REPO" init -q -b main
  git -C "$PUB_REPO" -c user.name=test -c user.email=test@example.com add -A
  git -C "$PUB_REPO" -c user.name=test -c user.email=test@example.com commit -qm init
}

@test "publish-github.sh: publish tree drops internal-only files, guard passes" {
  [ -f "$REPO_ROOT/scripts/publish-github.sh" ] || skip "internal-only script, absent from the public tree"
  setup_publish_repo
  cd "$PUB_REPO"

  # 개발자 셸의 PUBLISH_* export 에 영향받지 않게 격리(#39)
  run env -u PUBLISH_NAME -u PUBLISH_EMAIL bash scripts/publish-github.sh
  [ "$status" -eq 0 ]

  # main keeps internal-only files; publish/github must not contain them (#39: 가드 스크립트 자신 포함)
  git cat-file -e main:.gitlab-ci.yml
  git cat-file -e main:scripts/publish-github.sh
  run git ls-tree -r --name-only publish/github
  [ "$status" -eq 0 ]
  [[ "$output" != *".gitlab-ci.yml"* ]]
  [[ "$output" != *"publish-github.sh"* ]]

  # fresh history: single parentless commit (%p 가 비어 있어야 함)
  run git log publish/github --format='%ae %p'
  [ "$status" -eq 0 ]
  [[ "$output" == *"@users.noreply.github.com"* ]]
  [[ "$output" != *" "?*[0-9a-f]* ]] || [ "$(git rev-list --count publish/github)" -eq 1 ]

  # author/committer name uses the public handle, not an internal one (#34)
  run git log publish/github --format='%an %cn'
  [ "$status" -eq 0 ]
  [ "$output" = "leeyudok leeyudok" ]
}

@test "publish-github.sh: guard aborts when an internal reference remains" {
  [ -f "$REPO_ROOT/scripts/publish-github.sh" ] || skip "internal-only script, absent from the public tree"
  setup_publish_repo
  cd "$PUB_REPO"

  # split so this test file itself never contains the literal internal string
  echo "internal host: dok""sam" > leak.txt
  git -c user.name=test -c user.email=test@example.com add leak.txt
  git -c user.name=test -c user.email=test@example.com commit -qm leak

  run bash scripts/publish-github.sh
  [ "$status" -ne 0 ]
  [[ "$output" == *"leak.txt"* ]]
}

@test "publish-github.sh: guard catches private/public IP ranges (#39)" {
  [ -f "$REPO_ROOT/scripts/publish-github.sh" ] || skip "internal-only script, absent from the public tree"
  setup_publish_repo
  cd "$PUB_REPO"

  # 이 테스트 파일 자체가 가드에 걸리지 않게 IP 를 조립식으로 생성
  printf 'db host: 10.%s\n' '1.2.3' > ipleak.txt
  git -c user.name=test -c user.email=test@example.com add ipleak.txt
  git -c user.name=test -c user.email=test@example.com commit -qm ipleak

  run bash scripts/publish-github.sh
  [ "$status" -ne 0 ]
  [[ "$output" == *"ipleak.txt"* ]]
}

# --- 14) forge preset merge (#33) ---

@test "--forge github merges GitHub forge.md rule" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --forge github --yes
  [ "$status" -eq 0 ]
  grep -q 'Forge 워크플로 — GitHub' "$BATS_TEST_TMPDIR/.claude/rules/forge.md"
}

@test "--forge gitlab merges GitLab forge.md rule and commands" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --forge gitlab --yes
  [ "$status" -eq 0 ]
  grep -q 'Forge 워크플로 — GitLab' "$BATS_TEST_TMPDIR/.claude/rules/forge.md"
  # forge-gitlab preset also overrides the sdlc-cycle/fix-issue commands
  diff -q "$REPO_ROOT/presets/forge-gitlab/.claude/commands/fix-issue.md" \
      "$BATS_TEST_TMPDIR/.claude/commands/fix-issue.md"
}

@test "--forge gitlab --lang en applies English forge overlay" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --forge gitlab --lang en --yes
  [ "$status" -eq 0 ]
  # en overlay must differ from the Korean forge preset file
  ! diff -q "$REPO_ROOT/presets/forge-gitlab/.claude/rules/forge.md" \
      "$BATS_TEST_TMPDIR/.claude/rules/forge.md" >/dev/null
}

@test "unknown --forge is rejected with exit 1" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --forge bitbucket --yes
  [ "$status" -eq 1 ]
}

# --- 15) --update mode (#33, mechanics from issue #13) ---

@test "--update re-adds deleted base file, stages .new for local edits, skips pre-commit.sh" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --yes
  [ "$status" -eq 0 ]

  # simulate drift: base file deleted + base file locally edited
  rm "$BATS_TEST_TMPDIR/.claude/rules/security.md"
  echo "local customization" >> "$BATS_TEST_TMPDIR/.claude/rules/data.md"

  run "$SCRIPT" "$BATS_TEST_TMPDIR" --update --yes
  [ "$status" -eq 0 ]

  # deleted file re-added
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/security.md" ]
  [[ "$output" == *"+ .claude/rules/security.md"* ]]

  # locally-edited file untouched, refreshed copy staged as .new
  grep -q 'local customization' "$BATS_TEST_TMPDIR/.claude/rules/data.md"
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/data.md.new" ]
  ! grep -q 'local customization' "$BATS_TEST_TMPDIR/.claude/rules/data.md.new"

  # pre-commit.sh is never overwritten (stack partials may be spliced in)
  [[ "$output" == *"pre-commit.sh"*"skipped"* ]]
  [ ! -f "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh.new" ]
}

@test "--update leaves placeholder-free identical files unchanged (no .new spam)" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --yes
  [ "$status" -eq 0 ]
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --update --yes
  [ "$status" -eq 0 ]
  # no-op 업데이트는 .new 를 만들지 않아야 한다 — 플레이스홀더 든 파일 포함(#39).
  # 예외: forge 프리셋이 덮어쓴 commands/ 2개는 base 와 다른 게 정상(--update 는 forge 미인지).
  [ ! -f "$BATS_TEST_TMPDIR/.claude/rules/security.md.new" ]
  [ ! -f "$BATS_TEST_TMPDIR/AGENTS.md.new" ]
  stray="$(find "$BATS_TEST_TMPDIR" -name '*.new' ! -path '*/.claude/commands/*' | wc -l | tr -d ' ')"
  [ "$stray" -eq 0 ]
}

# --- 16) preset partial invariant (#33) ---
# PRESET_SPEC.md mandates: a pre-commit.partial.sh must never call `exit 0`
# (it is spliced mid-hook; exit 0 would skip every later stack's gate — issue #6).

@test "no duplicate scaffold entry point at repo root (#35)" {
  # PR #22 가 루트에 bin/agents-scaffold.sh 의 축약 재구현을 심었고, 그 스크립트는
  # .claude/settings.json 을 스텁으로 truncate 해 deny 규칙과 훅 바인딩을 파괴했다.
  # 진입점은 bin/ 하나뿐이어야 한다.
  [ ! -e "$REPO_ROOT/agents-scaffold.sh" ]
  [ ! -e "$REPO_ROOT/hooks/pre-commit.sh" ]
  [ -x "$REPO_ROOT/bin/agents-scaffold.sh" ]
}

@test "scaffold never truncates an existing .claude/settings.json (#35)" {
  t="$BATS_TEST_TMPDIR/keepsettings"
  mkdir -p "$t/.claude"
  printf '%s\n' '{"permissions":{"deny":["MYRULE"]},"hooks":{}}' > "$t/.claude/settings.json"
  run bash "$SCRIPT" "$t" --forge github --name keep --yes
  [ "$status" -eq 0 ]
  grep -q 'MYRULE' "$t/.claude/settings.json"
}

@test "no pre-commit.partial.sh in any preset contains exit 0" {
  local found=0 p
  while IFS= read -r p; do
    if grep -vE '^[[:space:]]*#' "$p" | grep -nE '(^|[^[:alnum:]_])exit[[:space:]]+0([^0-9]|$)'; then
      echo "exit 0 found in: $p"
      found=1
    fi
  done < <(find "$REPO_ROOT/presets" -name 'pre-commit.partial.sh')
  [ "$found" -eq 0 ]
}

# --- 17) 바이너리 내성 (#37) ---
# 유닛테스트 실행 등이 .claude 트리에 __pycache__(.pyc)를 남겨도 스캐폴드가
# 죽지 않아야 한다 (macOS sed illegal byte sequence 회귀).

@test "scaffold survives .pyc binary inside base .claude tree" {
  copy="$BATS_TEST_TMPDIR/repo-copy-pyc"
  cp -R "$REPO_ROOT" "$copy"
  mkdir -p "$copy/.claude/scripts/__pycache__"
  printf '\x00\x01\x02\xff\xfe' > "$copy/.claude/scripts/__pycache__/x.cpython-313.pyc"

  target="$BATS_TEST_TMPDIR/pyc-target"
  mkdir -p "$target"
  run "$copy/bin/agents-scaffold.sh" "$target" --yes
  [ "$status" -eq 0 ]
  grep -q 'pyc-target' "$target/AGENTS.md"
  # untracked 바이너리는 아예 복사되지 않아야 한다(#39 git ls-files 기반 복사)
  [ ! -e "$target/.claude/scripts/__pycache__" ]
}

# --- 18) javaweb 프리셋 (#38) ---

@test "javaweb stack merges rules and splices partial after marker" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack javaweb --yes
  [ "$status" -eq 0 ]
  grep -q 'Java + JSP' "$BATS_TEST_TMPDIR/.claude/rules/javaweb.md"
  ! grep -q '{{JAVA_VERSION}}' "$BATS_TEST_TMPDIR/.claude/rules/javaweb.md"
  grep -q 'javaweb' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh"
  # 파셜이 마커 뒤, 베이스 exit 0 앞에 삽입됐는지
  marker_line="$(grep -n 'STACK CHECKS' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh" | head -1 | cut -d: -f1)"
  javaweb_line="$(grep -n 'javaweb: maven compile' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh" | head -1 | cut -d: -f1)"
  [ "$javaweb_line" -gt "$marker_line" ]
}

@test "javaweb JSP gate blocks newly added scriptlets, allows EL/JSTL (#40)" {
  target="$BATS_TEST_TMPDIR/jspgate"
  mkdir -p "$target"
  run "$SCRIPT" "$target" --stack javaweb --yes
  [ "$status" -eq 0 ]

  cd "$target"
  git init -q -b main
  git config user.name t; git config user.email t@e.c

  # EL/JSTL + 지시자/주석만 있는 JSP → 통과
  mkdir -p src/main/webapp
  cat > src/main/webapp/ok.jsp <<'JSP'
<%@ page pageEncoding="UTF-8" %>
<%-- comment --%>
<c:out value="${user.name}"/>
JSP
  git add src/main/webapp/ok.jsp
  run bash .claude/hooks/pre-commit.sh
  [ "$status" -eq 0 ]

  # 신규 스크립틀릿 추가 → exit 2 차단
  cat > src/main/webapp/bad.jsp <<'JSP'
<% String id = request.getParameter("id"); %>
JSP
  git add src/main/webapp/bad.jsp
  run bash .claude/hooks/pre-commit.sh
  [ "$status" -eq 2 ]
  [[ "$output" == *"스크립틀릿"* ]]
}

# --- 9) harness (#16) ---

@test "harness codex installs native skills, drops Claude-only layers, wires git hook (#50)" {
  t="$BATS_TEST_TMPDIR/codex"
  mkdir -p "$t"
  git -C "$t" init -q
  mkdir -p "$t/.agents/skills/status"
  echo 'user-owned codex skill' > "$t/.agents/skills/status/SKILL.md"
  run bash "$SCRIPT" "$t" --forge github --stack go --harness codex --name codex-app --yes
  [ "$status" -eq 0 ]
  # kept: shared layers + Codex-native repository skills
  [ -f "$t/AGENTS.md" ]
  [ -f "$t/.claude/rules/go.md" ]
  [ -f "$t/.agents/skills/review/SKILL.md" ]
  grep -q 'user-owned codex skill' "$t/.agents/skills/status/SKILL.md"
  [ -f "$t/.claude/hooks/pre-commit.sh" ]
  # dropped: Claude Code-only layers
  [ ! -e "$t/.claude/settings.json" ]
  # #64: .claude/agents is the adapter source — kept, and generated as Codex TOML
  [ -f "$t/.claude/agents/code-reviewer.md" ]
  [ -f "$t/.codex/agents/code-reviewer.toml" ]
  [ ! -d "$t/.claude/commands" ]
  # #61: .claude/skills is a symlink to the single source .agents/skills — the user-owned skill wins
  [ -L "$t/.claude/skills" ]
  grep -q 'user-owned codex skill' "$t/.claude/skills/status/SKILL.md"
  [ ! -d "$t/.claude/workflows" ]
  [ ! -e "$t/CLAUDE.md" ]
  [ ! -e "$t/GEMINI.md" ]
  [ ! -e "$t/.gemini" ]
  # git hook wired and executable, chains the gate
  [ -x "$t/.git/hooks/pre-commit" ]
  grep -q 'pre-commit.sh' "$t/.git/hooks/pre-commit"
  # the wired gate actually blocks a staged .env
  cd "$t"
  echo 'X=1' > .env
  git add -f .env
  run bash .git/hooks/pre-commit
  [ "$status" -eq 2 ]
}

@test "harness agy matches the codex layout: AGENTS.md + .agents/skills, no Claude-only layers (#60)" {
  t="$BATS_TEST_TMPDIR/agymode"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --stack python --harness agy --name agy-app --yes
  [ "$status" -eq 0 ]
  [ -f "$t/AGENTS.md" ]
  [ -f "$t/.agents/skills/review/SKILL.md" ]
  [ -f "$t/.claude/rules/python.md" ]
  [ ! -e "$t/.claude/settings.json" ]
  # #64: .claude/agents is the adapter source — kept, and generated for agy
  [ -f "$t/.claude/agents/code-reviewer.md" ]
  [ -f "$t/.agents/agents/code-reviewer.md" ]
  [ ! -d "$t/.claude/commands" ]
  [ ! -d "$t/.claude/workflows" ]
  [ ! -e "$t/.gemini" ]
  [ ! -e "$t/GEMINI.md" ]
  [ -x "$t/.git/hooks/pre-commit" ]
}

@test "skills live once in .agents/skills; .claude/skills is a symlink to it (#61)" {
  t="$BATS_TEST_TMPDIR/ssot"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name ssot-app --yes
  [ "$status" -eq 0 ]
  [ -L "$t/.claude/skills" ]
  [ "$(readlink "$t/.claude/skills")" = "../.agents/skills" ]
  [ -d "$t/.agents/skills" ]
  [ ! -L "$t/.agents/skills" ]
  [ -f "$t/.agents/skills/handoff/SKILL.md" ]
  [ -f "$t/.claude/skills/handoff/SKILL.md" ]
  # placeholders are substituted in the source (bats ignores a bare `! cmd`, so assert on status)
  run grep -rl '{{PROJECT_NAME}}' "$t/.agents/skills"
  [ "$status" -eq 1 ]
  # the gate accepts the symlink layout
  cd "$t"
  run bash .git/hooks/pre-commit
  [ "$status" -eq 0 ]
  # re-running the installer keeps the link, makes no backup, and substitutes a base skill
  # it re-adds through the link (find does not follow the link on its own)
  rm "$t/.agents/skills/review/SKILL.md"
  run bash "$SCRIPT" "$t" --forge github --name ssot-app --yes
  [ "$status" -eq 0 ]
  [ -L "$t/.claude/skills" ]
  [ -z "$(ls -d "$t"/.claude/skills.pre-ssot-* 2>/dev/null)" ]
  [ -f "$t/.agents/skills/review/SKILL.md" ]
  run grep -l '{{PROJECT_NAME}}' "$t/.agents/skills/review/SKILL.md"
  [ "$status" -eq 1 ]
}

@test "AGENTS_SCAFFOLD_NO_SYMLINK=1 falls back to a copy; gate blocks a drifted copy (#61)" {
  t="$BATS_TEST_TMPDIR/copymode"
  mkdir -p "$t"
  git -C "$t" init -q
  run env AGENTS_SCAFFOLD_NO_SYMLINK=1 bash "$SCRIPT" "$t" --forge github --name copy-app --yes
  [ "$status" -eq 0 ]
  [[ "$output" == *"symlink unavailable"* ]]
  [ -d "$t/.claude/skills" ]
  [ ! -L "$t/.claude/skills" ]
  diff -rq "$t/.agents/skills" "$t/.claude/skills"
  cd "$t"
  git add .agents/skills .claude/skills
  run bash .git/hooks/pre-commit
  [ "$status" -eq 0 ]
  # untracked caches in the copy do not block — the gate compares the index, not the working tree
  mkdir -p .claude/skills/review/__pycache__
  echo 'x' > .claude/skills/review/__pycache__/m.pyc
  run bash .git/hooks/pre-commit
  [ "$status" -eq 0 ]
  # a staged drift in the copy blocks
  echo 'drift' >> .claude/skills/handoff/SKILL.md
  git add .claude/skills/handoff/SKILL.md
  run bash .git/hooks/pre-commit
  [ "$status" -eq 2 ]
  [[ "$output" == *"differs from its source .agents/skills"* ]]
}

@test "pre-existing .claude/skills: unique skills migrate, a conflicting copy is backed up (#61)" {
  t="$BATS_TEST_TMPDIR/premig"
  mkdir -p "$t/.claude/skills/my-skill" "$t/.claude/skills/status" "$t/.agents/skills/status"
  git -C "$t" init -q
  echo 'mine' > "$t/.claude/skills/my-skill/SKILL.md"
  echo 'claude status' > "$t/.claude/skills/status/SKILL.md"
  echo 'agents status' > "$t/.agents/skills/status/SKILL.md"
  run bash "$SCRIPT" "$t" --forge github --name premig-app --yes
  [ "$status" -eq 0 ]
  [ -L "$t/.claude/skills" ]
  grep -q 'mine' "$t/.agents/skills/my-skill/SKILL.md"
  grep -q 'agents status' "$t/.agents/skills/status/SKILL.md"
  backup="$(ls -d "$t"/.claude/skills.pre-ssot-*)"
  grep -q 'claude status' "$backup/status/SKILL.md"
}

@test "--update migrates a pre-#61 real .claude/skills to .agents/skills + symlink (#61)" {
  t="$BATS_TEST_TMPDIR/updmig"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name updmig-app --yes
  [ "$status" -eq 0 ]
  # rebuild the old layout: real .claude/skills, no .agents/
  rm "$t/.claude/skills"
  cp -R "$t/.agents/skills" "$t/.claude/skills"
  rm -r "$t/.agents"
  echo 'local skill edit' >> "$t/.claude/skills/handoff/SKILL.md"
  run bash "$SCRIPT" "$t" --update --yes
  [ "$status" -eq 0 ]
  [[ "$output" == *"skills migrated"* ]]
  [ -L "$t/.claude/skills" ]
  grep -q 'local skill edit' "$t/.agents/skills/handoff/SKILL.md"
  [ -f "$t/.agents/skills/handoff/SKILL.md.new" ]
  [[ "$output" == *".agents/skills/handoff/SKILL.md -> .agents/skills/handoff/SKILL.md.new"* ]]
}

@test "--update leaves differing .claude/skills and .agents/skills alone (#61)" {
  t="$BATS_TEST_TMPDIR/upddiff"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name upddiff-app --yes
  [ "$status" -eq 0 ]
  rm "$t/.claude/skills"
  cp -R "$t/.agents/skills" "$t/.claude/skills"
  echo 'only in the claude copy' >> "$t/.claude/skills/handoff/SKILL.md"
  run bash "$SCRIPT" "$t" --update --yes
  [ "$status" -eq 0 ]
  [[ "$output" == *"not migrated"* ]]
  [ -d "$t/.claude/skills" ]
  [ ! -L "$t/.claude/skills" ]
  grep -q 'only in the claude copy' "$t/.claude/skills/handoff/SKILL.md"
  # nothing migrated: the source is untouched and the refresh lands next to the Claude copy
  run grep -q 'only in the claude copy' "$t/.agents/skills/handoff/SKILL.md"
  [ "$status" -eq 1 ]
  [ -f "$t/.claude/skills/handoff/SKILL.md.new" ]
  [ ! -e "$t/.agents/skills/handoff/SKILL.md.new" ]
}

@test "--update aborts without deleting skills when .agents cannot be created (#61)" {
  t="$BATS_TEST_TMPDIR/updabort"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name updabort-app --yes
  [ "$status" -eq 0 ]
  rm "$t/.claude/skills"
  cp -R "$t/.agents/skills" "$t/.claude/skills"
  mkdir -p "$t/.claude/skills/mine"
  echo 'mine' > "$t/.claude/skills/mine/SKILL.md"
  rm -r "$t/.agents"
  echo 'not a directory' > "$t/.agents"
  run bash "$SCRIPT" "$t" --update --yes
  [ "$status" -ne 0 ]
  [ -d "$t/.claude/skills" ]
  grep -q 'mine' "$t/.claude/skills/mine/SKILL.md"
}

@test "symlinked skill entries survive the move into .agents/skills (#61)" {
  t="$BATS_TEST_TMPDIR/linkedentry"
  mkdir -p "$t/shared/linked-skill" "$t/.claude/skills"
  git -C "$t" init -q
  echo 'shared skill' > "$t/shared/linked-skill/SKILL.md"
  ln -s ../../shared/linked-skill "$t/.claude/skills/linked-skill"
  run bash "$SCRIPT" "$t" --forge github --name linked-app --yes
  [ "$status" -eq 0 ]
  [ -L "$t/.agents/skills/linked-skill" ]
  grep -q 'shared skill' "$t/.claude/skills/linked-skill/SKILL.md"
}

@test "re-install over the symlink layout keeps a user-edited skill (#61)" {
  t="$BATS_TEST_TMPDIR/reinstall"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --lang en --name reinstall-app --yes
  [ "$status" -eq 0 ]
  [ -L "$t/.claude/skills" ]
  echo 'user edit' >> "$t/.agents/skills/review/SKILL.md"
  # the lang-en overlay ships review/SKILL.md; it must not overwrite the shared source
  run bash "$SCRIPT" "$t" --forge github --lang en --name reinstall-app --yes
  [ "$status" -eq 0 ]
  grep -q 'user edit' "$t/.agents/skills/review/SKILL.md"
}

@test "--update leaves a .claude/skills symlink to elsewhere alone (#61)" {
  t="$BATS_TEST_TMPDIR/foreignlink"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name foreign-app --yes
  [ "$status" -eq 0 ]
  mv "$t/.agents/skills" "$t/my-skills"
  rm -r "$t/.agents"
  rm "$t/.claude/skills"
  ln -s ../my-skills "$t/.claude/skills"
  run bash "$SCRIPT" "$t" --update --yes
  [ "$status" -eq 0 ]
  [[ "$output" == *"links to ../my-skills"* ]]
  [ "$(readlink "$t/.claude/skills")" = "../my-skills" ]
  [ ! -e "$t/.agents/skills" ]
}

@test "copy-layout gate lists the differing files and never suggests directory-wide staging (#61)" {
  t="$BATS_TEST_TMPDIR/gatemsg"
  mkdir -p "$t"
  git -C "$t" init -q
  run env AGENTS_SCAFFOLD_NO_SYMLINK=1 bash "$SCRIPT" "$t" --forge github --name gatemsg-app --yes
  [ "$status" -eq 0 ]
  cd "$t"
  git add -- .agents/skills .claude/skills
  echo 'drift' >> .claude/skills/handoff/SKILL.md
  git add -- .claude/skills/handoff/SKILL.md
  run bash .git/hooks/pre-commit
  [ "$status" -eq 2 ]
  [[ "$output" == *"  handoff/SKILL.md"* ]]
  [[ "$output" != *"git add .agents/skills .claude/skills"* ]]
}

@test "copy-layout gate blocks a staged deletion of either side, allows switching to the symlink (#61)" {
  t="$BATS_TEST_TMPDIR/gatedel"
  mkdir -p "$t"
  git -C "$t" init -q
  run env AGENTS_SCAFFOLD_NO_SYMLINK=1 bash "$SCRIPT" "$t" --forge github --name gatedel-app --yes
  [ "$status" -eq 0 ]
  cd "$t"
  git add -- .agents/skills .claude/skills
  git -c user.name=t -c user.email=t@t commit -q --no-verify -m init
  # deleting the copy alone
  git rm -r -q -- .claude/skills
  run bash .git/hooks/pre-commit
  [ "$status" -eq 2 ]
  git reset -q --hard
  # deleting the source alone
  git rm -r -q -- .agents/skills
  run bash .git/hooks/pre-commit
  [ "$status" -eq 2 ]
  git reset -q --hard
  # replacing the copy with the symlink is the link layout, not drift
  git rm -r -q --cached -- .claude/skills
  rm -r .claude/skills
  ln -s ../.agents/skills .claude/skills
  git add -- .claude/skills
  run bash .git/hooks/pre-commit
  [ "$status" -eq 0 ]
}

@test "copy-layout gate ignores repos that never had .agents/skills (#61)" {
  t="$BATS_TEST_TMPDIR/gatenoagents"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name noagents-app --yes
  [ "$status" -eq 0 ]
  cd "$t"
  # a Claude-only layout: real .claude/skills, no .agents/
  rm .claude/skills
  cp -R .agents/skills .claude/skills
  rm -r .agents
  git add -- .claude/skills
  run bash .git/hooks/pre-commit
  [ "$status" -eq 0 ]
}

@test "AGENTS_SCAFFOLD_NO_SYMLINK=1 turns an existing symlink into a copy on reinstall and --update (#61)" {
  t="$BATS_TEST_TMPDIR/tocopy"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name tocopy-app --yes
  [ "$status" -eq 0 ]
  [ -L "$t/.claude/skills" ]
  run env AGENTS_SCAFFOLD_NO_SYMLINK=1 bash "$SCRIPT" "$t" --forge github --name tocopy-app --yes
  [ "$status" -eq 0 ]
  [ -d "$t/.claude/skills" ]
  [ ! -L "$t/.claude/skills" ]
  diff -rq "$t/.agents/skills" "$t/.claude/skills"

  t2="$BATS_TEST_TMPDIR/tocopy-update"
  mkdir -p "$t2"
  git -C "$t2" init -q
  run bash "$SCRIPT" "$t2" --forge github --name tocopy2-app --yes
  [ "$status" -eq 0 ]
  run env AGENTS_SCAFFOLD_NO_SYMLINK=1 bash "$SCRIPT" "$t2" --update --yes
  [ "$status" -eq 0 ]
  [ -d "$t2/.claude/skills" ]
  [ ! -L "$t2/.claude/skills" ]
  diff -rq "$t2/.agents/skills" "$t2/.claude/skills"
}

@test "gate warns when .claude/skills is a plain file from a core.symlinks=false checkout (#61)" {
  t="$BATS_TEST_TMPDIR/plainfile"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name plain-app --yes
  [ "$status" -eq 0 ]
  rm "$t/.claude/skills"
  printf '../.agents/skills' > "$t/.claude/skills"
  cd "$t"
  run bash .git/hooks/pre-commit
  [ "$status" -eq 0 ]
  [[ "$output" == *"plain file"* ]]
}

@test "harness agy generates .agents/rules from .claude/rules with converted globs (#63)" {
  t="$BATS_TEST_TMPDIR/agyrules"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --stack python,ops --harness agy --name agyrules-app --yes
  [ "$status" -eq 0 ]
  # paths: -> trigger: glob, relative patterns with a slash get **/, joined by "," without spaces
  grep -qx 'trigger: glob' "$t/.agents/rules/python.md"
  grep -qx 'globs: "\*\*/\*.py,\*\*/app/\*\*/\*.py,\*\*/src/\*\*/\*.py"' "$t/.agents/rules/python.md"
  grep -q '^globs: "Dockerfile,Containerfile,\*.dockerfile,' "$t/.agents/rules/ops.md"
  grep -q ',\*\*/quadlet/\*\*,' "$t/.agents/rules/ops.md"
  # no paths: -> always_on; README.md is documentation, not a rule
  grep -qx 'trigger: always_on' "$t/.agents/rules/common.md"
  [ ! -e "$t/.agents/rules/README.md" ]
  # the body is the source body after the generated marker line
  diff <(awk 'NR==1&&$0=="---"{f=1;next} f&&$0=="---"{f=0;next} !f' "$t/.claude/rules/security.md") \
       <(awk 'NR==1&&$0=="---"{f=1;next} f&&$0=="---"{f=0;next} !f' "$t/.agents/rules/security.md" | tail -n +3)
  grep -q 'Generated by agents-scaffold from .claude/rules/security.md' "$t/.agents/rules/security.md"
}

@test "agy rules are generated for agy and all only (#63)" {
  for h in claude codex all; do
    t="$BATS_TEST_TMPDIR/rules-$h"
    mkdir -p "$t"
    git -C "$t" init -q
    run bash "$SCRIPT" "$t" --forge github --harness "$h" --name "rules-$h" --yes
    [ "$status" -eq 0 ]
    if [ "$h" = "all" ]; then
      [ -f "$t/.agents/rules/common.md" ]
    else
      [ ! -e "$t/.agents/rules" ]
    fi
  done
}

@test "agy rule generation keeps user-owned files and follows --update (#63)" {
  t="$BATS_TEST_TMPDIR/agyrules-upd"
  mkdir -p "$t/.agents/rules"
  git -C "$t" init -q
  echo 'my own agy rule' > "$t/.agents/rules/data.md"
  run bash "$SCRIPT" "$t" --forge github --harness agy --name upd-app --yes
  [ "$status" -eq 0 ]
  [[ "$output" == *".agents/rules/data.md was not generated by agents-scaffold"* ]]
  grep -qx 'my own agy rule' "$t/.agents/rules/data.md"
  # --update regenerates from the current .claude/rules and drops orphans
  printf -- '---\npaths: ["svc/**", "*.sql"]\n---\n# Svc rule\nbody line\n' > "$t/.claude/rules/svc.md"
  run bash "$SCRIPT" "$t" --update --yes
  [ "$status" -eq 0 ]
  grep -qx 'globs: "\*\*/svc/\*\*,\*.sql"' "$t/.agents/rules/svc.md"
  grep -qx 'body line' "$t/.agents/rules/svc.md"
  grep -qx 'my own agy rule' "$t/.agents/rules/data.md"
  # a CRLF source (Windows autocrlf checkout) still yields a glob rule, not always_on
  printf -- '---\r\npaths:\r\n  - "crlf/**"\r\n---\r\nCRLF body\r\n' > "$t/.claude/rules/crlf.md"
  run bash "$SCRIPT" "$t" --update --yes
  [ "$status" -eq 0 ]
  grep -qx 'globs: "\*\*/crlf/\*\*"' "$t/.agents/rules/crlf.md"
  grep -qx 'CRLF body' "$t/.agents/rules/crlf.md"
  # a generated rule whose source is gone is removed on the next --update
  rm "$t/.claude/rules/svc.md"
  run bash "$SCRIPT" "$t" --update --yes
  [ "$status" -eq 0 ]
  [ ! -e "$t/.agents/rules/svc.md" ]
  [ -f "$t/.agents/rules/common.md" ]
}

@test "agy rule globs follow YAML quoting and comments; --update --harness agy migrates (#63)" {
  t="$BATS_TEST_TMPDIR/agyrules-yaml"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name yaml-app --yes
  [ "$status" -eq 0 ]
  [ ! -e "$t/.agents/rules" ]
  printf -- "---\npaths:\n  - 'src/**' # application sources\n  - lib/** # unquoted\n  - \"a#b/**\"\n\n  # comment line\n  - \"**/*.py\"\n---\nbody\n" > "$t/.claude/rules/yc.md"
  printf -- "---\npaths: [\"x/**\", 'y/*.md', z/** ] # trailing\n---\nbody\n" > "$t/.claude/rules/yi.md"
  # an existing Claude-only project moves to agy through --update --harness agy (no marker yet)
  run bash "$SCRIPT" "$t" --update --harness agy --yes
  [ "$status" -eq 0 ]
  [ -f "$t/.agents/rules/common.md" ]
  grep -qx 'globs: "\*\*/src/\*\*,\*\*/lib/\*\*,\*\*/a#b/\*\*,\*\*/\*.py"' "$t/.agents/rules/yc.md"
  grep -qx 'globs: "\*\*/x/\*\*,\*\*/y/\*.md,\*\*/z/\*\*"' "$t/.agents/rules/yi.md"
}

@test "subagent adapters: codex TOML and agy markdown from .claude/agents (#64)" {
  t="$BATS_TEST_TMPDIR/agents-all"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --harness all --name agents-app --yes
  [ "$status" -eq 0 ]
  # codex: name/description/developer_instructions, body as a TOML literal string
  grep -qx 'name = "code-reviewer"' "$t/.codex/agents/code-reviewer.toml"
  grep -qx "developer_instructions = '''" "$t/.codex/agents/code-reviewer.toml"
  grep -q 'Generated by agents-scaffold from .claude/agents/code-reviewer.md' "$t/.codex/agents/code-reviewer.toml"
  # agy: only name and description — Claude tools/model/memory make agy drop the agent
  grep -qx "name: 'code-reviewer'" "$t/.agents/agents/code-reviewer.md"
  run grep -E '^(tools|model|memory):' "$t/.agents/agents/code-reviewer.md"
  [ "$status" -eq 1 ]
  [ ! -e "$t/.agents/agents/README.md" ]
  [ ! -e "$t/.codex/agents/README.toml" ]
  # parsers agree with the source when available (python3 >= 3.11 has tomllib)
  if python3 -c 'import tomllib' 2>/dev/null; then
    run python3 - "$t" <<'PY'
import glob, os, sys, tomllib
t = sys.argv[1]
for f in glob.glob(t + "/.codex/agents/*.toml"):
    with open(f, "rb") as fh:
        d = tomllib.load(fh)
    with open(t + "/.claude/agents/" + os.path.basename(f)[:-5] + ".md", encoding="utf-8") as fh:
        src = fh.read().split("---\n", 2)[2]
    assert set(d) == {"name", "description", "developer_instructions"}, f
    assert d["developer_instructions"].rstrip("\n") == src.rstrip("\n"), f
PY
    [ "$status" -eq 0 ]
  fi
}

@test "subagent adapters follow the harness: claude none, codex toml, agy md (#64)" {
  for h in claude codex agy; do
    t="$BATS_TEST_TMPDIR/agents-$h"
    mkdir -p "$t"
    git -C "$t" init -q
    run bash "$SCRIPT" "$t" --forge github --harness "$h" --name "agents-$h" --yes
    [ "$status" -eq 0 ]
    case "$h" in
      claude) [ ! -e "$t/.codex/agents" ]; [ ! -e "$t/.agents/agents" ] ;;
      codex)  [ -f "$t/.codex/agents/security-audit.toml" ]; [ ! -e "$t/.agents/agents" ] ;;
      agy)    [ -f "$t/.agents/agents/security-audit.md" ]; [ ! -e "$t/.codex/agents" ] ;;
    esac
  done
}

@test "subagent adapters keep user files, quote values, skip triple quotes for codex, follow --update (#64)" {
  t="$BATS_TEST_TMPDIR/agents-upd"
  mkdir -p "$t/.codex/agents"
  git -C "$t" init -q
  echo 'name = "mine"' > "$t/.codex/agents/db-migration.toml"
  run bash "$SCRIPT" "$t" --forge github --name agupd-app --yes
  [ "$status" -eq 0 ]
  [ ! -e "$t/.agents/agents" ]
  # a quoted description, a body with ''' and an orphan-to-be
  cat > "$t/.claude/agents/quoted.md" <<'MD'
---
name: 'quo-ted'
description: "it's a \"test\""
---
body
MD
  cat > "$t/.claude/agents/tq.md" <<'MD'
---
name: tq
description: has triple quotes
---
say '''hi'''
MD
  cat > "$t/.claude/agents/gone.md" <<'MD'
---
name: gone
description: will be removed
---
body
MD
  # an existing Claude-only project moves to Codex and agy through --update --harness all
  run bash "$SCRIPT" "$t" --update --harness all --yes
  [ "$status" -eq 0 ]
  [[ "$output" == *".codex/agents/db-migration.toml was not generated by agents-scaffold"* ]]
  grep -qx 'name = "mine"' "$t/.codex/agents/db-migration.toml"
  [ -f "$t/.agents/agents/db-migration.md" ]
  grep -qxF "description: 'it''s a \"test\"'" "$t/.agents/agents/quoted.md"
  grep -qxF "description = \"it's a \\\"test\\\"\"" "$t/.codex/agents/quoted.toml"
  [[ "$output" == *"tq.md contains '''"* ]]
  [ ! -e "$t/.codex/agents/tq.toml" ]
  [ -f "$t/.agents/agents/tq.md" ]
  # a generated adapter whose source is gone is removed on the next --update
  rm "$t/.claude/agents/gone.md"
  run bash "$SCRIPT" "$t" --update --yes
  [ "$status" -eq 0 ]
  [ ! -e "$t/.codex/agents/gone.toml" ]
  [ ! -e "$t/.agents/agents/gone.md" ]
  [ -f "$t/.codex/agents/code-reviewer.toml" ]
}

@test "harness all keeps everything and wires git hook; default claude also wires it (#21)" {
  t="$BATS_TEST_TMPDIR/allmode"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --harness all --name all-app --yes
  [ "$status" -eq 0 ]
  [ -f "$t/.claude/settings.json" ]
  [ -f "$t/.claude/skills/review/SKILL.md" ]
  [ -f "$t/.agents/skills/review/SKILL.md" ]
  [ ! -e "$t/.gemini" ]
  [ -x "$t/.git/hooks/pre-commit" ]

  # #21: git hook 은 하네스와 무관하게 항상 배선된다. Claude Code 의 PreToolUse 훅은
  # 그 세션이 Bash 툴로 커밋할 때만 발동하므로, 사람이 터미널에서 직접 커밋하거나
  # 다른 하네스가 커밋하면 게이트를 타지 않았다 (이전 동작: claude 모드에서 미배선).
  t2="$BATS_TEST_TMPDIR/claudemode"
  mkdir -p "$t2"
  git -C "$t2" init -q
  run bash "$SCRIPT" "$t2" --forge github --name claude-app --yes
  [ "$status" -eq 0 ]
  [ -x "$t2/.git/hooks/pre-commit" ]

  run bash "$SCRIPT" "$BATS_TEST_TMPDIR" --harness nope --yes
  [ "$status" -eq 1 ]
}

@test "default harness (claude) gate blocks a staged .env through the real git hook (#21)" {
  t="$BATS_TEST_TMPDIR/claudegate"
  mkdir -p "$t"
  git -C "$t" init -q
  run bash "$SCRIPT" "$t" --forge github --name claude-gate --yes
  [ "$status" -eq 0 ]
  cd "$t"
  echo 'X=1' > .env
  git add -f .env
  run bash .git/hooks/pre-commit
  [ "$status" -eq 2 ]
}

@test "stack P0 is inlined into AGENTS.md body, not left as a rules reference (#21)" {
  t="$BATS_TEST_TMPDIR/p0inline"
  mkdir -p "$t"
  run bash "$SCRIPT" "$t" --forge github --stack python,springboot --name p0-app --yes
  [ "$status" -eq 0 ]
  # 선택한 두 스택의 P0 가 본문에 삽입된다
  grep -q '^\*\*python\*\*$' "$t/AGENTS.md"
  grep -q '^\*\*springboot\*\*$' "$t/AGENTS.md"
  grep -q 'mypy' "$t/AGENTS.md"
  # 선택하지 않은 스택은 삽입되지 않는다 (context flooding 방지)
  ! grep -q '^\*\*rust\*\*$' "$t/AGENTS.md"
  # 참조 위임 문구는 사라졌다
  ! grep -q '.claude/rules/<stack>.md` 의 `## P0` 섹션 참조' "$t/AGENTS.md"
}

@test "AGENTS.md owns the single memory-index @import (#54, supersedes #21)" {
  t="$BATS_TEST_TMPDIR/noimport"
  mkdir -p "$t"
  run bash "$SCRIPT" "$t" --forge github --name noimport-app --yes
  [ "$status" -eq 0 ]
  run grep -c '^@' "$t/AGENTS.md"
  [ "$output" = "1" ]
  grep -q '^@.claude/memory/MEMORY.md$' "$t/AGENTS.md"
  [ -f "$t/.claude/memory/MEMORY.md" ]
}

@test "every stack preset has a P0 section and an AGENTS.partial.md (#21)" {
  for d in "$REPO_ROOT"/presets/*/; do
    name="$(basename "$d")"
    case "$name" in forge-*|lang-*) continue ;; esac
    [ -f "$d/AGENTS.partial.md" ] || { echo "missing AGENTS.partial.md: $name"; return 1; }
    rf="$(find "$d/.claude/rules" -name '*.md' -type f | head -1)"
    grep -q '^## P0' "$rf" || { echo "missing ## P0: $rf"; return 1; }
    en="$REPO_ROOT/presets/lang-en/stacks/$name"
    [ -f "$en/AGENTS.partial.md" ] || { echo "missing en AGENTS.partial.md: $name"; return 1; }
    erf="$(find "$en/.claude/rules" -name '*.md' -type f | head -1)"
    grep -q '^## P0' "$erf" || { echo "missing en ## P0: $erf"; return 1; }
  done
}

# --- 19) ruby-rails 프리셋 (#9) ---

@test "ruby-rails stack merges rules and splices partial after marker" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack ruby-rails --yes
  [ "$status" -eq 0 ]
  grep -q 'Ruby on Rails' "$BATS_TEST_TMPDIR/.claude/rules/ruby-rails.md"
  grep -q '^## P0' "$BATS_TEST_TMPDIR/.claude/rules/ruby-rails.md"
  marker_line="$(grep -n 'STACK CHECKS' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh" | head -1 | cut -d: -f1)"
  gate_line="$(grep -n 'ruby-rails: master.key' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh" | head -1 | cut -d: -f1)"
  [ "$gate_line" -gt "$marker_line" ]
  # 스택 P0 가 AGENTS.md 본문에 인라인됐는지 (#21)
  grep -q 'ruby-rails' "$BATS_TEST_TMPDIR/AGENTS.md"
}

@test "ruby-rails gate blocks a staged master.key, passes without one (#9)" {
  target="$BATS_TEST_TMPDIR/railsgate"
  mkdir -p "$target"
  run "$SCRIPT" "$target" --stack ruby-rails --yes
  [ "$status" -eq 0 ]

  cd "$target"
  git init -q -b main
  git config user.name t; git config user.email t@e.c
  # Gemfile 이 있어야 게이트가 켜진다. rubocop/rspec 은 미설치 → 통과해야 함.
  printf "source 'https://rubygems.org'\n" > Gemfile
  mkdir -p app/models config
  printf "class User < ApplicationRecord\nend\n" > app/models/user.rb
  git add Gemfile app/models/user.rb
  run bash .claude/hooks/pre-commit.sh
  [ "$status" -eq 0 ]

  printf 'deadbeef\n' > config/master.key
  git add -f config/master.key
  run bash .claude/hooks/pre-commit.sh
  [ "$status" -eq 2 ]
  [[ "$output" == *"master.key"* ]]
}

@test "ruby-rails combined with another stack: both gates run (#6 regression class)" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack ruby-rails,bun --yes
  [ "$status" -eq 0 ]
  grep -q 'ruby-rails: master.key' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh"
  grep -q 'tsc' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh"
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/ruby-rails.md" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/bun.md" ]
}

# --- 20) dotnet 프리셋 (#7) ---

@test "dotnet stack merges rules and splices partial after marker" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack dotnet --yes
  [ "$status" -eq 0 ]
  grep -q '.NET' "$BATS_TEST_TMPDIR/.claude/rules/dotnet.md"
  grep -q '^## P0' "$BATS_TEST_TMPDIR/.claude/rules/dotnet.md"
  marker_line="$(grep -n 'STACK CHECKS' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh" | head -1 | cut -d: -f1)"
  gate_line="$(grep -n 'dotnet: secrets' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh" | head -1 | cut -d: -f1)"
  [ "$gate_line" -gt "$marker_line" ]
  # 스택 P0 가 AGENTS.md 본문에 인라인됐는지 (#21)
  grep -q 'dotnet' "$BATS_TEST_TMPDIR/AGENTS.md"
}

@test "dotnet gate blocks a staged secrets.json (#7)" {
  target="$BATS_TEST_TMPDIR/dotnetgate"
  mkdir -p "$target"
  run "$SCRIPT" "$target" --stack dotnet --yes
  [ "$status" -eq 0 ]

  cd "$target"
  git init -q -b main
  git config user.name t; git config user.email t@e.c
  # csproj 가 추적돼야 게이트가 켜진다.
  printf '<Project Sdk="Microsoft.NET.Sdk"></Project>\n' > App.csproj
  git add App.csproj
  printf '{"ConnectionStrings":{"Default":"x"}}\n' > secrets.json
  git add -f secrets.json
  run bash .claude/hooks/pre-commit.sh
  [ "$status" -eq 2 ]
  [[ "$output" == *"secrets.json"* ]]
}

@test "dotnet gate is a no-op without a project file (#7)" {
  target="$BATS_TEST_TMPDIR/dotnetnoop"
  mkdir -p "$target"
  run "$SCRIPT" "$target" --stack dotnet --yes
  [ "$status" -eq 0 ]

  cd "$target"
  git init -q -b main
  git config user.name t; git config user.email t@e.c
  printf 'hello\n' > README.md
  git add README.md
  run bash .claude/hooks/pre-commit.sh
  [ "$status" -eq 0 ]
}

@test "dotnet combined with another stack: both gates run (#6 regression class)" {
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --stack dotnet,bun --yes
  [ "$status" -eq 0 ]
  grep -q 'dotnet: secrets' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh"
  grep -q 'tsc' "$BATS_TEST_TMPDIR/.claude/hooks/pre-commit.sh"
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/dotnet.md" ]
  [ -f "$BATS_TEST_TMPDIR/.claude/rules/bun.md" ]
}

# --- 오프라인 번들 · Windows 줄끝 (#58) ---

@test "offline bundle installs from extracted tree without network (#58)" {
  command -v git >/dev/null || skip "git required"
  # CI 체크아웃은 HEAD 커밋이 있으므로 git archive 가능. 번들은 커밋 내용 기준이다.
  run "$REPO_ROOT/scripts/make-offline-bundle.sh" --out "$BATS_TEST_TMPDIR/dist"
  [ "$status" -eq 0 ]
  (cd "$BATS_TEST_TMPDIR/dist" && sha256sum -c SHA256SUMS >/dev/null 2>&1 || shasum -a 256 -c SHA256SUMS >/dev/null)
  ls "$BATS_TEST_TMPDIR"/dist/agents-scaffold-offline-*.zip >/dev/null

  mkdir -p "$BATS_TEST_TMPDIR/x" "$BATS_TEST_TMPDIR/target"
  tar -xzf "$BATS_TEST_TMPDIR"/dist/agents-scaffold-offline-*.tar.gz -C "$BATS_TEST_TMPDIR/x"
  bundle="$BATS_TEST_TMPDIR/x/agents-scaffold"
  [ -f "$bundle/bin/agents-scaffold.cmd" ]

  # 원격 소스를 도달 불가 주소로 바꿔도 성공해야 한다 = 다운로드 경로를 타지 않음
  AGENTS_SCAFFOLD_REPO="http://127.0.0.1:9/unreachable" \
    run bash "$bundle/bin/agents-scaffold.sh" "$BATS_TEST_TMPDIR/target" --yes
  [ "$status" -eq 0 ]
  [[ "$output" != *"remote install"* ]]
  [ -f "$BATS_TEST_TMPDIR/target/AGENTS.md" ]
  [ -f "$BATS_TEST_TMPDIR/target/.claude/hooks/pre-commit.sh" ]
}

@test "install adds hook LF rule to .gitattributes idempotently (#58)" {
  printf '*.png binary' > "$BATS_TEST_TMPDIR/.gitattributes"   # 개행 없이 끝나는 기존 파일
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --yes
  [ "$status" -eq 0 ]
  grep -qx '\*.png binary' "$BATS_TEST_TMPDIR/.gitattributes"
  grep -qx '.claude/hooks/\*.sh text eol=lf' "$BATS_TEST_TMPDIR/.gitattributes"

  run "$SCRIPT" --update "$BATS_TEST_TMPDIR"
  [ "$status" -eq 0 ]
  [ "$(grep -c '.claude/hooks/\*.sh' "$BATS_TEST_TMPDIR/.gitattributes")" -eq 1 ]
}

@test "windows launcher is CRLF and ASCII-only (#58)" {
  f="$REPO_ROOT/bin/agents-scaffold.cmd"
  [ -f "$f" ]
  # cmd.exe 는 LF 전용 배치에서 파싱이 어긋날 수 있고, 비ASCII 는 코드페이지에 따라 깨진다
  [ "$(grep -c $'\r$' "$f")" -eq "$(wc -l < "$f")" ]
  ! LC_ALL=C grep -q $'[\x80-\xff]' "$f"
}

@test "existing crlf or commented hook rule still gets LF override (#58)" {
  printf '# .claude/hooks/*.sh text eol=lf\n.claude/hooks/*.sh text eol=crlf\n' > "$BATS_TEST_TMPDIR/.gitattributes"
  run "$SCRIPT" "$BATS_TEST_TMPDIR" --yes
  [ "$status" -eq 0 ]
  [ "$(tail -n2 "$BATS_TEST_TMPDIR/.gitattributes" | head -n1)" = '.claude/hooks/*.sh text eol=lf' ]

  # git 레포에서는 실효값으로 판정: 광역 crlf 규칙이 뒤에 와도 LF 가 다시 붙는다
  t2="$BATS_TEST_TMPDIR/repo"; mkdir -p "$t2"; git -C "$t2" init -q
  printf '.claude/hooks/*.sh text eol=lf\n*.sh text eol=crlf\n' > "$t2/.gitattributes"
  run "$SCRIPT" "$t2" --yes
  [ "$status" -eq 0 ]
  [ "$(git -C "$t2" check-attr eol -- .claude/hooks/pre-commit.sh)" = '.claude/hooks/pre-commit.sh: eol: lf' ]
}

@test "LF rule judged from repo .gitattributes only, not local git config (#58)" {
  # .git/info/attributes 의 LF 는 다른 체크아웃에 없다 → 레포 .gitattributes 에 규칙이 추가돼야 한다
  t="$BATS_TEST_TMPDIR/repo"; mkdir -p "$t"; git -C "$t" init -q
  mkdir -p "$t/.git/info"; printf '.claude/hooks/*.sh text eol=lf\n' > "$t/.git/info/attributes"
  run "$SCRIPT" "$t" --yes
  [ "$status" -eq 0 ]
  grep -qx '.claude/hooks/\*.sh text eol=lf' "$t/.gitattributes"

  # 비-레포(worktree 처럼 .git 디렉터리 없음)에서도 뒤따르는 광역 crlf 를 실효값으로 잡는다
  u="$BATS_TEST_TMPDIR/plain"; mkdir -p "$u"
  printf '.claude/hooks/*.sh text eol=lf\n*.sh text eol=crlf\n' > "$u/.gitattributes"
  run "$SCRIPT" "$u" --yes
  [ "$status" -eq 0 ]
  [ "$(tail -n2 "$u/.gitattributes" | head -n1)" = '.claude/hooks/*.sh text eol=lf' ]
}
