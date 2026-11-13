"""지원 매트릭스 검사기의 만료 처리(#107).

PR 검사(--no-expiry)는 만료를 경고로만 내고, 주간 워크플로(플래그 없음)는 만료에 실패한다.
--warn-days 는 만료가 다가오면 실패 없이 경고한다. 날짜는 실제 manifest 에서 계산한다 —
manifest 의 last_measured 가 갱신돼도 시험이 낡지 않는다.
"""

import json
import os
import subprocess
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "dev" / "check-harness-matrix.py"
MANIFEST = json.loads(
    (ROOT / "docs" / "harness-matrix.json").read_text(encoding="utf-8")
)
MAX_AGE = MANIFEST["policy"]["full_max_age_days"]
FULL = [h for h in MANIFEST["harnesses"] if h["tier"] == "full"]


def run(*args, github=False):
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
    if github:
        env["GITHUB_ACTIONS"] = "true"
    return subprocess.run(
        [sys.executable, str(CHECK), *args], capture_output=True, text=True, env=env
    )


@unittest.skipUnless(FULL, "tier=full 하네스가 없으면 만료 검사 대상이 없다")
class ExpiryTests(unittest.TestCase):
    def setUp(self):
        # 가장 오래된 full 실측이 만료 시점을 정한다.
        oldest = min(date.fromisoformat(h["last_measured"]) for h in FULL)
        self.newest = max(
            date.fromisoformat(h["last_measured"]) for h in MANIFEST["harnesses"]
        )
        self.expires = oldest + timedelta(days=MAX_AGE)

    def day(self, offset):
        return (self.expires + timedelta(days=offset)).isoformat()

    def test_fresh_manifest_passes_without_warnings(self):
        proc = run("--today", self.newest.isoformat(), "--warn-days", "14")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("WARN", proc.stderr)

    def test_expired_full_tier_fails_by_default(self):
        proc = run("--today", self.day(1))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("FAIL:", proc.stderr)
        self.assertIn("tier=full", proc.stderr)

    def test_last_valid_day_still_passes(self):
        proc = run("--today", self.day(0))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_no_expiry_downgrades_expiry_to_a_warning(self):
        proc = run("--today", self.day(30), "--no-expiry")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("WARN:", proc.stderr)
        self.assertNotIn("FAIL:", proc.stderr)

    def test_warn_days_warns_inside_the_window_only(self):
        inside = run("--today", self.day(-14), "--warn-days", "14")
        self.assertEqual(inside.returncode, 0, inside.stdout + inside.stderr)
        self.assertIn("WARN:", inside.stderr)
        self.assertIn("14", inside.stderr)

        outside = run("--today", self.day(-15), "--warn-days", "14")
        self.assertEqual(outside.returncode, 0, outside.stdout + outside.stderr)
        self.assertNotIn("WARN", outside.stderr)

    def test_warnings_become_annotations_on_github_actions(self):
        proc = run("--today", self.day(-3), "--warn-days", "14", github=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("::warning title=harness-matrix::", proc.stdout)

    def test_no_expiry_still_fails_on_consistency_errors(self):
        # 미래 날짜 실측은 만료가 아니라 정합성 오류다 — --no-expiry 로 가려지지 않는다.
        before = (self.newest - timedelta(days=1)).isoformat()
        proc = run("--today", before, "--no-expiry")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("미래", proc.stderr)


if __name__ == "__main__":
    unittest.main()
