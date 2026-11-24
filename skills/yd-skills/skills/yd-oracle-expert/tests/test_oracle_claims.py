"""SKILL.md 단언을 실제 Oracle 로 재현한다 (stdlib only).

판정은 scripts/verify_oracle_claims.py 의 EXPECT 한 곳에 있다. 여기서는 단언마다
테스트 하나를 두어 tests/claims.json 이 가리킬 수 있게 하고, 실패하면 관찰값을 보여준다.

Oracle 재현은 YD_ORACLE_SQLPLUS(표준 입력으로 SQL 을 받는 sqlplus 명령)가 있어야 돈다.
없으면 이유를 적고 skip 한다. CI 는 .github/workflows/oracle.yml 이 컨테이너를 띄워
skip 없이 돌린다. ClaimsList 는 Oracle 없이도 돈다.
"""

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_oracle_claims",
                                              SKILL / "scripts" / "verify_oracle_claims.py")
v = importlib.util.module_from_spec(spec)
sys.modules["verify_oracle_claims"] = v
spec.loader.exec_module(v)


@unittest.skipUnless(os.environ.get(v.ENV),
                     f"{v.ENV} 가 없어 Oracle 재현을 건너뛴다 — SKILL.md 10장 참고")
class OracleClaims(unittest.TestCase):
    def check(self, claim):
        obs, ok = v.check(claim)
        self.assertTrue(ok, f"{claim} 가 Oracle 에서 문서와 다르다: {obs}")

    def test_empty_string_is_null(self):
        self.check("EMPTY-STRING-NULL")

    def test_concat_with_null_keeps_string(self):
        self.check("CONCAT-NULL")

    def test_date_equality_misses_time(self):
        self.check("DATE-HAS-TIME")

    def test_to_date_depends_on_session_format(self):
        self.check("NLS-DATE-FORMAT")

    def test_varchar2_counts_bytes(self):
        self.check("VARCHAR2-BYTES")

    def test_varchar2_4000_byte_cap(self):
        self.check("VARCHAR2-4000-CAP")

    def test_number_scale_rounds_silently(self):
        self.check("NUMBER-SCALE")

    def test_unquoted_identifiers_fold_upper(self):
        self.check("IDENT-UPPERCASE")

    def test_identifier_limit_is_bytes(self):
        self.check("IDENT-128-BYTES")

    def test_limit_is_rejected(self):
        self.check("LIMIT-UNSUPPORTED")

    def test_rownum_applies_before_order_by(self):
        self.check("ROWNUM-BEFORE-ORDER")

    def test_rownum_greater_than_one_is_empty(self):
        self.check("ROWNUM-GT-EMPTY")

    def test_ddl_commits_prior_dml(self):
        self.check("DDL-IMPLICIT-COMMIT")

    def test_uncommitted_change_is_invisible(self):
        self.check("READ-CONSISTENCY")

    def test_serializable_raises_08177(self):
        self.check("SERIALIZABLE-08177")

    def test_in_list_limit_23ai(self):
        self.check("IN-LIST-LIMIT")

    def test_boolean_column_23ai(self):
        self.check("BOOLEAN-23AI")

    def test_select_without_from_23ai(self):
        self.check("NO-FROM-23AI")

    def test_identity_always_rejects_value(self):
        self.check("IDENTITY-ALWAYS")

    def test_identity_resync_with_limit_value(self):
        self.check("IDENTITY-RESYNC")

    def test_merge_duplicate_source_key(self):
        self.check("MERGE-DUP-SOURCE")

    def test_literals_create_distinct_cursors(self):
        self.check("BIND-CURSOR-SHARING")

    def test_sqlplus_exit_code_hides_errors(self):
        self.check("SQLPLUS-EXIT-CODE")

    def test_sqlplus_ampersand_swallows_next_line(self):
        self.check("SQLPLUS-AMPERSAND")

    def test_sqlplus_drops_long_lines(self):
        self.check("SQLPLUS-LINE-LIMIT")


class ClaimsList(unittest.TestCase):
    def test_every_reproduction_is_listed(self):
        claims = json.loads((SKILL / "tests" / "claims.json").read_text(encoding="utf-8"))["claims"]
        self.assertEqual(sorted(c["id"] for c in claims), sorted(v.EXPECT),
                         "verify_oracle_claims.EXPECT 와 tests/claims.json 의 단언이 어긋났다")

    def test_missing_env_is_reported_not_crashed(self):
        saved = os.environ.pop(v.ENV, None)
        try:
            with self.assertRaises(v.OracleUnavailable):
                v.command()
        finally:
            if saved is not None:
                os.environ[v.ENV] = saved


if __name__ == "__main__":
    unittest.main()
