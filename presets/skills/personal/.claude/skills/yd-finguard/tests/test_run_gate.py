import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_gate.py"
SPEC = importlib.util.spec_from_file_location("run_gate", SCRIPT)
run_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_gate)


def finding(severity="ERROR"):
    return json.dumps({
        "severity": severity,
        "location": {"path": "src/app.ts", "range": {"start": {"line": 7}}},
        "message": "[FG-001] 테스트 탐지\n상세",
    })


class TestRunGate(unittest.TestCase):
    def run_main(self, stdout="", returncode=0, block_on="ERROR"):
        with tempfile.TemporaryDirectory() as directory:
            completed = run_gate.subprocess.CompletedProcess([], returncode, stdout, "")
            output = io.StringIO()
            errors = io.StringIO()
            with patch.object(run_gate.subprocess, "run", return_value=completed):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    code = run_gate.main(["--dir", directory, "--block-on", block_on])
        return code, output.getvalue(), errors.getvalue()

    def test_blocks_configured_severity(self):
        code, output, _ = self.run_main(finding("ERROR"))
        self.assertEqual(code, 1)
        self.assertIn("src/app.ts:7 [ERROR]", output)
        self.assertIn("차단 대상 1건", output)

    def test_non_blocking_finding_passes(self):
        code, output, _ = self.run_main(finding("WARNING"))
        self.assertEqual(code, 0)
        self.assertIn("매핑된 finding 1건", output)

    def test_invalid_rdjsonl_is_tool_error(self):
        code, _, errors = self.run_main("not-json")
        self.assertEqual(code, 2)
        self.assertIn("파싱 실패", errors)

    def test_finguard_failure_is_tool_error(self):
        code, _, errors = self.run_main(returncode=3)
        self.assertEqual(code, 2)
        self.assertIn("exit 3", errors)


if __name__ == "__main__":
    unittest.main()
