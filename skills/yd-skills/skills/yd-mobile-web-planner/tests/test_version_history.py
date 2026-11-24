"""Cover/Document History 버전 정합 검사 테스트 (stdlib only) — 이슈 #74."""
import importlib.util
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "validate_storyboard", SKILL_ROOT / "scripts" / "validate_storyboard.py")
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)


def doc(cover_ver, rows):
    trs = "".join(f"<tr><td>{v}</td><td>2026-07-30</td><td>UX 기획</td><td>{d}</td></tr>"
                  for v, d in rows)
    return (
        f'<div class="ppt-top-no">NO. 01</div><div class="ppt-top-title">Cover</div>'
        f'<table><tr><td>Version</td><td>{cover_ver}</td></tr></table>'
        f'<div class="ppt-top-no">NO. 02</div><div class="ppt-top-title">History</div>'
        f'<table><tr><td>Version</td><td>Date</td><td>Author</td><td>Description</td></tr>{trs}</table>'
    )


class TestVersionHistory(unittest.TestCase):
    def test_matching_versions_pass(self):
        markup = doc("1.0.0", [("1.0.0", "최초 작성")])
        self.assertEqual(vs.check_version_history(markup), [])

    def test_regeneration_appends_row_passes(self):
        markup = doc("2.0.0", [("1.0.0", "최초 작성"),
                               ("2.0.0", "템플릿 v2 재생성 — 목업 밀도 상향")])
        self.assertEqual(vs.check_version_history(markup), [])

    def test_cover_history_mismatch_flagged(self):
        # 콜드 재생성에서 1.0.0 행을 그대로 두고 Cover 만 2.0.0 으로 올린 사고
        markup = doc("2.0.0", [("1.0.0", "최초 작성")])
        v = vs.check_version_history(markup)
        self.assertTrue(any("다르다" in x for x in v), v)

    def test_replaced_row_keeps_first_write_label_flagged(self):
        # tossinvest v2 사고 재현: 1.0.0 행을 2.0.0 으로 치환해 "최초 작성" 이 남음
        markup = doc("2.0.0", [("1.5.0", "화면 추가"), ("2.0.0", "최초 작성")])
        v = vs.check_version_history(markup)
        self.assertTrue(any("최초 작성" in x for x in v), v)

    def test_missing_slides_not_judged(self):
        markup = '<div class="ppt-top-no">NO. 09.1</div>'
        self.assertEqual(vs.check_version_history(markup), [])


if __name__ == "__main__":
    sys.exit(unittest.main())
