"""SKILL.md 단언을 실제 typescript·bun 으로 재현한다 (stdlib only).

판정은 scripts/verify_typescript_claims.py 의 EXPECT 한 곳에 있다. npm install 이 필요하므로
YD_TS_VERIFY=1 일 때만 돈다. 없으면 사유와 함께 건너뛰고, CI 는
.github/workflows/ts-claims.yml 에서 환경변수를 켜고 건너뜀을 실패로 친다.
"""

import importlib.util
import os
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_typescript_claims", SKILL / "scripts" / "verify_typescript_claims.py")
v = importlib.util.module_from_spec(spec)
sys.modules["verify_typescript_claims"] = v
spec.loader.exec_module(v)


class TypeScriptClaims(unittest.TestCase):
    def check(self, claim):
        if os.environ.get("YD_TS_VERIFY") != "1":
            self.skipTest("YD_TS_VERIFY=1 이 아니다 (npm install 이 필요한 재현이라 opt-in)")
        why = v.unavailable()
        if why:
            self.skipTest(why)
        obs, ok = v.run(claim)
        self.assertTrue(ok, f"{claim} 가 {v.versions()} 에서 문서와 다르다: {obs}")

    def test_bun_run_and_build_skip_type_check(self):
        self.check("BUN-NO-TYPECHECK")

    def test_tsc_reports_the_error_bun_ignored(self):
        self.check("TSC-CATCHES")

    def test_tsc_rejects_files_next_to_tsconfig(self):
        self.check("TSC-PROJECT-CONFIG")

    def test_bun_build_target_defaults_to_browser(self):
        self.check("BUN-BUILD-TARGET")

    def test_bun_api_builds_for_browser_but_fails_without_bun(self):
        self.check("BUN-API-IN-BROWSER")

    def test_cast_compiles_but_value_is_wrong(self):
        self.check("CAST-NOT-VALIDATION")

    def test_non_null_assertion_compiles_but_throws(self):
        self.check("NONNULL-NOT-VALIDATION")

    def test_exact_optional_property_types_flags_explicit_undefined(self):
        self.check("EXACT-OPTIONAL")

    def test_no_unchecked_indexed_access_flags_unsafe_index(self):
        self.check("UNCHECKED-INDEX")

    def test_late_response_overwrites_without_guard(self):
        self.check("ASYNC-RACE")

    def test_generation_guard_keeps_latest(self):
        self.check("ASYNC-GUARD")

    def test_abort_controller_cancels_pending_fetch(self):
        self.check("ABORT-CONTROLLER")

    def test_ok_status_with_empty_body_fails_to_parse(self):
        self.check("EMPTY-BODY-200")


if __name__ == "__main__":
    unittest.main()
