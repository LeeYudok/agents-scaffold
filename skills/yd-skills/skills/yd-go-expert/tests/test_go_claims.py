"""SKILL.md 단언을 실제 Go 툴체인으로 재현한다 (stdlib only, 이슈 #201).

판정은 scripts/verify_go_claims.py 의 EXPECT 한 곳에 있다. 단언마다 테스트 하나를 두어
tests/claims.json 이 가리킬 수 있게 하고, 실패하면 관찰값을 보여준다. Go 가 없거나 버전이
모자라면 사유와 함께 건너뛴다 — CI 는 .github/workflows/go-claims.yml 이 건너뜀을 실패로 친다.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_go_claims", SKILL / "scripts" / "verify_go_claims.py")
v = importlib.util.module_from_spec(spec)
sys.modules["verify_go_claims"] = v
spec.loader.exec_module(v)


class GoClaims(unittest.TestCase):
    def check(self, claim):
        why = v.skip_reason(claim)
        if why:
            self.skipTest(why)
        obs, ok = v.run(claim)
        self.assertTrue(ok, f"{claim} 가 이 Go 에서 문서와 다르다: {obs}")

    def test_typed_nil_makes_error_non_nil(self):
        self.check("TYPED-NIL")

    def test_percent_w_keeps_is_and_as(self):
        self.check("ERRORS-WRAP-W")

    def test_percent_v_breaks_chain(self):
        self.check("ERRORS-WRAP-V")

    def test_loopvar_is_per_iteration_in_go122(self):
        self.check("LOOPVAR-122")

    def test_loopvar_is_shared_when_go_mod_says_121(self):
        self.check("LOOPVAR-OLD")

    def test_mux_method_and_wildcard(self):
        self.check("MUX-METHOD-WILDCARD")

    def test_mux_specific_pattern_wins(self):
        self.check("MUX-SPECIFIC-WINS")

    def test_mux_pathvalue_is_decoded(self):
        self.check("MUX-PATHVALUE-DECODED")

    def test_embed_without_match_fails_build(self):
        self.check("EMBED-NO-MATCH")

    def test_embed_cannot_climb_parent(self):
        self.check("EMBED-PARENT")

    def test_embed_skips_dot_underscore_unless_all(self):
        self.check("EMBED-HIDDEN")

    def test_defer_in_loop_waits_for_function_end(self):
        self.check("DEFER-IN-LOOP")

    def test_append_may_share_backing_array(self):
        self.check("APPEND-ALIAS")

    def test_json_nil_slice_is_null(self):
        self.check("JSON-NIL-SLICE")

    def test_os_root_rejects_escape(self):
        self.check("OS-ROOT")

    def test_symlink_bypasses_lexical_check(self):
        self.check("SYMLINK-BYPASS")

    def test_vet_flags_newer_stdlib_api(self):
        self.check("VET-STDVERSION-ASTYPE")

    def test_waitgroup_go_needs_go125(self):
        self.check("WG-GO")


if __name__ == "__main__":
    unittest.main()
