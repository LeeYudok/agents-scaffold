"""scan_secrets.py 가 값을 노출하지 않고 SKILL.md 의 커밋 전 절차를 지키는지 본다 (stdlib only, 이슈 #201).

agents-mem 레포는 쓰지 않는다 — 임시 git 레포에서 스테이징한다.
"""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scan_secrets", SKILL / "scripts" / "scan_secrets.py")
m = importlib.util.module_from_spec(spec)
sys.modules["scan_secrets"] = m
spec.loader.exec_module(m)

# 값 부분은 조각으로 이어 붙여 이 파일 자체가 스캔에 걸리지 않게 한다.
FAKE_PAT = "glpat-" + "ABCDEF0123456789xyz"
FAKE_PW = "hunter" + "2-very-secret"


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = m.main(argv)
    return code, out.getvalue(), err.getvalue()


class Repo:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")

    def git(self, *a):
        subprocess.run(["git", "-C", self.dir, *a], check=True, capture_output=True)

    def stage(self, rel, text):
        p = Path(self.dir, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        self.git("add", "--", rel)

    def commit(self):
        self.git("commit", "-q", "-m", "x")


class ScanSecrets(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.tmp.cleanup)

    def scan(self, *extra):
        return run(["--staged", "--repo", self.repo.dir, "--host", "mine", *extra])

    def test_value_never_printed(self):
        self.repo.stage("shared/a.md", f"ok\npassword: {FAKE_PW}\ntoken = {FAKE_PAT}\n")
        code, out, err = self.scan()
        self.assertEqual(code, 1)
        for secret in (FAKE_PW, FAKE_PAT, "hunter", "ABCDEF"):
            self.assertNotIn(secret, out + err)
        self.assertIn("shared/a.md:2 [password]", out)
        self.assertIn("shared/a.md:3 [glpat]", out)
        self.assertIn("걸린 줄 3건, 파일 1개", out)  # glpat 줄은 token 패턴에도 걸린다

    def test_clean_change_exits_zero(self):
        self.repo.stage("hosts/mine/m.md", "그냥 메모\n")
        self.assertEqual(self.scan()[0], 0)

    def test_placeholders_and_variable_refs_are_not_hits(self):
        self.repo.stage("shared/b.md", "password: <redacted>\ntoken=$GITLAB_TOKEN\nsecret: $(cat f)\n")
        self.assertEqual(self.scan()[0], 0)

    def test_only_added_lines_count(self):
        self.repo.stage("shared/old.md", f"token: {FAKE_PW}\n")
        self.repo.commit()
        Path(self.repo.dir, "shared/old.md").write_text(f"token: {FAKE_PW}\n새 줄\n")
        self.repo.git("add", "--", "shared/old.md")
        self.assertEqual(self.scan()[0], 0)

    def test_line_numbers_follow_hunks(self):
        self.repo.stage("shared/n.md", "a\nb\nc\n")
        self.repo.commit()
        self.repo.stage("shared/n.md", "a\nb\nc\nd\n" + f"secret: {FAKE_PW}\n")
        code, out, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertIn("shared/n.md:5 [secret]", out)

    def test_credential_file_blocked_by_name_only(self):
        self.repo.stage("hosts/mine/codex/auth.json", '{"k": "v"}\n')
        self.repo.stage("hosts/mine/gemini/oauth_creds.json", "{}\n")
        code, out, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertEqual(out.count("자격증명 파일"), 2)

    def test_other_host_and_legacy_dirs_blocked(self):
        self.repo.stage("hosts/other/x.md", "메모\n")
        self.repo.stage("hosts/_legacy-shared/y.md", "메모\n")
        self.repo.stage("hosts/mine/z.md", "메모\n")
        code, out, _ = self.scan()
        self.assertEqual(code, 1)
        self.assertIn("hosts/other/x.md", out)
        self.assertIn("hosts/_legacy-shared/y.md", out)
        self.assertNotIn("hosts/mine/z.md", out)

    def test_host_resolution_order(self):
        self.assertEqual(m.resolve_host("explicit"), "explicit")
        old = os.environ.get("AGENTS_MEM_HOST")
        os.environ["AGENTS_MEM_HOST"] = "from-env"
        try:
            self.assertEqual(m.resolve_host(None), "from-env")
        finally:
            if old is None:
                del os.environ["AGENTS_MEM_HOST"]
            else:
                os.environ["AGENTS_MEM_HOST"] = old

    def test_host_name_is_lowercased_like_sync(self):
        # sync_memory.sh 의 detect_host 는 호스트명을 소문자로 써서 미러 폴더가 소문자다 (이슈 #208)
        self.assertEqual(m.resolve_host("MyMac-Pro"), "mymac-pro")
        with mock.patch.dict(os.environ, {"AGENTS_MEM_HOST": "MyMac-Pro"}):
            self.assertEqual(m.resolve_host(None), "mymac-pro")

    def test_uppercase_host_matches_lowercase_mirror_dir(self):
        self.repo.stage("hosts/mymac-pro/m.md", "메모\n")
        self.assertEqual(run(["--staged", "--repo", self.repo.dir, "--host", "MyMac-Pro"])[0], 0)
        self.repo.stage("hosts/other/x.md", "메모\n")
        code, out, _ = run(["--staged", "--repo", self.repo.dir, "--host", "MyMac-Pro"])
        self.assertEqual(code, 1)
        self.assertIn("hosts/other/x.md", out)
        self.assertNotIn("hosts/mymac-pro/m.md", out)

    def test_not_a_repo_is_tool_error(self):
        with tempfile.TemporaryDirectory() as t:
            code, out, err = run(["--staged", "--repo", t, "--host", "h"])
        self.assertEqual(code, 2)
        self.assertIn("스캔하지 못했다", err)
        self.assertNotIn("걸린 줄", out)

    def test_tree_mode_reports_position_only(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t, "sub").mkdir()
            Path(t, "sub/c.md").write_text(f"x\nghp_{'a' * 20}\n")
            Path(t, "bin.dat").write_bytes(b"\xff\xfe\x00glpat-")
            code, out, err = run(["--tree", t])
        self.assertEqual(code, 1)
        self.assertIn("sub/c.md:2 [ghp]", out)
        self.assertNotIn("a" * 20, out + err)
        self.assertNotIn("bin.dat", out)  # 읽을 수 없는 바이너리는 건너뛴다

    def test_tree_missing_dir_is_tool_error(self):
        self.assertEqual(run(["--tree", "/no/such/dir"])[0], 2)


if __name__ == "__main__":
    unittest.main()
