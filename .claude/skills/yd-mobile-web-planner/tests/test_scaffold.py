"""scaffold.py 단위 테스트 (stdlib only)."""
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import scaffold  # noqa: E402
import validate_storyboard as vs  # noqa: E402


class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = scaffold.TEMPLATE.read_text(encoding="utf-8")

    def build(self, **kw):
        kw.setdefault("project", "테스트몰")
        kw.setdefault("version", "1.0.0")
        return scaffold.build(self.template, **kw)

    def test_carries_mermaid_runtime(self):
        # 이게 빠지면 IA·흐름도가 원문 텍스트로 남는다 (검증기가 위반으로 잡는 항목).
        self.assertIn("mermaid.min.js", self.build())

    def test_carries_trace_interaction_runtime(self):
        html = self.build()
        self.assertIn("is-trace-active", html)
        self.assertIn("pointerenter", html)

    def test_carries_full_style_block(self):
        html = self.build()
        css = vs.extract_style(html)
        for name in ("ppt-slide", "pointer-badge", "mock-caption", "mock-partial"):
            with self.subTest(name=name):
                self.assertIn(name, vs.defined_classes(css))

    def test_class_contract_matches_template(self):
        # 뼈대의 CSS 가 템플릿과 같은 클래스 집합을 정의해야 계약이 성립한다.
        self.assertEqual(
            vs.defined_classes(vs.extract_style(self.build())),
            vs.defined_classes(vs.extract_style(self.template)),
        )

    def test_title_uses_project_name(self):
        self.assertIn("<title>테스트몰 화면설계서</title>", self.build())

    def test_accent_override(self):
        html = self.build(accent="#1b64da", accent_ink="#ffffff")
        self.assertIn("--accent: #1b64da;", html)
        self.assertIn("--accent-ink: #ffffff;", html)

    def test_accent_defaults_to_template_value(self):
        self.assertIn("--accent: #ea580c;", self.build())

    def test_has_empty_docwrap_and_insert_marker(self):
        html = self.build()
        self.assertIn('<div class="docwrap">', html)
        self.assertIn(scaffold.INSERT_MARKER, html)

    def test_no_slides_yet(self):
        # CSS 에는 클래스 정의가 있으므로 마크업만 걷어내고 확인한다.
        self.assertNotIn('class="ppt-top-no"', vs.markup_only(self.build()))

    def test_leaves_no_placeholder(self):
        # 검증기는 남은 {{ }} 를 위반으로 잡는다.
        self.assertNotIn("{{", self.build())


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_writes_file_and_returns_zero(self):
        out = self.tmp / "몰_storyboard.html"
        self.assertEqual(scaffold.main([str(out), "--project", "몰"]), 0)
        self.assertTrue(out.exists())

    def test_refuses_to_overwrite_without_force(self):
        out = self.tmp / "a_storyboard.html"
        out.write_text("기존 산출물", encoding="utf-8")
        self.assertEqual(scaffold.main([str(out), "--project", "A"]), 2)
        self.assertEqual(out.read_text(encoding="utf-8"), "기존 산출물")

    def test_force_overwrites(self):
        out = self.tmp / "a_storyboard.html"
        out.write_text("기존 산출물", encoding="utf-8")
        self.assertEqual(scaffold.main([str(out), "--project", "A", "--force"]), 0)
        self.assertIn("docwrap", out.read_text(encoding="utf-8"))

    def test_creates_missing_parent_directory(self):
        out = self.tmp / "docs" / "a_storyboard.html"
        self.assertEqual(scaffold.main([str(out), "--project", "A"]), 0)
        self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
