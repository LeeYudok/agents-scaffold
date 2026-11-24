"""SKILL.md 단언을 일회용 실제 PostgreSQL 로 재현한다 (stdlib only).

판정은 scripts/verify_pg_claims.py 의 EXPECT 한 곳에 있다. 여기서는 단언마다
테스트 하나를 두어 tests/claims.json 이 가리킬 수 있게 하고, 실패하면 관찰값을 보여준다.

YD_PG_PSQL 이 없으면 서버가 필요한 테스트는 skip 한다. CI(.github/workflows/pg.yml)는
서비스 컨테이너를 붙여 skip 없이 돌린다. ClaimsList 는 서버 없이도 돈다.
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_pg_claims",
                                              SKILL / "scripts" / "verify_pg_claims.py")
v = importlib.util.module_from_spec(spec)
sys.modules["verify_pg_claims"] = v
spec.loader.exec_module(v)

NO_SERVER = f"{v.ENV} 가 없어 PostgreSQL 단언 재현을 건너뛴다 (SKILL.md 7장 참고)"


@unittest.skipUnless(os.environ.get(v.ENV, "").strip(), NO_SERVER)
class PgClaims(unittest.TestCase):
    def check(self, claim):
        obs, ok = v.run(claim)
        self.assertTrue(ok, f"{claim} 가 postgres {v.server_version()} 에서 문서와 다르다: {obs}")

    def test_fk_column_is_not_indexed(self):
        self.check("FK-NOT-INDEXED")

    def test_small_table_seq_scan_is_expected(self):
        self.check("SEQSCAN-SMALL-TABLE")

    def test_lower_needs_expression_index(self):
        self.check("LOWER-EXPRESSION-INDEX")

    def test_like_prefix_needs_pattern_ops(self):
        self.check("LIKE-PATTERN-OPS")

    def test_partial_index_needs_implied_predicate(self):
        self.check("PARTIAL-INDEX")

    def test_timestamp_drops_offset(self):
        self.check("TIMESTAMP-DROPS-OFFSET")

    def test_float_is_not_money(self):
        self.check("FLOAT-MONEY")

    def test_add_column_does_not_rewrite(self):
        self.check("ADD-COLUMN-NO-REWRITE")

    def test_volatile_default_rewrites(self):
        self.check("VOLATILE-DEFAULT-REWRITES")

    def test_int_to_bigint_rewrites(self):
        self.check("ALTER-TYPE-REWRITES")

    def test_varchar_widen_does_not_rewrite(self):
        self.check("VARCHAR-WIDEN-NO-REWRITE")

    def test_set_not_null_scans_without_rewrite(self):
        self.check("SET-NOT-NULL-SCAN")

    def test_not_valid_constraint_checks_new_rows_only(self):
        self.check("NOT-VALID-CONSTRAINT")

    def test_create_index_concurrently_fails_in_transaction(self):
        self.check("CIC-IN-TRANSACTION")

    def test_create_index_blocks_writes(self):
        self.check("CREATE-INDEX-BLOCKS-WRITES")

    def test_explain_analyze_executes_statement(self):
        self.check("EXPLAIN-ANALYZE-EXECUTES")

    def test_serializable_raises_40001(self):
        self.check("SERIALIZATION-RETRY")

    def test_read_committed_allows_write_skew(self):
        self.check("READ-COMMITTED-WRITE-SKEW")

    def test_open_transaction_blocks_vacuum(self):
        self.check("LONG-TX-BLOCKS-VACUUM")

    def test_idle_read_committed_does_not_block_vacuum(self):
        self.check("IDLE-RC-NO-VACUUM-BLOCK")

    def test_queued_alter_blocks_readers(self):
        self.check("LOCK-QUEUE")

    def test_unique_allows_many_nulls(self):
        self.check("UNIQUE-NULLS")

    def test_script_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(v.main(), 0)


class ClaimsList(unittest.TestCase):
    def test_every_reproduction_is_listed(self):
        claims = json.loads((SKILL / "tests" / "claims.json").read_text(encoding="utf-8"))["claims"]
        self.assertEqual(sorted(c["id"] for c in claims), sorted(v.EXPECT),
                         "verify_pg_claims.EXPECT 와 tests/claims.json 의 단언이 어긋났다")

    def test_missing_env_is_reported(self):
        """변수가 없을 때 조용히 빈 명령을 돌리지 않고 이유를 말한다."""
        saved = os.environ.pop(v.ENV, None)
        try:
            with self.assertRaisesRegex(RuntimeError, v.ENV):
                v.command()
        finally:
            if saved is not None:
                os.environ[v.ENV] = saved


if __name__ == "__main__":
    unittest.main()
