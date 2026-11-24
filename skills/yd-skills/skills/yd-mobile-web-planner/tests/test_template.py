"""template.html 의 목업 헤더 배지 계약 테스트 (stdlib only) — 이슈 #71.

mock-header 는 배지의 좌표 원점(position:relative)이어야 하고, 배지가 있는
헤더에는 mock-body 와 같은 gutter(단일 28px / 복수 34px)가 자동 부여되어야
한다. gutter 가 없으면 left:2px 배지가 헤더 제목 첫 글자를 가린다.
"""
import re
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "resources" / "template.html"
SKILL_MD = SKILL_ROOT / "SKILL.md"


def css():
    match = re.search(r"<style>(.*?)</style>", TEMPLATE.read_text(encoding="utf-8"), re.DOTALL)
    if not match:
        raise RuntimeError("template.html 에 <style> 블록이 없다")
    return match.group(1)


def rule_body(style, selector):
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", style)
    return m.group(1) if m else None


class TestHeaderBadgeContract(unittest.TestCase):
    def test_mock_header_is_positioning_origin(self):
        body = rule_body(css(), ".mock-header")
        self.assertIsNotNone(body, ".mock-header 규칙이 없다")
        self.assertIn("position: relative", body,
                      "mock-header 가 배지의 좌표 원점(position:relative)이 아니다")

    def test_mock_footer_is_positioning_origin(self):
        """푸터도 배지의 좌표 원점이다 (이슈 #137).

        없으면 푸터 안의 pointer-badge 가 .mock 기준으로 떠서 화면 최상단에
        찍힌다 — 마크업은 멀쩡해 정적 검사로는 안 잡히고 렌더해야 보인다.
        """
        body = rule_body(css(), ".mock-footer")
        self.assertIsNotNone(body, ".mock-footer 규칙이 없다")
        self.assertIn("position: relative", body,
                      "mock-footer 가 배지의 좌표 원점(position:relative)이 아니다")

    def test_footer_gutter_for_badges(self):
        body = rule_body(css(), ".mock-footer:has(.pointer-badge)")
        self.assertIsNotNone(body, "배지 있는 푸터의 gutter 규칙이 없다")
        self.assertIn("padding-left: 28px", body)

    def test_header_gutter_single_mock(self):
        body = rule_body(css(), ".mock-header:has(.pointer-badge)")
        self.assertIsNotNone(body, "배지 있는 헤더의 gutter 규칙이 없다")
        self.assertIn("padding-left: 28px", body)

    def test_header_gutter_multi_mock(self):
        body = rule_body(
            css(), ".ppt-wireframe:has(.mock ~ .mock) .mock-header:has(.pointer-badge)")
        self.assertIsNotNone(body, "복수 목업의 헤더 gutter 규칙이 없다")
        self.assertIn("padding-left: 34px", body)

    def test_skill_md_no_longer_teaches_negative_top(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertNotIn("음수 `top`(예: `-6px`)을 쓴다", text,
                         "SKILL.md 가 여전히 잘리는 음수 top 패턴을 지시한다")
        self.assertIn("`mock-header` 안에", text,
                      "SKILL.md 에 헤더 배지 배치 규칙이 없다")


class TestTraceInteraction(unittest.TestCase):
    def test_template_links_badges_and_descriptions_with_keyboard_support(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        for phrase in (".pointer-badge", ".desc-num", "pointerenter",
                       "event.key === 'Enter'", "event.key === ' '",
                       "is-trace-active", "is-trace-ping"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_reduced_motion_is_supported(self):
        self.assertIn("prefers-reduced-motion: reduce",
                      TEMPLATE.read_text(encoding="utf-8"))

    def test_runtime_classes_are_documented(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("`is-trace-active`", text)
        self.assertIn("`is-trace-ping`", text)


if __name__ == "__main__":
    sys.exit(unittest.main())
