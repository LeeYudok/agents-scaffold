"""목업 본문 실질 검증(check_mock_content 등) 테스트 (stdlib only) — 이슈 #75.

임계값은 tests/fixtures/runtime-parity 의 세 런타임 실측 산출물로
캘리브레이션됐다. 회귀 기준: claude 는 위반 0건 유지, codex·agy 는 잡힌다.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "runtime-parity"
spec = importlib.util.spec_from_file_location(
    "validate_storyboard", SKILL_ROOT / "scripts" / "validate_storyboard.py")
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)


def check_fixture(name):
    css = vs.extract_style(vs.TEMPLATE.read_text(encoding="utf-8"))
    return vs.check(FIXTURES / name, css)


class TestRuntimeParityRegression(unittest.TestCase):
    """세 런타임 실측 산출물 회귀 기준선."""

    def test_claude_stays_clean(self):
        violations, _ = check_fixture("claude.html")
        self.assertEqual(violations, [],
                         "claude 산출물에서 오탐 — 하한값이 과하다는 뜻이다")

    def test_agy_placeholder_and_density_caught(self):
        violations, _ = check_fixture("agy.html")
        text = "\n".join(violations)
        self.assertIn("자리표시자", text)
        self.assertIn("데이터 신호", text)

    def test_codex_retype_and_boilerplate_caught(self):
        violations, _ = check_fixture("codex.html")
        text = "\n".join(violations)
        self.assertIn("재탕", text)
        self.assertIn("시퀀스가 사실상 동일", text)


class TestMockContentUnits(unittest.TestCase):
    DETAIL = (
        '<div class="ppt-top-no">NO. 09.1</div>'
        '<div class="ppt-top-title">홈</div>'
        '{body}'
    )

    def _violations(self, body):
        v, _ = vs.check_mock_content(self.DETAIL.format(body=body))
        return "\n".join(v)

    def test_placeholder_flagged(self):
        body = ('<div class="mock-body" style="x">Mockup Content for 홈</div>'
                '<div class="mock-caption">홈 (AA-MAIN-001)</div>')
        self.assertIn("자리표시자", self._violations(body))

    def test_badge_labels_are_not_data_signals(self):
        # 배지 라벨(1-1, 2-3)은 숫자지만 목업 데이터가 아니다
        body = ('<div class="mock-body">'
                '<span class="pointer-badge" style="top:20px;">1-1</span>'
                '<span class="pointer-badge" style="top:80px;">2-3</span>'
                '내용 없는 화면</div>')
        text = vs.mock_body_text(body)
        self.assertEqual(vs.NUM_SIGNAL_RE.findall(text), [])

    def test_inline_style_values_are_not_text(self):
        body = ('<div class="mock-body" style="padding:16px;">'
                '<div style="height:48px; top:12px;">로그인</div></div>')
        text = vs.mock_body_text(body)
        self.assertEqual(vs.NUM_SIGNAL_RE.findall(text), [])

    def test_tab_arrow_retype_flagged(self):
        body = ('<div class="mock-body">계좌 요약 카드 탭 › 알림 배지 탭 › 이동</div>')
        self.assertIn("재탕", self._violations(body))

    def test_normal_dense_mock_passes(self):
        body = ('<div class="mock-body">총자산 24,580,000원 오늘 손익 +1.2% '
                '2026-08-01 기준</div>'
                '<ul><li><span class="desc-num">1</span> <div><b>총자산 카드</b>'
                '<br>읽기 전용</div></li></ul>')
        self.assertEqual(self._violations(body), "")


class TestSequenceBoilerplate(unittest.TestCase):
    def _slide(self, no, mermaid):
        return (f'<div class="ppt-top-no">NO. {no}</div>'
                f'<div class="mermaid">sequenceDiagram\n{mermaid}</div></div>')

    def test_identical_sequences_flagged(self):
        same = "사용자->>화면: 검증된 요청\n화면->>서버: 처리 결과\n서버-->>화면: 외부시스템 응답"
        markup = self._slide("07.1", same) + self._slide("07.2", same)
        self.assertTrue(vs.check_sequence_boilerplate(markup))

    def test_distinct_sequences_pass(self):
        a = "사용자->>가입: 약관 동의 후 계정 생성\n가입->>인증기관: 인증번호 발송"
        b = "스케줄러->>서버: 경보 감지\n서버->>푸시: 배치 발송 요청\n푸시-->>사용자: 수신"
        markup = self._slide("07.1", a) + self._slide("07.2", b)
        self.assertEqual(vs.check_sequence_boilerplate(markup), [])


if __name__ == "__main__":
    sys.exit(unittest.main())
