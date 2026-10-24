"""hosts.py 의 명령 조립과 실패 보고 (stdlib only)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import hosts  # noqa: E402


class HostsTest(unittest.TestCase):
    def test_remote_command_goes_through_ssh(self):
        argv = hosts.shell_cmd("pig", "workspace/a b", "git status")
        self.assertEqual(argv[0], "ssh")
        self.assertIn("pig", argv)
        self.assertIn("cd ~/'workspace/a b' && git status", argv[-1])

    def test_local_command_runs_in_bash(self):
        self.assertEqual(hosts.shell_cmd("local", "r", "true")[:2], ["bash", "-c"])

    def test_failed_command_raises_with_host_name(self):
        with self.assertRaises(RuntimeError) as ctx:
            hosts.run("local", "no-such-dir-yd-git-sync-test", "true")
        self.assertIn("local", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
