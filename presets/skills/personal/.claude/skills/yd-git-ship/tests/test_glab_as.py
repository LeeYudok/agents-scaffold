"""glab-as.sh 가 토큰을 출력하지 않고 glab 에만 환경변수로 넘기는지 가짜 glab 으로 확인한다."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GLAB_AS = Path(__file__).resolve().parents[1] / "scripts" / "glab-as.sh"
SECRET = "glpat-FAKE-SECRET-VALUE-123"

FAKE_GLAB = """#!/bin/sh
echo "args: $*" > "$FAKE_LOG"
echo "host: $GITLAB_HOST" >> "$FAKE_LOG"
if [ "$GITLAB_TOKEN" = "$EXPECT_TOKEN" ]; then echo "token-ok" >> "$FAKE_LOG"; fi
echo '{"username": "fake"}'
"""


class GlabAsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name, "home")
        (self.home / "workspace").mkdir(parents=True)
        self.bin = Path(self._tmp.name, "bin")
        self.bin.mkdir()
        glab = self.bin / "glab"
        glab.write_text(FAKE_GLAB)
        glab.chmod(0o755)
        self.log = Path(self._tmp.name, "log")

    def write_toml(self, text):
        (self.home / "workspace" / ".env.toml").write_text(text)

    def run_script(self, *args, host=None):
        env = {**os.environ, "HOME": str(self.home), "PATH": f"{self.bin}:{os.environ['PATH']}",
               "FAKE_LOG": str(self.log), "EXPECT_TOKEN": SECRET}
        env.pop("GITLAB_HOST", None)
        if host:
            env["GITLAB_HOST"] = host
        return subprocess.run(["sh", str(GLAB_AS), *args], env=env, capture_output=True, text=True)

    def test_passes_args_and_token_to_glab_without_printing_token(self):
        self.write_toml(f'[gitlab_claude_ai]\ntoken = "{SECRET}"\n')
        r = self.run_script("claude", "api", "user")
        self.assertEqual(r.returncode, 0, r.stderr)
        log = self.log.read_text()
        self.assertIn("args: api user", log)
        self.assertIn("token-ok", log)
        self.assertIn("host: \n", log)
        self.assertNotIn(SECRET, r.stdout)
        self.assertNotIn(SECRET, r.stderr)
        self.assertNotIn(SECRET, log)

    def test_passes_gitlab_host_through_when_set(self):
        self.write_toml(f'[gitlab_claude_ai]\ntoken = "{SECRET}"\n')
        r = self.run_script("claude", "api", "user", host="gitlab.example.com")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("host: gitlab.example.com", self.log.read_text())

    def test_picks_section_of_requested_agent(self):
        self.write_toml(f'[gitlab_claude_ai]\ntoken = "other"\n[gitlab_codex_ai]\ntoken = "{SECRET}"\n')
        r = self.run_script("codex", "api", "user")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("token-ok", self.log.read_text())

    def test_unknown_agent_prints_usage_and_exit_2(self):
        r = self.run_script("bob", "api", "user")
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage", r.stderr)
        self.assertFalse(self.log.exists())

    def test_missing_env_file_fails_without_running_glab(self):
        r = self.run_script("claude", "api", "user")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_missing_agent_section_fails_without_running_glab_or_leaking(self):
        self.write_toml(f'[gitlab_codex_ai]\ntoken = "{SECRET}"\n')
        r = self.run_script("claude", "api", "user")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.log.exists())
        self.assertNotIn(SECRET, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
