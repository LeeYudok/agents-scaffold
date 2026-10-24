#!/usr/bin/env python3
"""렌더된 산출물의 레이아웃 회귀를 Chrome headless 로 잡는다 (이슈 #137).

정적 검사기(validate_storyboard·check_badge_overflow·check_badge_alignment)는
마크업의 인라인 좌표만 본다. 템플릿 CSS 가 바뀌어 목업 높이·gutter·설명 패널
밀도가 달라지면 마크업은 그대로인데 결과만 깨지고, 그건 렌더해야 보인다.

전체 픽셀 비교는 브라우저·폰트 버전이 바뀔 때마다 false positive 를 내므로
1차 계약은 **구조·좌표**다. 여기서 판정하는 것은 넷뿐이다.

    slide-overflow   슬라이드가 자기 16:9 박스를 넘겼다 (내용이 잘린다)
    badge-outside    배지가 자기 좌표 원점 컨테이너 밖으로 나갔다
    badge-overlap    같은 컨테이너의 배지 둘이 겹쳤다 (번호를 못 읽는다)
    desc-clipped     설명 패널 내용이 패널 높이를 넘겼다 (인쇄 시 잘린다)
    desc-overlap     설명 항목끼리 겹쳤다

좌표 수집은 resources/layout-probe.js 가 하고 **임계값 판정은 이 파일이
한다** — 브라우저 없이도 판정 로직을 단위 테스트할 수 있게 하기 위해서다
(tests/test_layout_runtime.py).

기본은 오프라인 렌더다. 외부 폰트(@import)와 mermaid CDN 스크립트를 임시
사본에서 떼고 그린다 — CI 러너의 네트워크 상태가 판정을 흔들면 회귀 검사가
아니라 점집이 된다. mermaid 를 못 그리는 슬라이드는 slide-overflow 판정에서
제외하고 그 사실을 보고한다. 실제 mermaid 높이까지 보려면 --online 을 쓴다.
원본 파일은 절대 수정하지 않는다.

사용법:
    python3 scripts/check_layout_runtime.py <산출물.html> [...]
        [--chrome <경로>] [--online] [--json <저장경로>]

종료 코드: 위반 없으면 0, 있으면 1, 인자·Chrome 문제면 2.
"""
import argparse
import html as _html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_deck import (  # noqa: E402  Chrome 탐색·대기시간은 내보내기와 같은 계약을 쓴다
    DESIGN_W,
    RENDER_WAIT_MS,
    WINDOW_H,
    find_chrome,
)

SKILL_ROOT = Path(__file__).resolve().parent.parent
PROBE = SKILL_ROOT / "resources" / "layout-probe.js"

#: 서브픽셀 반올림과 border 1px 은 회귀가 아니다. 이보다 큰 이탈만 본다.
OVERFLOW_TOL = 2.0
BADGE_TOL = 1.0
#: 배지끼리 이만큼 이하로 겹치는 것은 그림자 여백 수준이라 읽기에 지장이 없다.
OVERLAP_TOL = 1.0


#: 설계 기준 폭으로 고정하는 CSS. 목업 높이(694px)와 배지 인라인 top 은 전부
#: DESIGN_W=1400 에서 나온 절대값이라, 브라우저 창 폭에 따라 슬라이드가
#: 좁아지면 목업이 슬라이드를 넘긴다 — 그건 회귀가 아니라 창이 좁은 것이다.
#: PDF·PPTX 내보내기가 쓰는 것과 같은 기하로 맞춰 그 구분을 없앤다.
DESIGN_CSS = ("body{margin:0 !important;padding:0 !important;background:#fff !important;}"
              ".docwrap{max-width:none !important;gap:0 !important;}")


def strip_network(html):
    """외부 요청을 유발하는 태그를 떼어 낸 사본 문자열을 만든다."""
    html = re.sub(r'<script\b[^>]*\bsrc="https?://[^"]*"[^>]*>\s*</script>', "", html)
    html = re.sub(r'@import\s+url\([^)]*\);?', "", html)
    # mermaid 블록은 스크립트가 없으면 원문 텍스트로 흘러 슬라이드를 넘긴다.
    # 숨겨서 판정 대상에서 빼되, 슬라이드에 mermaid 가 있었다는 사실은
    # probe 가 세어 보고한다.
    return html.replace("</style>", ".mermaid{display:none !important;}</style>", 1)


def measure(chrome, path, offline=True):
    """Chrome 으로 한 번 렌더해 probe 의 JSON 을 받아 온다."""
    snippet = PROBE.read_text(encoding="utf-8").strip().rstrip(";")
    inject = ('<script>window.addEventListener("load",()=>{setTimeout(()=>{'
              f"const r={snippet};"
              'const p=document.createElement("pre");p.id="__layout__";'
              'p.textContent=JSON.stringify(r);document.body.appendChild(p);'
              '},1200)});</script>')
    source = Path(path).read_text(encoding="utf-8")
    if offline:
        source = strip_network(source)
    source = source.replace("</style>", DESIGN_CSS + "</style>", 1)
    if "</body>" not in source:
        sys.exit(f"오류: </body> 가 없는 문서다 — {path}")
    source = source.replace("</body>", inject + "</body>", 1)

    with tempfile.TemporaryDirectory() as work:
        page = Path(work) / "probe.html"
        page.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
             "--no-sandbox",
             f"--virtual-time-budget={RENDER_WAIT_MS}",
             f"--window-size={DESIGN_W},{WINDOW_H}",
             "--dump-dom", f"file://{page.resolve()}"],
            capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"오류: Chrome 실행 실패 (exit {result.returncode})\n{result.stderr[-600:]}")
    found = re.search(r'<pre id="__layout__">(.*?)</pre>', result.stdout, re.DOTALL)
    if not found:
        sys.exit("오류: probe 결과를 받지 못했다 — 문서가 렌더되지 않았을 수 있다")
    return json.loads(_html.unescape(found.group(1)))


def _overlap(a, b):
    """두 사각형이 겹치는 폭·높이 중 작은 쪽. 안 겹치면 0 이하."""
    return min(
        min(a["right"], b["right"]) - max(a["left"], b["left"]),
        min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]),
    )


def judge(report, offline=True):
    """probe 측정값을 위반 목록으로 바꾼다. 브라우저 없이 테스트되는 지점."""
    violations = []

    def add(slide, kind, detail):
        violations.append({"slide": slide.get("no") or f"#{slide['index'] + 1}",
                           "kind": kind, "detail": detail})

    for slide in report.get("slides", []):
        geo = slide["slide"]
        skip_overflow = offline and slide.get("mermaid")
        if not skip_overflow:
            over_w = geo["overRight"]
            over_h = geo["overBottom"]
            if over_w > OVERFLOW_TOL or over_h > OVERFLOW_TOL:
                add(slide, "slide-overflow",
                    f"내용이 슬라이드 밖으로 {max(over_w, over_h):.0f}px 넘쳤다 "
                    f"(가로 {over_w:.0f}px · 세로 {over_h:.0f}px)")

        for container in slide.get("containers", []):
            rect = container["rect"]
            for badge in container["badges"]:
                out = max(rect["top"] - badge["top"], rect["left"] - badge["left"],
                          badge["right"] - rect["right"], badge["bottom"] - rect["bottom"])
                if out > BADGE_TOL:
                    add(slide, "badge-outside",
                        f"배지 {badge['label']} 가 {container['kind']} 밖으로 "
                        f"{out:.0f}px 나갔다")
            badges = container["badges"]
            for i, first in enumerate(badges):
                for second in badges[i + 1:]:
                    if _overlap(first, second) > OVERLAP_TOL:
                        add(slide, "badge-overlap",
                            f"배지 {first['label']} 와 {second['label']} 가 "
                            f"{container['kind']} 안에서 겹쳤다")

        for panel in slide.get("panels", []):
            clipped = panel["scrollH"] - panel["clientH"]
            if clipped > OVERFLOW_TOL:
                add(slide, "desc-clipped",
                    f"설명 패널 내용이 {clipped:.0f}px 잘렸다 "
                    f"(항목을 줄이거나 밀도 규칙을 확인)")

        items = slide.get("items", [])
        for i, first in enumerate(items):
            for second in items[i + 1:]:
                if _overlap(first, second) > OVERLAP_TOL:
                    add(slide, "desc-overlap",
                        f"설명 항목 {first['label']} 와 {second['label']} 가 겹쳤다")

    return violations


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Chrome headless 로 산출물 레이아웃 회귀를 검사한다")
    parser.add_argument("paths", nargs="+", help="검사할 산출물 HTML")
    parser.add_argument("--chrome", help="Chrome 실행 파일 경로")
    parser.add_argument("--online", action="store_true",
                        help="외부 폰트·mermaid CDN 을 그대로 두고 렌더한다")
    parser.add_argument("--json", help="측정 원본을 저장할 경로")
    args = parser.parse_args(argv)

    chrome = find_chrome(args.chrome)
    offline = not args.online
    total = 0
    dumps = {}
    for path in args.paths:
        if not Path(path).is_file():
            print(f"오류: 파일이 없다 — {path}", file=sys.stderr)
            return 2
        report = measure(chrome, path, offline=offline)
        dumps[path] = report
        violations = judge(report, offline=offline)
        total += len(violations)
        print(f"===== {path} =====")
        skipped = [s["no"] or f"#{s['index'] + 1}"
                   for s in report["slides"] if offline and s.get("mermaid")]
        if skipped:
            print(f"  - mermaid 슬라이드는 오프라인 렌더라 overflow 판정 제외: "
                  f"{', '.join(skipped)}")
        for item in violations:
            print(f"  X {item['slide']} [{item['kind']}] {item['detail']}")
        print(f"  => 레이아웃 위반 {len(violations)}건" if violations
              else f"  => 레이아웃 위반 없음 (슬라이드 {len(report['slides'])}장)")
    if args.json:
        Path(args.json).write_text(json.dumps(dumps, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
