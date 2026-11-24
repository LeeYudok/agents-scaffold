"""install-hook.sh 가 임시 저장소에 hook 을 설치하고 다시 돌려도 안전한지 확인한다."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
INSTALL = SCRIPTS / "install-hook.sh"
SRC = SCRIPTS / "commit-msg.sh"


class InstallHookTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.hook = self.repo / ".git" / "hooks" / "commit-msg"
        self.copy = self.repo / "scripts" / "commit-msg.sh"

    def install(self, *args):
        return subprocess.run(["sh", str(INSTALL), *args], cwd=self.repo, capture_output=True, text=True)

    def test_installs_script_copy_and_hook(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.copy.read_bytes(), SRC.read_bytes())
        self.assertTrue(os.access(self.copy, os.X_OK))
        self.assertTrue(os.access(self.hook, os.X_OK))
        self.assertIn("# yd-git-ship", self.hook.read_text())

    def test_check_fails_before_install_and_passes_after(self):
        self.assertEqual(self.install("--check").returncode, 1)
        self.install()
        r = self.install("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("OK", r.stdout)

    def test_second_run_is_idempotent(self):
        self.install()
        before = self.hook.read_text()
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("up to date", r.stdout)
        self.assertEqual(self.hook.read_text(), before)

    def test_rerun_updates_stale_repo_copy(self):
        self.install()
        self.copy.write_text("#!/bin/sh\nexit 0\n")
        self.assertEqual(self.install("--check").returncode, 1)
        self.install()
        self.assertEqual(self.copy.read_bytes(), SRC.read_bytes())

    def test_refuses_to_overwrite_foreign_hook(self):
        self.hook.parent.mkdir(exist_ok=True)
        self.hook.write_text("#!/bin/sh\necho mine\n")
        r = self.install()
        self.assertEqual(r.returncode, 1)
        self.assertIn("not ours", r.stderr)
        self.assertEqual(self.hook.read_text(), "#!/bin/sh\necho mine\n")

    def test_installed_hook_blocks_bad_commit_and_allows_good_one(self):
        self.install()
        (self.repo / "f.txt").write_text("x")
        subprocess.run(["git", "add", "f.txt"], cwd=self.repo, check=True)
        base = ["git", "-c", "user.name=claude-ai", "-c", "user.email=claude-ai@example.com", "commit", "-q"]
        bad = subprocess.run([*base, "-m", "docs: 태그 없음"], cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        good = subprocess.run([*base, "-m", "[Claude Opus 5.5] docs: 정상 (#1)"], cwd=self.repo,
                              capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)

    def test_does_not_touch_global_git_config(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        env = {**os.environ, "HOME": home.name, "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": home.name}
        subprocess.run(["sh", str(INSTALL)], cwd=self.repo, env=env, check=True, capture_output=True)
        self.assertEqual(os.listdir(home.name), [])


if __name__ == "__main__":
    unittest.main()
