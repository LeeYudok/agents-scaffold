"""글쓰기 품질 평가 과제의 형식과 채점기 (#139). 모델은 부르지 않는다."""

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
spec = importlib.util.spec_from_file_location("score_writing_tasks", SKILL / "scripts" / "score_writing_tasks.py")
st = importlib.util.module_from_spec(spec)
sys.modules["score_writing_tasks"] = st
spec.loader.exec_module(st)

DATA = st.load_tasks()
RULES = st.check_writing.load_rules()
TASKS = {t["id"]: t for t in DATA["tasks"]}

GOOD_NOTICE = """2026-11-21(토) 02:00부터 04:00까지 서비스를 점검합니다.

점검하는 동안 로그인, 결제, 글쓰기를 쓸 수 없습니다. 조회도 끊길 수 있습니다.
점검이 시작될 때 진행 중이던 결제는 실패로 처리하고 자동으로 환불합니다. 환불은 영업일 3일 안에 끝납니다.
결제와 글쓰기는 02:00 전에 마쳐 주세요.

문의는 고객센터 help@example.com 으로 보내 주세요.
"""

BAD_NOTICE = """안녕하세요. 운영팀입니다.

#482 이슈 관련하여 PG 17.4 패치 작업을 진행할 예정입니다. 서진 님이 run_patch.sh 리허설을 마쳤습니다.
switchover 때문에 약 10분 동안 쓰기가 안 됩니다.
점검은 2026-11-22 02:00 에 시작합니다.
"""

GOOD_MINUTES = """## 결정

- 검색 엔진은 지금 바꾸지 않는다. PG 튜닝과 OpenSearch PoC 를 2주 동안 비교하고 2026-11-28 리뷰에서 정한다.
- 비교 기준은 p95 와 붙여 쓴 말 검색 정답률이다.
- 검색 UI 개편은 예정대로 12월에 한다.

## 할 일

- 하준: PG 튜닝.
- 유나: OpenSearch PoC. 평가용 질의 200개는 2026-11-19 까지 만든다.
- 시온: 클러스터 견적을 2026-11-21 까지 받는다.

## 미결

- 검색 엔진을 OpenSearch 로 바꿀지는 2026-11-28 에 정한다.
"""

BAD_MINUTES = """## 결정

- 검색 엔진을 OpenSearch 로 전환하기로 했다.
- 검색 UI 개편은 12월에 한다.

## 할 일

- 유나: 평가용 질의를 2026-11-19 까지 만든다.
"""


def run(task_id, text):
    task = TASKS[task_id]
    return st.score(task, DATA["kinds"][task["kind"]], text, RULES)


class TaskFormat(unittest.TestCase):
    def test_twelve_tasks_three_per_kind(self):
        self.assertEqual(Counter(t["kind"] for t in DATA["tasks"]), {"issue": 3, "notice": 3, "incident": 3, "minutes": 3})
        self.assertEqual(len(TASKS), 12, "과제 id 가 겹친다")

    def test_every_fact_comes_from_the_material(self):
        for task in DATA["tasks"]:
            kind = DATA["kinds"][task["kind"]]
            source = st.material(task["id"])
            self.assertTrue(task["title"] and task["reader"] and task["lead"] and task["must_have"] and task["must_not"], task["id"])
            for item in task["lead"] + task["must_have"]:
                with self.subTest(task=task["id"], label=item["label"]):
                    self.assertTrue(item["any"])
                    if not item.get("free"):
                        self.assertTrue(st.has(source, item), "원자료에 없는 사실은 채점 기준이 될 수 없다")
                    if item.get("section"):
                        self.assertIn(item["section"], kind["sections"])
            for item in task["must_not"]:
                with self.subTest(task=task["id"], label=item["label"]):
                    self.assertTrue(item["any"] and item["why"])

    def test_instructions_do_not_leak_the_criteria(self):
        for task in DATA["tasks"]:
            text = st.prompt(task, DATA["kinds"][task["kind"]])
            self.assertIn(st.material(task["id"]), text)
            for item in task["must_not"]:
                self.assertNotIn(item["why"], text, "채점 기준을 지시문에 넣지 않는다")


class Scorer(unittest.TestCase):
    def test_good_notice_gets_full_score(self):
        result = run("notice-01", GOOD_NOTICE)
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["passed"], result["total"])

    def test_bad_notice_loses_the_points_it_should(self):
        result = run("notice-01", BAD_NOTICE)
        for label in ("검사기 오류 0건", "원문 대조 오류 0건", "첫머리: 날짜", "사실: 환불 안내", "사실: 문의처",
                      "금지: 이슈 번호", "금지: 내부 스크립트", "금지: 내부 용어", "금지: 담당자 이름"):
            self.assertIn(label, result["failed"])
        self.assertLess(result["passed"], run("notice-01", GOOD_NOTICE)["passed"])

    def test_sections_keep_decisions_and_open_questions_apart(self):
        good, bad = run("minutes-02", GOOD_MINUTES), run("minutes-02", BAD_MINUTES)
        self.assertEqual(good["failed"], [])
        for label in ("미결 절: 엔진 선택은 미결", "금지: 정하지 않은 것을 정한 것처럼 쓰지 않는다", "절: 미결", "할 일 절: PG 튜닝 담당"):
            self.assertIn(label, bad["failed"])

    def test_missing_output_scores_zero(self):
        result = run("issue-01", None)
        self.assertTrue(result["missing"])
        self.assertEqual(result["passed"], 0)

    def test_thousands_separator_is_ignored(self):
        self.assertTrue(st.has("대상은 610110건이다.", {"any": ["610,110"]}))

    def test_headings_in_three_styles(self):
        for line in ("## 미결", "**미결 사항**", "미결:"):
            self.assertIn("미결", st.heading_of(line) or "", line)
        self.assertIsNone(st.heading_of("- 검색 엔진은 지금 바꾸지 않는다."))


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        for name, notice, minutes in (("baseline", BAD_NOTICE, BAD_MINUTES), ("skill", GOOD_NOTICE, GOOD_MINUTES)):
            (self.tmp / name).mkdir()
            (self.tmp / name / "notice-01.md").write_text(notice, encoding="utf-8")
            (self.tmp / name / "minutes-02.md").write_text(minutes, encoding="utf-8")

    def main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = st.main([str(a) for a in args])
        return code, out.getvalue(), err.getvalue()

    def test_list_and_prompt(self):
        code, out, _ = self.main("--list")
        self.assertEqual((code, len(out.strip().splitlines())), (0, 12))
        code, out, _ = self.main("--prompt", "incident-01")
        self.assertEqual(code, 0)
        self.assertIn("독자: 팀장", out)
        self.assertEqual(self.main("--prompt", "none")[0], 2)

    def test_compare_shows_the_skill_folder_ahead(self):
        code, out, err = self.main(self.tmp / "baseline", "--compare", self.tmp / "skill", "--json")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        by = {name: {r["id"]: r for r in rows} for name, rows in data.items()}
        for task in ("notice-01", "minutes-02"):
            self.assertGreater(by["skill"][task]["passed"], by["baseline"][task]["passed"])
        self.assertTrue(by["skill"]["issue-01"]["missing"])
        code, out, _ = self.main(self.tmp / "baseline", "--compare", self.tmp / "skill")
        self.assertIn("| 공지 |", out)

    def test_blind_sheet_hides_which_folder_wrote_what(self):
        sheet, key = self.tmp / "sheet.md", self.tmp / "key.json"
        code, _, err = self.main("--blind", self.tmp / "baseline", self.tmp / "skill", "-o", sheet, "--key", key)
        self.assertEqual(code, 0, err)
        text = sheet.read_text(encoding="utf-8")
        self.assertNotIn("baseline", text)
        self.assertNotIn("skill", text)
        self.assertIn(GOOD_NOTICE.strip(), text)
        self.assertEqual(text.count("[ ] 가  [ ] 나  [ ] 같음"), 12 * len(st.QUESTIONS))
        answers = json.loads(key.read_text(encoding="utf-8"))["tasks"]
        self.assertEqual(len(answers), 12)
        self.assertEqual({tuple(sorted(v.values())) for v in answers.values()}, {("A", "B")})
        self.assertGreater(len({v["가"] for v in answers.values()}), 1, "순서를 섞어야 한다")
        self.assertEqual(self.main("--blind", self.tmp / "baseline", self.tmp / "skill", "-o", sheet)[0], 2)

    def test_missing_folder_is_a_tool_error(self):
        self.assertEqual(self.main(self.tmp / "none")[0], 2)
        self.assertEqual(self.main()[0], 2)


if __name__ == "__main__":
    unittest.main()
