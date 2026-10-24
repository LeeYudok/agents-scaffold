#!/usr/bin/env python3
"""SKILL.md 의 SQLite 단언을 stdlib sqlite3 로 재현한다 (이슈 #201).

    python3 .claude/skills/yd-sqlite-expert/scripts/verify_sqlite_claims.py

문서의 단언은 SQLite 버전이 바뀌면 낡는다. 이 스크립트는 단언마다 임시 디렉터리에서
실제로 재현하고 관찰값을 출력한다. 하나라도 문서와 다르면 exit 1 이다 — 그때는 문서를
고칠지, 단언이 버전에 묶였다고 적을지 판단한다.

각 check_* 함수는 관찰값 dict 를 돌려줄 뿐 판정하지 않는다. 판정은 EXPECT 한 곳에 있고,
테스트(tests/test_sqlite_claims.py)도 같은 함수를 불러 같은 관찰값을 검사한다.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import quote

SIDECARS = ("-wal", "-shm", "-journal")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sidecars(path: Path) -> list[str]:
    return [s for s in SIDECARS if Path(str(path) + s).exists()]


def _ro_uri(path: Path) -> str:
    return f"file:{quote(str(path))}?mode=ro"


def _make_db(path: Path, wal: bool = False) -> None:
    con = sqlite3.connect(path)
    if wal:
        con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t(x)")
    con.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
    con.commit()
    if wal:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    # 일부 빌드(macOS 등)는 닫아도 WAL 곁 파일을 남긴다. 시작 상태를 "본 파일만" 으로 고정한다.
    for s in SIDECARS:
        Path(str(path) + s).unlink(missing_ok=True)


def check_ro_rejects_write(d: Path) -> dict:
    """mode=ro 로 연 연결에서 DELETE 가 엔진 수준에서 실패한다."""
    db = d / "app.db"
    _make_db(db)
    con = sqlite3.connect(_ro_uri(db), uri=True)
    try:
        con.execute("DELETE FROM t")
        error = ""
    except sqlite3.OperationalError as e:
        error = str(e)
    rows = con.execute("SELECT count(*) FROM t").fetchone()[0]
    con.close()
    return {"write_error": error, "rows_after": rows}


def check_ro_leaves_original(d: Path) -> dict:
    """롤백 저널 DB 를 mode=ro 로 조회해도 본 파일 해시가 같고 곁 파일이 안 생긴다."""
    db = d / "app.db"
    _make_db(db)
    before = _sha(db)
    con = sqlite3.connect(_ro_uri(db), uri=True)
    con.execute("SELECT * FROM t WHERE x > ?", (1,)).fetchall()
    con.execute("SELECT count(*) FROM t").fetchone()
    con.close()
    return {"hash_same": _sha(db) == before, "sidecars": _sidecars(db)}


def check_ro_wal_without_shm(d: Path) -> dict:
    """곁 파일 없는 WAL DB 를 mode=ro 로 열면 버전에 따라 열기가 실패하거나 곁 파일이 생긴다.

    3.51.0 은 'unable to open database file', 3.53.4 는 열리지만 -wal·-shm 을 만든다
    (2026-10-04 실측). 어느 쪽이든 mode=ro 만으로는 깨끗한 조회가 안 된다.
    immutable=1 은 곁 파일 없이 읽는다 — 파일이 변하지 않는다는 약속이 지켜질 때만.
    """
    db = d / "app.db"
    _make_db(db, wal=True)
    before = _sha(db)
    con = sqlite3.connect(_ro_uri(db), uri=True)
    try:
        con.execute("SELECT count(*) FROM t").fetchone()
        open_error = ""
    except sqlite3.OperationalError as e:
        open_error = str(e)
    con.close()
    ro_sidecars = _sidecars(db)
    for s in SIDECARS:
        Path(str(db) + s).unlink(missing_ok=True)
    imm = sqlite3.connect(f"file:{quote(str(db))}?mode=ro&immutable=1", uri=True)
    imm_rows = imm.execute("SELECT count(*) FROM t").fetchone()[0]
    imm.close()
    return {"open_error": open_error, "sidecars": ro_sidecars, "hash_same": _sha(db) == before,
            "immutable_rows": imm_rows, "immutable_sidecars": _sidecars(db)}


def check_rw_wal_creates_sidecars(d: Path) -> dict:
    """WAL DB 를 읽기·쓰기 모드로 열고 조회만 해도 -wal·-shm 이 생긴다."""
    db = d / "app.db"
    _make_db(db, wal=True)
    con = sqlite3.connect(db)
    con.execute("SELECT count(*) FROM t").fetchone()
    during = _sidecars(db)
    con.close()
    return {"sidecars_during_read": during}


def check_uri_question_mark(d: Path) -> dict:
    """경로의 '?' 를 인코딩하지 않으면 다른 파일을 열고, mode=ro 도 무시된다."""
    folder = d / "a?b"
    folder.mkdir()
    db = folder / "app.db"
    _make_db(db)
    raw = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        raw.execute("SELECT count(*) FROM t").fetchone()
        raw_error = ""
    except sqlite3.OperationalError as e:
        raw_error = str(e)
    raw.close()
    stray = sorted(p.name for p in d.iterdir() if p.name != "a?b")
    enc = sqlite3.connect(_ro_uri(db), uri=True)
    rows = enc.execute("SELECT count(*) FROM t").fetchone()[0]
    enc.close()
    return {"raw_error": raw_error, "stray_files": stray, "encoded_rows": rows}


def check_main_file_copy_loses_wal(d: Path) -> dict:
    """WAL 모드에서 본 파일만 복사하면 체크포인트 전 커밋이 빠진다. backup API 는 담는다."""
    db = d / "app.db"
    _make_db(db, wal=True)
    con = sqlite3.connect(db)
    con.execute("PRAGMA wal_autocheckpoint=0")
    con.execute("INSERT INTO t VALUES (4)")
    con.commit()
    copy = d / "copy.db"
    shutil.copyfile(db, copy)
    backup = sqlite3.connect(d / "backup.db")
    con.backup(backup)
    backup_rows = backup.execute("SELECT count(*) FROM t").fetchone()[0]
    backup.close()
    con.close()
    c = sqlite3.connect(copy)
    copy_rows = c.execute("SELECT count(*) FROM t").fetchone()[0]
    c.close()
    return {"committed_rows": 4, "copy_rows": copy_rows, "backup_rows": backup_rows}


def check_foreign_keys_per_connection(d: Path) -> dict:
    """foreign_keys 는 기본이 꺼져 있고, 한 연결에서 켜도 다른 연결에는 적용되지 않는다."""
    db = d / "app.db"
    a = sqlite3.connect(db, isolation_level=None)
    default = a.execute("PRAGMA foreign_keys").fetchone()[0]
    a.execute("PRAGMA foreign_keys=ON")
    a.executescript("CREATE TABLE p(id INTEGER PRIMARY KEY);"
                    "CREATE TABLE c(pid INTEGER REFERENCES p(id));")
    try:
        a.execute("INSERT INTO c VALUES (99)")
        on_error = ""
    except sqlite3.IntegrityError as e:
        on_error = str(e)
    b = sqlite3.connect(db, isolation_level=None)
    other = b.execute("PRAGMA foreign_keys").fetchone()[0]
    b.execute("INSERT INTO c VALUES (99)")
    orphans = b.execute("SELECT count(*) FROM c WHERE pid NOT IN (SELECT id FROM p)").fetchone()[0]
    a.close()
    b.close()
    return {"default": default, "on_error": on_error, "other_connection": other, "orphans": orphans}


def _like(con: sqlite3.Connection, query: str, escape: bool) -> list[str]:
    if escape:
        q = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        sql = "SELECT s FROM t WHERE s LIKE ? ESCAPE '\\' ORDER BY s"
    else:
        q = query
        sql = "SELECT s FROM t WHERE s LIKE ? ORDER BY s"
    return [r[0] for r in con.execute(sql, (f"%{q}%",))]


def check_like_escape(d: Path) -> dict:
    """와일드카드를 이스케이프하지 않으면 '%' 하나로 전부 걸린다. 이스케이프하면 글자 그대로 찾는다."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE t(s)")
    con.executemany("INSERT INTO t VALUES (?)",
                    [("50% 할인",), ("500원",), ("a_b",), ("axb",), ("Ünïcode",)])
    out = {
        "percent_raw": _like(con, "%", escape=False),
        "percent_escaped": _like(con, "%", escape=True),
        "fifty_percent_escaped": _like(con, "50%", escape=True),
        "underscore_raw": _like(con, "a_b", escape=False),
        "underscore_escaped": _like(con, "a_b", escape=True),
        "ascii_case": _like(con, "ÜNÏ", escape=True) + _like(con, "ünï", escape=True),
    }
    out["ascii_case_ascii"] = [r[0] for r in con.execute("SELECT 'ABC' LIKE 'abc'")]
    con.close()
    return out


def check_composite_index_prefix(d: Path) -> dict:
    """(r, s) 복합 인덱스는 앞 컬럼 r 조회에는 쓰이고 s 단독 조회에는 SCAN 이 된다."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE m(r, s, body)")
    con.execute("CREATE INDEX m_rs ON m(r, s)")
    plan = lambda q: " ".join(row[-1] for row in con.execute("EXPLAIN QUERY PLAN " + q))
    out = {"by_r": plan("SELECT * FROM m WHERE r = 1"),
           "by_s": plan("SELECT * FROM m WHERE s = 1")}
    con.close()
    return out


def check_busy_timeout(d: Path) -> dict:
    """쓰기 잠금이 잡혀 있으면 timeout 0 은 즉시 locked, timeout 이 있으면 풀릴 때까지 기다린다."""
    db = d / "app.db"
    _make_db(db)
    holder = sqlite3.connect(db, isolation_level=None, check_same_thread=False)
    holder.execute("BEGIN IMMEDIATE")
    holder.execute("INSERT INTO t VALUES (10)")
    eager = sqlite3.connect(db, timeout=0, isolation_level=None)
    t0 = time.monotonic()
    try:
        eager.execute("INSERT INTO t VALUES (11)")
        no_timeout_error = ""
    except sqlite3.OperationalError as e:
        no_timeout_error = str(e)
    no_timeout_wait = time.monotonic() - t0
    eager.close()
    # 대기 시간을 절대값으로 재면 부하 걸린 CI 에서 흔들린다. 잠금을 풀기 직전 시각을
    # 기록하고, timeout 이 있는 쓰기가 그 뒤에 끝났는지(=풀릴 때까지 기다렸는지)를 본다.
    released: dict = {}

    def release_lock():
        released["at"] = time.monotonic()
        holder.execute("COMMIT")

    release = threading.Timer(0.3, release_lock)
    release.start()
    patient = sqlite3.connect(db, timeout=5, isolation_level=None)
    patient.execute("INSERT INTO t VALUES (12)")
    done_at = time.monotonic()
    release.join()
    waited_for_release = "at" in released and done_at >= released["at"]
    rows = patient.execute("SELECT count(*) FROM t").fetchone()[0]
    patient.close()
    holder.close()
    return {"no_timeout_error": no_timeout_error, "no_timeout_wait": round(no_timeout_wait, 2),
            "waited_for_release": waited_for_release, "rows": rows}


def check_transaction_batch(d: Path) -> dict:
    """같은 행 수를 자동 커밋(행마다 커밋)과 트랜잭션 하나로 넣어 걸린 시간을 비교한다."""
    n = 300
    auto = sqlite3.connect(d / "auto.db", isolation_level=None)
    auto.execute("PRAGMA synchronous=FULL")
    auto.execute("CREATE TABLE t(x)")
    t0 = time.monotonic()
    for i in range(n):
        auto.execute("INSERT INTO t VALUES (?)", (i,))
    auto_s = time.monotonic() - t0
    auto.close()
    tx = sqlite3.connect(d / "tx.db", isolation_level=None)
    tx.execute("PRAGMA synchronous=FULL")
    tx.execute("CREATE TABLE t(x)")
    t0 = time.monotonic()
    tx.execute("BEGIN")
    for i in range(n):
        tx.execute("INSERT INTO t VALUES (?)", (i,))
    tx.execute("COMMIT")
    tx_s = time.monotonic() - t0
    tx.close()
    return {"rows": n, "autocommit_s": round(auto_s, 4), "transaction_s": round(tx_s, 4),
            "ratio": round(auto_s / max(tx_s, 1e-6), 1)}


def check_user_version(d: Path) -> dict:
    """PRAGMA user_version 은 파일에 남아 다시 열어도 유지된다. 기본값은 0 이다."""
    db = d / "app.db"
    con = sqlite3.connect(db)
    default = con.execute("PRAGMA user_version").fetchone()[0]
    con.execute("PRAGMA user_version = 3")
    con.close()
    con = sqlite3.connect(db)
    after = con.execute("PRAGMA user_version").fetchone()[0]
    con.close()
    return {"default": default, "reopened": after}


# 단언 → (재현 함수, 관찰값이 문서와 맞는지)
EXPECT = {
    "RO-WRITE-REJECTED": (check_ro_rejects_write,
                          lambda o: "readonly" in o["write_error"] and o["rows_after"] == 3),
    "RO-ORIGINAL-UNCHANGED": (check_ro_leaves_original,
                              lambda o: o["hash_same"] and o["sidecars"] == []),
    "RO-WAL-NOT-CLEAN": (check_ro_wal_without_shm,
                         lambda o: o["hash_same"] and (o["open_error"] != "" or o["sidecars"] != [])),
    "IMMUTABLE-NO-SIDECAR": (check_ro_wal_without_shm,
                             lambda o: o["immutable_rows"] == 3 and o["immutable_sidecars"] == []),
    "RW-WAL-SIDECARS": (check_rw_wal_creates_sidecars,
                        lambda o: {"-wal", "-shm"} <= set(o["sidecars_during_read"])),
    "URI-QUESTION-MARK": (check_uri_question_mark,
                          lambda o: o["stray_files"] != [] and o["encoded_rows"] == 3),
    "WAL-COPY-LOSES-DATA": (check_main_file_copy_loses_wal,
                            lambda o: o["copy_rows"] < o["committed_rows"] == o["backup_rows"]),
    "FK-PER-CONNECTION": (check_foreign_keys_per_connection,
                          lambda o: o["default"] == 0 and "FOREIGN KEY" in o["on_error"]
                          and o["other_connection"] == 0 and o["orphans"] == 1),
    "LIKE-ESCAPE": (check_like_escape,
                    lambda o: len(o["percent_raw"]) == 5 and o["percent_escaped"] == ["50% 할인"]
                    and o["fifty_percent_escaped"] == ["50% 할인"]
                    and o["underscore_raw"] == ["a_b", "axb"] and o["underscore_escaped"] == ["a_b"]),
    "LIKE-ASCII-CASE": (check_like_escape,
                        lambda o: o["ascii_case_ascii"] == [1] and o["ascii_case"] == []),
    "INDEX-PREFIX": (check_composite_index_prefix,
                     lambda o: "USING INDEX m_rs" in o["by_r"] and "SCAN m" in o["by_s"]),
    "BUSY-TIMEOUT": (check_busy_timeout,
                     lambda o: "locked" in o["no_timeout_error"] and o["no_timeout_wait"] < 1.0
                     and o["waited_for_release"] and o["rows"] == 5),
    "TX-BATCH": (check_transaction_batch, lambda o: o["ratio"] > 1),
    "USER-VERSION": (check_user_version, lambda o: o["default"] == 0 and o["reopened"] == 3),
}


def run(claim: str) -> tuple[dict, bool]:
    fn, ok = EXPECT[claim]
    with tempfile.TemporaryDirectory() as tmp:
        obs = fn(Path(tmp))
    return obs, bool(ok(obs))


def main() -> int:
    print(f"sqlite {sqlite3.sqlite_version} · python {sys.version.split()[0]}")
    failed = 0
    for claim in EXPECT:
        obs, ok = run(claim)
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {claim}: {obs}")
    print(f"{len(EXPECT) - failed}/{len(EXPECT)} 단언 재현")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
