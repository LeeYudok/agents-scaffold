#!/usr/bin/env python3
"""SKILL.md 의 PostgreSQL 단언을 일회용 실제 서버에서 재현한다 (stdlib only).

    YD_PG_PSQL='podman exec -i ydpg-verify psql -U postgres' \\
        python3 .claude/skills/yd-pg-expert/scripts/verify_pg_claims.py

YD_PG_PSQL 은 표준입력으로 SQL 을 읽는 psql 명령 앞부분이다. 로컬은 버리는 컨테이너
(`podman run -d --rm --name ydpg-verify -e POSTGRES_PASSWORD=verify postgres:17`),
CI 는 서비스 컨테이너를 가리킨다. **운영 클러스터를 가리키지 않는다** — 단언마다 스키마를
만들고 지우며, 일부러 잠금을 잡고 타임아웃을 낸다.

각 check_* 함수는 관찰값 dict 를 돌려줄 뿐 판정하지 않는다. 판정은 EXPECT 한 곳에 있고,
테스트(tests/test_pg_claims.py)도 같은 함수를 불러 같은 관찰값을 검사한다.
하나라도 문서와 다르면 exit 1 이다 — 그때는 문서를 고칠지, 단언이 버전에 묶였다고 적을지
판단한다.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time

ENV = "YD_PG_PSQL"
# psql 출력 형식은 호출자가 준 옵션과 무관하게 여기서 고정한다.
HEADER = "\\set QUIET on\n\\set VERBOSITY verbose\n\\pset tuples_only on\n\\pset format unaligned\n"
SQLSTATE = re.compile(r"(?:ERROR|FATAL):\s+([0-9A-Z]{5}):")


def command() -> list[str]:
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        raise RuntimeError(f"{ENV} 가 비어 있다 — psql 명령 앞부분을 넣는다")
    return shlex.split(raw)


def _prelude(schema: str) -> str:
    return HEADER + f"\\set ON_ERROR_STOP off\nSET search_path TO {schema};\n"


def run_sql(schema: str, sql: str, timeout: float = 60) -> tuple[list[str], str]:
    """한 세션에서 SQL 을 실행하고 (출력 줄, stderr) 를 돌려준다. 오류가 나도 계속한다."""
    p = subprocess.run(command(), input=_prelude(schema) + sql, capture_output=True,
                       text=True, timeout=timeout)
    return [ln for ln in p.stdout.splitlines() if ln.strip()], p.stderr


def sqlstates(stderr: str) -> list[str]:
    return SQLSTATE.findall(stderr)


class Session:
    """동시성 단언용 장기 세션. sync() 는 앞선 문이 끝났음을 보장한다."""

    def __init__(self, schema: str):
        self.p = subprocess.Popen(command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, bufsize=1)
        self.n = 0
        self.send(_prelude(schema))
        self.sync()

    def send(self, sql: str) -> None:
        self.p.stdin.write(sql if sql.endswith("\n") else sql + "\n")
        self.p.stdin.flush()

    def sync(self) -> list[str]:
        """표식을 출력시키고 그때까지 나온 줄을 돌려준다. 막혀 있으면 여기서 기다린다."""
        self.n += 1
        mark = f"SYNC-{self.n}"
        self.send(f"SELECT '{mark}';")
        lines = []
        for line in self.p.stdout:
            if line.strip() == mark:
                return lines
            if line.strip():
                lines.append(line.strip())
        raise RuntimeError("psql 세션이 표식 전에 끝났다")

    def query(self, sql: str) -> list[str]:
        self.send(sql)
        return self.sync()

    def close(self) -> tuple[list[str], str]:
        out, err = self.p.communicate("\\q\n", timeout=30)
        return [ln for ln in out.splitlines() if ln.strip()], err


def fresh(schema: str) -> None:
    run_sql("public", f"DROP SCHEMA IF EXISTS {schema} CASCADE; CREATE SCHEMA {schema};")


def drop(schema: str) -> None:
    run_sql("public", f"DROP SCHEMA IF EXISTS {schema} CASCADE;")


def server_version() -> str:
    out, err = run_sql("public", "SHOW server_version;")
    return out[0] if out else f"(접속 실패) {err.strip()}"


def _relfilenode(table: str) -> str:
    return f"SELECT pg_relation_filenode('{table}');"


def _plan(sql: str) -> str:
    return f"EXPLAIN (COSTS OFF) {sql};"


# ---- 단언별 재현 -------------------------------------------------------------

def check_fk_not_indexed(s: str) -> dict:
    """PK·UNIQUE 는 인덱스가 자동으로 생기지만 FK 컬럼은 아니다."""
    out, _ = run_sql(s, """
        CREATE TABLE parent(id bigint PRIMARY KEY, code text UNIQUE);
        CREATE TABLE child(id bigint PRIMARY KEY, parent_id bigint REFERENCES parent(id));
        SELECT tablename || ':' || indexdef FROM pg_indexes
         WHERE schemaname = current_schema() ORDER BY 1;
    """)
    return {"indexes": out, "child_fk_indexed": any("child" in i and "parent_id" in i for i in out)}


def check_seq_scan_small_table(s: str) -> dict:
    """인덱스가 있어도 작은 테이블은 플래너가 Seq Scan 을 고른다."""
    out, _ = run_sql(s, """
        CREATE TABLE tiny(id int PRIMARY KEY, v text);
        INSERT INTO tiny SELECT g, 'v' || g FROM generate_series(1, 20) g;
        ANALYZE tiny;
    """ + _plan("SELECT v FROM tiny WHERE id > 3"))
    return {"plan": " / ".join(out)}


NAMES = """
    CREATE TABLE person(id int PRIMARY KEY, name text COLLATE "en_US.utf8", status text);
    INSERT INTO person SELECT g, 'Name' || g,
           CASE WHEN g % 100 = 0 THEN 'pending' ELSE 'done' END
      FROM generate_series(1, 20000) g;
"""


def check_lower_needs_expression_index(s: str) -> dict:
    """lower(name) 조건은 name 인덱스를 못 타고, lower(name) 표현식 인덱스는 탄다."""
    out, _ = run_sql(s, NAMES + """
        CREATE INDEX person_name ON person(name);
        ANALYZE person;
    """ + _plan("SELECT id FROM person WHERE lower(name) = 'name42'") + """
        SELECT '--';
        CREATE INDEX person_lower_name ON person(lower(name));
        ANALYZE person;
    """ + _plan("SELECT id FROM person WHERE lower(name) = 'name42'"))
    cut = out.index("--")
    return {"plain_index": " / ".join(out[:cut]), "expression_index": " / ".join(out[cut + 1:])}


def check_like_prefix_needs_pattern_ops(s: str) -> dict:
    """C 가 아닌 콜레이션 컬럼의 일반 인덱스는 LIKE 'abc%' 에 쓰이지 않는다."""
    out, _ = run_sql(s, NAMES + """
        CREATE INDEX person_name ON person(name);
        ANALYZE person;
    """ + _plan("SELECT id FROM person WHERE name LIKE 'Name42%'") + """
        SELECT '--';
        CREATE INDEX person_name_pattern ON person(name text_pattern_ops);
        ANALYZE person;
    """ + _plan("SELECT id FROM person WHERE name LIKE 'Name42%'"))
    cut = out.index("--")
    return {"plain_index": " / ".join(out[:cut]), "pattern_ops": " / ".join(out[cut + 1:])}


def check_partial_index(s: str) -> dict:
    """부분 인덱스는 조회 조건이 인덱스 조건을 함의할 때만 쓰인다."""
    out, _ = run_sql(s, NAMES + """
        CREATE INDEX person_pending ON person(id) WHERE status = 'pending';
        ANALYZE person;
    """ + _plan("SELECT id FROM person WHERE status = 'pending' AND id < 5000") + """
        SELECT '--';
    """ + _plan("SELECT id FROM person WHERE status = 'done' AND id < 50"))
    cut = out.index("--")
    return {"pending": " / ".join(out[:cut]), "done": " / ".join(out[cut + 1:])}


def check_timestamp_drops_offset(s: str) -> dict:
    """timestamp 는 입력의 오프셋을 버리고, timestamptz 는 같은 순간을 유지한다."""
    out, _ = run_sql(s, """
        SET TIME ZONE 'Asia/Seoul';
        CREATE TABLE ev(naive timestamp, aware timestamptz);
        INSERT INTO ev VALUES ('2026-01-01 09:00:00+09', '2026-01-01 09:00:00+09');
        SET TIME ZONE 'UTC';
        SELECT naive::text, aware::text,
               extract(epoch FROM naive)::bigint - extract(epoch FROM aware)::bigint FROM ev;
    """)
    naive, aware, gap = out[0].split("|")
    return {"naive": naive, "aware": aware, "gap_seconds": int(gap)}


def check_float_vs_numeric(s: str) -> dict:
    """float 는 0.1 + 0.2 가 0.3 이 아니고, numeric 은 정확하다."""
    out, _ = run_sql(s, """
        SELECT (0.1::float8 + 0.2::float8 = 0.3::float8)::text,
               (0.1::numeric + 0.2::numeric = 0.3::numeric)::text,
               (SELECT sum(0.1::float8) FROM generate_series(1, 10))::text,
               (SELECT sum(0.1::numeric) FROM generate_series(1, 10))::text;
    """)
    f_eq, n_eq, f_sum, n_sum = out[0].split("|")
    return {"float_equal": f_eq, "numeric_equal": n_eq, "float_sum_10": f_sum, "numeric_sum_10": n_sum}


def _rewrites(s: str, setup: str, alters: dict[str, str]) -> dict:
    """ALTER 마다 relfilenode 가 바뀌었는지(테이블을 새로 썼는지) 본다."""
    sql = setup
    for name, alter in alters.items():
        sql += f"SELECT '{name}', pg_relation_filenode('w');\n{alter}\nSELECT '{name}', pg_relation_filenode('w');\n"
    out, err = run_sql(s, sql)
    seen: dict[str, list[str]] = {}
    for line in out:
        name, node = line.split("|")
        seen.setdefault(name, []).append(node)
    result = {name: (nodes[0] != nodes[1]) if len(nodes) == 2 else None for name, nodes in seen.items()}
    result["errors"] = sqlstates(err)
    return result


W = """
    CREATE TABLE w(id int PRIMARY KEY, n int, label varchar(10));
    INSERT INTO w SELECT g, g, 'x' FROM generate_series(1, 1000) g;
"""


def check_add_column_rewrites(s: str) -> dict:
    """기본값 없는 컬럼·상수 기본값 컬럼은 다시 쓰지 않고, volatile 기본값은 다시 쓴다."""
    return _rewrites(s, W, {
        "nullable": "ALTER TABLE w ADD COLUMN a text;",
        "const_default": "ALTER TABLE w ADD COLUMN b int NOT NULL DEFAULT 0;",
        "volatile_default": "ALTER TABLE w ADD COLUMN c timestamptz DEFAULT clock_timestamp();",
    })


def check_alter_type_rewrites(s: str) -> dict:
    """int→bigint 는 다시 쓰고, varchar 길이 확장과 varchar→text 는 다시 쓰지 않는다."""
    return _rewrites(s, W, {
        "int_to_bigint": "ALTER TABLE w ALTER COLUMN n TYPE bigint;",
        "varchar_widen": "ALTER TABLE w ALTER COLUMN label TYPE varchar(20);",
        "varchar_to_text": "ALTER TABLE w ALTER COLUMN label TYPE text;",
    })


def check_set_not_null(s: str) -> dict:
    """SET NOT NULL 은 다시 쓰지 않지만 ACCESS EXCLUSIVE 를 잡고 검사한다.
    검증된 CHECK (col IS NOT NULL) 이 있으면 검사를 건너뛴다."""
    r = _rewrites(s, W, {"set_not_null": "ALTER TABLE w ALTER COLUMN n SET NOT NULL;"})
    out, err = run_sql(s, """
        BEGIN;
        ALTER TABLE w ALTER COLUMN n DROP NOT NULL;
        ALTER TABLE w ALTER COLUMN n SET NOT NULL;
        SELECT mode FROM pg_locks WHERE relation = 'w'::regclass AND pid = pg_backend_pid()
         ORDER BY mode;
        ROLLBACK;
        ALTER TABLE w ALTER COLUMN n DROP NOT NULL;
        ALTER TABLE w ADD CONSTRAINT w_n_nn CHECK (n IS NOT NULL) NOT VALID;
        ALTER TABLE w VALIDATE CONSTRAINT w_n_nn;
        SET client_min_messages = debug1;
        ALTER TABLE w ALTER COLUMN n SET NOT NULL;
    """)
    return {"rewrites": r["set_not_null"], "locks": out,
            "skipped_scan": "sufficient to prove" in err}


def check_not_valid_constraint(s: str) -> dict:
    """NOT VALID 제약은 기존 행을 검사하지 않고 새 행만 막는다. VALIDATE 는 기존 행을 검사하고,
    쓰기를 막지 않는 SHARE UPDATE EXCLUSIVE 잠금으로 돈다."""
    _, err = run_sql(s, """
        CREATE TABLE acct(id int PRIMARY KEY, balance int);
        INSERT INTO acct VALUES (1, -5);
        ALTER TABLE acct ADD CONSTRAINT bal_ok CHECK (balance >= 0) NOT VALID;
        INSERT INTO acct VALUES (2, -1);
        ALTER TABLE acct VALIDATE CONSTRAINT bal_ok;
    """)
    out, err2 = run_sql(s, """
        SELECT count(*) FROM acct;
        DELETE FROM acct WHERE balance < 0;
        BEGIN;
        ALTER TABLE acct VALIDATE CONSTRAINT bal_ok;
        SELECT mode FROM pg_locks WHERE relation = 'acct'::regclass AND pid = pg_backend_pid();
        COMMIT;
        SELECT convalidated::text FROM pg_constraint WHERE conname = 'bal_ok';
    """)
    return {"errors": sqlstates(err), "rows_kept": int(out[0]), "validate_lock": out[1:-1],
            "validated_after_cleanup": out[-1], "cleanup_errors": sqlstates(err2)}


def check_cic_in_transaction(s: str) -> dict:
    """CREATE INDEX CONCURRENTLY 는 트랜잭션 블록 안에서 실패한다."""
    _, err = run_sql(s, """
        CREATE TABLE t(id int);
        BEGIN;
        CREATE INDEX CONCURRENTLY t_id ON t(id);
        ROLLBACK;
    """)
    out, err2 = run_sql(s, "CREATE INDEX CONCURRENTLY t_id ON t(id); SELECT count(*) FROM pg_indexes WHERE indexname = 't_id';")
    return {"in_tx_errors": sqlstates(err), "outside_errors": sqlstates(err2), "index_count": out[0]}


def check_create_index_blocks_writes(s: str) -> dict:
    """일반 CREATE INDEX 는 SHARE 잠금으로 쓰기를 막고, CONCURRENTLY 는 막지 않는다."""
    run_sql(s, "CREATE TABLE t(id int); INSERT INTO t SELECT generate_series(1, 1000);")
    a = Session(s)
    a.query("BEGIN; CREATE INDEX t_id ON t(id);")
    locks = a.query("SELECT mode FROM pg_locks WHERE relation = 't'::regclass AND pid = pg_backend_pid() ORDER BY mode;")
    _, err = run_sql(s, "SET lock_timeout = '300ms'; INSERT INTO t VALUES (0); SELECT 1;")
    a.query("ROLLBACK;")
    a.close()
    return {"locks": locks, "writer_errors": sqlstates(err)}


def check_explain_analyze_executes(s: str) -> dict:
    """EXPLAIN ANALYZE 는 문을 실제로 실행한다. BEGIN … ROLLBACK 으로 감싸야 되돌린다."""
    out, _ = run_sql(s, """
        CREATE TABLE t(id int);
        INSERT INTO t SELECT generate_series(1, 10);
        EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY OFF) DELETE FROM t WHERE id <= 4;
        SELECT 'after_plain=' || count(*) FROM t;
        BEGIN;
        EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY OFF) DELETE FROM t;
        ROLLBACK;
        SELECT 'after_rollback=' || count(*) FROM t;
    """)
    vals = dict(line.split("=") for line in out if "=" in line and line.startswith("after"))
    return {"after_plain": int(vals["after_plain"]), "after_rollback": int(vals["after_rollback"])}


def check_serialization_failure(s: str) -> dict:
    """SERIALIZABLE 에서 서로의 읽기에 의존한 두 쓰기 중 하나는 40001 로 실패한다."""
    run_sql(s, "CREATE TABLE duty(doctor text, on_call bool); INSERT INTO duty VALUES ('a', true), ('b', true);")
    a, b = Session(s), Session(s)
    for x in (a, b):
        x.query("BEGIN ISOLATION LEVEL SERIALIZABLE; SELECT count(*) FROM duty WHERE on_call;")
    a.query("UPDATE duty SET on_call = false WHERE doctor = 'a';")
    b.query("UPDATE duty SET on_call = false WHERE doctor = 'b';")
    a.query("COMMIT;")
    b.query("COMMIT;")
    _, err_a = a.close()
    _, err_b = b.close()
    out, _ = run_sql(s, "SELECT count(*) FROM duty WHERE on_call;")
    return {"a_errors": sqlstates(err_a), "b_errors": sqlstates(err_b), "on_call_after": int(out[0])}


def check_read_committed_no_error(s: str) -> dict:
    """같은 흐름을 기본 격리수준(Read Committed)에서 돌리면 둘 다 커밋되어 규칙이 깨진다."""
    run_sql(s, "CREATE TABLE duty(doctor text, on_call bool); INSERT INTO duty VALUES ('a', true), ('b', true);")
    a, b = Session(s), Session(s)
    for x in (a, b):
        x.query("BEGIN; SELECT count(*) FROM duty WHERE on_call;")
    a.query("UPDATE duty SET on_call = false WHERE doctor = 'a';")
    b.query("UPDATE duty SET on_call = false WHERE doctor = 'b';")
    a.query("COMMIT;")
    b.query("COMMIT;")
    _, err_a = a.close()
    _, err_b = b.close()
    out, _ = run_sql(s, "SELECT count(*) FROM duty WHERE on_call;")
    return {"errors": sqlstates(err_a) + sqlstates(err_b), "on_call_after": int(out[0])}


def _vacuum_removed(s: str) -> tuple[int, int]:
    """VACUUM VERBOSE 의 (제거한 튜플, 아직 못 지우는 죽은 튜플)."""
    _, err = run_sql(s, "VACUUM (VERBOSE) v;")
    m = re.search(r"tuples: (\d+) removed, \d+ remain, (\d+) are dead but not yet removable", err)
    if not m:
        raise RuntimeError(f"VACUUM VERBOSE 출력에서 튜플 줄을 못 찾았다: {err[-400:]}")
    return int(m.group(1)), int(m.group(2))


def _vacuum_with_holder(s: str, holder_sql: str) -> dict:
    # autovacuum 이 끼어들어 먼저 지우면 관찰값이 흔들리므로 이 테이블만 끈다.
    run_sql(s, "CREATE TABLE v(id int) WITH (autovacuum_enabled = false);"
               " INSERT INTO v SELECT generate_series(1, 1000);")
    h = Session(s)
    h.query(holder_sql)
    run_sql(s, "DELETE FROM v WHERE id <= 500;")
    held = _vacuum_removed(s)
    h.query("COMMIT;")
    h.close()
    released = _vacuum_removed(s)
    return {"while_open": {"removed": held[0], "not_removable": held[1]},
            "after_commit": {"removed": released[0], "not_removable": released[1]}}


def check_long_tx_blocks_vacuum(s: str) -> dict:
    """xid 를 받았거나 REPEATABLE READ 스냅숏을 쥔 채 열린 트랜잭션은
    그 뒤에 생긴 죽은 튜플을 VACUUM 이 못 지우게 한다."""
    xid = _vacuum_with_holder(s, "BEGIN; SELECT pg_current_xact_id() IS NOT NULL;")
    run_sql(s, "DROP TABLE v;")
    rr = _vacuum_with_holder(s, "BEGIN ISOLATION LEVEL REPEATABLE READ; SELECT count(*) FROM v;")
    return {"xid_holder": xid, "repeatable_read_holder": rr}


def check_idle_read_committed_vacuum(s: str) -> dict:
    """읽기만 하고 멈춘 Read Committed 트랜잭션은 스냅숏을 붙잡지 않아 VACUUM 을 막지 않는다."""
    return _vacuum_with_holder(s, "BEGIN; SELECT count(*) FROM v;")


def _wait_for_lock_wait(s: str, query_prefix: str, limit: float = 10) -> None:
    """다른 세션의 문이 잠금 대기에 들어갈 때까지 기다린다. sleep 추측보다 결정적이다."""
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        out, _ = run_sql(s, "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'"
                            f" AND query LIKE '{query_prefix}%';")
        if out and out[0] != "0":
            return
        time.sleep(0.1)
    raise RuntimeError(f"'{query_prefix}' 가 {limit}초 안에 잠금 대기에 들어가지 않았다")


def check_lock_queue(s: str) -> dict:
    """idle in transaction 뒤에서 기다리는 ALTER 가 뒤따르는 단순 SELECT 까지 막는다.
    ALTER 에 lock_timeout 을 걸면 ALTER 만 실패하고 SELECT 는 지나간다."""
    run_sql(s, "CREATE TABLE q(id int); INSERT INTO q VALUES (1);")
    idle = Session(s)
    idle.query("BEGIN; SELECT count(*) FROM q;")
    alter = Session(s)
    alter.send("ALTER TABLE q ADD COLUMN x int;")
    _wait_for_lock_wait(s, "ALTER TABLE q ADD COLUMN x")
    _, err_blocked = run_sql(s, "SET statement_timeout = '500ms'; SELECT count(*) FROM q;")
    idle.query("ROLLBACK;")
    alter.sync()
    alter.close()
    idle.query("BEGIN; SELECT count(*) FROM q;")
    _, err_alter = run_sql(s, "SET lock_timeout = '300ms'; ALTER TABLE q ADD COLUMN y int;")
    out, err_reader = run_sql(s, "SET statement_timeout = '500ms'; SELECT count(*) FROM q;")
    idle.query("ROLLBACK;")
    idle.close()
    return {"reader_behind_queued_alter": sqlstates(err_blocked),
            "alter_with_lock_timeout": sqlstates(err_alter),
            "reader_after_timeout": sqlstates(err_reader), "reader_rows": out}


def check_unique_nulls(s: str) -> dict:
    """UNIQUE 는 기본적으로 NULL 을 여러 개 허용하고, PG15+ NULLS NOT DISTINCT 는 막는다."""
    _, err = run_sql(s, """
        CREATE TABLE d(email text UNIQUE);
        INSERT INTO d VALUES (NULL), (NULL);
        CREATE TABLE nd(email text UNIQUE NULLS NOT DISTINCT);
        INSERT INTO nd VALUES (NULL);
        INSERT INTO nd VALUES (NULL);
    """)
    out, _ = run_sql(s, "SELECT count(*) FROM d; SELECT count(*) FROM nd;")
    return {"default_rows": int(out[0]), "nulls_not_distinct_rows": int(out[1]), "errors": sqlstates(err)}


# 단언 → (재현 함수, 관찰값이 문서와 맞는지)
EXPECT = {
    "FK-NOT-INDEXED": (check_fk_not_indexed, lambda o: not o["child_fk_indexed"] and len(o["indexes"]) == 3),
    "SEQSCAN-SMALL-TABLE": (check_seq_scan_small_table, lambda o: o["plan"].startswith("Seq Scan")),
    "LOWER-EXPRESSION-INDEX": (check_lower_needs_expression_index,
                               lambda o: "person_name" not in o["plain_index"]
                               and "person_lower_name" in o["expression_index"]),
    "LIKE-PATTERN-OPS": (check_like_prefix_needs_pattern_ops,
                         lambda o: o["plain_index"].startswith("Seq Scan")
                         and "person_name_pattern" in o["pattern_ops"]),
    "PARTIAL-INDEX": (check_partial_index,
                      lambda o: "person_pending" in o["pending"] and "person_pending" not in o["done"]),
    "TIMESTAMP-DROPS-OFFSET": (check_timestamp_drops_offset,
                               lambda o: o["naive"] == "2026-01-01 09:00:00"
                               and o["aware"] == "2026-01-01 00:00:00+00" and o["gap_seconds"] == 32400),
    "FLOAT-MONEY": (check_float_vs_numeric,
                    lambda o: o["float_equal"] == "false" and o["numeric_equal"] == "true"
                    and o["float_sum_10"] != "1" and o["numeric_sum_10"] == "1.0"),
    "ADD-COLUMN-NO-REWRITE": (check_add_column_rewrites,
                              lambda o: o["nullable"] is False and o["const_default"] is False
                              and o["errors"] == []),
    "VOLATILE-DEFAULT-REWRITES": (check_add_column_rewrites, lambda o: o["volatile_default"] is True),
    "ALTER-TYPE-REWRITES": (check_alter_type_rewrites, lambda o: o["int_to_bigint"] is True),
    "VARCHAR-WIDEN-NO-REWRITE": (check_alter_type_rewrites,
                                 lambda o: o["varchar_widen"] is False and o["varchar_to_text"] is False
                                 and o["errors"] == []),
    "SET-NOT-NULL-SCAN": (check_set_not_null,
                          lambda o: o["rewrites"] is False and "AccessExclusiveLock" in o["locks"]
                          and o["skipped_scan"]),
    "NOT-VALID-CONSTRAINT": (check_not_valid_constraint,
                             lambda o: o["errors"] == ["23514", "23514"] and o["rows_kept"] == 1
                             and o["validate_lock"] == ["ShareUpdateExclusiveLock"]
                             and o["validated_after_cleanup"] == "true" and o["cleanup_errors"] == []),
    "CIC-IN-TRANSACTION": (check_cic_in_transaction,
                           lambda o: o["in_tx_errors"] == ["25001"] and o["outside_errors"] == []
                           and o["index_count"] == "1"),
    "CREATE-INDEX-BLOCKS-WRITES": (check_create_index_blocks_writes,
                                   lambda o: "ShareLock" in o["locks"] and o["writer_errors"] == ["55P03"]),
    "EXPLAIN-ANALYZE-EXECUTES": (check_explain_analyze_executes,
                                 lambda o: o["after_plain"] == 6 and o["after_rollback"] == 6),
    "SERIALIZATION-RETRY": (check_serialization_failure,
                            lambda o: o["a_errors"] == [] and o["b_errors"] == ["40001"]
                            and o["on_call_after"] == 1),
    "READ-COMMITTED-WRITE-SKEW": (check_read_committed_no_error,
                                  lambda o: o["errors"] == [] and o["on_call_after"] == 0),
    "LONG-TX-BLOCKS-VACUUM": (check_long_tx_blocks_vacuum,
                              lambda o: all(h["while_open"]["not_removable"] == 500
                                           and h["after_commit"]["removed"] == 500 for h in o.values())),
    "IDLE-RC-NO-VACUUM-BLOCK": (check_idle_read_committed_vacuum,
                                lambda o: o["while_open"]["removed"] == 500),
    "LOCK-QUEUE": (check_lock_queue,
                   lambda o: o["reader_behind_queued_alter"] == ["57014"]
                   and o["alter_with_lock_timeout"] == ["55P03"] and o["reader_after_timeout"] == []
                   and o["reader_rows"] == ["1"]),
    "UNIQUE-NULLS": (check_unique_nulls,
                     lambda o: o["default_rows"] == 2 and o["nulls_not_distinct_rows"] == 1
                     and o["errors"] == ["23505"]),
}


def run(claim: str) -> tuple[dict, bool]:
    fn, ok = EXPECT[claim]
    schema = "yd_" + claim.lower().replace("-", "_")
    fresh(schema)
    try:
        obs = fn(schema)
    finally:
        drop(schema)
    return obs, bool(ok(obs))


def main() -> int:
    print(f"postgres {server_version()} · python {sys.version.split()[0]}")
    failed = 0
    for claim in EXPECT:
        obs, ok = run(claim)
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {claim}: {obs}")
    print(f"{len(EXPECT) - failed}/{len(EXPECT)} 단언 재현")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
