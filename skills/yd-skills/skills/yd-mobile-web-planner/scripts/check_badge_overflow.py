#!/usr/bin/env python3
"""pointer-badge 가 목업의 가시 영역 밖으로 밀려났는지 판정한다.

`mock-body` 는 `overflow-y:auto` 라 내용이 넘쳐도 CSS 는 조용히 스크롤로 감춘다.
화면설계서는 종이/슬라이드로 읽히므로 스크롤로 감춰진 배지는 사실상 없는 것과
같다. 목업 프레임 높이에서 상태바·헤더·탭바를 뺀 가시 높이를 계산해, 그 아래에
놓인 배지를 보고한다.

    .mock         높이 694 + border 1px x 2 (box-sizing: border-box 이므로 692 내부)
    .mock-partial 높이 320 (팝업 위 회색 배경 힌트 블록만큼 body 가 줄어든다)
    .mock-status  26 / .mock-header 약 51 / .mock-footer 약 37 / .mock-footer-pill 54(44+하단 margin 10)
    .pointer-badge 높이 24

사용법:
    python3 scripts/check_badge_overflow.py <산출물.html>

종료 코드: 이탈 배지가 없으면 0, 있으면 1.
"""
import re
import sys
from pathlib import Path

BADGE_H = 24
STATUS_H = 26
HEADER_H = 51
FOOTER_H = 37
PILL_H = 54


def mock_blocks(slide_html):
    """슬라이드 안의 목업 블록을 (부분목업 여부, 마크업) 으로 잘라 반환한다."""
    for part in re.split(r'(?=<div class="mock(?: mock-partial)?">)', slide_html):
        if 'class="mock' not in part:
            continue
        head = part.split('>', 1)[0]
        yield 'mock-partial' in head, part


def visible_height(is_partial, markup):
    """목업 본문(mock-body)의 가시 높이를 px 로 계산한다."""
    if is_partial:
        hint = re.search(r'<div style="height:(\d+)px;background:#e2e8f0', markup)
        height = 320 - (int(hint.group(1)) if hint else 0)
    else:
        height = 692
    if 'class="mock-status"' in markup:
        height -= STATUS_H
    if 'class="mock-header"' in markup:
        height -= HEADER_H
    if 'class="mock-footer"' in markup:
        height -= FOOTER_H
    if 'class="mock-footer-pill"' in markup:
        height -= PILL_H
    return height


def check(path):
    html = re.sub(r"<style\b.*?</style>", "", Path(path).read_text(encoding="utf-8"),
                  flags=re.S)
    bad = []
    for m in re.finditer(r"NO\.\s*(09\.\d+)(.*?)(?=NO\.\s*09\.|\Z)", html, re.S):
        for is_partial, markup in mock_blocks(m.group(2)):
            avail = visible_height(is_partial, markup)
            for top in re.findall(r'class="pointer-badge"[^>]*top:\s*(\d+)px', markup):
                if int(top) + BADGE_H > avail:
                    bad.append((m.group(1), "partial" if is_partial else "full",
                                int(top), avail))
    return bad


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    total = 0
    for path in sys.argv[1:]:
        bad = check(path)
        total += len(bad)
        print(f"===== {path} =====")
        for no, kind, top, avail in bad:
            print(f"  X {no} {kind} 목업: 배지 top {top}px + 24 > 가시 {avail}px")
        print(f"  => 이탈 배지 {len(bad)}건" if bad else "  => 이탈 배지 없음")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
