"""apply_badge_audit.py 단위 테스트 (stdlib only) — 이슈 #72."""
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
spec = importlib.util.spec_from_file_location(
    "apply_badge_audit", SCRIPTS / "apply_badge_audit.py")
aba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aba)

HTML = """
<div class="ppt-top-no">NO. 09.1</div>
<div class="mock-body">
  <span class="pointer-badge" style="position:absolute; top:20px; left:2px; z-index:10;">1</span>
  <span class="pointer-badge" style="position:absolute; top:120px; left:2px; z-index:10;">2</span>
</div>
<div class="ppt-top-no">NO. 09.2</div>
<div class="mock-body">
  <span class="pointer-badge" style="position:absolute; top:20px; left:2px; z-index:10;">1-1</span>
</div>
"""


class TestApplyFixes(unittest.TestCase):
    def test_applies_suggested_top_per_slide_and_label(self):
        fixes = [
            {"slide": "09.1", "label": "2", "inlineTop": 120, "suggestedTop": 96},
            {"slide": "09.2", "label": "1-1", "inlineTop": 20, "suggestedTop": 34},
        ]
        html, applied, failed = aba.apply_fixes(HTML, fixes)
        self.assertEqual(len(applied), 2)
        self.assertEqual(failed, [])
        self.assertIn('top:96px; left:2px; z-index:10;">2<', html)
        self.assertIn('top:34px; left:2px; z-index:10;">1-1<', html)
        # 같은 라벨이라도 다른 슬라이드(09.1 의 "1")는 건드리지 않는다
        self.assertIn('top:20px; left:2px; z-index:10;">1<', html)

    def test_tolerance_skips_small_delta(self):
        fixes = [{"slide": "09.1", "label": "1", "inlineTop": 20, "suggestedTop": 22}]
        html, applied, failed = aba.apply_fixes(HTML, fixes, tolerance=3)
        self.assertEqual(applied, [])
        self.assertEqual(failed, [])
        self.assertEqual(html, HTML)

    def test_stale_inline_top_fails_instead_of_wrong_patch(self):
        # 파일이 이미 고쳐져 inlineTop 이 안 맞으면 조용히 넘어가지 않고 실패로 보고한다
        fixes = [{"slide": "09.1", "label": "2", "inlineTop": 999, "suggestedTop": 96}]
        html, applied, failed = aba.apply_fixes(HTML, fixes)
        self.assertEqual(applied, [])
        self.assertEqual(len(failed), 1)
        self.assertEqual(html, HTML)

    def test_unknown_slide_fails(self):
        fixes = [{"slide": "09.9", "label": "1", "inlineTop": 20, "suggestedTop": 50}]
        _html, applied, failed = aba.apply_fixes(HTML, fixes)
        self.assertEqual(applied, [])
        self.assertEqual(len(failed), 1)

    def test_negative_top_matches(self):
        html_src = HTML.replace('top:20px; left:2px; z-index:10;">1<',
                                'top:-6px; left:2px; z-index:10;">1<')
        fixes = [{"slide": "09.1", "label": "1", "inlineTop": -6, "suggestedTop": 10}]
        html, applied, failed = aba.apply_fixes(html_src, fixes)
        self.assertEqual(len(applied), 1)
        self.assertEqual(failed, [])
        self.assertIn('top:10px; left:2px; z-index:10;">1<', html)


if __name__ == "__main__":
    sys.exit(unittest.main())
