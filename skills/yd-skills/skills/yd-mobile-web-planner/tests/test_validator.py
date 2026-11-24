"""번들 검증기(validate_storyboard.py) 의 클래스 계약 단위 테스트 (stdlib only)."""
import re
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import validate_storyboard as vs


class TestExtractStyle(unittest.TestCase):
    def test_returns_css_between_style_tags(self):
        html = "<head><style>\n.a { color: red; }\n</style></head>"
        self.assertIn(".a { color: red; }", vs.extract_style(html))

    def test_raises_when_no_style_block(self):
        with self.assertRaises(ValueError):
            vs.extract_style("<head></head>")


class TestDefinedClasses(unittest.TestCase):
    def test_extracts_simple_class_selectors(self):
        css = ".ppt-slide { color: red; }\n.mock-tab { color: blue; }"
        self.assertEqual(vs.defined_classes(css), {"ppt-slide", "mock-tab"})

    def test_extracts_compound_and_descendant_selectors(self):
        css = ".mock-tab.active { color: red; }\n.desc-list li { margin: 0; }"
        self.assertEqual(vs.defined_classes(css), {"mock-tab", "active", "desc-list"})

    def test_ignores_element_and_pseudo_selectors(self):
        css = "body { margin: 0; }\n* { box-sizing: border-box; }\ncode { color: red; }"
        self.assertEqual(vs.defined_classes(css), set())

    def test_ignores_decimal_values_in_declarations(self):
        css = ".a { transform: scale(0.9); box-shadow: 0 2px 4px rgba(0,0,0,0.3); }"
        self.assertEqual(vs.defined_classes(css), {"a"})

    def test_ignores_at_import_url_extension(self):
        css = "@import url('https://cdn.example.com/pretendard.css');\n.a { color: red; }"
        self.assertEqual(vs.defined_classes(css), {"a"})


class TestUsedClasses(unittest.TestCase):
    def test_extracts_single_and_multiple_classes(self):
        html = '<div class="ppt-slide"><span class="mock-tab active"></span></div>'
        self.assertEqual(vs.used_classes(html), {"ppt-slide", "mock-tab", "active"})

    def test_collapses_extra_whitespace(self):
        html = '<div class="  a   b  "></div>'
        self.assertEqual(vs.used_classes(html), {"a", "b"})

    def test_returns_empty_when_no_class_attribute(self):
        self.assertEqual(vs.used_classes("<div></div>"), set())


class TestUndefinedClasses(unittest.TestCase):
    CSS = ".ppt-slide { color: red; }\n.mock-tab { color: blue; }"

    def test_returns_empty_when_all_defined(self):
        html = '<div class="ppt-slide"><span class="mock-tab"></span></div>'
        self.assertEqual(vs.undefined_classes(html, self.CSS), [])

    def test_reports_undefined_sorted(self):
        html = '<div class="storyboard"><span class="dochead"></span></div>'
        self.assertEqual(vs.undefined_classes(html, self.CSS), ["dochead", "storyboard"])

    def test_mermaid_is_whitelisted(self):
        html = '<div class="mermaid">mindmap</div>'
        self.assertEqual(vs.undefined_classes(html, self.CSS), [])

    def test_whitelist_contains_mermaid(self):
        self.assertIn("mermaid", vs.WHITELIST)


class TestAgainstRealTemplate(unittest.TestCase):
    """실제 template.html 로 계약이 성립하는지 확인한다."""

    def setUp(self):
        self.css = vs.extract_style(vs.TEMPLATE.read_text(encoding="utf-8"))

    def test_core_classes_are_defined(self):
        for name in ("docwrap", "ppt-slide", "ppt-top-no", "ppt-body-full",
                     "ppt-wireframe", "ppt-desc-panel", "desc-num",
                     "pointer-badge", "mock", "mock-tab", "ppt-footer", "icon"):
            with self.subTest(name=name):
                self.assertIn(name, vs.defined_classes(self.css))


class TestSkillClassQuickReference(unittest.TestCase):
    """SKILL.md 의 Class Quick Reference 표가 template.html 의 CSS 계약과
    맞는지 확인한다. 표는 에이전트가 template.html 을 열지 않고도 사용
    가능한 클래스를 알 수 있게 하는 권위이므로, 표가 template.html 과
    어긋나면 이 테스트가 잡아야 한다.
    """

    #: CSS 클래스가 아니라 엘리먼트 셀렉터로 정의된 항목. 표에는 등재되어
    #: 있으나 defined_classes() 에는 나오지 않는 게 정상이다.
    NOT_A_CLASS = frozenset({"code"})

    @classmethod
    def setUpClass(cls):
        skill_path = (
            SKILL_ROOT / "SKILL.md"
        )
        cls.skill_text = skill_path.read_text(encoding="utf-8")
        cls.css = vs.extract_style(vs.TEMPLATE.read_text(encoding="utf-8"))
        cls.defined = vs.defined_classes(cls.css)

    def _table_class_names(self) -> set[str]:
        """SKILL.md 의 '# Class Quick Reference' 섹션(다음 '#' 헤딩
        전까지)에서 표 행의 첫 번째 셀에 있는 backtick 식별자를 모두
        추출한다. 한 셀에 여러 클래스가 나열된 행(예: ppt-top-bar)도
        지원한다."""
        match = re.search(
            r"# Class Quick Reference\n(.*?)(?=\n# )",
            self.skill_text,
            re.DOTALL,
        )
        self.assertIsNotNone(
            match, "SKILL.md 에 '# Class Quick Reference' 섹션이 없다"
        )
        section = match.group(1)

        names: set[str] = set()
        for line in section.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not cells:
                continue
            first_cell = cells[0]
            # 헤더/구분선 행 스킵 ("클래스" 헤더, "---" 구분선)
            if first_cell in ("클래스", "") or set(first_cell) <= {"-", ":"}:
                continue
            names.update(re.findall(r"`([^`]+)`", first_cell))
        return names

    def test_every_table_class_is_defined_or_allowed(self):
        table_names = self._table_class_names()
        self.assertTrue(table_names, "표에서 클래스명을 하나도 못 찾았다")

        for name in sorted(table_names):
            # code 는 '<code>' 처럼 태그 형태로 적혀 있어 이름 자체가
            # 클래스명이 아니다 — <> 를 벗겨 NOT_A_CLASS 와 비교한다.
            bare_name = name.strip("<>")
            if bare_name in self.NOT_A_CLASS:
                continue
            with self.subTest(name=name):
                self.assertTrue(
                    name in self.defined or name in vs.WHITELIST,
                    f"SKILL.md 표의 '{name}' 이 template.html 의 CSS 에도, "
                    f"validate_storyboard.WHITELIST 에도 없다. template.html 에 "
                    "정의를 추가하거나, SKILL.md 표에서 항목을 빼거나, "
                    "WHITELIST/NOT_A_CLASS 에 명시적으로 등록할 것.",
                )


class TestScreenIds(unittest.TestCase):
    """검증기의 화면 ID 정의/참조 판정 (이슈 #26)."""

    co = vs

    def test_meta_id_is_a_definition(self):
        html = '<div class="ppt-meta-id">DTC-MAIN-001</div>'
        self.assertEqual(self.co.screen_ids(html), {"DTC-MAIN-001"})

    def test_caption_id_is_a_definition(self):
        """목업 2개짜리 슬라이드의 두 번째 화면 ID 는 캡션이 정의 자리다."""
        html = '<div class="mock-caption">게시글 상세 (DTC-BOARD-002)</div>'
        self.assertEqual(self.co.screen_ids(html), {"DTC-BOARD-002"})

    def test_meta_id_may_hold_several_ids(self):
        """런타임이 두 화면을 한 칸에 묶어 적어도 각각 정의로 읽는다."""
        html = '<div class="ppt-meta-id">DTC-BOARD-001 / DTC-BOARD-002</div>'
        self.assertEqual(self.co.screen_ids(html),
                         {"DTC-BOARD-001", "DTC-BOARD-002"})

    def test_caption_definition_is_not_counted_as_a_reference(self):
        html = ('<div class="mock-caption">게시글 상세 (DTC-BOARD-002)</div>'
                '<div>글 상세로 이동 (DTC-BOARD-003)</div>')
        self.assertEqual(self.co.referenced_ids(html), {"DTC-BOARD-003"})

    def test_reference_defined_only_in_caption_is_not_dangling(self):
        html = ('<div class="ppt-meta-id">DTC-BOARD-001</div>'
                '<div class="mock-caption">게시글 상세 (DTC-BOARD-002)</div>'
                '<div>탭 시 글 상세로 이동 (DTC-BOARD-002)</div>')
        dangling = self.co.referenced_ids(html) - self.co.screen_ids(html)
        self.assertEqual(dangling, set())


class TestIgnoresStyleBlock(unittest.TestCase):
    """CSS 주석의 사용 예시를 실제 마크업으로 세지 않는다 (이슈 #26)."""

    co = vs

    def test_markup_only_drops_style_block(self):
        html = '<style>/* <div class="mock mock-partial"> */</style><div class="mock"></div>'
        self.assertNotIn("mock-partial", self.co.markup_only(html))
        self.assertIn('class="mock"', self.co.markup_only(html))

    def test_partial_mock_in_css_comment_is_not_counted(self):
        template = vs.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('class="mock mock-partial"', template,
                      "템플릿 CSS 주석의 사용 예시가 사라졌다면 이 테스트의 전제가 깨진다")
        css = vs.extract_style(template)
        self.assertNotIn("mock-partial", self.co.markup_only(f"<style>{css}</style>"))


def _slide(no, body=""):
    """상단 바 앵커를 갖춘 최소 슬라이드 마크업."""
    return f'<div class="ppt-top-no">NO. {no}</div>{body}'


class TestSlideSectioning(unittest.TestCase):
    """슬라이드 구간은 상단 바 앵커로만 자른다 (이슈 #61).

    본문 텍스트나 HTML 주석에 등장하는 "NO. 09.1" 같은 문자열이 구간 경계로
    잡히면 한 슬라이드가 둘로 쪼개지고, 그 자리에서 배지와 desc-num 이 서로
    다른 구간으로 갈려 불일치를 놓친다.
    """

    def test_html_comment_is_stripped_by_markup_only(self):
        html = '<!-- ============ NO. 09.1 홈 ============ -->' + _slide("09.1")
        self.assertNotIn("<!--", vs.markup_only(html))
        self.assertEqual([no for no, _ in vs.detail_slides(vs.markup_only(html))],
                         ["09.1"])

    def test_comment_between_badge_and_desc_does_not_split_slide(self):
        # 배지 2개 / desc-num 1개 — 반드시 불일치로 잡혀야 한다.
        html = _slide(
            "09.1",
            '<span class="pointer-badge">1</span>'
            "<!-- NO. 09.1 설명 패널 -->"
            '<span class="pointer-badge">2</span><span class="desc-num">1</span>',
        )
        self.assertEqual(vs.badge_desc_mismatch(vs.markup_only(html)),
                         [("09.1", 2, 1)])

    def test_index_table_text_is_not_a_slide(self):
        html = _slide("03", "<td>NO. 09.1</td><td>홈</td>") + _slide("09.1")
        self.assertEqual([no for no, _ in vs.detail_slides(html)], ["09.1"])

    def test_last_detail_slide_stops_at_next_slide(self):
        # 09.x 뒤에 부록 슬라이드가 와도 그 배지가 마지막 화면 상세에 합산되지 않는다.
        html = (_slide("09.1", '<span class="pointer-badge">1</span>'
                               '<span class="desc-num">1</span>')
                + _slide("10", '<span class="pointer-badge">X</span>'))
        self.assertEqual(vs.badge_desc_mismatch(html), [])

    def test_slide_sections_filters_by_pattern(self):
        html = _slide("07.1") + _slide("08") + _slide("09.1")
        self.assertEqual([no for no, _ in vs.slide_sections(html, r"07\.\d+")], ["07.1"])
        self.assertEqual([no for no, _ in vs.slide_sections(html)], ["07.1", "08", "09.1"])


class TestRowScreenType(unittest.TestCase):
    """05 Screen List 유형은 유형 열의 셀 값으로 판정한다 (이슈 #61)."""

    def test_reads_type_cell(self):
        row = ('<td>DTC-DOC-101</td><td>서류등록</td><td>바텀시트</td>'
               '<td>홈 &gt; 서류</td><td>파일 선택</td>')
        self.assertEqual(vs.row_screen_type(row), "바텀시트")

    def test_description_wording_does_not_override_type_cell(self):
        # "주요 내용" 칸에 '화면' 이 섞여도 팝업 행이 화면으로 오판되면 안 된다.
        row = ('<td>DTC-DOC-101</td><td>서류등록</td><td>팝업</td>'
               '<td>홈</td><td>화면 일부를 덮는 선택 시트</td>')
        self.assertEqual(vs.row_screen_type(row), "팝업")

    def test_falls_back_to_row_text_when_no_type_cell(self):
        row = "<td>DTC-DOC-101</td><td>서류등록 바텀시트</td>"
        self.assertEqual(vs.row_screen_type(row), "바텀시트")

    def test_returns_none_when_untyped(self):
        self.assertIsNone(vs.row_screen_type("<td>DTC-DOC-101</td><td>서류등록</td>"))

    def test_screen_row_with_popup_wording_in_description_is_not_screen(self):
        markup = (
            _slide("05", '<tr><td>DTC-A-001</td><td>목록</td><td>화면</td>'
                         '<td>홈</td><td>목록 조회</td></tr>')
            + _slide("09.1", '<div class="ppt-meta-id">DTC-A-001</div>')
        )
        self.assertEqual(vs.check_screen_list_types(markup), [])


class TestInteractionBadgeCitation(unittest.TestCase):
    """BR 인터랙션 표의 트리거 칸은 배지 번호를 인용해야 한다 (이슈 #61)."""

    SECTION = """
### 입력 검증
해당 없음 — 조회 전용 화면.

### 인터랙션
| 트리거 | 조건/검증 | 동작 |
|---|---|---|
| 계좌 카드 탭 (1) | - | 계좌로 이동 (DTC-ACCT-001) |
| 알림 배지 탭 | - | 알림으로 이동 (DTC-NOTI-001) |
"""

    def test_reports_row_without_citation(self):
        self.assertEqual(vs.interaction_rows_without_badge(self.SECTION),
                         ["알림 배지 탭"])

    def test_accepts_two_level_citation(self):
        body = ("### 인터랙션\n| 트리거 | 조건/검증 | 동작 |\n|---|---|---|\n"
                "| 필터 칩 탭 (1-2) | - | 목록 갱신 |\n")
        self.assertEqual(vs.interaction_rows_without_badge(body), [])

    def test_screen_id_in_action_cell_does_not_count_as_citation(self):
        body = ("### 인터랙션\n| 트리거 | 조건/검증 | 동작 |\n|---|---|---|\n"
                "| 행 탭 | - | 상세로 이동 (DTC-BOARD-002) |\n")
        self.assertEqual(vs.interaction_rows_without_badge(body), ["행 탭"])

    def test_none_section_is_exempt(self):
        body = "### 인터랙션\n해당 없음 — 표시 전용 배너다.\n"
        self.assertEqual(vs.interaction_rows_without_badge(body), [])

    def test_missing_section_is_exempt(self):
        self.assertEqual(vs.interaction_rows_without_badge("### 출력 규칙\n표시만.\n"), [])

    def test_check_rules_reports_it(self):
        md = "# X Business Rules\n\n## DTC-MAIN-001 홈\n" + self.SECTION + """
### 출력 규칙
표시.

### 엣지케이스
없음.
"""
        violations, _info = vs.check_rules(md, {"DTC-MAIN-001"})
        self.assertTrue(any("배지 번호 인용이 없는 행" in v for v in violations), violations)


if __name__ == "__main__":
    unittest.main()
