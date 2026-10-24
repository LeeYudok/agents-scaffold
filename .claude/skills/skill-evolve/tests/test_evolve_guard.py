"""evolve_guard.py 를 임시 git 저장소에서 검증한다 (stdlib only, 이슈 #201)."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "evolve_guard.py"
spec = importlib.util.spec_from_file_location("evolve_guard", SCRIPT)
g = importlib.util.module_from_spec(spec)
sys.modules["evolve_guard"] = g
spec.loader.exec_module(g)

GOOD = """---
name: demo
description: 데모 스킬
---

# 본문

## Learned warnings

- (2026-08-01) 첫 경고.
- (2026-09-02) 둘째 경고.
"""


def skill_md(name="demo", warnings=("- (2026-08-01) 첫 경고.", "- (2026-09-02) 둘째 경고."), extra_fm=""):
    return (f"---\nname: {name}\ndescription: 데모 스킬\n{extra_fm}---\n\n# 본문\n\n"
            "## Learned warnings\n\n" + "\n".join(warnings) + "\n")


class CheckText(unittest.TestCase):
    def test_good_file_passes(self):
        self.assertEqual(g.check_text("demo", GOOD, GOOD, require_section=True), [])

    def test_extra_frontmatter_key_and_wrong_name(self):
        text = skill_md(name="other", extra_fm="version: 2\n")
        p = g.check_text("demo", text)
        self.assertTrue(any("version" in x for x in p))
        self.assertTrue(any("디렉터리명" in x for x in p))

    def test_missing_or_unclosed_frontmatter(self):
        self.assertTrue(g.check_text("demo", "# 제목만\n"))
        self.assertTrue(g.check_text("demo", "---\nname: demo\n# 닫히지 않음\n"))

    def test_emoji_is_rejected_but_arrows_and_checks_are_not(self):
        bad = GOOD + "\n완료 \U0001F680\n"
        self.assertTrue(any("이모지" in x for x in g.check_text("demo", bad)))
        ok = "---\nname: demo\ndescription: d\n---\n\n입력 → 출력, A ⇒ B, 통과 ✓, 메뉴 ⋮\n"
        self.assertEqual(g.check_text("demo", ok), [])
        self.assertTrue(g.check_text("demo", ok + "\u2705 완료\n"))

    def test_warning_line_format(self):
        text = skill_md(warnings=("- 날짜 없는 경고", "- (2026-8-1) 한 자리 월", "* (2026-08-01) 별표"))
        self.assertEqual(len(g.check_text("demo", text)), 3)

    def test_impossible_date_is_rejected(self):
        text = skill_md(warnings=("- (2026-02-30) 없는 날짜",))
        self.assertTrue(any("달력" in x for x in g.check_text("demo", text)))

    def test_continuation_lines_are_not_warnings(self):
        text = skill_md(warnings=("- (2026-08-01) 첫 줄", "  이어지는 설명"))
        self.assertEqual(g.check_text("demo", text), [])

    def test_removed_warning_is_a_violation_unless_allowed(self):
        new = skill_md(warnings=("- (2026-09-02) 둘째 경고.",))
        self.assertTrue(any("사라졌다" in x for x in g.check_text("demo", new, GOOD)))
        self.assertEqual(g.check_text("demo", new, GOOD, allow_removal=True), [])

    def test_appending_a_warning_is_fine(self):
        new = GOOD + "- (2026-10-04) 셋째 경고.\n"
        self.assertEqual(g.check_text("demo", new, GOOD), [])

    def test_section_stops_at_next_heading(self):
        text = GOOD + "\n## 다음 절\n\n- 이 줄은 경고가 아니다\n"
        self.assertEqual(g.check_text("demo", text), [])

    def test_missing_section_is_ok_unless_required(self):
        text = "---\nname: demo\ndescription: d\n---\n\n본문\n"
        self.assertEqual(g.check_text("demo", text), [])
        self.assertTrue(g.check_text("demo", text, require_section=True))


class Repo(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.repo = Path(self._t.name)
        self.git("init", "-q")
        for n in ("demo", "other"):
            (self.repo / "skills" / n).mkdir(parents=True)
            (self.repo / "skills" / n / "SKILL.md").write_text(skill_md(n))
        (self.repo / "scripts").mkdir()
        self.set_tests(0)
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")

    def git(self, *a):
        r = subprocess.run(["git", "-C", str(self.repo), *a], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def set_tests(self, code):
        f = self.repo / "scripts" / "run_tests.sh"
        f.write_text(f"#!/bin/sh\nexit {code}\n")
        f.chmod(0o755)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--repo", str(self.repo)],
                              capture_output=True, text=True, timeout=60)

    def read(self, name):
        return (self.repo / "skills" / name / "SKILL.md").read_text()

    def test_clean_reports_dirty_tree(self):
        self.assertEqual(self.cli("clean").returncode, 0)
        (self.repo / "stray.txt").write_text("x")
        r = self.cli("clean")
        self.assertEqual(r.returncode, 1)
        self.assertIn("stray.txt", r.stdout)

    def test_clean_outside_git_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(SCRIPT), "clean", "--repo", d],
                               capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_rollback_restores_only_that_skill(self):
        (self.repo / "skills" / "demo" / "SKILL.md").write_text("망가진 편집")
        other_edit = skill_md("other") + "\n다른 에이전트의 작업 중인 편집\n"
        (self.repo / "skills" / "other" / "SKILL.md").write_text(other_edit)
        (self.repo / "notes.txt").write_text("미추적 파일")
        self.assertEqual(self.cli("rollback", "demo").returncode, 0)
        self.assertEqual(self.read("demo"), skill_md("demo"))
        self.assertEqual(self.read("other"), other_edit)
        self.assertTrue((self.repo / "notes.txt").exists())

    def test_verify_failure_rolls_back_only_the_edited_skill(self):
        (self.repo / "skills" / "demo" / "SKILL.md").write_text("테스트를 깨는 편집")
        other_edit = skill_md("other") + "\n병렬 편집\n"
        (self.repo / "skills" / "other" / "SKILL.md").write_text(other_edit)
        self.set_tests(3)
        r = self.cli("verify", "demo")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.read("demo"), skill_md("demo"))
        self.assertEqual(self.read("other"), other_edit)

    def test_verify_success_keeps_the_edit(self):
        edited = skill_md("demo") + "\n새 내용\n"
        (self.repo / "skills" / "demo" / "SKILL.md").write_text(edited)
        r = self.cli("verify", "demo")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("demo"), edited)

    def test_verify_with_missing_test_runner_counts_as_failure(self):
        (self.repo / "skills" / "demo" / "SKILL.md").write_text("편집")
        (self.repo / "scripts" / "run_tests.sh").unlink()
        r = subprocess.run([sys.executable, str(SCRIPT), "verify", "demo", "--repo", str(self.repo)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.read("demo"), "편집")  # 검증을 못 했을 뿐이라 편집은 남는다

    def test_unknown_or_traversal_skill_is_usage_error(self):
        for bad in ("nope", "../etc", "Demo", ""):
            r = self.cli("rollback", bad)
            self.assertEqual(r.returncode, 2, bad)

    def test_check_uses_head_as_base_for_preservation(self):
        (self.repo / "skills" / "demo" / "SKILL.md").write_text(
            skill_md(warnings=("- (2026-09-02) 둘째 경고.",)))
        r = self.cli("check", "demo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("사라졌다", r.stdout)
        self.assertEqual(self.cli("check", "demo", "--allow-removal").returncode, 0)


if __name__ == "__main__":
    unittest.main()
