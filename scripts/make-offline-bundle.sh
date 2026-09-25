#!/usr/bin/env bash
# 폐쇄망 반입용 오프라인 번들 생성 (#58).
# 인터넷 PC 에서 실행 → dist/ 에 zip·tar.gz·SHA256SUMS 를 만든다. 반입 후 압축을 풀고
# bin/agents-scaffold.sh(Windows 는 bin\agents-scaffold.cmd)를 실행하면 네트워크 없이 설치된다.
# 커밋된 내용만 담는다(git archive) — 미커밋 변경은 번들에 들어가지 않는다.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/make-offline-bundle.sh [--ref <git-ref>] [--out <dir>]
  --ref  Git ref to bundle (default: HEAD)
  --out  Output directory (default: dist/)
USAGE
}

REF="HEAD"
OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: $ROOT is not a git checkout — clone the repository first." >&2
  exit 1
fi
if ! git -C "$ROOT" rev-parse --verify --quiet "$REF^{commit}" >/dev/null; then
  echo "Error: unknown ref '$REF'" >&2
  exit 1
fi
if [ "$REF" = "HEAD" ] && [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
  echo "Warning: uncommitted changes are NOT included (bundle = committed HEAD)." >&2
fi

OUT="${OUT:-$ROOT/dist}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

version="$(git -C "$ROOT" describe --tags --always "$REF")"
name="agents-scaffold-offline-$version"

# --prefix: 풀면 agents-scaffold/ 하나로 떨어진다. .gitattributes(eol) 가 아카이브에도 적용돼
# Windows(autocrlf) 에서 만들어도 *.sh 는 LF 로 담긴다.
git -C "$ROOT" archive --format=zip    --prefix=agents-scaffold/ -o "$OUT/$name.zip"    "$REF"
git -C "$ROOT" archive --format=tar.gz --prefix=agents-scaffold/ -o "$OUT/$name.tar.gz" "$REF"

if command -v sha256sum >/dev/null 2>&1; then
  sha() { sha256sum "$@"; }
else
  sha() { shasum -a 256 "$@"; }
fi
(cd "$OUT" && sha "$name.zip" "$name.tar.gz" > SHA256SUMS)

echo "== offline bundle ready ==" >&2
echo "  $OUT/$name.zip" >&2
echo "  $OUT/$name.tar.gz" >&2
echo "  $OUT/SHA256SUMS" >&2
echo "Next: carry these into the closed network — see docs/OFFLINE_INSTALL.md" >&2
