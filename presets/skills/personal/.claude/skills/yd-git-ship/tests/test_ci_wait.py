"""ci_wait.py 의 종료 코드(0 성공·파이프라인 없음 / 1 실패 / 2 시간 초과)를 가짜 glab 으로 확인한다."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_wait.py"

# FAKE_DIR/seq.json 의 응답을 호출 순서대로 내놓고 마지막 응답을 반복한다. 인자는 FAKE_DIR/calls 에 남긴다.
FAKE_GLAB = """#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAKE_DIR"]
with open(os.path.join(d, "calls"), "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
    f.write("token=" + ("yes" if os.environ.get("GITLAB_TOKEN") else "no") + "\\n")
if os.environ.get("FAKE_FAIL"):
    sys.stderr.write("glab: 401 Unauthorized\\n")
    sys.exit(1)
seq = json.load(open(os.path.join(d, "seq.json")))
n_path = os.path.join(d, "n")
n = int(open(n_path).read()) if os.path.exists(n_path) else 0
open(n_path, "w").write(str(n + 1))
print(json.dumps(seq[min(n, len(seq) - 1)]))
"""


def pipe(status, pid=7):
    return [{"id": pid, "status": status, "web_url": f"https://gitlab.example.com/x/-/pipelines/{pid}"}]


class CiWaitTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        glab = self.bin / "glab"
        glab.write_text(FAKE_GLAB)
        glab.chmod(0o755)

    def run_wait(self, seq, *extra, fail=False, home=None, host="gitlab.example.com"):
        (self.dir / "seq.json").write_text(json.dumps(seq))
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "FAKE_DIR": str(self.dir)}
        env.pop("GITLAB_HOST", None)
        if host:
            env["GITLAB_HOST"] = host
        if fail:
            env["FAKE_FAIL"] = "1"
        if home:
            env["HOME"] = home
        return subprocess.run([sys.executable, str(SCRIPT), *extra, "group/repo", "abcdef1234567890",
                               "--interval", "0"], env=env, capture_output=True, text=True, timeout=60)

    def calls(self):
        return (self.dir / "calls").read_text()

    def test_success_exits_0_and_prints_url(self):
        r = self.run_wait([pipe("success")])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pipeline 7 success", r.stdout)
        self.assertIn("https://gitlab.example.com/x/-/pipelines/7", r.stdout)

    def test_skipped_counts_as_success(self):
        self.assertEqual(self.run_wait([pipe("skipped")]).returncode, 0)

    def test_waits_through_running_until_success(self):
        r = self.run_wait([pipe("pending"), pipe("running"), pipe("success")])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(int((self.dir / "n").read_text()), 3)

    def test_failed_exits_1(self):
        r = self.run_wait([pipe("running"), pipe("failed")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("failed", r.stdout)

    def test_canceled_exits_1(self):
        self.assertEqual(self.run_wait([pipe("canceled")]).returncode, 1)

    def test_no_pipeline_after_four_empty_polls_exits_0(self):
        r = self.run_wait([[]])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no pipeline for abcdef12", r.stdout)
        self.assertEqual(int((self.dir / "n").read_text()), 4)

    def test_pipeline_appearing_late_is_still_tracked(self):
        r = self.run_wait([[], [], pipe("success")])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pipeline 7 success", r.stdout)

    def test_timeout_exits_2(self):
        (self.dir / "seq.json").write_text(json.dumps([pipe("running")]))
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "FAKE_DIR": str(self.dir)}
        r = subprocess.run([sys.executable, str(SCRIPT), "group/repo", "abcdef1234567890",
                            "--timeout", "1", "--interval", "1"], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertIn("timeout waiting for abcdef12", r.stdout)

    def test_queries_pipelines_of_sha_on_gitlab_host_with_encoded_repo(self):
        self.run_wait([pipe("success")])
        c = self.calls()
        self.assertIn("--hostname gitlab.example.com", c)
        self.assertIn("projects/group%2Frepo/pipelines?sha=abcdef1234567890", c)

    def test_without_gitlab_host_leaves_host_to_glab(self):
        self.run_wait([pipe("success")], host=None)
        self.assertNotIn("--hostname", self.calls())

    def test_agent_option_routes_through_glab_as_with_token(self):
        home = self.dir / "home"
        (home / "workspace").mkdir(parents=True)
        (home / "workspace" / ".env.toml").write_text('[gitlab_claude_ai]\ntoken = "glpat-FAKE"\n')
        r = self.run_wait([pipe("success")], "--agent", "claude", home=str(home))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("token=yes", self.calls())
        self.assertNotIn("glpat-FAKE", r.stdout + r.stderr)

    def test_agent_without_token_file_is_tool_error_not_success(self):
        home = self.dir / "emptyhome"
        home.mkdir()
        r = self.run_wait([pipe("success")], "--agent", "claude", home=str(home))
        self.assertEqual(r.returncode, 3)
        self.assertNotIn("pipeline 7 success", r.stdout)
        self.assertFalse((self.dir / "calls").exists())

    def test_glab_auth_failure_never_reports_success_or_no_pipeline(self):
        r = self.run_wait([pipe("success")], fail=True)
        self.assertEqual(r.returncode, 3)
        self.assertIn("401 Unauthorized", r.stderr)
        self.assertNotIn("success", r.stdout)
        self.assertNotIn("no pipeline", r.stdout)


if __name__ == "__main__":
    unittest.main()
