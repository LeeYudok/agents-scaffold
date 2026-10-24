"""validate_storyboard.py 의 Business Rules 판정 단위 테스트 (stdlib only)."""
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import validate_storyboard as vs


def section(sid, name="화면", extra_body=""):
    """네 필수 헤딩을 모두 갖춘 유효한 섹션 마크다운을 만든다."""
    return (
        f"## {sid} {name}\n\n"
        "### 입력 검증\n해당 없음 — 조회 전용 화면.\n\n"
        "### 출력 규칙\n| 상태 | 표시 |\n|---|---|\n| 로딩 | 스켈레톤 |\n\n"
        "### 인터랙션\n해당 없음 — 정적 화면.\n\n"
        f"### 엣지케이스\n- 네트워크 오류 시 재시도 배너.\n{extra_body}\n"
    )


class TestRulesPathFor(unittest.TestCase):
    def test_storyboard_suffix_is_swapped(self):
        self.assertEqual(
            vs.rules_path_for("/tmp/petshop_storyboard.html").name,
            "petshop_business-rules.md")

    def test_non_contract_name_uses_stem(self):
        self.assertEqual(
            vs.rules_path_for("/tmp/output.html").name,
            "output_business-rules.md")


class TestRulesSections(unittest.TestCase):
    def test_splits_sections_by_id_heading(self):
        md = section("DTC-MAIN-001") + section("DTC-BOARD-001")
        ids = [sid for sid, _ in vs.rules_sections(md)]
        self.assertEqual(ids, ["DTC-MAIN-001", "DTC-BOARD-001"])

    def test_heading_without_id_is_not_a_section(self):
        md = "## 개요\n내용\n" + section("DTC-MAIN-001")
        ids = [sid for sid, _ in vs.rules_sections(md)]
        self.assertEqual(ids, ["DTC-MAIN-001"])


class TestCheckRules(unittest.TestCase):
    def test_valid_doc_has_no_violations(self):
        md = section("DTC-MAIN-001")
        violations, info = vs.check_rules(md, {"DTC-MAIN-001"})
        self.assertEqual(violations, [])
        self.assertTrue(any("섹션 1개" in line for line in info))

    def test_missing_screen_section_is_a_violation(self):
        md = section("DTC-MAIN-001")
        violations, _ = vs.check_rules(md, {"DTC-MAIN-001", "DTC-BOARD-001"})
        self.assertTrue(any("DTC-BOARD-001" in v and "섹션이 없는" in v
                            for v in violations))

    def test_extra_section_is_a_violation(self):
        md = section("DTC-MAIN-001") + section("DTC-GHOST-999")
        violations, _ = vs.check_rules(md, {"DTC-MAIN-001"})
        self.assertTrue(any("DTC-GHOST-999" in v and "정의되지 않은" in v
                            for v in violations))

    def test_duplicate_section_is_a_violation(self):
        md = section("DTC-MAIN-001") + section("DTC-MAIN-001")
        violations, _ = vs.check_rules(md, {"DTC-MAIN-001"})
        self.assertTrue(any("중복" in v for v in violations))

    def test_missing_required_heading_is_a_violation(self):
        md = ("## DTC-MAIN-001 홈\n\n### 입력 검증\n내용\n\n"
              "### 출력 규칙\n내용\n\n### 인터랙션\n내용\n")
        violations, _ = vs.check_rules(md, {"DTC-MAIN-001"})
        self.assertTrue(any("엣지케이스" in v and "누락" in v
                            for v in violations))

    def test_empty_required_heading_is_a_violation(self):
        md = ("## DTC-MAIN-001 홈\n\n### 입력 검증\n\n"
              "### 출력 규칙\n내용\n\n### 인터랙션\n내용\n\n"
              "### 엣지케이스\n내용\n")
        violations, _ = vs.check_rules(md, {"DTC-MAIN-001"})
        self.assertTrue(any("입력 검증" in v and "내용 없는" in v
                            for v in violations))

    def test_dangling_reference_is_a_violation(self):
        md = section("DTC-MAIN-001",
                     extra_body="- 탭 시 글 상세로 이동 (DTC-BOARD-002).")
        violations, _ = vs.check_rules(md, {"DTC-MAIN-001"})
        self.assertTrue(any("DTC-BOARD-002" in v and "참조" in v
                            for v in violations))

    def test_reference_to_defined_id_is_ok(self):
        md = (section("DTC-MAIN-001",
                      extra_body="- 탭 시 게시판으로 이동 (DTC-BOARD-001).")
              + section("DTC-BOARD-001"))
        violations, _ = vs.check_rules(
            md, {"DTC-MAIN-001", "DTC-BOARD-001"})
        self.assertEqual(violations, [])


class TestRuleIds(unittest.TestCase):
    def test_valid_rule_ids_pass(self):
        md = """## DTC-MAIN-001 홈

### 입력 검증
해당 없음 — 조회 전용.

### 출력 규칙
| 상태 | 표시 |
|---|---|
| DTC-MAIN-001.OUT-01 · 로딩 | 스켈레톤 |

### 인터랙션
해당 없음 — 정적 화면.

### 엣지케이스
- DTC-MAIN-001.EDGE-01 — 네트워크 오류 시 재시도.
"""
        self.assertEqual(vs.rule_id_violations(vs.rules_sections(md)), [])

    def test_missing_duplicate_and_mismatched_ids_fail(self):
        md = """## DTC-MAIN-001 홈

### 입력 검증
해당 없음 — 조회 전용.

### 출력 규칙
| 상태 | 표시 |
|---|---|
| 로딩 | 스켈레톤 |

### 인터랙션
- DTC-OTHER-001.OUT-01 — 잘못된 화면과 구분.

### 엣지케이스
- DTC-MAIN-001.EDGE-01 — A
- DTC-MAIN-001.EDGE-01 — B
"""
        violations = vs.rule_id_violations(vs.rules_sections(md))
        joined = "\n".join(violations)
        self.assertIn("규칙 ID 누락", joined)
        self.assertIn("화면 불일치", joined)
        self.assertIn("구분 불일치", joined)
        self.assertIn("중복 규칙 ID", joined)


class TestCheckIntegration(unittest.TestCase):
    """check() 가 storyboard 와 rules 파일 짝을 함께 판정하는지 확인한다."""

    HTML = (
        '<div class="ppt-slide"><div class="ppt-top-no">NO. 05</div>'
        '<div class="ppt-top-title">Screen List</div>'
        '<table><tr><td>ID</td><td>유형</td></tr>'
        '<tr><td>DTC-MAIN-001</td><td>홈</td><td>화면</td></tr></table></div>'
        '<div class="ppt-slide"><div class="ppt-top-no">NO. 06</div>'
        '<div class="ppt-top-title">Service Flow</div>'
        '<div class="mermaid">flowchart LR\n'
        'A["홈&lt;br/&gt;DTC-MAIN-001"]</div></div>'
        '<div class="ppt-slide"><div class="ppt-top-no">NO. 07.1</div>'
        '<div class="ppt-top-title">Sequence — 제출</div>'
        '<div class="mermaid">sequenceDiagram\n'
        'participant M as 홈 (DTC-MAIN-001)\nM->>S: 제출</div></div>'
        '<div class="ppt-slide"><div class="ppt-top-no">NO. 09.1</div>'
        '<div class="ppt-top-title">홈</div>'
        '<div class="ppt-meta-value">홈</div>'
        '<div class="ppt-meta-id">DTC-MAIN-001</div></div>'
        '<script src="mermaid.min.js"></script>'
    )
    CSS = (".ppt-slide{} .ppt-top-no{} .ppt-top-title{} "
           ".ppt-meta-value{} .ppt-meta-id{}")

    def _run(self, write_rules):
        with tempfile.TemporaryDirectory() as td:
            html_path = Path(td) / "dtc_storyboard.html"
            html_path.write_text(self.HTML, encoding="utf-8")
            if write_rules:
                (Path(td) / "dtc_business-rules.md").write_text(
                    section("DTC-MAIN-001"), encoding="utf-8")
            return vs.check(str(html_path), self.CSS)

    def test_missing_rules_file_is_a_violation(self):
        violations, _ = self._run(write_rules=False)
        self.assertTrue(any("Business Rules 문서 없음" in v
                            for v in violations))

    def test_paired_rules_file_passes(self):
        violations, _ = self._run(write_rules=True)
        self.assertEqual(violations, [])


class TestCaptionMismatch(unittest.TestCase):
    """모든 목업에 mock-caption 필수 판정 (이슈 #37 렌더 피드백)."""

    def test_single_mock_without_caption_is_flagged(self):
        html = ('<div class="ppt-top-no">NO. 09.1</div>'
                '<div class="mock"><div class="mock-screen"></div></div>')
        self.assertEqual(vs.caption_mismatch(html), [("09.1", 1, 0)])

    def test_captioned_mocks_pass(self):
        html = ('<div class="ppt-top-no">NO. 09.1</div>'
                '<div class="mock"><div class="mock-caption">홈 (TC-MAIN-001)</div></div>'
                '<div class="mock mock-partial">'
                '<div class="mock-caption">팝업 (TC-MAIN-101)</div></div>')
        self.assertEqual(vs.caption_mismatch(html), [])

    def test_hyphen_classes_are_not_counted_as_mocks(self):
        html = ('<div class="ppt-top-no">NO. 09.1</div>'
                '<div class="mock-screen"></div><div class="mock-body"></div>')
        self.assertEqual(vs.caption_mismatch(html), [])


    def test_circled_desc_num_is_flagged(self):
        html = ('<div class="ppt-top-no">NO. 09.1</div>'
                '<div class="mock"><div class="mock-caption">홈 (TC-MAIN-001)</div></div>')
        # 원문자 판정은 check() 내부 정규식과 동일한 패턴을 직접 확인
        import re as _re
        self.assertTrue(_re.findall(
            r'class="desc-num"[^>]*>([^<]*[\u2460-\u2473][^<]*)<',
            '<span class="desc-num">①</span>'))
        self.assertFalse(_re.findall(
            r'class="desc-num"[^>]*>([^<]*[\u2460-\u2473][^<]*)<',
            '<span class="desc-num">1-1</span>'))


class TestEventCoverage(unittest.TestCase):
    """이벤트 표기 커버리지 판정 (이슈 #43)."""

    def slide(self, no, items):
        lis = "".join(f'<li><span class="desc-num">{i+1}</span> <div>{x}</div></li>'
                      for i, x in enumerate(items))
        return (f'<div class="ppt-top-no">NO. {no}</div>'
                f'<ul class="desc-list">{lis}</ul>')

    def test_slide_with_event_label_counts(self):
        html = self.slide("09.1", ["<b>배너</b><br>탭: 공지로 이동 (DTC-NOTICE-001)",
                                   "<b>로고</b><br>정적 표시"])
        self.assertEqual(vs.event_coverage(html), [("09.1", 1, 2)])

    def test_slide_without_any_event_label(self):
        html = self.slide("09.1", ["<b>배너</b><br>주요 속보 롤링"])
        self.assertEqual(vs.event_coverage(html), [("09.1", 0, 1)])

    def test_slide_without_items_is_not_flagged(self):
        html = '<div class="ppt-top-no">NO. 09.1</div><div>목업만</div>'
        self.assertEqual(vs.event_coverage(html), [("09.1", 0, 0)])

    def test_swipe_and_input_labels_count(self):
        html = self.slide("09.2", ["<b>탭바</b><br>스와이프: 인접 탭 이동",
                                   "<b>검색</b><br>입력: 1~50자 실시간 필터"])
        self.assertEqual(vs.event_coverage(html), [("09.2", 2, 2)])


class TestScreenListTypes(unittest.TestCase):
    """05 Screen List 유형 정합 판정 (이슈 #41)."""

    DETAIL = ('<div class="ppt-top-no">NO. 09.1</div>'
              '<div class="ppt-meta-id">DTC-MAIN-001</div>')

    def slide05(self, rows):
        return (f'<div class="ppt-top-no">NO. 05</div>'
                f'<div class="ppt-top-title">Screen List</div><table>{rows}</table>')

    def test_typed_and_drawn_screen_passes(self):
        html = self.slide05('<tr><td>DTC-MAIN-001</td><td>홈</td><td>화면</td></tr>') + self.DETAIL
        self.assertEqual(vs.check_screen_list_types(html), [])

    def test_row_without_type_is_flagged(self):
        html = self.slide05('<tr><td>DTC-MAIN-001</td><td>홈</td></tr>') + self.DETAIL
        self.assertTrue(any("유형" in v and "DTC-MAIN-001" in v
                            for v in vs.check_screen_list_types(html)))

    def test_screen_typed_but_undrawn_is_flagged(self):
        html = (self.slide05('<tr><td>DTC-MAIN-001</td><td>홈</td><td>화면</td></tr>'
                             '<tr><td>DTC-MYPAGE-001</td><td>내 정보</td><td>화면</td></tr>')
                + self.DETAIL)
        self.assertTrue(any("09.x 에 정의되지 않은" in v and "DTC-MYPAGE-001" in v
                            for v in vs.check_screen_list_types(html)))

    def test_popup_row_is_not_required_to_have_slide(self):
        html = (self.slide05('<tr><td>DTC-AUTH-101</td><td>로그인 유도 팝업</td><td>팝업</td></tr>')
                + self.DETAIL)
        self.assertEqual(vs.check_screen_list_types(html), [])

    def test_bottomsheet_description_mentioning_screen_is_not_misread(self):
        """설명에 '화면' 이 섞여도 바텀시트 행이 화면으로 오판되지 않는다."""
        html = (self.slide05('<tr><td>DTC-DOC-101</td><td>서류 등록</td><td>바텀시트</td>'
                             '<td>화면 하단에서 올라옴</td></tr>') + self.DETAIL)
        self.assertEqual(vs.check_screen_list_types(html), [])

    def test_no_screen_list_slide_defers_to_overview_check(self):
        self.assertEqual(vs.check_screen_list_types(self.DETAIL), [])


class TestSequenceSlides(unittest.TestCase):
    """07.x Sequence Diagram 판정 (이슈 #39)."""

    def slide(self, no, body):
        return (f'<div class="ppt-top-no">NO. {no}</div>'
                f'<div class="ppt-top-title">t</div>{body}')

    def test_valid_sequence_passes(self):
        html = self.slide("07.1", '<div class="mermaid">sequenceDiagram\n'
                                  'participant V as 투표 (DTC-VOTE-001)</div>')
        self.assertEqual(vs.check_sequence_slides(html), [])

    def test_missing_sequence_slide_is_flagged(self):
        html = self.slide("06", '<div class="mermaid">flowchart LR\nA</div>')
        self.assertTrue(any("07.x Sequence Diagram 슬라이드 없음" in v
                            for v in vs.check_sequence_slides(html)))

    def test_sequence_without_diagram_is_flagged(self):
        html = self.slide("07.1", "<div>텍스트 설명뿐</div>")
        self.assertTrue(any("07.1" in v and "sequenceDiagram 이 없다" in v
                            for v in vs.check_sequence_slides(html)))

    def test_sequence_without_screen_id_is_flagged(self):
        html = self.slide("07.1", '<div class="mermaid">sequenceDiagram\nA->>B: x</div>')
        self.assertTrue(any("화면 ID 가 없다" in v
                            for v in vs.check_sequence_slides(html)))

    def test_flowchart_mermaid_does_not_satisfy(self):
        html = self.slide("07.1", '<div class="mermaid">flowchart LR\n'
                                  'A["DTC-MAIN-001"]</div>')
        self.assertTrue(any("sequenceDiagram 이 없다" in v
                            for v in vs.check_sequence_slides(html)))


class TestOverviewSlides(unittest.TestCase):
    """05 Screen List · 06 Service Flow 판정 (이슈 #37)."""

    IDS = {"DTC-MAIN-001", "DTC-BOARD-001"}

    def slide(self, no, body):
        return (f'<div class="ppt-top-no">NO. {no}</div>'
                f'<div class="ppt-top-title">t</div>{body}')

    def test_valid_slides_pass(self):
        html = (self.slide("05", "<div>DTC-MAIN-001 홈 / DTC-BOARD-001 게시판</div>")
                + self.slide("06", '<div class="mermaid">flowchart LR\n'
                                   'A["홈 DTC-MAIN-001"] --> B["게시판 DTC-BOARD-001"]</div>'))
        self.assertEqual(vs.check_overview_slides(html, self.IDS), [])

    def test_missing_screen_list_slide(self):
        html = self.slide("06", '<div class="mermaid">DTC-MAIN-001</div>')
        self.assertTrue(any("05 Screen List 슬라이드 없음" in v
                            for v in vs.check_overview_slides(html, self.IDS)))

    def test_screen_list_missing_id(self):
        html = (self.slide("05", "<div>DTC-MAIN-001 홈</div>")
                + self.slide("06", '<div class="mermaid">DTC-MAIN-001</div>'))
        self.assertTrue(any("DTC-BOARD-001" in v and "05 Screen List" in v
                            for v in vs.check_overview_slides(html, self.IDS)))

    def test_missing_flow_slide(self):
        html = self.slide("05", "<div>DTC-MAIN-001 DTC-BOARD-001</div>")
        self.assertTrue(any("06 Service Flow 슬라이드 없음" in v
                            for v in vs.check_overview_slides(html, self.IDS)))

    def test_flow_without_mermaid(self):
        html = (self.slide("05", "<div>DTC-MAIN-001 DTC-BOARD-001</div>")
                + self.slide("06", "<div>텍스트 흐름 설명 DTC-MAIN-001</div>"))
        self.assertTrue(any("mermaid 흐름도가 없다" in v
                            for v in vs.check_overview_slides(html, self.IDS)))

    def test_flow_without_ids(self):
        html = (self.slide("05", "<div>DTC-MAIN-001 DTC-BOARD-001</div>")
                + self.slide("06", '<div class="mermaid">flowchart LR\nA --> B</div>'))
        self.assertTrue(any("화면 ID 가 없다" in v
                            for v in vs.check_overview_slides(html, self.IDS)))

    def test_sub_numbered_slide_is_not_slide_05(self):
        """09.5 같은 하위 번호가 05 로 오인되지 않는다."""
        self.assertIsNone(vs.slide_body(self.slide("09.5", "<div>x</div>"), "05"))


if __name__ == "__main__":
    unittest.main()
