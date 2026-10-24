"""tomllib 없는 Python(3.9 등)에서도 glab-as.sh 가 요청한 계정 토큰만 읽는지 검사한다 (#203).

토큰 전달·미노출의 기본 동작은 test_glab_as.py 가 맡는다.

가짜 glab 은 토큰 값 대신 길이만 출력한다. tomllib 이 없는 Python(3.9 등)은
YD_TOML_FALLBACK=1 로 같은 경로를 강제해 흉내 낸다.
"""
import os
import subprocess
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "glab-as.sh")
TOKEN = "dummy-token-for-tests-only"
TOML = """# agent accounts
[other]
token = "not-this-one"

[gitlab_claude_ai]
username = "claude-ai"
token = "%s"   # trailing comment

[gitlab_codex_ai]
token = 'codex-literal-token'
""" % TOKEN


class GlabAsFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        bindir = os.path.join(self.tmp.name, "bin")
        os.mkdir(bindir)
        fake = os.path.join(bindir, "glab")
        with open(fake, "w") as f:
            f.write('#!/bin/sh\necho "len=${#GITLAB_TOKEN} host=$GITLAB_HOST args=$*"\n')
        os.chmod(fake, 0o755)
        self.toml = os.path.join(self.tmp.name, "env.toml")
        with open(self.toml, "w") as f:
            f.write(TOML)
        self.env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], YD_ENV_TOML=self.toml)
        self.env.pop("GITLAB_HOST", None)

    def run_as(self, agent, extra_env=None):
        env = dict(self.env, **(extra_env or {}))
        return subprocess.run(["sh", SCRIPT, agent, "api", "user"], capture_output=True, text=True, env=env)

    def assert_passed(self, out, length):
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "len=%d host= args=api user" % length)
        self.assertNotIn(TOKEN, out.stdout + out.stderr)

    def test_tomllib_path(self):
        self.assert_passed(self.run_as("claude"), len(TOKEN))

    def test_fallback_reader_matches(self):
        self.assert_passed(self.run_as("claude", {"YD_TOML_FALLBACK": "1"}), len(TOKEN))
        self.assert_passed(self.run_as("codex", {"YD_TOML_FALLBACK": "1"}), len("codex-literal-token"))

    def test_header_comment_does_not_leak_other_section(self):
        # claude 섹션에 token 이 없고, 다음 헤더에 주석이 붙어 있다 — claude 는 실패해야 한다
        with open(self.toml, "w") as f:
            f.write('[gitlab_claude_ai]\nusername = "claude-ai"\n'
                    '[gitlab_codex_ai] # codex account\ntoken = "%s"\n[[servers]]\ntoken = "array-token"\n' % TOKEN)
        for extra in ({}, {"YD_TOML_FALLBACK": "1"}):
            out = self.run_as("claude", extra)
            self.assertNotEqual(out.returncode, 0, extra)
            self.assertNotIn(TOKEN, out.stdout + out.stderr)
            self.assert_passed(self.run_as("codex", extra), len(TOKEN))

    def test_missing_section_fails_without_leaking(self):
        for extra in ({}, {"YD_TOML_FALLBACK": "1"}):
            out = self.run_as("agy", extra)
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("gitlab_agy_ai", out.stderr)
            self.assertNotIn(TOKEN, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
