#!/usr/bin/env python3
"""doksam-ui 표준 준수 스캐너 (stdlib only).

SKILL.md §5.2 가 부르는 자가 검증기. 맨손 grep 이 내던 오탐을 제거하는 것이
존재 이유다.

  grep -r ' any' src/            → company, many, Germany 를 잡는다
  grep -r '[^\\x00-\\x7F]' src/   → 한글 텍스트를 전부 잡는다
  grep -r 'https://' src/        → 주석·문서 링크까지 잡는다

노이즈에 묻힌 "통과"는 아무것도 증명하지 못하므로, 여기서는 단어 경계·이모지
코드포인트·소스 확장자·문자열 리터럴로 범위를 좁힌다.

사용:
    python3 check_standards.py [경로...]          # 기본 경로: app components lib src
    python3 check_standards.py --only color,any .
    python3 check_standards.py --json .

위반이 하나라도 있으면 exit 1.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".css", ".scss"}
STYLE_SUFFIXES = {".css", ".scss"}
SKIP_DIRS = {
    "node_modules", ".next", ".git", "dist", "build", "out", "coverage",
    "__pycache__", ".turbo", ".vercel",
}
DEFAULT_TARGETS = ("app", "components", "lib", "src")

# --- 하드코딩 색 -----------------------------------------------------------
# CSS 변수를 정의하는 토큰 원본 파일(globals.css 등)은 hex 를 쓸 수밖에 없으므로
# 검사 대상에서 뺀다. 그 파일이 곧 토큰의 단일 진실원천이다.
TOKEN_SOURCE_NAMES = {"globals.css", "theme.css", "tokens.css"}

# 6·8자리는 언제나 색이다. 3·4자리는 이슈 참조(`#233`)·앵커(`href="#feed"`)와
# 구분이 안 되므로, 문자열이나 CSS 값으로 **단독으로** 놓였을 때만 색으로 본다.
HEX = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\b(?![0-9a-fA-F])")
HEX_SHORT = re.compile(
    r"""(?: (['"])\#[0-9a-fA-F]{3,4}\1        # "#f00"
          | :\s*\#[0-9a-fA-F]{3,4}\s*[;}\n]   # color: #f00;
        )""",
    re.VERBOSE,
)
COLOR_FN = re.compile(r"\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\s*\(")
TAILWIND_PALETTE = re.compile(
    r"\b(?:text|bg|border|ring|fill|stroke|from|via|to|decoration|outline|shadow|accent|caret|divide|placeholder)"
    r"-(?:slate|gray|grey|zinc|neutral|stone|red|orange|amber|yellow|lime|green|"
    r"emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b"
)

# --- 이모지 ---------------------------------------------------------------
# 한글(가-힣)·CJK 는 건드리지 않는다. 이모지 블록과 VS16 만 본다.
#
# 화살표 블록(U+2190~U+21FF, U+2B00~U+2BFF)은 의도적으로 제외한다.
# 산문의 "A → B" 까지 위반으로 잡으면 오탐이 본문을 덮어 스캐너가 무시당한다.
# 이 검사가 막는 것은 "아이콘 자리에 쓰인 그림문자"다.
EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # 이모티콘·픽토그램·보조 기호·확장
    "☀-➿"           # 기타 기호(☀★☑) + 딩뱃(✅✨❌)
    "⭐⭕"            # ⭐⭕
    "️"                  # variation selector-16 (이모지 표현 강제)
    "]"
)

# --- 외부 URL -------------------------------------------------------------
# 폐쇄망 규칙이 막는 것은 **리소스를 실제로 가져오는 것**이다. 바깥으로 나가는
# 앵커 링크(`<a href>`)나 화면에 글자로 보여주는 URL, 목 데이터의 baseUrl 은
# 네트워크 요청이 아니므로 위반이 아니다. 로드 위치에 있는 것만 잡는다.
URL_LOADING = re.compile(
    r"""(?:
          \b(?:src|srcSet|poster|imageSrcSet)\s*=\s*['"{`]?\s*(https?://[^'"`}\s]+)
        | <link\b[^>]*?\bhref\s*=\s*['"{`]?\s*(https?://[^'"`}\s]+)
        | \b(?:fetch|importScripts)\s*\(\s*['"`](https?://[^'"`]+)
        | \b(?:axios|ky)\s*(?:\.\s*\w+\s*)?\(\s*['"`](https?://[^'"`]+)
        | @import\s+(?:url\()?\s*['"](https?://[^'"]+)
        )""",
    re.VERBOSE,
)
URL_IN_CSS = re.compile(r"url\(\s*['\"]?(https?://[^)'\"\s]+)")
LOCALHOST = re.compile(r"^https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?:[:/]|$)")

# --- TypeScript any -------------------------------------------------------
# `: any`, `<any>`, `as any`, `any[]`, `Array<any>` 만. company·many 는 아니다.
ANY_TYPE = re.compile(
    r"(?::\s*any\b)"
    r"|(?:\bas\s+any\b)"
    r"|(?:<\s*any\s*[,>])"
    r"|(?:\bany\s*\[\])"
)

LINE_COMMENT = re.compile(r"^\s*(?://|\*|/\*)")

# --- 예외 표기 -------------------------------------------------------------
# 정당한 예외가 실제로 있다(색 선택기의 스와치 팔레트, 색 입력의 placeholder).
# 그런 줄은 이유를 적어 명시적으로 면제한다. 면제가 없으면 사람은 스캐너 전체를
# 무시하게 되고, 그 순간 검증은 죽는다.
#
#     const SWATCHES = ["#ef4444", ...]  // doksam-ui:allow-color 색 선택기 팔레트 원본
#
# `doksam-ui:allow` 는 그 줄의 모든 검사를, `doksam-ui:allow-<검사>` 는 해당
# 검사만 면제한다.
ALLOW = re.compile(r"doksam-ui:allow(?:-(color|emoji|url|any))?\b")


def suppressed(line, key):
    for match in ALLOW.finditer(line):
        if match.group(1) in (None, key):
            return True
    return False


def iter_files(targets):
    for target in targets:
        path = Path(target)
        if path.is_file():
            if path.suffix in SOURCE_SUFFIXES:
                yield path
            continue
        if not path.is_dir():
            continue
        for child in sorted(path.rglob("*")):
            if not child.is_file() or child.suffix not in SOURCE_SUFFIXES:
                continue
            if SKIP_DIRS.intersection(child.parts):
                continue
            yield child


def is_test_file(path):
    return bool(re.search(r"\.(?:test|spec)\.[jt]sx?$", path.name))


def is_shadcn_primitive(path):
    """`components/ui/` 는 shadcn CLI 원본이고 수정 금지 대상이다.

    고칠 수 없는 파일을 위반으로 세면 스캐너 출력이 영구 적자가 되고,
    사람은 그 순간부터 결과를 보지 않는다.
    """
    parts = path.parts
    return "ui" in parts and "components" in parts and \
        parts.index("ui") == parts.index("components") + 1


def check_color(path, lineno, line):
    if path.name in TOKEN_SOURCE_NAMES or is_shadcn_primitive(path):
        return None
    if is_test_file(path) or LINE_COMMENT.match(line):
        return None
    if HEX.search(line):
        return "하드코딩 hex 색"
    for match in HEX_SHORT.finditer(line):
        # `href="#feed"`, `href: "#top"` 은 앵커지 색이 아니다.
        if "href" in line[max(0, match.start() - 12):match.start()]:
            continue
        return "하드코딩 hex 색"
    if path.suffix not in STYLE_SUFFIXES and COLOR_FN.search(line):
        return "색 함수 리터럴 (rgb/hsl/oklch)"
    if TAILWIND_PALETTE.search(line):
        return "Tailwind 팔레트 클래스 (시맨틱 토큰이 아님)"
    return None


def check_emoji(path, lineno, line):
    return "이모지" if EMOJI.search(line) else None


def check_url(path, lineno, line):
    if LINE_COMMENT.match(line):
        return None
    for match in URL_LOADING.finditer(line):
        url = next(g for g in match.groups() if g)
        if not LOCALHOST.match(url):
            return f"외부 리소스 로드 ({url})"
    if path.suffix in STYLE_SUFFIXES:
        for match in URL_IN_CSS.finditer(line):
            if not LOCALHOST.match(match.group(1)):
                return f"외부 URL (CSS url()) ({match.group(1)})"
    return None


def check_any(path, lineno, line):
    if path.suffix not in {".ts", ".tsx"}:
        return None
    # 테스트 파일의 전역 스텁(`(globalThis as any).ResizeObserver ??= ...`)은
    # 프로덕션 타입 안전성과 무관하다. strict 규율의 대상은 앱 코드다.
    if is_test_file(path):
        return None
    if LINE_COMMENT.match(line):
        return None
    return "TypeScript any" if ANY_TYPE.search(line) else None


CHECKS = {
    "color": ("하드코딩 색", check_color),
    "emoji": ("이모지 아이콘", check_emoji),
    "url": ("외부 URL / CDN", check_url),
    "any": ("TypeScript any", check_any),
}


def scan(targets, only=None):
    selected = list(only) if only else list(CHECKS)
    findings = {key: [] for key in selected}
    for path in iter_files(targets):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lines = text.splitlines()
        for lineno, line in enumerate(lines, 1):
            for key in selected:
                if suppressed(line, key):
                    continue
                reason = CHECKS[key][1](path, lineno, line)
                if reason:
                    findings[key].append(
                        {"file": str(path), "line": lineno,
                         "reason": reason, "text": line.strip()[:160]})
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description="doksam-ui 표준 준수 스캐너")
    parser.add_argument("targets", nargs="*", default=None,
                        help="검사할 경로 (기본: app components lib src 중 존재하는 것)")
    parser.add_argument("--only", default=None,
                        help=f"검사 항목 쉼표 구분 ({', '.join(CHECKS)})")
    parser.add_argument("--json", action="store_true", help="JSON 으로 출력")
    args = parser.parse_args(argv)

    targets = args.targets or [t for t in DEFAULT_TARGETS if Path(t).exists()]
    if not targets:
        print("검사할 경로가 없다. 경로를 인자로 넘겨라.", file=sys.stderr)
        return 2

    only = None
    if args.only:
        only = [k.strip() for k in args.only.split(",") if k.strip()]
        unknown = [k for k in only if k not in CHECKS]
        if unknown:
            parser.error(f"알 수 없는 검사 항목: {', '.join(unknown)}")

    findings = scan(targets, only)

    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
        return 1 if any(findings.values()) else 0

    total = 0
    for key, hits in findings.items():
        label = CHECKS[key][0]
        total += len(hits)
        if not hits:
            print(f"[Pass] {label} 0건")
            continue
        print(f"[Fail] {label} {len(hits)}건")
        for hit in hits:
            print(f"    {hit['file']}:{hit['line']}: {hit['reason']}")
            print(f"        {hit['text']}")
    print(f"\n검사 경로: {', '.join(str(t) for t in targets)}")
    print(f"위반 합계: {total}건")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
