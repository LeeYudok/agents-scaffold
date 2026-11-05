"""npx skills(vercel-labs/skills) 노출 범위(#102).

skills CLI 는 레포의 .claude/skills/ 와 .claude-plugin/marketplace.json 플러그인을 탐색하고,
frontmatter metadata.internal: true 인 스킬은 INSTALL_INTERNAL_SKILLS=1 일 때만 보인다(skills 1.7.6 실측).
스캐폴드 에이전트가 있어야 도는 스킬·템플릿·개인 스킬만 숨기고 나머지는 노출한다.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".claude" / "skills"
EN = ROOT / "presets" / "lang" / "en" / "base" / ".claude" / "skills"
PERSONAL = ROOT / "presets" / "skills" / "personal" / ".claude" / "skills"
# 템플릿, 그리고 code-reviewer·security-audit·sdlc-* 에이전트가 있어야 도는 스킬
SCAFFOLD_ONLY = {"example-skill", "review", "security-precheck"}
INTERNAL = re.compile(r"^metadata:\n  internal: true$", re.M)


def frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split("---\n", 2)[1]


def is_internal(path: Path) -> bool:
    return bool(INTERNAL.search(frontmatter(path)))


class SkillVisibilityTests(unittest.TestCase):
    def test_scaffold_only_and_personal_skills_are_internal(self):
        for root in (BASE, EN):
            for name in SCAFFOLD_ONLY:
                self.assertTrue(is_internal(root / name / "SKILL.md"), f"{root}/{name}")
        for skill in sorted(PERSONAL.glob("*/SKILL.md")):
            self.assertTrue(is_internal(skill), skill)

    def test_general_skills_stay_visible(self):
        visible = [
            p.parent.name for p in sorted(BASE.glob("*/SKILL.md")) if not is_internal(p)
        ]
        self.assertEqual(len(visible), 21, visible)  # workflow 7 + yd-* 14
        self.assertEqual(sum(n.startswith("yd-") for n in visible), 14)
        for name in visible:
            self.assertNotIn(name, SCAFFOLD_ONLY)


if __name__ == "__main__":
    unittest.main()
