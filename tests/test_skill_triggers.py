"""스킬 발동 평가 자료의 형식 검사(#131). 모델을 부르지 않는다.

실제 평가는 scripts/dev/eval-skill-triggers.py 가 `claude plugin eval` 로 돌린다(수동).
여기서는 노출 스킬마다 tests/triggers.json 이 있고 형식이 맞는지, 실행기가 케이스를 제대로 만드는지만 본다.
"""

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"
PERSONAL = ROOT / "presets" / "skills" / "personal" / ".claude" / "skills"
MIN_PER_SIDE = 3

spec = importlib.util.spec_from_file_location("eval_skill_triggers", ROOT / "scripts" / "dev" / "eval-skill-triggers.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def all_skill_names() -> set[str]:
    return {p.parent.name for root in (SKILLS, PERSONAL) for p in root.glob("*/SKILL.md")}


class TriggerDataTests(unittest.TestCase):
    def test_every_visible_skill_has_well_formed_triggers(self):
        known = all_skill_names()
        for name in runner.visible_skills():
            with self.subTest(skill=name):
                path = SKILLS / name / "tests" / "triggers.json"
                self.assertTrue(path.is_file(), f"{name}: tests/triggers.json 이 없다")
                rows = json.loads(path.read_text(encoding="utf-8"))
                queries = [row["query"] for row in rows]
                self.assertEqual(len(queries), len(set(queries)), "같은 질문이 두 번 있다")
                for row in rows:
                    self.assertLessEqual(set(row), {"query", "should_trigger", "expect"})
                    self.assertIsInstance(row["should_trigger"], bool)
                    self.assertTrue(row["query"].strip())
                    if "expect" in row:
                        self.assertFalse(row["should_trigger"], "expect 는 비발동 질문에만 쓴다")
                        self.assertIn(row["expect"], known)
                        self.assertNotEqual(row["expect"], name)
                for wanted in (True, False):
                    count = sum(row["should_trigger"] is wanted for row in rows)
                    self.assertGreaterEqual(count, MIN_PER_SIDE, f"should_trigger={wanted} 질문이 {count}개다")

    def test_no_query_should_trigger_two_skills(self):
        owners = {}
        for name in runner.visible_skills():
            for row in runner.load_triggers(name):
                if row["should_trigger"]:
                    owners.setdefault(row["query"], []).append(name)
        shared = {query: names for query, names in owners.items() if len(names) > 1}
        self.assertEqual(shared, {})


class RunnerTests(unittest.TestCase):
    def test_dry_run_builds_one_case_per_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertEqual(runner.main(["--dry-run", "--out", str(out), "--skill", "yd-cve-check"]), 0)
            plugin = out / "plugin"
            cases = sorted(p.name for p in (plugin / "evals").iterdir())
            self.assertEqual(len(cases), len(runner.load_triggers("yd-cve-check")))
            # 스킬끼리 경쟁해야 하므로 플러그인에는 노출 스킬이 전부 들어간다
            self.assertEqual(sorted(p.name for p in (plugin / "skills").iterdir()), runner.visible_skills())
            self.assertFalse(list(plugin.rglob("triggers.json")), "질문 자료가 평가 대상에 섞이면 안 된다")
            grader = (plugin / "evals" / cases[0] / "graders" / "trigger.md").read_text(encoding="utf-8")
            self.assertIn("type: tool_used", grader)
            pattern = re.search(r"input_match: '(.*)'", grader).group(1)
            self.assertRegex('{"skill": "yd-cve-check"}', pattern)
            self.assertRegex('{"skill":"yd-trigger-eval:yd-cve-check"}', pattern)
            self.assertNotRegex('{"skill": "yd-cve-check-extra"}', pattern)
            prompt = (plugin / "evals" / cases[0] / "prompt.md").read_text(encoding="utf-8")
            self.assertIn("allowed_tools: [Skill]", prompt)

    def test_unknown_skill_is_rejected(self):
        self.assertEqual(runner.main(["--dry-run", "--skill", "review"]), 2)  # 내부 스킬은 평가 대상이 아니다

    def test_summary_counts_a_quiet_negative_as_correct(self):
        cases = {
            "a-01": {"skill": "a", "query": "q1", "should_trigger": True},
            "a-02": {"skill": "a", "query": "q2", "should_trigger": False, "expect": "b"},
            "a-03": {"skill": "a", "query": "q3", "should_trigger": False},
        }
        result = {"cases": [
            {"name": "a-01", "arms": {"with": [{"passed": True}]}},
            {"name": "a-02", "arms": {"with": [{"passed": False}]}},
            {"name": "a-03", "arms": {"with": [{"passed": True}]}},
        ]}
        table, wrong = runner.summarize(cases, result)
        self.assertEqual(table, [("a", 1, 1, 1, 2)])
        self.assertEqual(wrong, ["a: 잘못 발동 — q3"])


if __name__ == "__main__":
    unittest.main()
