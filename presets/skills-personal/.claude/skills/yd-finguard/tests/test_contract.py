import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
PIPELINE = (ROOT / "references" / "ai-sdlc.md").read_text(encoding="utf-8")


class TestSkillContract(unittest.TestCase):
    def test_source_and_limitations_are_explicit(self):
        for phrase in ("https://github.com/LeeYudok/finguard", "SCA/CVE",
                       "모의해킹", "취약점 없음", "최대 3회"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, SKILL)

    def test_gate_wrapper_is_the_automation_entrypoint(self):
        self.assertIn("scripts/run_gate.py", SKILL)
        self.assertTrue((ROOT / "scripts" / "run_gate.py").is_file())

    def test_pipeline_names_inputs_evidence_and_stops(self):
        for phrase in ("yd-mobile-web-planner", "yd-nextjs-implementer", "yd-finguard",
                       "통과 근거", "중단 조건", "http://localhost:3000",
                       "http://localhost:5173"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, PIPELINE)


if __name__ == "__main__":
    unittest.main()
