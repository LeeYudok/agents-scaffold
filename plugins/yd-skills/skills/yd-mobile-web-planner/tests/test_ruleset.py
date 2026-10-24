"""규칙 세트 버전·2단 출력 테스트 (stdlib only) — 이슈 #77."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "validate_storyboard", SKILL_ROOT / "scripts" / "validate_storyboard.py")
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

scaffold_spec = importlib.util.spec_from_file_location(
    "scaffold", SKILL_ROOT / "scripts" / "scaffold.py")
scaffold = importlib.util.module_from_spec(scaffold_spec)
scaffold_spec.loader.exec_module(scaffold)

RULES = """# T Business Rules

Version: 1.0.0

## TT-MAIN-001 홈

### 입력 검증
해당 없음 — 조회 전용.

### 출력 규칙
| 상태 | 표시 |
|---|---|
| 로딩 | 스켈레톤 |

### 인터랙션
| 트리거 | 조건/검증 | 동작 |
|---|---|---|
| 행 탭 | - | 상태 갱신 |

### 엣지케이스
- 없음에 준함.
"""

#: 인터랙션 표 배지 인용 없음(v2 규칙) 위반이 하나 나오는 최소 문서.
def storyboard(meta):
    return (
        f'{meta}'
        '<div class="ppt-top-no">NO. 05</div><div class="ppt-top-title">Screen List</div>'
        '<table><tr><td>TT-MAIN-001</td><td>홈</td><td>화면</td><td>홈</td><td>-</td></tr></table>'
        '<div class="ppt-top-no">NO. 06</div><div class="ppt-top-title">Service Flow</div>'
        '<div class="mermaid">flowchart LR\nA["홈 TT-MAIN-001"]</div>'
        '<div class="ppt-top-no">NO. 07.1</div><div class="ppt-top-title">Sequence</div>'
        '<div class="mermaid">sequenceDiagram\nparticipant M as 홈 (TT-MAIN-001)\nM->>S: 제출</div>'
        '<div class="ppt-top-no">NO. 09.1</div><div class="ppt-top-title">홈</div>'
        '<div class="ppt-meta-value">홈</div><div class="ppt-meta-id">TT-MAIN-001</div>'
        '<div class="mock-body">잔액 1,000원 2건</div>'
        '<div class="mock-caption">홈 (TT-MAIN-001)</div>'
        '<span class="pointer-badge" style="top:10px; left:2px;">1</span>'
        '<span class="desc-num">1</span><li>행 목록 탭: 갱신</li>'
        '<script src="mermaid.min.js"></script>')


def run_check(meta, strict=False):
    css = ".ppt-slide{}"
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "t_storyboard.html"
        html_path.write_text(storyboard(meta), encoding="utf-8")
        (Path(td) / "t_business-rules.md").write_text(RULES, encoding="utf-8")
        return vs.check(str(html_path), css, strict=strict)


class TestRulesetTiering(unittest.TestCase):
    def test_legacy_doc_demotes_v2_rules_to_advisory(self):
        violations, info = run_check(meta="")
        self.assertFalse(any("배지 번호 인용" in v for v in violations),
                         "메타 없는 옛 문서에서 v2 규칙이 위반으로 집계됐다")
        self.assertTrue(any("신규 규칙 위반" in x for x in info), info)

    def test_strict_enforces_all(self):
        violations, _ = run_check(meta="", strict=True)
        self.assertTrue(any("배지 번호 인용" in v for v in violations))

    def test_current_doc_enforces_v2(self):
        violations, _ = run_check(meta='<meta name="skill-ruleset" content="2">')
        self.assertTrue(any("배지 번호 인용" in v for v in violations))
        self.assertFalse(any("규칙 ID" in v for v in violations),
                         "v2 문서에는 v3 규칙이 기본 위반이면 안 된다")

    def test_doc_ruleset_parse(self):
        self.assertEqual(vs.doc_ruleset('<meta name="skill-ruleset" content="2">'), 2)
        self.assertEqual(vs.doc_ruleset("<head></head>"), 1)


class TestScaffoldMeta(unittest.TestCase):
    def test_scaffold_embeds_current_ruleset(self):
        html = scaffold.build(scaffold.TEMPLATE.read_text(encoding="utf-8"),
                              project="티", version="1.0.0")
        self.assertIn(f'<meta name="skill-ruleset" content="{vs.RULESET_VERSION}">', html)


if __name__ == "__main__":
    sys.exit(unittest.main())
