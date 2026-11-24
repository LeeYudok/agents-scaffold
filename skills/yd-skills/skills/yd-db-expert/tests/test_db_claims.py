"""SKILL.md 의 엔진 공통 단언을 stdlib sqlite3 로 재현한다.

판정은 scripts/verify_db_claims.py 의 EXPECT 한 곳에 있다. 여기서는 단언마다
테스트 하나를 두어 tests/claims.json 이 가리킬 수 있게 하고, 실패하면 관찰값을 보여준다.
"""

import contextlib
import importlib.util
import io
import json
import sqlite3
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_db_claims",
                                              SKILL / "scripts" / "verify_db_claims.py")
v = importlib.util.module_from_spec(spec)
sys.modules["verify_db_claims"] = v
spec.loader.exec_module(v)


class DbClaims(unittest.TestCase):
    def check(self, claim):
        obs, ok = v.run(claim)
        self.assertTrue(ok, f"{claim} 가 sqlite {sqlite3.sqlite_version} 에서 문서와 다르다: {obs}")

    def test_db_constraint_catches_bypassing_writer(self):
        self.check("CONSTRAINT-IN-DB")

    def test_null_equality_is_unknown(self):
        self.check("NULL-COMPARISON")

    def test_not_in_with_null_returns_nothing(self):
        self.check("NOT-IN-NULL")

    def test_unique_allows_many_nulls(self):
        self.check("UNIQUE-NULLS")

    def test_fk_does_not_create_index(self):
        self.check("FK-NOT-INDEXED")

    def test_function_on_column_skips_index(self):
        self.check("FUNCTION-ON-COLUMN")

    def test_n_plus_one_statement_count(self):
        self.check("N-PLUS-ONE")

    def test_offset_paging_duplicates_after_insert(self):
        self.check("OFFSET-DRIFT")

    def test_keyset_needs_unique_tiebreak(self):
        self.check("KEYSET-TIEBREAK")

    def test_transaction_is_all_or_nothing(self):
        self.check("TX-ATOMICITY")

    def test_string_concat_is_injectable(self):
        self.check("CONCAT-INJECTION")

    def test_placeholder_cannot_bind_identifier(self):
        self.check("PLACEHOLDER-NOT-IDENTIFIER")

    def test_soft_delete_needs_partial_unique(self):
        self.check("SOFT-DELETE-UNIQUE")


class ClaimsList(unittest.TestCase):
    def test_every_reproduction_is_listed(self):
        claims = json.loads((SKILL / "tests" / "claims.json").read_text(encoding="utf-8"))["claims"]
        self.assertEqual(sorted(c["id"] for c in claims), sorted(v.EXPECT),
                         "verify_db_claims.EXPECT 와 tests/claims.json 의 단언이 어긋났다")

    def test_script_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(v.main(), 0)


if __name__ == "__main__":
    unittest.main()
