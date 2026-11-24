"""check_layout_runtime.py 계약 테스트 (이슈 #137).

두 층으로 나뉜다.

1. 판정 로직 — probe 가 준 좌표를 위반으로 바꾸는 규칙. 브라우저 없이 항상
   돈다. 임계값이 파이썬 한 곳에만 있기 때문에 가능하다.
2. 실제 렌더 — Chrome 이 있을 때만 돈다. 템플릿에서 만든 기준 문서를 그려
   위반 0건인지 본다. CI 에서는 별도 job(.github/workflows/layout.yml)이
   Chrome 을 보장하고, 로컬 stdlib 테스트에서는 조용히 skip 된다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURE = SKILL_ROOT / "tests" / "fixtures" / "layout" / "baseline-slides.html"
PROBE = SKILL_ROOT / "resources" / "layout-probe.js"

sys.path.insert(0, str(SCRIPTS))
import check_layout_runtime as clr  # noqa: E402
from export_deck import CHROME_CANDIDATES  # noqa: E402


def rect(top, left, bottom, right):
    return {"top": top, "left": left, "bottom": bottom, "right": right}


def slide(**kw):
    base = {
        "index": 0,
        "no": "NO. 09.1",
        "mermaid": 0,
        "slide": {"w": 1400, "h": 787.5, "overRight": 0, "overBottom": 0},
        "containers": [],
        "panels": [],
        "items": [],
    }
    base.update(kw)
    return base


def kinds(report, offline=True):
    return [v["kind"] for v in clr.judge(report, offline=offline)]


class TestJudge(unittest.TestCase):
    def test_clean_document_has_no_violation(self):
        report = {"slides": [slide(
            containers=[{"kind": "mock-body", "rect": rect(0, 0, 600, 320), "clipped": False,
                         "badges": [{"label": "1", **rect(20, 2, 44, 26)},
                                    {"label": "2", **rect(170, 2, 194, 26)}]}],
            panels=[{"clientH": 500, "scrollH": 480}],
            items=[{"label": "1", **rect(0, 0, 60, 400)},
                   {"label": "2", **rect(76, 0, 130, 400)}],
        )]}
        self.assertEqual(clr.judge(report), [])

    def test_slide_overflow_detected(self):
        report = {"slides": [slide(
            slide={"w": 1400, "h": 787.5, "overRight": 0, "overBottom": 40})]}
        self.assertEqual(kinds(report), ["slide-overflow"])

    def test_subpixel_overflow_is_not_a_regression(self):
        report = {"slides": [slide(
            slide={"w": 1400, "h": 787.5, "overRight": 1, "overBottom": 1})]}
        self.assertEqual(kinds(report), [])

    def test_badge_outside_its_container(self):
        report = {"slides": [slide(containers=[
            {"kind": "mock-body", "rect": rect(0, 0, 600, 320), "clipped": False,
             "badges": [{"label": "9", **rect(590, 2, 614, 26)}]}])]}
        self.assertEqual(kinds(report), ["badge-outside"])

    def test_badges_overlapping_each_other(self):
        report = {"slides": [slide(containers=[
            {"kind": "mock-body", "rect": rect(0, 0, 600, 320), "clipped": False,
             "badges": [{"label": "1", **rect(20, 2, 44, 26)},
                        {"label": "2", **rect(30, 2, 54, 26)}]}])]}
        self.assertEqual(kinds(report), ["badge-overlap"])

    def test_badges_in_different_containers_are_not_compared(self):
        """헤더와 본문은 좌표 원점이 달라 겹쳐 보여도 서로 다른 층이다."""
        common = [{"label": "1", **rect(20, 2, 44, 26)}]
        report = {"slides": [slide(containers=[
            {"kind": "mock-header", "rect": rect(0, 0, 51, 320), "clipped": False,
             "badges": common},
            {"kind": "mock-body", "rect": rect(0, 0, 600, 320), "clipped": False,
             "badges": [dict(common[0])]}])]}
        self.assertEqual(kinds(report), [])

    def test_desc_panel_clipped(self):
        report = {"slides": [slide(panels=[{"clientH": 500, "scrollH": 640}])]}
        self.assertEqual(kinds(report), ["desc-clipped"])

    def test_desc_items_overlapping(self):
        report = {"slides": [slide(items=[
            {"label": "1", **rect(0, 0, 80, 400)},
            {"label": "2", **rect(40, 0, 120, 400)}])]}
        self.assertEqual(kinds(report), ["desc-overlap"])

    def test_mermaid_slide_skips_overflow_only_offline(self):
        report = {"slides": [slide(
            mermaid=1,
            slide={"w": 1400, "h": 787.5, "overRight": 0, "overBottom": 180})]}
        self.assertEqual(kinds(report, offline=True), [])
        self.assertEqual(kinds(report, offline=False), ["slide-overflow"])


class TestNetworkStripping(unittest.TestCase):
    def test_external_script_and_font_import_removed(self):
        html = ('<html><head><style>@import url("https://fonts.example/x.css");'
                'body{color:red}</style>'
                '<script src="https://cdn.example/mermaid.min.js"></script></head>'
                '<body><div class="mermaid">graph TD;</div></body></html>')
        out = clr.strip_network(html)
        self.assertNotIn("https://", out)
        self.assertIn(".mermaid{display:none !important;}", out)
        self.assertIn("body{color:red}", out, "본문 CSS 까지 지우면 안 된다")


def build_fixture(target_dir):
    """template.html 의 head 로 기준 문서를 조립한다. head 는 커밋하지 않는다."""
    out = Path(target_dir) / "layout-baseline.html"
    subprocess.run(
        [sys.executable, str(SCRIPTS / "scaffold.py"), str(out),
         "--project", "Layout Fixture", "--version", "1.0.0"],
        check=True, capture_output=True, text=True)
    from scaffold import INSERT_MARKER  # noqa: E402  scaffold 와 삽입 규약을 공유한다
    html = out.read_text(encoding="utf-8")
    if INSERT_MARKER not in html:
        raise AssertionError("scaffold 산출물에 삽입 마커가 없다")
    out.write_text(
        html.replace(INSERT_MARKER,
                     FIXTURE.read_text(encoding="utf-8") + "\n" + INSERT_MARKER, 1),
        encoding="utf-8")
    return out


def chrome_available():
    for cand in (os.environ.get("CHROME"), *CHROME_CANDIDATES):
        if cand and (Path(cand).is_file() or shutil.which(cand)):
            return True
    return False


@unittest.skipUnless(chrome_available(), "Chrome 이 없어 렌더 검사를 건너뛴다")
class TestRenderedBaseline(unittest.TestCase):
    def test_baseline_document_has_no_layout_violation(self):
        with tempfile.TemporaryDirectory() as work:
            doc = build_fixture(work)
            dump = Path(work) / "measured.json"
            code = clr.main([str(doc), "--json", str(dump)])
            measured = json.loads(dump.read_text(encoding="utf-8"))[str(doc)]
            self.assertTrue(measured["slides"], "슬라이드를 하나도 못 읽었다")
            self.assertEqual(code, 0, "기준 문서에서 레이아웃 위반이 나왔다")

    def test_broken_css_is_caught(self):
        """검사기가 실제로 회귀를 잡는지 본다 — 통과만 확인하면 무의미하다.

        목업을 200px 키우면 슬라이드를 넘고, 배지 gutter 를 없애면 배지가
        본문 텍스트 위로 올라온다. 전자는 slide-overflow 로 잡혀야 한다.
        """
        with tempfile.TemporaryDirectory() as work:
            doc = build_fixture(work)
            broken = Path(work) / "broken.html"
            broken.write_text(
                doc.read_text(encoding="utf-8").replace(
                    "</style>", ".mock{height:894px !important;}</style>", 1),
                encoding="utf-8")
            self.assertEqual(clr.main([str(broken)]), 1,
                             "깨진 레이아웃을 통과시켰다")
            report = clr.measure(clr.find_chrome(), broken)
            self.assertIn("slide-overflow",
                          [v["kind"] for v in clr.judge(report)])

    def test_probe_reports_badges_and_items(self):
        with tempfile.TemporaryDirectory() as work:
            doc = build_fixture(work)
            report = clr.measure(clr.find_chrome(), doc)
            first = report["slides"][0]
            badges = [b["label"] for c in first["containers"] for b in c["badges"]]
            self.assertEqual(sorted(badges), ["1", "2", "3"])
            self.assertEqual([i["label"] for i in first["items"]], ["1", "2", "3"])


class TestProbeShape(unittest.TestCase):
    def test_probe_is_a_single_expression_snippet(self):
        """주입은 `const r=<snippet>` 형태다 — 세미콜론으로 끝나면 문법이 깨진다."""
        text = PROBE.read_text(encoding="utf-8").strip()
        self.assertTrue(text.endswith("})();"), "IIFE 로 끝나야 한다")
        self.assertIn("return {", text, "측정값을 반환하지 않는다")


if __name__ == "__main__":
    unittest.main()
