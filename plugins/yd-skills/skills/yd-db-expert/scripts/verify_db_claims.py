#!/usr/bin/env python3
"""SKILL.md 의 엔진 공통 설계 단언을 stdlib sqlite3 로 재현한다.

    python3 .claude/skills/yd-db-expert/scripts/verify_db_claims.py

이 스킬의 단언은 특정 엔진이 아니라 SQL 의미론과 접근 패턴에 관한 것이다(NULL 비교,
제약, N+1, 페이징, 원자성, 플레이스홀더). 그래서 어디서나 있는 SQLite 로 재현한다.
엔진마다 다른 동작(잠금·재작성·실행계획 세부)은 엔진 스킬의 검증기가 맡는다.

각 check_* 함수는 관찰값 dict 를 돌려줄 뿐 판정하지 않는다. 판정은 EXPECT 한 곳에 있고,
테스트(tests/test_db_claims.py)도 같은 함수를 불러 같은 관찰값을 검사한다.
"""

from __future__ import annotations

import sqlite3
import sys


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:", isolation_level=None)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def check_constraint_catches_bypass() -> dict:
    """애플리케이션 검증을 거치지 않은 쓰기(수동 SQL)를 DB 제약만이 막는다."""
    out = {}
    for name, ddl in {"no_constraint": "CREATE TABLE acct(id INTEGER PRIMARY KEY, email TEXT, balance INT)",
                      "with_constraint": "CREATE TABLE acct(id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,"
                                         " balance INT NOT NULL CHECK (balance >= 0))"}.items():
        con = _db()
        con.execute(ddl)
        con.execute("INSERT INTO acct(email, balance) VALUES ('a@x', 10)")
        rejected = []
        for bad in ("INSERT INTO acct(email, balance) VALUES (NULL, 1)",
                    "INSERT INTO acct(email, balance) VALUES ('a@x', 1)",
                    "UPDATE acct SET balance = -100"):
            try:
                con.execute(bad)
            except sqlite3.IntegrityError:
                rejected.append(bad.split()[0])
        out[name] = {"rejected": len(rejected),
                     "bad_rows": con.execute("SELECT count(*) FROM acct WHERE email IS NULL OR balance < 0"
                                             " OR email IN (SELECT email FROM acct GROUP BY email"
                                             " HAVING count(*) > 1)").fetchone()[0]}
        con.close()
    return out


def check_null_comparison() -> dict:
    """NULL = NULL 은 참이 아니라 NULL 이다. = NULL 조건은 아무 행도 고르지 못한다."""
    con = _db()
    con.execute("CREATE TABLE p(id INT, phone TEXT)")
    con.executemany("INSERT INTO p VALUES (?, ?)", [(1, None), (2, None), (3, "010")])
    out = {"null_eq_null": con.execute("SELECT NULL = NULL").fetchone()[0],
           "eq_null_rows": con.execute("SELECT count(*) FROM p WHERE phone = NULL").fetchone()[0],
           "is_null_rows": con.execute("SELECT count(*) FROM p WHERE phone IS NULL").fetchone()[0],
           "neq_rows": con.execute("SELECT count(*) FROM p WHERE phone <> '010'").fetchone()[0]}
    con.close()
    return out


def check_not_in_with_null() -> dict:
    """NOT IN 서브쿼리에 NULL 이 하나라도 있으면 결과가 비고, NOT EXISTS 는 의도대로 나온다."""
    con = _db()
    con.executescript("""
        CREATE TABLE users(id INT);
        CREATE TABLE banned(user_id INT);
        INSERT INTO users VALUES (1), (2), (3);
        INSERT INTO banned VALUES (1), (NULL);
    """)
    out = {"not_in": [r[0] for r in con.execute(
               "SELECT id FROM users WHERE id NOT IN (SELECT user_id FROM banned) ORDER BY id")],
           "not_exists": [r[0] for r in con.execute(
               "SELECT id FROM users u WHERE NOT EXISTS"
               " (SELECT 1 FROM banned b WHERE b.user_id = u.id) ORDER BY id")]}
    con.close()
    return out


def check_unique_allows_nulls() -> dict:
    """UNIQUE 는 NULL 끼리 같다고 보지 않는다. NULL 행 여러 개가 통과한다."""
    con = _db()
    con.execute("CREATE TABLE u(email TEXT UNIQUE)")
    con.executemany("INSERT INTO u VALUES (?)", [(None,), (None,), (None,)])
    try:
        con.execute("INSERT INTO u VALUES ('a'), ('a')")
        dup_error = ""
    except sqlite3.IntegrityError as e:
        dup_error = str(e)
    out = {"null_rows": con.execute("SELECT count(*) FROM u WHERE email IS NULL").fetchone()[0],
           "dup_error": dup_error}
    con.close()
    return out


def check_fk_not_auto_indexed() -> dict:
    """FK 를 선언해도 자식 컬럼 인덱스는 생기지 않는다. 부모 조회는 자식 테이블을 SCAN 한다."""
    con = _db()
    con.executescript("""
        CREATE TABLE parent(id INTEGER PRIMARY KEY);
        CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INT REFERENCES parent(id));
    """)
    plan = lambda: " ".join(r[-1] for r in con.execute(
        "EXPLAIN QUERY PLAN SELECT id FROM child WHERE parent_id = 1"))
    out = {"child_indexes": [r[1] for r in con.execute("PRAGMA index_list('child')")],
           "plan_without": plan()}
    con.execute("CREATE INDEX child_parent ON child(parent_id)")
    out["plan_with"] = plan()
    con.close()
    return out


def check_function_on_column() -> dict:
    """함수를 씌운 조건은 컬럼 인덱스를 못 타고, 표현식 인덱스는 탄다."""
    con = _db()
    con.execute("CREATE TABLE person(id INTEGER PRIMARY KEY, name TEXT)")
    con.execute("CREATE INDEX person_name ON person(name)")
    plan = lambda: " ".join(r[-1] for r in con.execute(
        "EXPLAIN QUERY PLAN SELECT id FROM person WHERE lower(name) = 'kim'"))
    out = {"plain_index": plan()}
    con.execute("CREATE INDEX person_lower ON person(lower(name))")
    out["expression_index"] = plan()
    con.close()
    return out


def _orders(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE customer(id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INT, total INT);
    """)
    con.executemany("INSERT INTO customer VALUES (?, ?)", [(i, f"c{i}") for i in range(1, 51)])
    con.executemany("INSERT INTO orders(customer_id, total) VALUES (?, ?)",
                    [(i % 50 + 1, i) for i in range(200)])


def check_n_plus_one() -> dict:
    """목록을 돌며 건마다 조회하면 문이 N+1 개, IN 한 번이면 2 개다. 결과는 같다."""
    con = _db()
    _orders(con)
    statements: list[str] = []
    con.set_trace_callback(statements.append)
    loop = {}
    for (cid,) in con.execute("SELECT id FROM customer ORDER BY id").fetchall():
        loop[cid] = con.execute("SELECT count(*) FROM orders WHERE customer_id = ?", (cid,)).fetchone()[0]
    loop_count = len(statements)
    statements.clear()
    ids = [r[0] for r in con.execute("SELECT id FROM customer ORDER BY id")]
    marks = ",".join("?" * len(ids))
    batched = {cid: n for cid, n in con.execute(
        f"SELECT customer_id, count(*) FROM orders WHERE customer_id IN ({marks}) GROUP BY customer_id", ids)}
    batched_count = len(statements)
    con.close()
    return {"customers": len(ids), "loop_statements": loop_count,
            "batched_statements": batched_count, "same_result": loop == batched}


def check_offset_paging_drift() -> dict:
    """페이지 사이에 새 행이 들어오면 OFFSET 은 중복을 내고, 커서(키 기준)는 내지 않는다."""
    con = _db()
    con.execute("CREATE TABLE post(id INTEGER PRIMARY KEY, title TEXT)")
    con.executemany("INSERT INTO post VALUES (?, ?)", [(i, f"p{i}") for i in range(1, 11)])
    page = 3
    first = [r[0] for r in con.execute("SELECT id FROM post ORDER BY id DESC LIMIT ?", (page,))]
    con.execute("INSERT INTO post VALUES (11, 'new')")
    offset_next = [r[0] for r in con.execute(
        "SELECT id FROM post ORDER BY id DESC LIMIT ? OFFSET ?", (page, page))]
    cursor_next = [r[0] for r in con.execute(
        "SELECT id FROM post WHERE id < ? ORDER BY id DESC LIMIT ?", (first[-1], page))]
    con.close()
    return {"first": first, "offset_next": offset_next, "cursor_next": cursor_next,
            "offset_duplicates": sorted(set(first) & set(offset_next)),
            "cursor_duplicates": sorted(set(first) & set(cursor_next))}


def check_keyset_tiebreak() -> dict:
    """정렬 키가 유일하지 않으면 커서가 동률 행을 건너뛴다. (키, id) 로 유일하게 만들면 빠짐이 없다."""
    con = _db()
    con.execute("CREATE TABLE ev(id INTEGER PRIMARY KEY, at TEXT)")
    con.executemany("INSERT INTO ev VALUES (?, ?)",
                    [(1, "09:00"), (2, "09:01"), (3, "09:01"), (4, "09:01"), (5, "09:02")])
    first = con.execute("SELECT id, at FROM ev ORDER BY at, id LIMIT 2").fetchall()
    last_id, last_at = first[-1]
    by_key = [r[0] for r in con.execute(
        "SELECT id FROM ev WHERE at > ? ORDER BY at, id LIMIT 3", (last_at,))]
    by_pair = [r[0] for r in con.execute(
        "SELECT id FROM ev WHERE (at, id) > (?, ?) ORDER BY at, id LIMIT 3", (last_at, last_id))]
    con.close()
    seen = {r[0] for r in first}
    return {"first": [r[0] for r in first], "key_only_next": by_key, "pair_next": by_pair,
            "key_only_missing": sorted({1, 2, 3, 4, 5} - seen - set(by_key)),
            "pair_missing": sorted({1, 2, 3, 4, 5} - seen - set(by_pair))}


def _transfer(con: sqlite3.Connection, atomic: bool) -> None:
    if atomic:
        con.execute("BEGIN")
    try:
        con.execute("UPDATE acct SET balance = balance + 500 WHERE id = 2")
        con.execute("UPDATE acct SET balance = balance - 500 WHERE id = 1")
        if atomic:
            con.execute("COMMIT")
    except sqlite3.IntegrityError:
        if atomic:
            con.execute("ROLLBACK")


def check_transaction_atomicity() -> dict:
    """두 쓰기를 트랜잭션으로 묶으면 뒤가 실패할 때 앞도 되돌아간다. 묶지 않으면 반만 반영된다."""
    out = {}
    for atomic in (False, True):
        con = _db()
        con.execute("CREATE TABLE acct(id INTEGER PRIMARY KEY, balance INT CHECK (balance >= 0))")
        con.executemany("INSERT INTO acct VALUES (?, ?)", [(1, 100), (2, 100)])
        _transfer(con, atomic)
        out["transaction" if atomic else "autocommit"] = {
            "balances": [r[0] for r in con.execute("SELECT balance FROM acct ORDER BY id")],
            "total": con.execute("SELECT sum(balance) FROM acct").fetchone()[0]}
        con.close()
    return out


def check_string_concat_injection() -> dict:
    """값을 문자열로 이어 붙이면 입력이 SQL 이 된다. 플레이스홀더는 입력을 값으로만 다룬다."""
    con = _db()
    con.execute("CREATE TABLE member(name TEXT)")
    con.executemany("INSERT INTO member VALUES (?)", [("kim",), ("lee",), ("O'Brien",)])
    attack = "x' OR '1'='1"
    concat_rows = len(con.execute(f"SELECT name FROM member WHERE name = '{attack}'").fetchall())
    bound_rows = len(con.execute("SELECT name FROM member WHERE name = ?", (attack,)).fetchall())
    try:
        con.execute("SELECT name FROM member WHERE name = '%s'" % "O'Brien").fetchall()
        quote_error = ""
    except sqlite3.OperationalError as e:
        quote_error = str(e)
    bound_quote = con.execute("SELECT name FROM member WHERE name = ?", ("O'Brien",)).fetchall()
    con.close()
    return {"concat_rows": concat_rows, "bound_rows": bound_rows,
            "concat_quote_error": quote_error, "bound_quote": [r[0] for r in bound_quote]}


def check_placeholder_not_for_identifier() -> dict:
    """플레이스홀더는 값 자리에만 쓸 수 있다. 테이블명 자리에 넣으면 문 준비 단계에서 실패한다."""
    con = _db()
    con.execute("CREATE TABLE member(name TEXT)")
    try:
        con.execute("SELECT * FROM ?", ("member",))
        error = ""
    except sqlite3.OperationalError as e:
        error = str(e)
    con.close()
    return {"error": error}


def check_soft_delete_unique() -> dict:
    """deleted_at 소프트 삭제 테이블의 일반 UNIQUE 는 탈퇴한 이메일의 재가입을 막는다.
    살아 있는 행에만 거는 부분 유니크 인덱스는 재가입을 허용하고 활성 중복은 막는다."""
    out = {}
    for name, idx in {"plain_unique": "CREATE UNIQUE INDEX u_email ON u(email)",
                      "partial_unique": "CREATE UNIQUE INDEX u_email ON u(email) WHERE deleted_at IS NULL"}.items():
        con = _db()
        con.execute("CREATE TABLE u(id INTEGER PRIMARY KEY, email TEXT NOT NULL, deleted_at TEXT)")
        con.execute(idx)
        con.execute("INSERT INTO u(email, deleted_at) VALUES ('a@x', '2026-01-01')")
        result = {}
        for label, sql in {"rejoin": "INSERT INTO u(email) VALUES ('a@x')",
                           "active_duplicate": "INSERT INTO u(email) VALUES ('a@x')"}.items():
            try:
                con.execute(sql)
                result[label] = "ok"
            except sqlite3.IntegrityError:
                result[label] = "rejected"
        out[name] = result
        con.close()
    return out


# 단언 → (재현 함수, 관찰값이 문서와 맞는지)
EXPECT = {
    "CONSTRAINT-IN-DB": (check_constraint_catches_bypass,
                         lambda o: o["no_constraint"]["rejected"] == 0 and o["no_constraint"]["bad_rows"] == 3
                         and o["with_constraint"]["rejected"] == 3 and o["with_constraint"]["bad_rows"] == 0),
    "NULL-COMPARISON": (check_null_comparison,
                        lambda o: o["null_eq_null"] is None and o["eq_null_rows"] == 0
                        and o["is_null_rows"] == 2 and o["neq_rows"] == 0),
    "NOT-IN-NULL": (check_not_in_with_null, lambda o: o["not_in"] == [] and o["not_exists"] == [2, 3]),
    "UNIQUE-NULLS": (check_unique_allows_nulls,
                     lambda o: o["null_rows"] == 3 and "UNIQUE" in o["dup_error"]),
    "FK-NOT-INDEXED": (check_fk_not_auto_indexed,
                       lambda o: o["child_indexes"] == [] and o["plan_without"].startswith("SCAN")
                       and "child_parent" in o["plan_with"]),
    "FUNCTION-ON-COLUMN": (check_function_on_column,
                           lambda o: o["plain_index"].startswith("SCAN")
                           and "person_lower" in o["expression_index"]),
    "N-PLUS-ONE": (check_n_plus_one,
                   lambda o: o["loop_statements"] == o["customers"] + 1
                   and o["batched_statements"] == 2 and o["same_result"]),
    "OFFSET-DRIFT": (check_offset_paging_drift,
                     lambda o: o["offset_duplicates"] != [] and o["cursor_duplicates"] == []),
    "KEYSET-TIEBREAK": (check_keyset_tiebreak,
                        lambda o: o["key_only_missing"] != [] and o["pair_missing"] == []),
    "TX-ATOMICITY": (check_transaction_atomicity,
                     lambda o: o["autocommit"]["total"] == 700 and o["transaction"]["balances"] == [100, 100]),
    "CONCAT-INJECTION": (check_string_concat_injection,
                         lambda o: o["concat_rows"] == 3 and o["bound_rows"] == 0
                         and "syntax error" in o["concat_quote_error"] and o["bound_quote"] == ["O'Brien"]),
    "PLACEHOLDER-NOT-IDENTIFIER": (check_placeholder_not_for_identifier,
                                   lambda o: "syntax error" in o["error"]),
    "SOFT-DELETE-UNIQUE": (check_soft_delete_unique,
                           lambda o: o["plain_unique"]["rejoin"] == "rejected"
                           and o["partial_unique"] == {"rejoin": "ok", "active_duplicate": "rejected"}),
}


def run(claim: str) -> tuple[dict, bool]:
    fn, ok = EXPECT[claim]
    obs = fn()
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
