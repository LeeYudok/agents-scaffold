"""codex-qwen 역할 배치 규칙이 스킬 문서에 남아 있는지 본다."""

import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]


class QwenRoleContract(unittest.TestCase):
    def setUp(self):
        self.text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    def test_qwen_is_not_primary_coordinator(self):
        self.assertIn(
            "`codex-qwen` 은 초기에는 주 지휘자로 세우지 않고 독립 실행자·2차 리뷰어로 배치한다.",
            self.text,
        )

    def test_qwen_has_preferred_task_shapes_and_guarded_boundaries(self):
        for phrase in (
            "교차 리뷰",
            "독립 구현안 비교",
            "경계가 분명한 A2A 작업",
            "`128K` 문맥",
            "전체 지휘, 장시간 자율 루프, 운영 배포 판단",
            "리뷰만 맡길 때는 `read-only` 로 제한한다.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)


if __name__ == "__main__":
    unittest.main()
