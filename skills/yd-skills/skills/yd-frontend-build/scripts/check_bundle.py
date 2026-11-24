#!/usr/bin/env python3
"""빌드 산출물을 검사한다 — 외부 출처 · 소스맵 · 번들 예산.

    python3 check_bundle.py <dist 경로> [--allow-host example.com] [--json]

폐쇄망 배포에서 외부 요청이 남아 있으면 조용히 실패한다. 소스맵이 딸려가면
배포본에서 원본을 복원할 수 있다. 둘 다 빌드 로그만 봐서는 드러나지 않으므로
산출물을 직접 훑는다.

위반이 있으면 exit 1.

stdlib 만 쓴다 (이 환경의 Homebrew Python 은 외부 라이브러리 import 가 깨져 있다).
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

# 검사 대상 텍스트 자산.
TEXT_SUFFIXES = {".js", ".mjs", ".cjs", ".css", ".html", ".json", ".webmanifest"}

# 외부로 나가지 않는 호스트. 로컬·사설 주소는 개발 설정 잔재라도 요청이 밖으로 안 나간다.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

# gzip 기준 예산 (바이트). 넘으면 원인을 지목해 보고하라는 신호다.
BUDGET_JS = 200 * 1024
BUDGET_CSS = 50 * 1024

# URL 이 있다고 요청이 나가는 것은 아니다. 라이브러리들은 에러 메시지에 문서 링크를
# 심어 두므로(react.dev, tailwindcss.com 등) 단순 검색은 오탐으로 뒤덮인다.
# 그래서 "실제로 네트워크를 유발하는 문맥"에 있는 URL 만 잡는다.
REQUESTING_PATTERNS = [
    # HTML/JSX 속성: <script src=...> <link href=...> <img src=...>
    re.compile(rb"""(?:src|href)\s*=\s*["']\s*(https?://[A-Za-z0-9._:-]+)"""),
    # CSS: url(...) 과 @import
    re.compile(rb"""url\(\s*["']?\s*(https?://[A-Za-z0-9._:-]+)"""),
    re.compile(rb"""@import\s+["']\s*(https?://[A-Za-z0-9._:-]+)"""),
    # JS 호출: fetch("..."), import("..."), importScripts("...")
    re.compile(rb"""(?:fetch|import|importScripts)\s*\(\s*["'`]\s*(https?://[A-Za-z0-9._:-]+)"""),
    # JS 대입: el.src = "...", el.href = "..."
    re.compile(rb"""\.(?:src|href)\s*=\s*["'`]\s*(https?://[A-Za-z0-9._:-]+)"""),
    # new URL("https://...") / XHR open
    re.compile(rb"""(?:new\s+URL|\.open)\s*\(\s*["'`]?\s*["'`](https?://[A-Za-z0-9._:-]+)"""),
]

# --strict 에서만 쓰는 광범위 검색 (문서 링크까지 전부 훑는다).
ANY_URL_RE = re.compile(rb"https?://([A-Za-z0-9._:-]+)")

SOURCE_MAP_RE = re.compile(rb"sourceMappingURL=([^\s*'\"]+)")

# 표준 스키마·네임스페이스 URL 은 요청이 아니다 (XML/SVG 네임스페이스 등).
IGNORED_HOST_SUFFIXES = (
    "www.w3.org",
    "www.w3.org:80",
    "schemas.microsoft.com",
    "ns.adobe.com",
)


class Finding:
    def __init__(self, kind: str, path: Path, line: int, detail: str):
        self.kind = kind
        self.path = path
        self.line = line
        self.detail = detail

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "file": str(self.path),
            "line": self.line,
            "detail": self.detail,
        }

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else str(self.path)
        return f"  {where}  {self.detail}"


def is_ignored_host(host: str, allowed: set[str]) -> bool:
    bare = host.split(":", 1)[0]
    if bare in LOCAL_HOSTS or bare in allowed:
        return True
    if bare.endswith(IGNORED_HOST_SUFFIXES):
        return True
    # 사설 대역은 폐쇄망 안이다.
    return bare.startswith(("192.168.", "10.")) or bare.startswith("172.")


def scan_text_asset(path: Path, allowed: set[str], strict: bool = False) -> list[Finding]:
    """요청을 유발하는 외부 URL 과 소스맵 참조를 줄 번호와 함께 찾는다.

    strict 면 문맥을 가리지 않고 모든 외부 URL 을 보고한다 — 감사용이며
    라이브러리 에러 메시지의 문서 링크까지 잡히므로 기본값이 아니다.
    """
    found: list[Finding] = []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [Finding("read-error", path, 0, str(exc))]

    patterns = [ANY_URL_RE] if strict else REQUESTING_PATTERNS
    for lineno, line in enumerate(raw.splitlines(), start=1):
        seen: set[str] = set()
        for pattern in patterns:
            for match in pattern.finditer(line):
                url = match.group(1).decode("utf-8", "replace")
                host = url.split("//", 1)[-1]
                if is_ignored_host(host, allowed) or host in seen:
                    continue
                seen.add(host)
                found.append(Finding("external-url", path, lineno, f"외부 출처 {host}"))
        for match in SOURCE_MAP_RE.finditer(line):
            ref = match.group(1).decode("utf-8", "replace")
            found.append(Finding("sourcemap", path, lineno, f"소스맵 참조 {ref}"))
    return found


def gzip_size(path: Path) -> int:
    try:
        return len(gzip.compress(path.read_bytes(), 6))
    except OSError:
        return 0


def check_budget(dist: Path) -> tuple[list[Finding], dict[str, int]]:
    """초기 로드에 들어가는 js/css 합계를 gzip 기준으로 본다."""
    totals = {"js": 0, "css": 0}
    for path in sorted(dist.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in {".js", ".mjs"}:
            totals["js"] += gzip_size(path)
        elif path.suffix == ".css":
            totals["css"] += gzip_size(path)

    found: list[Finding] = []
    if totals["js"] > BUDGET_JS:
        found.append(Finding("budget", dist, 0,
                             f"JS {totals['js'] // 1024}KB(gzip) > 예산 {BUDGET_JS // 1024}KB"))
    if totals["css"] > BUDGET_CSS:
        found.append(Finding("budget", dist, 0,
                             f"CSS {totals['css'] // 1024}KB(gzip) > 예산 {BUDGET_CSS // 1024}KB"))
    return found, totals


def collect(dist: Path, allowed: set[str], strict: bool = False) -> tuple[list[Finding], dict[str, int]]:
    found: list[Finding] = []
    for path in sorted(dist.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".map":
            found.append(Finding("sourcemap", path, 0, "배포물에 소스맵 파일이 있다"))
            continue
        if path.suffix in TEXT_SUFFIXES:
            found.extend(scan_text_asset(path, allowed, strict))
    budget, totals = check_budget(dist)
    return found + budget, totals


def main() -> int:
    parser = argparse.ArgumentParser(description="빌드 산출물 검사 (외부 출처·소스맵·예산)")
    parser.add_argument("dist", type=Path, help="빌드 산출물 디렉터리")
    parser.add_argument("--allow-host", action="append", default=[],
                        metavar="HOST", help="허용할 외부 호스트 (반복 지정 가능)")
    parser.add_argument("--strict", action="store_true",
                        help="문맥을 가리지 않고 모든 외부 URL 을 보고 (감사용)")
    parser.add_argument("--json", action="store_true", help="결과를 JSON 으로 출력")
    args = parser.parse_args()

    dist: Path = args.dist
    if not dist.is_dir():
        print(f"오류: 디렉터리가 아니다 — {dist}", file=sys.stderr)
        return 2

    found, totals = collect(dist, set(args.allow_host), args.strict)

    if args.json:
        print(json.dumps({
            "violations": [f.as_dict() for f in found],
            "gzipBytes": totals,
        }, ensure_ascii=False, indent=1))
        return 1 if found else 0

    by_kind: dict[str, list[Finding]] = {}
    for f in found:
        by_kind.setdefault(f.kind, []).append(f)

    labels = {
        "external-url": "외부 출처",
        "sourcemap": "소스맵",
        "budget": "번들 예산",
        "read-error": "읽기 실패",
    }
    for kind, label in labels.items():
        hits = by_kind.get(kind, [])
        if hits:
            print(f"[Fail] {label} {len(hits)}건")
            for f in hits:
                print(f)
        else:
            print(f"[Pass] {label} 0건")

    print()
    print(f"검사 경로: {dist}")
    print(f"gzip 합계: JS {totals['js'] // 1024}KB · CSS {totals['css'] // 1024}KB")
    print(f"위반 합계: {len(found)}건")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
