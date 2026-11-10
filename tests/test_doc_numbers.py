"""scripts/dev/check-doc-numbers.py 검사 (#105 #107).

레포 자체에서 통과하는지, 숫자·등급을 틀리게 고친 사본에서 잡아내는지 본다.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dev" / "check-doc-numbers.py"


def run_check(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def copy_inputs(dst: Path) -> None:
    """검사기가 읽는 것만 임시 폴더에 옮긴다."""
    for readme in ROOT.glob("README*.md"):
        shutil.copy(readme, dst / readme.name)
    (dst / "docs").mkdir()
    for name in ("index.html", "llms.txt", "harness-matrix.json"):
        shutil.copy(ROOT / "docs" / name, dst / "docs" / name)
    for stack in (ROOT / "presets" / "stacks").iterdir():
        if stack.is_dir():
            (dst / "presets" / "stacks" / stack.name).mkdir(parents=True)
    for skill in (ROOT / ".claude" / "skills").glob("*/SKILL.md"):
        target = dst / ".claude" / "skills" / skill.parent.name
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("stub\n", encoding="utf-8")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError(
            f"{path.name} 에 '{old}' 가 없다 — 테스트의 전제가 바뀌었다"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


class DocNumbersTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        copy_inputs(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_repo_passes(self):
        result = run_check(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK:", result.stdout)

    def test_untouched_copy_passes(self):
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_stack_count_in_readme_fails(self):
        stacks = len(list((self.tmp / "presets" / "stacks").iterdir()))
        replace_once(
            self.tmp / "README.md",
            f"{stacks} stack presets",
            f"{stacks - 1} stack presets",
        )
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 1)
        self.assertIn("README.md", result.stderr)
        self.assertIn(f"{stacks}개", result.stderr)

    def test_wrong_stack_count_in_landing_page_fails(self):
        stacks = len(list((self.tmp / "presets" / "stacks").iterdir()))
        replace_once(
            self.tmp / "docs" / "index.html",
            f"{stacks} stack presets",
            f"{stacks + 1} stack presets",
        )
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/index.html", result.stderr)

    def test_new_stack_directory_makes_docs_stale(self):
        (self.tmp / "presets" / "stacks" / "elixir").mkdir()
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 1)

    def test_wrong_tier_in_landing_page_fails(self):
        replace_once(
            self.tmp / "docs" / "index.html",
            'data-harness="codex" data-tier="baseline"',
            'data-harness="codex" data-tier="full"',
        )
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 1)
        self.assertIn("codex", result.stderr)

    def test_wrong_tier_in_llms_txt_fails(self):
        replace_once(
            self.tmp / "docs" / "llms.txt",
            "agy 1.5.0 baseline tier",
            "agy 1.5.0 full tier",
        )
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/llms.txt", result.stderr)

    def test_stale_cli_version_fails(self):
        replace_once(
            self.tmp / "README.ko.md", "codex-cli 0.166.0", "codex-cli 0.160.0"
        )
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 1)
        self.assertIn("README.ko.md", result.stderr)

    def test_wrong_skill_count_fails(self):
        replace_once(
            self.tmp / "README.ja.md", "| `--lang en` | 10 |", "| `--lang en` | 24 |"
        )
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 1)
        self.assertIn("README.ja.md", result.stderr)


if __name__ == "__main__":
    unittest.main()
