"""SKILL.md 단언을 실제 SQLite 로 재현한다 (stdlib only, 이슈 #201).

판정은 scripts/verify_sqlite_claims.py 의 EXPECT 한 곳에 있다. 여기서는 단언마다
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
spec = importlib.util.spec_from_file_location("verify_sqlite_claims",
                                              SKILL / "scripts" / "verify_sqlite_claims.py")
v = importlib.util.module_from_spec(spec)
sys.modules["verify_sqlite_claims"] = v
spec.loader.exec_module(v)


class SqliteClaims(unittest.TestCase):
    def check(self, claim):
        obs, ok = v.run(claim)
        self.assertTrue(ok, f"{claim} 가 sqlite {sqlite3.sqlite_version} 에서 문서와 다르다: {obs}")

    def test_ro_rejects_write(self):
        self.check("RO-WRITE-REJECTED")

    def test_ro_leaves_original(self):
        self.check("RO-ORIGINAL-UNCHANGED")

    def test_ro_wal_is_not_clean(self):
        self.check("RO-WAL-NOT-CLEAN")

    def test_immutable_reads_without_sidecars(self):
        self.check("IMMUTABLE-NO-SIDECAR")

    def test_rw_open_of_wal_creates_sidecars(self):
        self.check("RW-WAL-SIDECARS")

    def test_unencoded_question_mark_opens_other_file(self):
        self.check("URI-QUESTION-MARK")

    def test_main_file_copy_loses_wal_commits(self):
        self.check("WAL-COPY-LOSES-DATA")

    def test_foreign_keys_are_per_connection(self):
        self.check("FK-PER-CONNECTION")

    def test_like_wildcards_need_escape(self):
        self.check("LIKE-ESCAPE")

    def test_like_ignores_case_for_ascii_only(self):
        self.check("LIKE-ASCII-CASE")

    def test_composite_index_needs_leading_column(self):
        self.check("INDEX-PREFIX")

    def test_busy_timeout_waits_for_lock(self):
        self.check("BUSY-TIMEOUT")

    def test_transaction_batches_inserts(self):
        self.check("TX-BATCH")

    def test_user_version_persists(self):
        self.check("USER-VERSION")


class ClaimsList(unittest.TestCase):
    def test_every_reproduction_is_listed(self):
        claims = json.loads((SKILL / "tests" / "claims.json").read_text(encoding="utf-8"))["claims"]
        self.assertEqual(sorted(c["id"] for c in claims), sorted(v.EXPECT),
                         "verify_sqlite_claims.EXPECT 와 tests/claims.json 의 단언이 어긋났다")

    def test_script_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(v.main(), 0)


if __name__ == "__main__":
    unittest.main()
