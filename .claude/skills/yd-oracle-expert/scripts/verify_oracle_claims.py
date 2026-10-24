#!/usr/bin/env python3
"""SKILL.md 의 Oracle 단언을 실제 Oracle 에서 재현한다 (stdlib only).

    export YD_ORACLE_SQLPLUS="podman exec -i ydora-verify sqlplus -S -L system/verify@//localhost/FREEPDB1"
    python3 .claude/skills/yd-oracle-expert/scripts/verify_oracle_claims.py

YD_ORACLE_SQLPLUS 는 표준 입력으로 SQL 스크립트를 받는 명령이다. 버리는 컨테이너
(gvenzl/oracle-free 등)에만 연결한다 — 검증기는 ydv_ 로 시작하는 테이블·프로시저를
만들고 지운다.

각 check_* 함수는 관찰값 dict 를 돌려줄 뿐 판정하지 않는다. 판정은 EXPECT 한 곳에 있고,
테스트(tests/test_oracle_claims.py)도 같은 함수를 불러 같은 관찰값을 검사한다. 하나라도
문서와 다르면 exit 1 이다 — 그때는 문서를 고칠지, 단언이 버전에 묶였다고 적을지 판단한다.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import uuid

ENV = "YD_ORACLE_SQLPLUS"

# 출력에서 값만 남기고, 오류가 나도 다음 문장으로 넘어가 ORA- 코드를 모은다.
PREAMBLE = """SET HEADING OFF
SET FEEDBACK OFF
SET PAGESIZE 0
SET LINESIZE 4000
SET TRIMOUT ON
SET DEFINE OFF
SET SQLBLANKLINES ON
SET SERVEROUTPUT ON
WHENEVER OSERROR EXIT 9
WHENEVER SQLERROR CONTINUE
"""

ORA_RE = re.compile(r"\b(ORA-\d{5}|SP2-\d{4})\b")
KV_RE = re.compile(r"^([a-z_0-9]+)=(.*)$")


class OracleUnavailable(RuntimeError):
    """YD_ORACLE_SQLPLUS 가 없거나 접속에 실패했다."""


def command() -> list[str]:
    cmd = os.environ.get(ENV, "").strip()
    if not cmd:
        raise OracleUnavailable(f"{ENV} 가 설정되지 않았다")
    return shlex.split(cmd)


def sqlplus(script: str, preamble: bool = True) -> tuple[int, str]:
    """스크립트를 실행하고 (종료 코드, 표준 출력+오류) 를 돌려준다."""
    body = (PREAMBLE if preamble else "") + script.strip() + "\nEXIT\n"
    try:
        p = subprocess.run(command(), input=body, capture_output=True, text=True, timeout=180)
    except FileNotFoundError as e:
        raise OracleUnavailable(f"{ENV} 명령을 실행할 수 없다: {e}") from e
    out = p.stdout + p.stderr
    if "SP2-0751" in out or "ORA-01017" in out or "ORA-12541" in out or "ORA-12514" in out:
        raise OracleUnavailable(f"Oracle 접속 실패: {out.strip()[:300]}")
    return p.returncode, out


def run(script: str) -> dict[str, dict]:
    """PROMPT @@이름 으로 나눈 구간마다 {"kv": 값, "ora": 오류 코드 목록, "text": 원문} 을 만든다."""
    _, out = sqlplus(script)
    parts: dict[str, dict] = {}
    name = "_"
    for line in out.splitlines():
        if line.startswith("@@"):
            name = line[2:].strip()
            # 출력이 없는 구간(오류 없이 끝난 INSERT 등)도 빈 구간으로 남긴다
            parts.setdefault(name, {"kv": {}, "ora": [], "text": ""})
            continue
        sec = parts.setdefault(name, {"kv": {}, "ora": [], "text": ""})
        sec["text"] += line + "\n"
        sec["ora"] += ORA_RE.findall(line)
        m = KV_RE.match(line.strip())
        if m:
            sec["kv"][m.group(1)] = m.group(2)
    return parts


def check_empty_string_null() -> dict:
    """'' 는 NULL 이다. = '' 는 0행이고 NOT NULL 컬럼에 '' 를 넣으면 ORA-01400 이다."""
    p = run("""
DROP TABLE IF EXISTS ydv_e PURGE;
CREATE TABLE ydv_e (s VARCHAR2(10), nn VARCHAR2(10) NOT NULL);
PROMPT @@is_null
SELECT 'is_null=' || CASE WHEN '' IS NULL THEN 'Y' ELSE 'N' END FROM dual;
INSERT INTO ydv_e VALUES ('', 'x');
PROMPT @@not_null
INSERT INTO ydv_e VALUES ('a', '');
PROMPT @@count
SELECT 'eq_empty=' || count(*) FROM ydv_e WHERE s = '';
SELECT 'is_null_rows=' || count(*) FROM ydv_e WHERE s IS NULL;
DROP TABLE ydv_e PURGE;
""")
    return {"is_null": p["is_null"]["kv"].get("is_null"), "not_null_error": p["not_null"]["ora"],
            **p["count"]["kv"]}


def check_concat_null() -> dict:
    """'a' || NULL 은 NULL 이 아니라 'a' 다."""
    p = run("PROMPT @@c\nSELECT 'concat=[' || ('a' || NULL) || ']' FROM dual;")
    return p["c"]["kv"]


def check_date_has_time() -> dict:
    """DATE 는 시각을 담아 날짜 리터럴 등호 비교가 행을 놓친다. 범위 조건은 찾는다."""
    p = run("""
DROP TABLE IF EXISTS ydv_d PURGE;
CREATE TABLE ydv_d (d DATE);
INSERT INTO ydv_d VALUES (TO_DATE('2026-10-04 13:45:00', 'YYYY-MM-DD HH24:MI:SS'));
PROMPT @@q
SELECT 'equal=' || count(*) FROM ydv_d WHERE d = DATE '2026-10-04';
SELECT 'range=' || count(*) FROM ydv_d WHERE d >= DATE '2026-10-04' AND d < DATE '2026-10-05';
SELECT 'time=' || TO_CHAR(d, 'HH24:MI:SS') FROM ydv_d;
DROP TABLE ydv_d PURGE;
""")
    return p["q"]["kv"]


def check_nls_date_format() -> dict:
    """형식 없는 TO_DATE 는 세션 NLS_DATE_FORMAT 에 따라 실패하거나 통과한다."""
    p = run("""
ALTER SESSION SET NLS_DATE_FORMAT = 'DD-MON-RR';
PROMPT @@dmy
SELECT 'v=' || TO_CHAR(TO_DATE('2026-10-04'), 'YYYYMMDD') FROM dual;
SELECT 'explicit=' || TO_CHAR(TO_DATE('2026-10-04', 'YYYY-MM-DD'), 'YYYYMMDD') FROM dual;
ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD';
PROMPT @@ymd
SELECT 'v=' || TO_CHAR(TO_DATE('2026-10-04'), 'YYYYMMDD') FROM dual;
""")
    return {"dmy_error": p["dmy"]["ora"], "dmy_explicit": p["dmy"]["kv"].get("explicit"),
            "ymd_value": p["ymd"]["kv"].get("v")}


def check_varchar2_bytes() -> dict:
    """VARCHAR2(10) 은 바이트라 한글 4자(12바이트)를 거부하고, 10 CHAR 는 받는다."""
    p = run("""
DROP TABLE IF EXISTS ydv_v PURGE;
CREATE TABLE ydv_v (b VARCHAR2(10), c VARCHAR2(10 CHAR));
PROMPT @@byte
INSERT INTO ydv_v (b) VALUES ('가나다라');
PROMPT @@char
INSERT INTO ydv_v (c) VALUES ('가나다라');
PROMPT @@q
SELECT 'bytes=' || LENGTHB('가나다라') FROM dual;
SELECT 'rows=' || count(*) FROM ydv_v;
DROP TABLE ydv_v PURGE;
""")
    return {"byte_error": p["byte"]["ora"], "char_error": p["char"]["ora"], **p["q"]["kv"]}


def check_varchar2_4000_cap() -> dict:
    """VARCHAR2(4000 CHAR) 도 4000바이트에서 막히고, SQL 함수 결과는 그 상한에서 잘린다."""
    p = run("""
DROP TABLE IF EXISTS ydv_v PURGE;
CREATE TABLE ydv_v (c VARCHAR2(4000 CHAR));
PROMPT @@param
SELECT 'max_string_size=' || value FROM v$parameter WHERE name = 'max_string_size';
PROMPT @@fit
DECLARE s VARCHAR2(32767);
BEGIN FOR i IN 1..1333 LOOP s := s || '가'; END LOOP; INSERT INTO ydv_v VALUES (s); END;
/
PROMPT @@over
DECLARE s VARCHAR2(32767);
BEGIN FOR i IN 1..1334 LOOP s := s || '가'; END LOOP; INSERT INTO ydv_v VALUES (s); END;
/
PROMPT @@q
SELECT 'rows=' || count(*) FROM ydv_v;
SELECT 'replace_len=' || LENGTH(REPLACE(RPAD('x', 1334, 'x'), 'x', '가')) FROM dual;
DROP TABLE ydv_v PURGE;
""")
    return {"max_string_size": p["param"]["kv"].get("max_string_size"),
            "fit_error": p["fit"]["ora"], "over_error": p["over"]["ora"], **p["q"]["kv"]}


def check_number_scale() -> dict:
    """NUMBER(5,2) 는 소수 자리를 조용히 반올림하고 정수부 초과만 ORA-01438 로 거부한다."""
    p = run("""
DROP TABLE IF EXISTS ydv_n PURGE;
CREATE TABLE ydv_n (v NUMBER(5,2));
PROMPT @@round
INSERT INTO ydv_n VALUES (123.456);
SELECT 'stored=' || TO_CHAR(v) FROM ydv_n;
PROMPT @@over
INSERT INTO ydv_n VALUES (1234.5);
DROP TABLE ydv_n PURGE;
""")
    return {"round_error": p["round"]["ora"], "stored": p["round"]["kv"].get("stored"),
            "over_error": p["over"]["ora"]}


def check_identifier_uppercase() -> dict:
    """따옴표 없는 식별자는 대문자로 접히고, 소문자 따옴표 이름은 ORA-00904 다."""
    p = run("""
DROP TABLE IF EXISTS ydv_c PURGE;
CREATE TABLE ydv_c (Name NUMBER);
PROMPT @@dict
SELECT 'column=' || column_name FROM user_tab_columns WHERE table_name = 'YDV_C';
PROMPT @@quoted
SELECT "name" FROM ydv_c;
PROMPT @@plain
SELECT 'plain=' || count(name) FROM ydv_c;
DROP TABLE ydv_c PURGE;
""")
    return {"column": p["dict"]["kv"].get("column"), "quoted_error": p["quoted"]["ora"],
            "plain": p["plain"]["kv"].get("plain"), "plain_error": p["plain"]["ora"]}


def check_identifier_bytes() -> dict:
    """식별자 상한은 128바이트다. 한글은 3바이트라 접두어 ydv_ + 41자는 되고 42자는 안 된다."""
    ok_ascii, bad_ascii = "ydv_" + "a" * 124, "ydv_" + "a" * 125
    ok_ko, bad_ko = "ydv_" + "가" * 41, "ydv_" + "가" * 42
    p = run(f"""
PROMPT @@ok_ascii
CREATE TABLE {ok_ascii} (x NUMBER);
DROP TABLE IF EXISTS {ok_ascii} PURGE;
PROMPT @@bad_ascii
CREATE TABLE {bad_ascii} (x NUMBER);
PROMPT @@ok_ko
CREATE TABLE {ok_ko} (x NUMBER);
DROP TABLE IF EXISTS {ok_ko} PURGE;
PROMPT @@bad_ko
CREATE TABLE {bad_ko} (x NUMBER);
""")
    return {k: p[k]["ora"] for k in ("ok_ascii", "bad_ascii", "ok_ko", "bad_ko")}


def check_limit_unsupported() -> dict:
    """LIMIT 은 문법 오류다."""
    p = run("PROMPT @@q\nSELECT 1 FROM dual LIMIT 1;")
    return {"error": p["q"]["ora"]}


def _ten_rows() -> str:
    return """
DROP TABLE IF EXISTS ydv_r PURGE;
CREATE TABLE ydv_r (x NUMBER);
BEGIN FOR i IN 1..10 LOOP INSERT INTO ydv_r VALUES (i); END LOOP; COMMIT; END;
/
"""


def check_rownum_before_order() -> dict:
    """ROWNUM 은 ORDER BY 전에 붙어 '상위 3개' 가 아닌 행을 돌려준다. FETCH FIRST 는 맞다."""
    p = run(_ten_rows() + """
PROMPT @@q
SELECT 'rownum=' || LISTAGG(x, ',') WITHIN GROUP (ORDER BY x DESC)
  FROM (SELECT x FROM ydv_r WHERE ROWNUM <= 3 ORDER BY x DESC);
SELECT 'fetch_first=' || LISTAGG(x, ',') WITHIN GROUP (ORDER BY x DESC)
  FROM (SELECT x FROM ydv_r ORDER BY x DESC FETCH FIRST 3 ROWS ONLY);
DROP TABLE ydv_r PURGE;
""")
    return p["q"]["kv"]


def check_rownum_greater_than() -> dict:
    """WHERE ROWNUM > 1 은 언제나 0행이다."""
    p = run(_ten_rows() + """
PROMPT @@q
SELECT 'gt1=' || count(*) FROM ydv_r WHERE ROWNUM > 1;
DROP TABLE ydv_r PURGE;
""")
    return p["q"]["kv"]


def check_ddl_implicit_commit() -> dict:
    """DDL 은 앞선 INSERT 를 커밋한다. ORA-00955 로 실패해도 커밋되고, 문법 오류면 안 된다."""
    p = run("""
DROP TABLE IF EXISTS ydv_t PURGE;
CREATE TABLE ydv_t (id NUMBER);
PROMPT @@semantic
INSERT INTO ydv_t VALUES (1);
CREATE TABLE ydv_t (id NUMBER);
ROLLBACK;
SELECT 'rows=' || count(*) FROM ydv_t;
PROMPT @@syntax
INSERT INTO ydv_t VALUES (2);
CREATE TABLEX ydv_t2 (id NUMBER);
ROLLBACK;
SELECT 'rows=' || count(*) FROM ydv_t;
DROP TABLE ydv_t PURGE;
""")
    return {"semantic_error": p["semantic"]["ora"], "rows_after_semantic": p["semantic"]["kv"].get("rows"),
            "syntax_error": p["syntax"]["ora"], "rows_after_syntax": p["syntax"]["kv"].get("rows")}


_SERIAL_SETUP = """
DROP TABLE IF EXISTS ydv_s PURGE;
CREATE TABLE ydv_s (k NUMBER PRIMARY KEY, v NUMBER);
INSERT INTO ydv_s VALUES (1, 0);
COMMIT;
CREATE OR REPLACE PROCEDURE ydv_bump AS PRAGMA AUTONOMOUS_TRANSACTION;
BEGIN UPDATE ydv_s SET v = v + 1 WHERE k = 1; COMMIT; END;
/
CREATE OR REPLACE FUNCTION ydv_peek RETURN NUMBER AS PRAGMA AUTONOMOUS_TRANSACTION; n NUMBER;
BEGIN SELECT v INTO n FROM ydv_s WHERE k = 1; COMMIT; RETURN n; END;
/
"""
_SERIAL_TEARDOWN = """
DROP PROCEDURE ydv_bump;
DROP FUNCTION ydv_peek;
DROP TABLE ydv_s PURGE;
"""


def check_read_consistency() -> dict:
    """커밋 안 된 UPDATE 는 다른 트랜잭션(자율 트랜잭션)에 보이지 않고, 그 조회는 막히지 않는다."""
    p = run(_SERIAL_SETUP + """
PROMPT @@q
UPDATE ydv_s SET v = 99 WHERE k = 1;
SELECT 'other_sees=' || ydv_peek FROM dual;
SELECT 'self_sees=' || v FROM ydv_s;
ROLLBACK;
""" + _SERIAL_TEARDOWN)
    return {**p["q"]["kv"], "error": p["q"]["ora"]}


def check_serializable_08177() -> dict:
    """SERIALIZABLE 트랜잭션이 시작 뒤 다른 트랜잭션이 커밋한 행을 고치면 ORA-08177 이다."""
    p = run(_SERIAL_SETUP + """
PROMPT @@q
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
SELECT 'before=' || v FROM ydv_s;
EXEC ydv_bump
SELECT 'snapshot=' || v FROM ydv_s;
UPDATE ydv_s SET v = v + 10 WHERE k = 1;
ROLLBACK;
""" + _SERIAL_TEARDOWN)
    return {**p["q"]["kv"], "error": p["q"]["ora"]}


def _in_list(n: int) -> str:
    items = [str(i) for i in range(1, n + 1)]
    # SQL*Plus 는 4999자를 넘는 줄을 버리므로(SQLPLUS-LINE-LIMIT) 줄을 나눈다
    return ",\n".join(",".join(items[i:i + 200]) for i in range(0, n, 200))


def check_in_list_limit() -> dict:
    """IN 목록은 23ai 에서 65535개까지 된다. 65536개는 ORA-01795 다."""
    p = run(f"""
PROMPT @@n1001
SELECT 'hit=' || count(*) FROM dual WHERE 1 IN (
{_in_list(1001)});
PROMPT @@n65535
SELECT 'hit=' || count(*) FROM dual WHERE 1 IN (
{_in_list(65535)});
PROMPT @@n65536
SELECT 'hit=' || count(*) FROM dual WHERE 1 IN (
{_in_list(65536)});
""")
    return {k: {"hit": p[k]["kv"].get("hit"), "error": p[k]["ora"]} for k in ("n1001", "n65535", "n65536")}


def check_boolean_column() -> dict:
    """23ai 는 BOOLEAN 컬럼을 만들고 WHERE f 로 바로 거른다."""
    p = run("""
DROP TABLE IF EXISTS ydv_b PURGE;
PROMPT @@q
CREATE TABLE ydv_b (f BOOLEAN);
INSERT INTO ydv_b VALUES (TRUE);
INSERT INTO ydv_b VALUES (FALSE);
SELECT 'true_rows=' || count(*) FROM ydv_b WHERE f;
DROP TABLE IF EXISTS ydv_b PURGE;
""")
    return {**p["q"]["kv"], "error": p["q"]["ora"]}


def check_select_without_from() -> dict:
    """23ai 는 FROM dual 없는 SELECT 를 받는다. DROP TABLE IF EXISTS 도 된다."""
    p = run("""
PROMPT @@q
SELECT 'no_from=' || 1;
DROP TABLE IF EXISTS ydv_never_created PURGE;
""")
    return {**p["q"]["kv"], "error": p["q"]["ora"]}


def check_identity_always() -> dict:
    """GENERATED ALWAYS IDENTITY 컬럼에 값을 넣으면 ORA-32795 다."""
    p = run("""
DROP TABLE IF EXISTS ydv_i PURGE;
CREATE TABLE ydv_i (id NUMBER GENERATED ALWAYS AS IDENTITY, v NUMBER);
PROMPT @@q
INSERT INTO ydv_i (v) VALUES (1);
INSERT INTO ydv_i (id, v) VALUES (100, 2);
SELECT 'ids=' || LISTAGG(id, ',') WITHIN GROUP (ORDER BY id) FROM ydv_i;
DROP TABLE ydv_i PURGE;
""")
    return {**p["q"]["kv"], "error": p["q"]["ora"]}


def check_identity_resync() -> dict:
    """직접 넣은 값을 시퀀스가 따라오지 않아 ORA-00001 이 나고, START WITH LIMIT VALUE 가 맞춘다."""
    p = run("""
DROP TABLE IF EXISTS ydv_i PURGE;
CREATE TABLE ydv_i (id NUMBER GENERATED BY DEFAULT ON NULL AS IDENTITY PRIMARY KEY, v NUMBER);
INSERT INTO ydv_i (id, v) VALUES (1, 0);
INSERT INTO ydv_i (id, v) VALUES (2, 0);
PROMPT @@collide
INSERT INTO ydv_i (v) VALUES (1);
PROMPT @@resync
ALTER TABLE ydv_i MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY (START WITH LIMIT VALUE);
INSERT INTO ydv_i (v) VALUES (2);
SELECT 'ids=' || LISTAGG(id, ',') WITHIN GROUP (ORDER BY id) FROM ydv_i;
DROP TABLE ydv_i PURGE;
""")
    return {"collide_error": p["collide"]["ora"], "resync_error": p["resync"]["ora"],
            "ids": p["resync"]["kv"].get("ids")}


def check_merge_duplicate_source() -> dict:
    """MERGE 원본에 같은 키가 둘이면 ORA-30926 이다. 키가 유일하면 된다."""
    p = run("""
DROP TABLE IF EXISTS ydv_m PURGE;
CREATE TABLE ydv_m (k NUMBER PRIMARY KEY, v NUMBER);
INSERT INTO ydv_m VALUES (1, 0);
COMMIT;
PROMPT @@dup
MERGE INTO ydv_m t
USING (SELECT 1 k, 10 v FROM dual UNION ALL SELECT 1, 20 FROM dual) s
ON (t.k = s.k) WHEN MATCHED THEN UPDATE SET t.v = s.v;
PROMPT @@uniq
MERGE INTO ydv_m t
USING (SELECT 1 k, 10 v FROM dual) s
ON (t.k = s.k) WHEN MATCHED THEN UPDATE SET t.v = s.v;
SELECT 'v=' || v FROM ydv_m;
DROP TABLE ydv_m PURGE;
""")
    return {"dup_error": p["dup"]["ora"], "uniq_error": p["uniq"]["ora"], "v": p["uniq"]["kv"].get("v")}


def check_bind_cursor_sharing() -> dict:
    """리터럴로 5번 실행하면 sql_id 5개, 바인드로 5번 실행하면 1개다."""
    tag = "ydv" + uuid.uuid4().hex[:12]
    p = run(f"""
PROMPT @@q
SELECT 'cursor_sharing=' || value FROM v$parameter WHERE name = 'cursor_sharing';
DECLARE n NUMBER;
BEGIN
  FOR i IN 1..5 LOOP
    EXECUTE IMMEDIATE 'SELECT /* {tag}lit */ count(*) FROM dual WHERE 1 = ' || i INTO n;
  END LOOP;
  FOR i IN 1..5 LOOP
    EXECUTE IMMEDIATE 'SELECT /* {tag}bnd */ count(*) FROM dual WHERE 1 = :1' INTO n USING i;
  END LOOP;
  SELECT count(DISTINCT sql_id) INTO n FROM v$sql WHERE sql_text LIKE 'SELECT /* {tag}lit */%';
  DBMS_OUTPUT.PUT_LINE('literal_sql_ids=' || n);
  SELECT count(DISTINCT sql_id) INTO n FROM v$sql WHERE sql_text LIKE 'SELECT /* {tag}bnd */%';
  DBMS_OUTPUT.PUT_LINE('bind_sql_ids=' || n);
END;
/
""")
    return {**p["q"]["kv"], "error": p["q"]["ora"]}


def check_sqlplus_error_exit_code() -> dict:
    """SQL*Plus 는 오류가 나도 종료 코드 0 이다. WHENEVER SQLERROR EXIT 를 두면 0 이 아니다."""
    rc_plain, out_plain = sqlplus("SELECT * FROM ydv_no_such_table;", preamble=False)
    rc_guard, _ = sqlplus("WHENEVER SQLERROR EXIT SQL.SQLCODE\nSELECT * FROM ydv_no_such_table;",
                          preamble=False)
    return {"error": ORA_RE.findall(out_plain), "rc_without_guard": rc_plain, "rc_with_guard": rc_guard}


def check_sqlplus_ampersand() -> dict:
    """SET DEFINE OFF 가 없으면 '&' 가 치환 변수가 되어 표준 입력의 다음 줄을 값으로 삼킨다."""
    script = """SET HEADING OFF
SET FEEDBACK OFF
SET VERIFY OFF
SELECT 'value=' || 'R&D' FROM dual;
PROMPT swallowed-line
SELECT 'after=ok' FROM dual;"""
    _, out = sqlplus(script, preamble=False)
    kv = {m.group(1): m.group(2) for m in map(KV_RE.match, (l.strip() for l in out.splitlines())) if m}
    prompt_ran = any(l.strip() == "swallowed-line" for l in out.splitlines())
    return {"value": kv.get("value"), "after": kv.get("after"), "prompt_line_ran": prompt_ran}


def check_sqlplus_line_limit() -> dict:
    """4999자를 넘는 줄은 SP2-0027 과 함께 버려지고 종료 코드는 0 이다."""
    long_line = "SELECT 'long=' || count(*) FROM dual WHERE 1 IN (" + ",".join(["1"] * 2600) + ");"
    rc, out = sqlplus(long_line + "\nSELECT 'after=ok' FROM dual;", preamble=True)
    kv = {m.group(1): m.group(2) for m in map(KV_RE.match, (l.strip() for l in out.splitlines())) if m}
    return {"line_chars": len(long_line), "errors": ORA_RE.findall(out), "long": kv.get("long"),
            "after": kv.get("after"), "rc": rc}


# 단언 → (재현 함수, 관찰값이 문서와 맞는지)
EXPECT = {
    "EMPTY-STRING-NULL": (check_empty_string_null,
                          lambda o: o["is_null"] == "Y" and o["not_null_error"] == ["ORA-01400"]
                          and o["eq_empty"] == "0" and o["is_null_rows"] == "1"),
    "CONCAT-NULL": (check_concat_null, lambda o: o.get("concat") == "[a]"),
    "DATE-HAS-TIME": (check_date_has_time,
                      lambda o: o == {"equal": "0", "range": "1", "time": "13:45:00"}),
    "NLS-DATE-FORMAT": (check_nls_date_format,
                        lambda o: o["dmy_error"] == ["ORA-01861"] and o["dmy_explicit"] == "20261004"
                        and o["ymd_value"] == "20261004"),
    "VARCHAR2-BYTES": (check_varchar2_bytes,
                       lambda o: o["byte_error"] == ["ORA-12899"] and o["char_error"] == []
                       and o["bytes"] == "12" and o["rows"] == "1"),
    "VARCHAR2-4000-CAP": (check_varchar2_4000_cap,
                          lambda o: o["max_string_size"] == "STANDARD" and o["fit_error"] == []
                          and "ORA-12899" in o["over_error"] and o["rows"] == "1"
                          and o["replace_len"] == "1333"),
    "NUMBER-SCALE": (check_number_scale,
                     lambda o: o["round_error"] == [] and o["stored"] == "123.46"
                     and o["over_error"] == ["ORA-01438"]),
    "IDENT-UPPERCASE": (check_identifier_uppercase,
                        lambda o: o["column"] == "NAME" and o["quoted_error"] == ["ORA-00904"]
                        and o["plain"] == "0" and o["plain_error"] == []),
    "IDENT-128-BYTES": (check_identifier_bytes,
                        lambda o: o["ok_ascii"] == [] and o["bad_ascii"] == ["ORA-00972"]
                        and o["ok_ko"] == [] and o["bad_ko"] == ["ORA-00972"]),
    "LIMIT-UNSUPPORTED": (check_limit_unsupported, lambda o: o["error"] == ["ORA-03047"]),
    "ROWNUM-BEFORE-ORDER": (check_rownum_before_order,
                            lambda o: o.get("rownum") == "3,2,1" and o.get("fetch_first") == "10,9,8"),
    "ROWNUM-GT-EMPTY": (check_rownum_greater_than, lambda o: o.get("gt1") == "0"),
    "DDL-IMPLICIT-COMMIT": (check_ddl_implicit_commit,
                            lambda o: o["semantic_error"] == ["ORA-00955"] and o["rows_after_semantic"] == "1"
                            and o["syntax_error"] == ["ORA-00901"] and o["rows_after_syntax"] == "1"),
    "READ-CONSISTENCY": (check_read_consistency,
                         lambda o: o.get("other_sees") == "0" and o.get("self_sees") == "99"
                         and o["error"] == []),
    "SERIALIZABLE-08177": (check_serializable_08177,
                           lambda o: o.get("before") == "0" and o.get("snapshot") == "0"
                           and o["error"] == ["ORA-08177"]),
    "IN-LIST-LIMIT": (check_in_list_limit,
                      lambda o: o["n1001"] == {"hit": "1", "error": []}
                      and o["n65535"] == {"hit": "1", "error": []}
                      and o["n65536"]["error"] == ["ORA-01795"]),
    "BOOLEAN-23AI": (check_boolean_column, lambda o: o.get("true_rows") == "1" and o["error"] == []),
    "NO-FROM-23AI": (check_select_without_from, lambda o: o.get("no_from") == "1" and o["error"] == []),
    "IDENTITY-ALWAYS": (check_identity_always,
                        lambda o: o["error"] == ["ORA-32795"] and o.get("ids") == "1"),
    # 23ai 는 ORA-00001 뒤에 ORA-03301 상세 줄을 덧붙이므로 첫 코드만 본다
    "IDENTITY-RESYNC": (check_identity_resync,
                        lambda o: o["collide_error"][:1] == ["ORA-00001"] and o["resync_error"] == []
                        and o["ids"] == "1,2,3"),
    "MERGE-DUP-SOURCE": (check_merge_duplicate_source,
                         lambda o: o["dup_error"] == ["ORA-30926"] and o["uniq_error"] == []
                         and o["v"] == "10"),
    "BIND-CURSOR-SHARING": (check_bind_cursor_sharing,
                            lambda o: o.get("cursor_sharing") == "EXACT" and o.get("literal_sql_ids") == "5"
                            and o.get("bind_sql_ids") == "1" and o["error"] == []),
    "SQLPLUS-EXIT-CODE": (check_sqlplus_error_exit_code,
                          lambda o: o["error"] == ["ORA-00942"] and o["rc_without_guard"] == 0
                          and o["rc_with_guard"] != 0),
    "SQLPLUS-AMPERSAND": (check_sqlplus_ampersand,
                          lambda o: o["value"] not in (None, "R&D") and not o["prompt_line_ran"]
                          and o["after"] == "ok"),
    "SQLPLUS-LINE-LIMIT": (check_sqlplus_line_limit,
                           lambda o: o["line_chars"] > 4999 and o["errors"] == ["SP2-0027"]
                           and o["long"] is None and o["after"] == "ok" and o["rc"] == 0),
}


def version() -> str:
    _, out = sqlplus("SELECT 'version=' || version_full FROM product_component_version WHERE ROWNUM = 1;")
    m = re.search(r"version=(\S+)", out)
    return m.group(1) if m else "?"


def check(claim: str) -> tuple[dict, bool]:
    fn, ok = EXPECT[claim]
    obs = fn()
    try:
        return obs, bool(ok(obs))
    except (KeyError, TypeError):
        return obs, False


def main() -> int:
    try:
        print(f"oracle {version()}")
    except OracleUnavailable as e:
        print(f"건너뜀: {e}", file=sys.stderr)
        return 2
    failed = 0
    for claim in EXPECT:
        obs, ok = check(claim)
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {claim}: {obs}")
    print(f"{len(EXPECT) - failed}/{len(EXPECT)} 단언 재현")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
