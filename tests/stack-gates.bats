#!/usr/bin/env bats
# 스택 프리셋 pre-commit 게이트(presets/stacks/<stack>/.claude/hooks/pre-commit.partial.sh) 실동작 테스트 (#107)
#
# 실행: bats tests/stack-gates.bats
#
# 실제 툴체인에 의존하지 않는다. 훅은 격리된 PATH 로만 실행한다:
#   $FAKE  — 테스트가 만든 가짜 툴(서브커맨드별 exit code 를 흉내낸다)
#   $SAFE  — 훅이 쓰는 기본 유틸(git·grep·sed…)만 심링크한 디렉터리
# 러너에 dotnet·go·java 가 깔려 있어도 PATH 에 없으므로 가짜 fixture 프로젝트에 실제 빌드가
# 돌지 않는다(.claude/memory/project_preset-gate-verification.md 의 CI 전용 실패 회피).
# 가짜 툴은 호출 인자를 $FAKE_LOG 에 남긴다 — "무엇을 실행했는가"까지 단언할 수 있다.
#
# 테스트 이름은 ASCII 로 유지한다(tests/agents-scaffold.bats 머리말 참조).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  SCRIPT="$REPO_ROOT/bin/agents-scaffold.sh"
  FAKE="$BATS_TEST_TMPDIR/fakebin"
  SAFE="$BATS_TEST_TMPDIR/safebin"
  FAKE_LOG="$BATS_TEST_TMPDIR/fake.log"
  mkdir -p "$FAKE" "$SAFE"
  : > "$FAKE_LOG"
  local tool path
  for tool in bash sh env git grep sed awk diff sort tail head find cat tr cut dirname basename \
    mkdir rm ls wc uname cmp; do
    path="$(command -v "$tool" 2>/dev/null)" || continue
    ln -s "$path" "$SAFE/$tool"
  done
}

# install_stack <stack> — 임시 디렉터리에 스캐폴드를 깔고 git 레포로 만든 뒤 그 안으로 들어간다.
install_stack() {
  local target="$BATS_TEST_TMPDIR/proj"
  mkdir -p "$target"
  "$SCRIPT" "$target" --stack "$1" --yes >/dev/null
  cd "$target" || return 1
  git init -q -b main
  git config user.name t
  git config user.email t@e.c
}

# fake_at <path> <log-name> — stdin 본문으로 가짜 실행 파일을 만든다. 호출은 $FAKE_LOG 에 남는다.
fake_at() {
  {
    printf '#!/usr/bin/env bash\n'
    printf 'echo "%s $*" >> "$FAKE_LOG"\n' "$2"
    cat
  } > "$1"
  chmod +x "$1"
}

# fake <tool> — $FAKE(PATH 맨 앞)에 가짜 툴을 만든다.
fake() { fake_at "$FAKE/$1" "$1"; }

# 격리된 PATH 로 훅을 실행한다.
run_hook() {
  run env PATH="$FAKE:$SAFE" FAKE_LOG="$FAKE_LOG" "$@" bash .claude/hooks/pre-commit.sh
}

# refute_logged <ERE> — 가짜 툴이 그렇게 호출되지 않았어야 한다.
# bats 에서 `! cmd` 는 마지막 줄이 아니면 테스트를 실패시키지 않는다(SC2314) — 그래서 함수로 둔다.
refute_logged() {
  if grep -qE -- "$1" "$FAKE_LOG"; then
    echo "unexpected call matching '$1':"
    cat "$FAKE_LOG"
    return 1
  fi
}

stage() {
  local f
  for f in "$@"; do
    mkdir -p "$(dirname "$f")"
    [ -e "$f" ] || printf 'x\n' > "$f"
    git add -f -- "$f"
  done
}

# --- 계약: 전 스택 공통 ---

@test "every stack with a gate partial has a blocks test and a no-op test here" {
  local p stack missing=0
  for p in "$REPO_ROOT"/presets/stacks/*/.claude/hooks/pre-commit.partial.sh; do
    stack="$(basename "$(dirname "$(dirname "$(dirname "$p")")")")"
    grep -qE "^@test \"$stack gate blocks" "$BATS_TEST_FILENAME" || { echo "no blocks test: $stack"; missing=1; }
    grep -qE "^@test \"$stack gate is a no-op" "$BATS_TEST_FILENAME" || { echo "no no-op test: $stack"; missing=1; }
  done
  [ "$missing" -eq 0 ]
}

@test "gate partials print English messages only (comments may be Korean)" {
  run python3 - "$REPO_ROOT"/presets/stacks/*/.claude/hooks/pre-commit.partial.sh <<'PY'
import re, sys
bad = []
for path in sys.argv[1:]:
    for no, line in enumerate(open(path, encoding="utf-8"), 1):
        code = line.split("#", 1)[0] if line.lstrip().startswith("#") else line
        if re.search(r"\b(echo|printf)\b", code) and re.search(r"[ㄱ-ㆎ가-힣]", code):
            bad.append(f"{path}:{no}: {line.rstrip()}")
print("\n".join(bad))
sys.exit(1 if bad else 0)
PY
  [ "$status" -eq 0 ]
}

@test "gate partials block with exit 2 only (no other exit code)" {
  local p found=0
  for p in "$REPO_ROOT"/presets/stacks/*/.claude/hooks/pre-commit.partial.sh; do
    # 주석 줄은 뺀다(계약 설명에 `exit 0` 이 나온다)
    if grep -vE '^[[:space:]]*#' "$p" | grep -nE '(^|[^[:alnum:]_])exit[[:space:]]+([013-9]|2[0-9])'; then
      echo "non-2 exit in: $p"
      found=1
    fi
  done
  [ "$found" -eq 0 ]
}

# --- android ---

@test "android gate blocks when ktlint fails" {
  install_stack android
  fake_at ./gradlew gradlew <<'SH'
[ "$1" = "ktlintCheck" ] && { echo "Main.kt:3:1 Unexpected indentation"; exit 1; }
exit 0
SH
  stage app/src/main/kotlin/Main.kt
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: ktlint failed"* ]]
  [[ "$output" == *"Unexpected indentation"* ]]
}

@test "android gate passes when ktlint and detekt pass" {
  install_stack android
  fake_at ./gradlew gradlew <<'SH'
exit 0
SH
  stage app/src/main/kotlin/Main.kt
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^gradlew ktlintCheck' "$FAKE_LOG"
  grep -q '^gradlew detekt' "$FAKE_LOG"
}

@test "android gate ignores .kt files under build/, .gradle/ and node_modules/" {
  install_stack android
  fake_at ./gradlew gradlew <<'SH'
exit 1
SH
  mkdir -p app/build/generated .gradle/caches node_modules/pkg
  printf 'x\n' > app/build/generated/Gen.kt
  printf 'x\n' > .gradle/caches/Cached.kt
  printf 'x\n' > node_modules/pkg/Dep.kt
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

@test "android gate is a no-op without gradlew" {
  install_stack android
  stage app/src/main/kotlin/Main.kt
  run_hook
  [ "$status" -eq 0 ]
}

# --- bun ---

@test "bun gate blocks on TypeScript errors" {
  install_stack bun
  fake bunx <<'SH'
case "$*" in
  *"tsc --version"*) exit 0 ;;
  *"tsc --noEmit"*) echo "src/a.ts(1,7): error TS2322: Type 'string' is not assignable to type 'number'."; exit 2 ;;
esac
SH
  stage tsconfig.json
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: TypeScript errors"* ]]
  [[ "$output" == *"error TS2322"* ]]
}

@test "bun gate passes on a clean typecheck and when tsc is unavailable" {
  install_stack bun
  stage tsconfig.json
  # tsc 없음 → 경고만 하고 통과
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"skipping typecheck"* ]]

  fake bunx <<'SH'
exit 0
SH
  run_hook
  [ "$status" -eq 0 ]
  grep -q 'tsc --noEmit' "$FAKE_LOG"
}

@test "bun gate is a no-op without tsconfig.json" {
  install_stack bun
  fake bunx <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- nextjs ---

@test "nextjs gate blocks on TypeScript errors" {
  install_stack nextjs
  fake npx <<'SH'
case "$*" in
  *"tsc --version"*) exit 0 ;;
  *"tsc --noEmit"*) echo "app/page.tsx(4,3): error TS2304: Cannot find name 'foo'."; exit 2 ;;
esac
SH
  stage tsconfig.json
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: TypeScript errors"* ]]
  [[ "$output" == *"error TS2304"* ]]
}

@test "nextjs gate passes on a clean typecheck, preferring bunx over npx" {
  install_stack nextjs
  fake npx <<'SH'
exit 1
SH
  fake bunx <<'SH'
exit 0
SH
  stage tsconfig.json
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^bunx .*tsc --noEmit' "$FAKE_LOG"
  refute_logged '^npx'
}

@test "nextjs gate is a no-op without tsconfig.json" {
  install_stack nextjs
  fake npx <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- dotnet ---

@test "dotnet gate blocks when the build fails" {
  install_stack dotnet
  fake dotnet <<'SH'
[ "$1" = "build" ] && { echo "Program.cs(3,1): error CS1002: ; expected"; exit 1; }
exit 0
SH
  stage App.csproj
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: dotnet build failed"* ]]
  [[ "$output" == *"error CS1002"* ]]
}

@test "dotnet gate blocks on a format mismatch and on failing tests" {
  install_stack dotnet
  fake dotnet <<'SH'
[ "$1" = "format" ] && [ "$2" = "--verify-no-changes" ] && exit 2
exit 0
SH
  stage App.csproj
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: formatting differs"* ]]

  fake dotnet <<'SH'
[ "$1" = "test" ] && exit 1
exit 0
SH
  stage App.Tests/App.Tests.csproj
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: dotnet test failed"* ]]
}

@test "dotnet gate passes when build and format pass, and when the SDK is missing" {
  install_stack dotnet
  stage App.csproj
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"dotnet SDK not installed"* ]]

  fake dotnet <<'SH'
exit 0
SH
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^dotnet build' "$FAKE_LOG"
  # 테스트 프로젝트가 없으면 dotnet test 를 돌리지 않는다
  refute_logged '^dotnet test'
}

@test "dotnet gate is a no-op without a project file" {
  install_stack dotnet
  fake dotnet <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- flutter ---

@test "flutter gate blocks on unformatted files and on analyze failure" {
  install_stack flutter
  fake flutter <<'SH'
exit 0
SH
  fake dart <<'SH'
exit 1
SH
  stage pubspec.yaml
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: some files are not formatted"* ]]

  fake dart <<'SH'
exit 0
SH
  fake flutter <<'SH'
[ "$1" = "analyze" ] && { echo "error - Undefined name 'x' - lib/main.dart:3:5"; exit 1; }
exit 0
SH
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: flutter analyze failed"* ]]
  [[ "$output" == *"Undefined name"* ]]
}

@test "flutter gate passes when checks pass, and when flutter is missing" {
  install_stack flutter
  stage pubspec.yaml
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"flutter not installed"* ]]

  fake flutter <<'SH'
exit 0
SH
  fake dart <<'SH'
exit 0
SH
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^flutter analyze' "$FAKE_LOG"
  # test/ 디렉터리가 없으면 flutter test 를 돌리지 않는다
  refute_logged '^flutter test'
}

@test "flutter gate is a no-op without pubspec.yaml" {
  install_stack flutter
  fake flutter <<'SH'
exit 1
SH
  fake dart <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- go ---

@test "go gate blocks when build, vet or golangci-lint fails" {
  install_stack go
  fake go <<'SH'
[ "$1" = "build" ] && { echo "./main.go:5:2: undefined: foo"; exit 1; }
exit 0
SH
  stage go.mod
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: go build failed"* ]]
  [[ "$output" == *"undefined: foo"* ]]

  fake go <<'SH'
[ "$1" = "vet" ] && exit 1
exit 0
SH
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: go vet failed"* ]]

  fake go <<'SH'
exit 0
SH
  fake golangci-lint <<'SH'
[ "$2" = "--help" ] && { echo "      --fast-only   Filter enabled linters to run only fast linters"; exit 0; }
exit 1
SH
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: golangci-lint failed"* ]]
  # v2 는 --fast-only 로 호출한다
  grep -q '^golangci-lint run --fast-only' "$FAKE_LOG"
}

@test "go gate passes when build and vet pass, and when go is missing" {
  install_stack go
  stage go.mod
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"go not installed"* ]]

  fake go <<'SH'
exit 0
SH
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^go build' "$FAKE_LOG"
  grep -q '^go vet' "$FAKE_LOG"
}

@test "go gate is a no-op without go.mod" {
  install_stack go
  fake go <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- javaweb ---

@test "javaweb gate blocks when the maven compile fails" {
  install_stack javaweb
  fake mvn <<'SH'
echo "[ERROR] COMPILATION ERROR"
exit 1
SH
  stage pom.xml
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: maven compile failed"* ]]
  [[ "$output" == *"COMPILATION ERROR"* ]]
}

@test "javaweb gate blocks a newly added JSP scriptlet with an English message" {
  install_stack javaweb
  mkdir -p src/main/webapp
  printf '<%% String id = request.getParameter("id"); %%>\n' > src/main/webapp/bad.jsp
  git add src/main/webapp/bad.jsp
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: new JSP scriptlet"* ]]
  [[ "$output" == *"request.getParameter"* ]]
}

@test "javaweb gate passes when the compile passes, and when no build tool is installed" {
  install_stack javaweb
  stage pom.xml
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"maven not installed"* ]]

  fake mvn <<'SH'
exit 0
SH
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^mvn -q -DskipTests compile' "$FAKE_LOG"
}

@test "javaweb gate is a no-op without a build file or JSP" {
  install_stack javaweb
  fake mvn <<'SH'
exit 1
SH
  fake ant <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- php-laravel ---

@test "php-laravel gate blocks when composer validate, pint or phpunit fails" {
  install_stack php-laravel
  fake composer <<'SH'
echo "./composer.json is invalid"
exit 2
SH
  stage composer.json
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: composer validate failed"* ]]
  [[ "$output" == *"composer.json is invalid"* ]]

  fake composer <<'SH'
exit 0
SH
  fake php <<'SH'
exit 0
SH
  mkdir -p vendor/bin tests
  fake_at vendor/bin/pint pint <<'SH'
exit 1
SH
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: style differs"* ]]

  fake_at vendor/bin/pint pint <<'SH'
exit 0
SH
  fake_at vendor/bin/phpunit phpunit <<'SH'
echo "FAILURES!"
exit 1
SH
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: phpunit failed"* ]]
}

@test "php-laravel gate passes when checks pass, and when composer and php are missing" {
  install_stack php-laravel
  stage composer.json
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"composer not installed"* ]]
  [[ "$output" == *"php not installed"* ]]

  fake composer <<'SH'
exit 0
SH
  fake php <<'SH'
exit 0
SH
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^composer validate' "$FAKE_LOG"
  [[ "$output" == *"pint not installed"* ]]
}

@test "php-laravel gate is a no-op without composer.json" {
  install_stack php-laravel
  fake composer <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- python ---

@test "python gate blocks on ruff findings and shows them" {
  install_stack python
  fake ruff <<'SH'
[ "$1" = "check" ] && { echo "app/main.py:1:8: F401 [*] \`os\` imported but unused"; exit 1; }
exit 0
SH
  stage app/main.py
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: ruff check failed"* ]]
  # ruff 출력이 버려지지 않는다
  [[ "$output" == *"F401"* ]]
}

@test "python gate ignores uv on PATH unless the project uses uv" {
  install_stack python
  fake uv <<'SH'
exit 1
SH
  fake ruff <<'SH'
exit 0
SH
  stage app/main.py
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^ruff check' "$FAKE_LOG"
  refute_logged '^uv'
}

@test "python gate blocks through uv run ruff in a uv project, falls back to ruff when uv cannot resolve it" {
  install_stack python
  fake uv <<'SH'
case "$*" in
  "run ruff --version") exit 0 ;;
  "run ruff check .") echo "app/main.py:2:1: E999 SyntaxError"; exit 1 ;;
esac
exit 1
SH
  fake ruff <<'SH'
exit 0
SH
  stage app/main.py uv.lock
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"E999"* ]]

  # uv 환경에 ruff 가 없으면 PATH 의 ruff 로 폴백한다
  fake uv <<'SH'
exit 1
SH
  : > "$FAKE_LOG"
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^ruff check' "$FAKE_LOG"
  refute_logged '^uv run ruff check'
}

@test "python gate blocks on mypy errors when mypy is configured" {
  install_stack python
  fake mypy <<'SH'
echo "src/pkg/mod.py:3: error: Incompatible return value type  [return-value]"
echo "Found 1 error in 1 file (checked 1 source file)"
exit 1
SH
  printf '[tool.mypy]\nstrict = true\n' > pyproject.toml
  stage src/pkg/mod.py pyproject.toml
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: mypy failed"* ]]
  [[ "$output" == *"Incompatible return value type"* ]]
  grep -q '^mypy src' "$FAKE_LOG"
}

@test "python gate skips mypy when it is not configured" {
  install_stack python
  fake mypy <<'SH'
exit 1
SH
  # setup.cfg 는 있지만 [mypy] 섹션이 없다
  printf '[metadata]\nname = x\n' > setup.cfg
  stage src/pkg/mod.py setup.cfg
  run_hook
  [ "$status" -eq 0 ]
  refute_logged '^mypy'

  printf '[mypy]\nstrict = True\n' > setup.cfg
  run_hook
  [ "$status" -eq 2 ]
}

@test "python gate passes when ruff and mypy pass, and when neither is installed" {
  install_stack python
  printf '[mypy]\n' > mypy.ini
  stage app/main.py mypy.ini
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"ruff not installed"* ]]
  [[ "$output" == *"mypy is configured but not installed"* ]]

  fake ruff <<'SH'
exit 0
SH
  fake mypy <<'SH'
exit 0
SH
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^ruff check \.' "$FAKE_LOG"
  grep -q '^mypy app' "$FAKE_LOG"
}

@test "python gate is a no-op without Python files" {
  install_stack python
  fake ruff <<'SH'
exit 1
SH
  fake mypy <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- ruby-rails ---

@test "ruby-rails gate blocks when rubocop or rspec fails" {
  install_stack ruby-rails
  fake rubocop <<'SH'
[ "$1" = "--version" ] && exit 0
echo "app/models/user.rb:1:1: C: Style/FrozenStringLiteralComment"
exit 1
SH
  stage Gemfile
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: rubocop failed"* ]]
  [[ "$output" == *"FrozenStringLiteralComment"* ]]

  fake rubocop <<'SH'
exit 0
SH
  fake rspec <<'SH'
[ "$1" = "--version" ] && exit 0
exit 1
SH
  mkdir -p spec
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: rspec failed"* ]]
}

@test "ruby-rails gate passes when rubocop passes, and when it is missing" {
  install_stack ruby-rails
  stage Gemfile
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"rubocop not installed"* ]]

  fake rubocop <<'SH'
exit 0
SH
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^rubocop --force-exclusion' "$FAKE_LOG"
}

@test "ruby-rails gate is a no-op without a Gemfile" {
  install_stack ruby-rails
  fake rubocop <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- rust ---

@test "rust gate blocks when cargo check or clippy fails" {
  install_stack rust
  fake cargo <<'SH'
[ "$1" = "check" ] && { echo "error[E0425]: cannot find value \`x\` in this scope"; exit 101; }
exit 0
SH
  stage Cargo.toml
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: cargo check failed"* ]]
  [[ "$output" == *"E0425"* ]]

  fake cargo <<'SH'
[ "$1" = "clippy" ] && [ "$2" = "--quiet" ] && { echo "error: this loop never actually loops"; exit 101; }
exit 0
SH
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: cargo clippy errors"* ]]
  [[ "$output" == *"never actually loops"* ]]
}

@test "rust gate passes when cargo passes, and when cargo is missing" {
  install_stack rust
  stage Cargo.toml
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"cargo not installed"* ]]

  fake cargo <<'SH'
exit 0
SH
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^cargo check' "$FAKE_LOG"
}

@test "rust gate is a no-op without Cargo.toml" {
  install_stack rust
  fake cargo <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- springboot ---

@test "springboot gate blocks when the gradle compile fails" {
  install_stack springboot
  fake_at ./gradlew gradlew <<'SH'
echo "App.java:7: error: cannot find symbol"
exit 1
SH
  stage build.gradle
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: gradle testClasses failed"* ]]
  [[ "$output" == *"cannot find symbol"* ]]
}

@test "springboot gate blocks when the maven compile fails" {
  install_stack springboot
  fake mvn <<'SH'
echo "[ERROR] COMPILATION ERROR"
exit 1
SH
  stage pom.xml
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: maven test-compile failed"* ]]
  grep -q '^mvn -q test-compile' "$FAKE_LOG"
}

@test "springboot gate compiles without running the test suite unless SPRINGBOOT_GATE_TESTS=1" {
  install_stack springboot
  # 테스트 태스크는 실패하고 컴파일 태스크만 성공하는 gradlew
  fake_at ./gradlew gradlew <<'SH'
for a in "$@"; do [ "$a" = "test" ] && exit 1; done
exit 0
SH
  stage build.gradle.kts
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^gradlew -q testClasses' "$FAKE_LOG"

  run_hook SPRINGBOOT_GATE_TESTS=1
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: gradle test failed"* ]]
}

@test "springboot gate passes with a warning when the build tool is missing" {
  install_stack springboot
  stage build.gradle
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"no executable ./gradlew"* ]]

  git rm -q --cached build.gradle
  rm build.gradle
  stage pom.xml
  run_hook
  [ "$status" -eq 0 ]
  [[ "$output" == *"maven not installed"* ]]
}

@test "springboot gate is a no-op without a build file" {
  install_stack springboot
  # 빌드 파일 없이 gradlew 만 있는 레포: 게이트가 켜지면 안 된다
  fake_at ./gradlew gradlew <<'SH'
exit 1
SH
  fake mvn <<'SH'
exit 1
SH
  stage README.md
  run_hook
  [ "$status" -eq 0 ]
  [ ! -s "$FAKE_LOG" ]
}

# --- 조합: 앞 스택이 통과해도 뒤 스택 게이트가 돈다 (#6 회귀 클래스) ---

@test "combined stacks: a passing gate does not swallow a later blocking gate" {
  install_stack python,springboot,go
  fake ruff <<'SH'
exit 0
SH
  fake go <<'SH'
exit 0
SH
  fake_at ./gradlew gradlew <<'SH'
exit 1
SH
  stage app/main.py go.mod build.gradle
  run_hook
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked: gradle testClasses failed"* ]]

  fake_at ./gradlew gradlew <<'SH'
exit 0
SH
  : > "$FAKE_LOG"
  run_hook
  [ "$status" -eq 0 ]
  grep -q '^ruff check' "$FAKE_LOG"
  grep -q '^gradlew -q testClasses' "$FAKE_LOG"
  grep -q '^go build' "$FAKE_LOG"
}
