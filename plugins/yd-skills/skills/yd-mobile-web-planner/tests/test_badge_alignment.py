"""check_badge_alignment.py 단위 테스트 (stdlib only)."""
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import check_badge_alignment as cba  # noqa: E402


def badge(label, top):
    return (f'<span class="pointer-badge" style="position:absolute; '
            f'top:{top}px; left:2px; z-index:10;">{label}</span>')


def slide(no, mocks):
    """mocks: [[(컨테이너클래스, [배지…]), …], …] — 목업마다 컨테이너 목록."""
    out = [f'<div class="ppt-top-no">NO. {no}</div>']
    for containers in mocks:
        out.append('<div class="mock">')
        for cls, badges in containers:
            out.append(f'<div class="{cls}">' + "".join(badges) + "</div>")
        out.append("</div>")
    return "".join(out)


class TestLabelKey(unittest.TestCase):
    def test_parses_flat_and_two_level(self):
        self.assertEqual(cba.label_key("3"), (3,))
        self.assertEqual(cba.label_key("1-2"), (1, 2))

    def test_returns_none_for_non_numeric(self):
        self.assertIsNone(cba.label_key("A"))
        self.assertIsNone(cba.label_key("1-x"))

    def test_two_level_sorts_numerically_not_lexically(self):
        # 문자열 정렬이면 "1-10" < "1-9" 가 되어 순서 검사가 뒤집힌다.
        self.assertLess(cba.label_key("1-9"), cba.label_key("1-10"))


class TestBadgesIn(unittest.TestCase):
    def test_reads_label_and_top(self):
        self.assertEqual(cba.badges_in(badge("1-1", 40)), [("1-1", 40)])

    def test_skips_badge_without_top(self):
        html = '<span class="pointer-badge" style="left:2px;">1</span>'
        self.assertEqual(cba.badges_in(html), [])


class TestOverlap(unittest.TestCase):
    def _check(self, html, tmp):
        p = tmp / "x_storyboard.html"
        p.write_text(html, encoding="utf-8")
        return cba.check(p)

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def test_reports_badges_closer_than_badge_height(self):
        html = slide("09.1", [[("mock-body", [badge("1", 100), badge("2", 110)])]])
        problems = self._check(html, self.tmp)
        self.assertTrue(any("겹친다" in p for p in problems), problems)

    def test_allows_badges_exactly_one_height_apart(self):
        html = slide("09.1", [[("mock-body", [badge("1", 100), badge("2", 124)])]])
        self.assertEqual(self._check(html, self.tmp), [])


class TestOrdering(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def _check(self, html):
        p = self.tmp / "x_storyboard.html"
        p.write_text(html, encoding="utf-8")
        return cba.check(p)

    def test_reports_label_order_against_top_order(self):
        html = slide("09.1", [[("mock-body", [badge("1-2", 200), badge("1-3", 80)])]])
        self.assertTrue(any("위에 있다" in p for p in self._check(html)))

    def test_negative_top_is_exempt(self):
        # 음수 top 은 헤더 영역을 가리키는 관용 패턴이라 라벨 순서와 어긋나도 정상이다.
        html = slide("09.1", [[("mock-body", [badge("1", 40), badge("2", -6)])]])
        self.assertEqual(self._check(html), [])

    def test_different_containers_are_not_compared(self):
        # mock-footer 의 top:9px 는 mock-body 의 좌표계와 무관하다.
        html = slide("09.1", [[("mock-body", [badge("1", 40), badge("2", 200)]),
                               ("mock-footer", [badge("3", 9)])]])
        self.assertEqual(self._check(html), [])

    def test_different_mocks_are_not_compared(self):
        html = slide("09.1", [[("mock-body", [badge("1-1", 300)])],
                              [("mock-body", [badge("2-1", 20)])]])
        self.assertEqual(self._check(html), [])

    def test_clean_slide_reports_nothing(self):
        html = slide("09.1", [[("mock-body", [badge("1", 20), badge("2", 90),
                                              badge("3", 200)])]])
        self.assertEqual(self._check(html), [])


class TestHtmlCommentsIgnored(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def test_comment_does_not_split_slide(self):
        html = ('<!-- ==== NO. 09.1 홈 ==== -->'
                + slide("09.1", [[("mock-body", [badge("1", 100), badge("2", 108)])]]))
        p = self.tmp / "x_storyboard.html"
        p.write_text(html, encoding="utf-8")
        self.assertTrue(any("겹친다" in x for x in cba.check(p)))


class TestFooterPillContainer(unittest.TestCase):
    """mock-footer-pill 은 별도 좌표 원점 — body 배지와 순서·겹침을 비교하지 않는다 (#69)."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def _check(self, html):
        p = self.tmp / "x_storyboard.html"
        p.write_text(html, encoding="utf-8")
        return cba.check(p)

    def test_pill_badge_not_compared_with_body(self):
        html = slide("09.1", [[("mock-body", [badge("1-4", 205)]),
                               ("mock-footer-pill", [badge("1-5", 10)])]])
        self.assertEqual(self._check(html), [])
