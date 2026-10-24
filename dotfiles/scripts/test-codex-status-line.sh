#!/usr/bin/env bash
# codex/status-line.py 왕복 시험 — 임시 HOME 에서 apply 2회(멱등) → restore 후 원본과 바이트 단위 비교.
# 실제 홈은 건드리지 않는다. 사용법: scripts/test-codex-status-line.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=codex/status-line.py
fail=0
T="$(mktemp -d)"
# 좁은 터미널에서는 뒤부터 잘리므로 순서 자체가 사양이다 (#9) — 위치 → 모델 → 컨텍스트 → 비용 → 한도 → 부가 정보
WANT_LINE='status_line = ["current-dir", "estimated-thread-cost", "thread-credits", "weekly-limit", "five-hour-limit", "model-with-reasoning", "context-used", "git-branch", "total-input-tokens", "total-output-tokens", "fast-mode", "codex-version"]'

run() { HOME="$T/$1" python3 "$PY" "$2"; }

roundtrip() {           # roundtrip <케이스 이름> — $T/<이름>/.codex/config.toml 이 준비돼 있어야 한다 (없으면 "파일 없음" 케이스)
  local name="$1" cfg="$T/$1/.codex/config.toml"
  mkdir -p "$T/$name/.codex"
  [ -f "$cfg" ] && cp "$cfg" "$T/$name.expected"
  run "$name" check
  run "$name" apply >/dev/null
  cp "$cfg" "$T/$name.applied"
  run "$name" apply | grep -q '이미 최신' || { echo "FAIL $name: 두 번째 apply 가 멱등이 아님"; fail=1; }
  cmp -s "$cfg" "$T/$name.applied" || { echo "FAIL $name: 두 번째 apply 가 파일을 바꿈"; fail=1; }
  grep -qxF "$WANT_LINE" "$cfg" || { echo "FAIL $name: status_line 이 기대한 순서와 다름"; grep status_line "$cfg"; fail=1; }
  run "$name" restore >/dev/null
  if [ -f "$T/$name.expected" ]; then
    cmp -s "$cfg" "$T/$name.expected" || { echo "FAIL $name: restore 결과가 원본과 다름"; diff "$T/$name.expected" "$cfg" || true; fail=1; }
  else
    [ ! -e "$cfg" ] || { echo "FAIL $name: 설치 전에 없던 config.toml 이 남음"; fail=1; }
  fi
  echo "ok   $name"
}

# (a) config.toml 없음
roundtrip absent

# (b) 다른 테이블만 있음, 끝 개행 없음
mkdir -p "$T/other/.codex"
printf 'model = "x"\n\n[projects."/tmp/p"]\ntrust_level = "trusted"' > "$T/other/.codex/config.toml"
roundtrip other

# (c) [tui] 에 다른 키 + 여러 줄 status_line + 뒤따르는 테이블
mkdir -p "$T/multi/.codex"
cat > "$T/multi/.codex/config.toml" <<'TOML'
model = "x"

[tui]
# 주석은 그대로 남아야 한다
theme = "dark"
status_line = [
  "model-with-reasoning",   # ] 가 주석에 있어도
  "git-branch",
]
notifications = [["a"], ["b"]]

[profiles.p]
model = "y"
TOML
roundtrip multi

# (d) [tui] 는 있는데 status_line 없음
mkdir -p "$T/nokey/.codex"
printf '[tui]\ntheme = "dark"\n\n[profiles.p]\nmodel = "y"\n' > "$T/nokey/.codex/config.toml"
roundtrip nokey

# (e) 깨진 TOML (tomllib 이 있을 때만 잡힌다) / (f) 미지원 표기 — check·apply 가 실패하고 홈은 그대로
reject() {              # reject <케이스 이름>
  local name="$1" cfg="$T/$1/.codex/config.toml"
  cp "$cfg" "$T/$name.expected"
  if run "$name" check 2>/dev/null; then echo "FAIL $name: check 가 통과함"; fail=1; fi
  if run "$name" apply >/dev/null 2>&1; then echo "FAIL $name: apply 가 통과함"; fail=1; fi
  cmp -s "$cfg" "$T/$name.expected" || { echo "FAIL $name: 실패했는데 파일이 바뀜"; fail=1; }
  [ ! -e "$T/$name/.config/dotfiles/backup" ] || { echo "FAIL $name: 실패했는데 백업 디렉터리가 생김"; fail=1; }
  echo "ok   $name (거부)"
}
mkdir -p "$T/dotted/.codex"
printf 'tui.status_line = ["git-branch"]\n' > "$T/dotted/.codex/config.toml"
reject dotted
if python3 -c 'import tomllib' 2>/dev/null; then
  mkdir -p "$T/broken/.codex"
  printf '[tui\nstatus_line = [\n' > "$T/broken/.codex/config.toml"
  reject broken
else
  echo "skip broken (python3 < 3.11 — tomllib 없음)"
fi

# (g) 기록 없는 머신에서 restore 는 아무것도 하지 않는다
mkdir -p "$T/norecord/.codex"
printf '[tui]\nstatus_line = ["git-branch"]\n' > "$T/norecord/.codex/config.toml"
cp "$T/norecord/.codex/config.toml" "$T/norecord.expected"
run norecord restore
cmp -s "$T/norecord/.codex/config.toml" "$T/norecord.expected" || { echo "FAIL norecord: 기록 없이 restore 가 파일을 바꿈"; fail=1; }
echo "ok   norecord"

rm -rf "$T"
[ "$fail" = 0 ] && echo "전체 통과" || { echo "실패 있음"; exit 1; }
