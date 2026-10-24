"""sync_auth.py 의 원본 추출·호스트 목록·원격 병합·출력 위생 (stdlib only)."""
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sync_auth  # noqa: E402

ACCESS = "sk-ant-oat01-ACCESSfakeACCESSfake"
REFRESH = "sk-ant-ort01-REFRESHfakeREFRESHfake"


def blob(**extra):
    oauth = {"accessToken": ACCESS, "refreshToken": REFRESH, "expiresAt": 1792000000000, "subscriptionType": "max"}
    oauth.update(extra)
    return json.dumps({"claudeAiOauth": oauth, "mcpOAuth": {"srv": {"accessToken": "mcp-secret"}}})


def run_merge(home: Path, payload: str, ts: str) -> str:
    """원격 병합 스크립트를 임시 HOME 에서 그대로 돌린다."""
    env = dict(os.environ, HOME=str(home))
    proc = subprocess.run(
        ["bash", "-c", sync_auth.merge_command(ts)], input=payload.encode(), env=env, capture_output=True, check=True,
    )
    return proc.stdout.decode().strip()


class ExtractTest(unittest.TestCase):
    def test_moves_only_claude_oauth(self):
        payload, summary = sync_auth.extract_payload(blob())
        data = json.loads(payload)
        self.assertEqual(list(data), ["claudeAiOauth"])
        self.assertNotIn("mcp-secret", payload)
        self.assertEqual(summary["subscription"], "max")

    def test_summary_has_no_token(self):
        _, summary = sync_auth.extract_payload(blob())
        self.assertNotIn("sk-ant", json.dumps(summary))

    def test_missing_refresh_token_is_refused(self):
        with self.assertRaises(SystemExit):
            sync_auth.extract_payload(json.dumps({"claudeAiOauth": {"accessToken": ACCESS}}))

    def test_non_json_is_refused(self):
        with self.assertRaises(SystemExit):
            sync_auth.extract_payload("not json")


class HostsTest(unittest.TestCase):
    def test_parse_skips_comments_blanks_and_dupes(self):
        self.assertEqual(sync_auth.parse_hosts("a\n# c\n\nb  # note\na\n"), ["a", "b"])

    def test_missing_hosts_file_explains_where(self):
        with self.assertRaises(SystemExit) as ctx:
            sync_auth.load_hosts(Path("/no/such/yd-claude-auth-sync/hosts"))
        self.assertIn("/no/such/yd-claude-auth-sync/hosts", str(ctx.exception))

    def test_env_overrides_default_path(self):
        old = os.environ.get(sync_auth.HOSTS_ENV)
        os.environ[sync_auth.HOSTS_ENV] = "/tmp/x-hosts"
        try:
            self.assertEqual(sync_auth.hosts_file(), Path("/tmp/x-hosts"))
        finally:
            if old is None:
                del os.environ[sync_auth.HOSTS_ENV]
            else:
                os.environ[sync_auth.HOSTS_ENV] = old


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.cred = self.home / ".claude" / ".credentials.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_host_gets_file_with_mode_600(self):
        payload, _ = sync_auth.extract_payload(blob())
        self.assertEqual(run_merge(self.home, payload, "1"), "updated")
        self.assertEqual(stat.S_IMODE(self.cred.stat().st_mode), 0o600)
        self.assertEqual(json.loads(self.cred.read_text())["claudeAiOauth"]["refreshToken"], REFRESH)

    def test_keeps_other_keys_and_backs_up(self):
        self.cred.parent.mkdir(parents=True)
        self.cred.write_text(json.dumps({"claudeAiOauth": {"refreshToken": "old"}, "mcpOAuth": {"keep": 1}}))
        payload, _ = sync_auth.extract_payload(blob())
        self.assertEqual(run_merge(self.home, payload, "2"), "updated")
        data = json.loads(self.cred.read_text())
        self.assertEqual(data["mcpOAuth"], {"keep": 1})
        backup = self.cred.with_name(".credentials.json.bak-2")
        self.assertEqual(json.loads(backup.read_text())["claudeAiOauth"]["refreshToken"], "old")

    def test_same_value_writes_nothing(self):
        payload, _ = sync_auth.extract_payload(blob())
        run_merge(self.home, payload, "3")
        self.assertEqual(run_merge(self.home, payload, "4"), "same")
        self.assertFalse(self.cred.with_name(".credentials.json.bak-4").exists())

    def test_merge_command_carries_no_token(self):
        self.assertNotIn("sk-ant", sync_auth.merge_command("5"))


class MainTest(unittest.TestCase):
    def run_main(self, argv, runner):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = sync_auth.main(argv, run=runner, blob=blob())
        return code, out.getvalue()

    def test_output_never_shows_token(self):
        calls = []

        def runner(host, script, stdin):
            calls.append((host, script, stdin))
            # 원격이 실수로 토큰을 흘려도 화면에는 가려져야 한다
            return 1, f"boom {ACCESS}"

        code, out = self.run_main(["--host", "h1"], runner)
        self.assertEqual(code, 1)
        self.assertNotIn(ACCESS, out)
        self.assertNotIn(REFRESH, out)
        self.assertIn(REFRESH.encode(), calls[0][2])  # 토큰은 stdin 으로만 간다
        self.assertNotIn("sk-ant", calls[0][1])

    def test_verify_reports_ok_on_pong(self):
        def runner(host, script, stdin):
            return 0, "updated" if stdin else "pong"

        code, out = self.run_main(["--host", "h1", "--verify"], runner)
        self.assertEqual(code, 0)
        self.assertIn("h1: updated", out)
        self.assertIn("verify ok", out)

    def test_verify_fails_without_pong(self):
        def runner(host, script, stdin):
            return 0, "same" if stdin else "Invalid API key"

        code, out = self.run_main(["--host", "h1", "--verify"], runner)
        self.assertEqual(code, 1)
        self.assertIn("verify failed", out)

    def test_missing_claude_is_reported(self):
        def runner(host, script, stdin):
            return 0, "claude-missing"

        code, out = self.run_main(["--host", "h1", "--verify-only"], runner)
        self.assertEqual(code, 1)
        self.assertIn("claude 없음", out)

    def test_dry_run_touches_no_host(self):
        def runner(host, script, stdin):
            raise AssertionError("dry-run 은 호스트에 접속하지 않는다")

        code, out = self.run_main(["--host", "h1", "--host", "h2", "--dry-run"], runner)
        self.assertEqual(code, 0)
        self.assertIn("h2: 대상", out)


if __name__ == "__main__":
    unittest.main()
