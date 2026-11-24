"""yd-nextjs-implementer 가 참조하는 외부 계약의 드리프트 검출 (stdlib only).

이 스킬의 SKILL.md 는 yd-mobile-web-planner 산출물의 구조(Business Rules 4개 절)
를 구현 체크리스트로 쓴다고 약속한다. 기획 스킬이 절 이름을 바꾸면 이 약속이
조용히 낡으므로, 두 스킬 문서를 대조해 어긋남을 테스트로 잡는다.
"""
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = SKILL_ROOT.parent
# agents-scaffold(#78): 옵트인 스킬은 presets/skills/personal/.claude/skills 에 있다. 에이전트 원본은
# .claude/agents/<스킬명>.md 하나이고 Codex·agy 에이전트는 설치기가 생성한다.
REPO_ROOT = SKILL_ROOT.parents[2]
SKILL_DIRS = (SKILLS_DIR, REPO_ROOT / "presets" / "skills" / "personal" / ".claude" / "skills")
AGENT = SKILL_ROOT.parent.parent / "agents" / f"{SKILL_ROOT.name}.md"


def flat(text):
    """줄바꿈으로 갈라진 구문도 잡히게 공백을 한 칸으로 정규화한다."""
    return re.sub(r"\s+", " ", text)


SKILL_MD = flat((SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8"))

# SKILL.md 가 "4개 절"로 약속하는 Business Rules 섹션 명칭.
BR_SECTIONS = ("입력 검증", "출력 규칙", "인터랙션", "엣지케이스")


class TestPlannerContract(unittest.TestCase):
    """yd-mobile-web-planner 산출물 구조에 대한 참조가 실제와 일치해야 한다."""

    @classmethod
    def setUpClass(cls):
        cls.planner = flat((
            SKILLS_DIR / "yd-mobile-web-planner" / "SKILL.md"
        ).read_text(encoding="utf-8"))

    def test_br_sections_exist_in_planner(self):
        """참조하는 4개 절 명칭이 기획 스킬 문서에도 그대로 있어야 한다."""
        for section in BR_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, self.planner)
                self.assertIn(section, SKILL_MD)

    def test_storyboard_slide_refs_exist_in_planner(self):
        """참조하는 슬라이드 번호(05/06/07.x/08/09.x)가 기획 스킬의 번호
        체계에 존재해야 한다 — 체계가 바뀌면 여기서 드리프트가 잡힌다."""
        for ref in ("05 Screen List", "06 Service Flow", "08 General Rule"):
            with self.subTest(ref=ref):
                self.assertIn(ref, SKILL_MD)
                self.assertIn(ref.split(" ", 1)[1], self.planner)
        self.assertIn("07.x", SKILL_MD)
        self.assertIn("09.x", SKILL_MD)

    def test_deliverable_filename_patterns_match_planner(self):
        """입력 파일명 패턴이 기획 스킬의 산출물 명명과 일치해야 한다."""
        for pattern in ("_storyboard.html", "_business-rules.md"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, SKILL_MD)
                self.assertIn(pattern, self.planner)


class TestBackendModeConsistency(unittest.TestCase):
    """백엔드 모드의 기술 계약은 SKILL.md 한 곳에서 유지한다."""

    def test_java_version_is_consistent(self):
        self.assertIn("Java 1.8", SKILL_MD)

    def test_spring_boot_line_is_java8_compatible(self):
        """Spring Boot 는 2.7 (Java 8 을 지원하는 마지막 라인)로 고정한다."""
        self.assertIn("Spring Boot 2.7", SKILL_MD)
        self.assertNotRegex(
            SKILL_MD, r"Spring Boot 3",
            "Spring Boot 3 은 Java 17 필수 — Java 1.8 계약과 모순된다")

    def test_doksam_ui_link_targets_existing_skill(self):
        """yd-doksam-ui 연계 문구가 있다면 그 스킬이 실제로 존재해야 한다."""
        if "yd-doksam-ui" not in SKILL_MD:
            self.skipTest("yd-doksam-ui 연계 문구 없음")
        self.assertTrue(
            any((d / "yd-doksam-ui" / "SKILL.md").is_file() for d in SKILL_DIRS),
            "SKILL.md 가 yd-doksam-ui Skill 을 참조하지만 스킬이 없다")


class TestFrontendModeContract(unittest.TestCase):
    def test_two_frontend_modes_and_owners_are_explicit(self):
        for phrase in ("Next.js App Router", "Vite + React SPA",
                       "yd-frontend-build", "yd-react-expert", "yd-doksam-ui"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, SKILL_MD)

    def test_mode_reference_and_traceability_contract_exist(self):
        reference = SKILL_ROOT / "references" / "implementation-modes.md"
        self.assertTrue(reference.is_file())
        text = flat(reference.read_text(encoding="utf-8"))
        for phrase in ("http://localhost:3000", "http://localhost:5173",
                       "traceability.json", "ruleId", "screenId"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertTrue((SKILL_ROOT / "scripts" / "validate_traceability.py").is_file())

    def test_adapters_name_both_frontend_families(self):
        text = AGENT.read_text(encoding="utf-8")
        self.assertIn("Next.js", text)
        self.assertIn("Vite + React", text)


if __name__ == "__main__":
    unittest.main()


class TestReferencedFiles(unittest.TestCase):
    """SKILL.md 가 가리키는 참조 문서와 스크립트가 실제로 있어야 한다.

    링크만 남고 파일이 사라지면 에이전트는 그 절을 조용히 건너뛴다 — 실행
    계약이 있다고 믿는 상태가 없는 상태보다 나쁘다.
    """

    def test_linked_references_exist(self):
        for name in re.findall(r"\(references/([\w.-]+)\)",
                               (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")):
            with self.subTest(reference=name):
                self.assertTrue((SKILL_ROOT / "references" / name).is_file(),
                                f"references/{name} 가 없다")

    def test_serve_and_check_is_wired(self):
        self.assertIn("serve_and_check.py", SKILL_MD,
                      "기동·헬스체크가 스크립트로 연결돼 있지 않다")
        self.assertTrue((SKILL_ROOT / "scripts" / "serve_and_check.py").is_file())

    def test_smb_reference_keeps_planner_first(self):
        """소상공인 경로가 기획 단계를 건너뛰지 않아야 한다."""
        smb = flat((SKILL_ROOT / "references" / "smb-quickstart.md")
                   .read_text(encoding="utf-8"))
        self.assertIn("yd-mobile-web-planner", smb)
        for term in ("사업자등록번호", "통신판매업 신고번호", "개인정보"):
            with self.subTest(term=term):
                self.assertIn(term, smb)
