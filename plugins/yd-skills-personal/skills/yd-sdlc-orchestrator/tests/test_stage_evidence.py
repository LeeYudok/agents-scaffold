"""check_stage_evidence.py 가 SKILL.md 의 게이트 단언을 판정하는지 본다 (stdlib only, 이슈 #201)."""

import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_stage_evidence",
                                              SKILL / "scripts" / "check_stage_evidence.py")
m = importlib.util.module_from_spec(spec)
sys.modules["check_stage_evidence"] = m
spec.loader.exec_module(m)

SHA = "a" * 64


def entry(stage, status="pass", exit_code=0, cmds=None):
    cmds = cmds or m.REQUIRED_COMMANDS[stage]
    return {"stage": stage, "status": status, "artifact": f"out/{stage}", "sha256": SHA,
            "checks": [{"command": c, "exit_code": exit_code} for c in cmds]}


def good():
    return {"stages": [entry(s) for s in m.STAGES]}


def run(argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = m.main(argv)
    finally:
        sys.stdin = old
    return code, out.getvalue(), err.getvalue()


class StageEvidence(unittest.TestCase):
    def test_complete_record_passes(self):
        self.assertEqual(m.check(good()), [])

    def test_earlier_failure_blocks_later_pass(self):
        d = good()
        d["stages"][1] = entry("implementation", "fail", 1)
        errs = m.check(d)
        self.assertTrue(any("앞 단계 implementation" in e for e in errs), errs)

    def test_failed_gate_recovered_by_retry_passes(self):
        d = good()
        d["stages"][2:2] = [entry("security", "fail", 1), entry("implementation")]
        # planning, implementation, security(fail), implementation, security(pass), local-run
        d["stages"] = [d["stages"][0], d["stages"][1], d["stages"][2], d["stages"][3],
                       entry("security"), entry("local-run")]
        self.assertEqual(m.check(d), [])

    def test_skipped_stage_counts_as_failure(self):
        d = good()
        d["stages"][2]["status"] = "skipped"
        errs = m.check(d)
        self.assertTrue(any("건너뛴" in e for e in errs), errs)

    def test_todo_marker_is_failure(self):
        d = good()
        d["stages"][2]["checks"][0]["command"] = "run_gate.py (추가 예정)"
        self.assertTrue(any("추가 예정" in e for e in m.check(d)))

    def test_missing_stage_is_failure(self):
        d = good()
        del d["stages"][2]
        self.assertTrue(any("security 의 기록이 없다" in e for e in m.check(d)))

    def test_wrong_order_is_failure(self):
        d = good()
        d["stages"][1], d["stages"][2] = d["stages"][2], d["stages"][1]
        self.assertTrue(any("순서" in e for e in m.check(d)))

    def test_pass_with_nonzero_exit_is_failure(self):
        d = good()
        d["stages"][0]["checks"][1]["exit_code"] = 1
        self.assertTrue(any("exit_code 가 0 이 아닌" in e for e in m.check(d)))

    def test_wrapper_bypass_is_failure(self):
        """래퍼 없이 finguard scan 만 돌린 기록은 통과로 읽지 않는다."""
        d = good()
        d["stages"][2]["checks"] = [{"command": "finguard scan --format rdjsonl .", "exit_code": 0}]
        self.assertTrue(any("run_gate.py" in e for e in m.check(d)))

    def test_planning_needs_all_three_validators(self):
        d = good()
        d["stages"][0]["checks"] = d["stages"][0]["checks"][:1]
        errs = m.check(d)
        self.assertTrue(any("check_badge_alignment.py" in e for e in errs), errs)

    def test_missing_hash_or_command_is_failure(self):
        d = good()
        d["stages"][0]["sha256"] = "xyz"
        d["stages"][1]["checks"] = []
        errs = m.check(d)
        self.assertTrue(any("sha256" in e for e in errs) and any("checks" in e for e in errs), errs)

    def test_security_retries_capped_at_three(self):
        d = good()
        fails = [entry("security", "fail", 1) for _ in range(4)]
        d["stages"][2:2] = fails
        self.assertTrue(any("최대 3회" in e for e in m.check(d)))

    def test_unknown_stage_name_reported(self):
        d = good()
        d["stages"].append({"stage": "deploy"})
        self.assertTrue(any("알 수 없는 단계" in e for e in m.check(d)))

    def test_unreadable_input_is_tool_error(self):
        code, _, err = run(["-"], stdin="{not json")
        self.assertEqual(code, 2)
        self.assertIn("읽지 못했다", err)
        self.assertEqual(run([str(SKILL / "no-such.json")])[0], 2)

    def test_cli_exit_codes(self):
        self.assertEqual(run(["-"], stdin=json.dumps(good()))[0], 0)
        bad = good()
        bad["stages"][3]["status"] = "fail"
        code, out, _ = run(["-"], stdin=json.dumps(bad))
        self.assertEqual(code, 1)
        self.assertIn("위반", out)

    def test_verify_files_detects_changed_artifact(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "out").mkdir()
            d = good()
            for e in d["stages"]:
                p = root / e["artifact"]
                p.write_text("v1")
                e["sha256"] = m.hash_path(p)
            self.assertEqual(m.verify_files(d, root), [])
            (root / "out/security").write_text("v2")
            errs = m.verify_files(d, root)
            self.assertEqual(len(errs), 1)
            self.assertIn("sha256 과 다르다", errs[0])
            (root / "out/planning").unlink()
            self.assertTrue(any("가 없다" in e for e in m.verify_files(d, root)))

    def test_directory_hash_covers_contents_and_names(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "a.txt").write_text("x")
            h1 = m.hash_path(d)
            (d / "a.txt").write_text("y")
            h2 = m.hash_path(d)
            (d / "a.txt").rename(d / "b.txt")
            self.assertEqual(len({h1, h2, m.hash_path(d)}), 3)

    def test_hash_subcommand_matches_sha256(self):
        import hashlib
        with tempfile.NamedTemporaryFile() as f:
            f.write(b"abc")
            f.flush()
            code, out, _ = run(["hash", f.name])
        self.assertEqual((code, out.strip()), (0, hashlib.sha256(b"abc").hexdigest()))
        self.assertEqual(run(["hash", "/no/such/path"])[0], 2)


if __name__ == "__main__":
    unittest.main()
