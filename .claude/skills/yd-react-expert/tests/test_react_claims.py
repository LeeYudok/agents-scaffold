"""SKILL.md 단언을 실제 react@19 로 재현한다 (stdlib only, 이슈 #201).

판정은 scripts/verify_react_claims.py 의 EXPECT 한 곳에 있다. npm install 이 필요하므로
YD_REACT_VERIFY=1 일 때만 돈다. 없으면 사유와 함께 건너뛰고, CI 는
.github/workflows/react-claims.yml 에서 환경변수를 켜고 건너뜀을 실패로 친다.
"""

import importlib.util
import os
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_react_claims", SKILL / "scripts" / "verify_react_claims.py")
v = importlib.util.module_from_spec(spec)
sys.modules["verify_react_claims"] = v
spec.loader.exec_module(v)


class ReactClaims(unittest.TestCase):
    def check(self, claim):
        if os.environ.get("YD_REACT_VERIFY") != "1":
            self.skipTest("YD_REACT_VERIFY=1 이 아니다 (npm install 이 필요한 재현이라 opt-in)")
        why = v.unavailable()
        if why:
            self.skipTest(why)
        obs, ok = v.run(claim)
        self.assertTrue(ok, f"{claim} 가 react {v.PINNED['react']} 에서 문서와 다르다: {obs}")

    def test_derived_state_computed_in_render(self):
        self.check("DERIVED-IN-RENDER")

    def test_strictmode_runs_effect_twice(self):
        self.check("STRICT-EFFECT-TWICE")

    def test_strictmode_double_run_is_dev_only(self):
        self.check("STRICT-DEV-ONLY")

    def test_late_response_overwrites_without_cleanup(self):
        self.check("ASYNC-RACE")

    def test_index_key_misattaches_state(self):
        self.check("INDEX-KEY")

    def test_changing_key_resets_state(self):
        self.check("KEY-RESET")

    def test_inline_component_remounts_each_render(self):
        self.check("INLINE-COMPONENT")

    def test_ref_is_plain_prop(self):
        self.check("REF-AS-PROP")

    def test_ref_callback_cleanup_runs(self):
        self.check("REF-CLEANUP")

    def test_use_reads_conditionally(self):
        self.check("USE-CONDITIONAL")

    def test_use_action_state_works_in_spa(self):
        self.check("USE-ACTION-STATE-SPA")

    def test_jsx_text_is_escaped(self):
        self.check("TEXT-ESCAPED")

    def test_inner_html_is_not_escaped(self):
        self.check("INNERHTML-RAW")

    def test_react_neutralizes_javascript_url(self):
        self.check("JS-URL")

    def test_lint_flags_missing_dependency(self):
        self.check("LINT-MISSING-DEP")

    def test_lint_blocks_conditional_hook(self):
        self.check("LINT-HOOK-CONDITIONAL")

    def test_sequential_await_is_slower_than_promise_all(self):
        self.check("WATERFALL")

    def test_deferred_value_lags_one_render(self):
        self.check("DEFERRED-VALUE")

    def test_memo_defeated_by_fresh_object(self):
        self.check("MEMO-FRESH-OBJECT")


if __name__ == "__main__":
    unittest.main()
