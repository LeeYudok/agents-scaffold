---
name: yd-pg-expert
description: PostgreSQL 고유 동작(timestamptz·numeric·실행계획·잠금을 잡는 ALTER·CREATE INDEX CONCURRENTLY·VACUUM·직렬화 재시도)을 다루거나 여러 서비스가 함께 쓰는 공유 PostgreSQL 클러스터를 운영할 때 사용한다. 엔진 공통 설계는 yd-db-expert 를 쓴다.
---

# yd-pg-expert

PostgreSQL 엔진 고유 동작과 공유 클러스터 운영이 대상이다. 엔진과 무관한
설계(정규화·키·NULL·제약·쿼리 원칙·트랜잭션 경계·마이그레이션 단계)는 `yd-db-expert`,
SQLite 파일 문제는 `yd-sqlite-expert` 가 맡는다. 여기서는 그 원칙을 반복하지 않는다.

엔진 동작에 관한 단언은 `scripts/verify_pg_claims.py` 가 일회용 서버에서 재현한다.
아래 관찰값은 PostgreSQL 17.11 에서 얻었다 (2026-10-04 실측). 버전을 올리면 다시 돌린다.

## 1. 타입

- **타임스탬프는 `timestamptz`.** `timestamp` 는 입력에 붙은 오프셋을 오류 없이 버린다.
  `'2026-01-01 09:00:00+09'` 를 넣으면 `09:00:00` 이 그대로 남아 UTC 로 읽을 때 9시간 어긋난다.
  `timestamptz` 는 같은 순간(`00:00:00+00`)을 유지한다.
- 저장은 UTC, 표시에서 변환한다. 사용자 표기는 `YYYY-MM-DD HH:MM:SS.mmm` (KST 가정).
- **돈은 `numeric`.** `float8` 은 `0.1 + 0.2 = 0.3` 이 거짓이고, 0.1 을 열 번 더하면
  `0.9999999999999999` 다. `numeric` 은 둘 다 정확하다.
- `UNIQUE` 는 별도 옵션이 없으면 NULL 을 여러 개 허용한다. NULL 도 하나만 허용하려면
  `UNIQUE NULLS NOT DISTINCT` (PostgreSQL 15 부터)를 쓴다.

## 2. 인덱스와 실행계획

- **FK 컬럼에는 인덱스가 자동으로 생기지 않는다.** PK·`UNIQUE` 만 생긴다. 부모 행을
  지우거나 키를 바꿀 때 자식 테이블을 풀스캔하므로 FK 인덱스는 직접 만든다.
- 확인은 추측이 아니라 `EXPLAIN (ANALYZE, BUFFERS) <쿼리>` 로 한다.
- **`EXPLAIN ANALYZE` 는 문을 실제로 실행한다.** `DELETE`·`UPDATE` 를 분석하면 행이 정말
  지워진다. 쓰기 문은 `BEGIN; EXPLAIN ANALYZE ...; ROLLBACK;` 으로 감싼다.
- 작은 테이블의 `Seq Scan` 은 인덱스 누락이 아니다. 20행 테이블은 PK 가 있어도 플래너가
  일부러 순차 스캔을 고른다. 원인을 찾을 대상은 큰 테이블의 `Seq Scan` 이다.
- 함수를 씌운 조건(`WHERE lower(name) = ...`)은 `name` 인덱스를 못 탄다.
  `CREATE INDEX ... ON t (lower(name))` 표현식 인덱스를 만든다.
- **C 가 아닌 콜레이션 컬럼의 일반 인덱스는 `LIKE 'abc%'` 에 쓰이지 않는다.** 공식
  `postgres` 컨테이너 이미지의 기본 콜레이션은 `en_US.utf8` 이다. 접두 검색이 필요하면
  `text_pattern_ops` 인덱스를 따로 만든다.
- 부분 인덱스(`WHERE status = 'pending'`)는 조회 조건이 인덱스 조건을 함의할 때만 쓰인다.
  `status = 'done'` 조회에는 쓰이지 않는다.

## 3. 잠금과 온라인 스키마 변경

모든 `ALTER TABLE` 은 짧게라도 `ACCESS EXCLUSIVE` 잠금을 잡는다. 관건은 두 가지다 —
테이블을 다시 쓰는가(잠금이 데이터 크기에 비례해 길어진다), 잠금을 기다리는 동안 무엇이 막히는가.

| 변경 | 테이블 재작성 |
|---|---|
| `ADD COLUMN` (기본값 없음, NULL 허용) | 없음 |
| `ADD COLUMN ... NOT NULL DEFAULT 0` (상수 기본값) | 없음 (PostgreSQL 11 부터) |
| `ADD COLUMN ... DEFAULT clock_timestamp()` (volatile 기본값) | 있음 |
| `ALTER COLUMN ... TYPE bigint` (`int` 에서) | 있음 |
| `varchar(10)` → `varchar(20)`, `varchar` → `text` | 없음 |
| `ALTER COLUMN ... SET NOT NULL` | 없음. 대신 잠금을 쥔 채 전체를 스캔한다 |

- **volatile 기본값을 가진 컬럼 추가는 테이블을 다시 쓴다.** 행마다 값을 계산해야 해서다.
- **`int` → `bigint` 는 테이블을 다시 쓴다.** 큰 테이블이면 새 컬럼 추가 → 배치 백필 →
  전환 순서로 나눈다.
- `SET NOT NULL` 은 다시 쓰지 않지만 `ACCESS EXCLUSIVE` 를 잡고 전 행을 검사한다.
  큰 테이블은 `CHECK (col IS NOT NULL) NOT VALID` 를 추가하고 `VALIDATE CONSTRAINT` 로 검증한 뒤
  `SET NOT NULL` 한다. 검증된 CHECK 가 있으면 PostgreSQL 12 부터 전 행 검사를 건너뛴다.
- `NOT VALID` 로 추가한 제약은 기존 행을 검사하지 않고 새 행만 막는다. `VALIDATE` 는
  기존 행을 검사하되 쓰기를 막지 않는 잠금으로 돈다. 위반 행이 남아 있으면 `VALIDATE` 가 실패한다.
- 일반 `CREATE INDEX` 는 `SHARE` 잠금으로 끝날 때까지 쓰기를 막는다. 운영 테이블은
  `CREATE INDEX CONCURRENTLY` 로 만든다.
- **`CREATE INDEX CONCURRENTLY` 는 트랜잭션 블록 안에서 실패한다** (SQLSTATE `25001`).
  마이그레이션 도구가 파일마다 트랜잭션으로 감싸면 그 파일은 비트랜잭션으로 표시한다.

### 마이그레이션 세션에는 `lock_timeout` 을 건다

`idle in transaction` 세션이 `SELECT` 하나로 테이블에 잠금을 쥐고 있으면 `ALTER` 는 그 뒤에서
기다린다. **기다리는 `ALTER` 뒤로 그 테이블의 단순 `SELECT` 까지 줄을 선다.** 마이그레이션 하나가
서비스 전체 조회를 멈춘다. `SET lock_timeout = '3s'` 를 걸면 `ALTER` 만 `55P03` 으로 실패하고
조회는 지나간다. 실패한 마이그레이션은 재시도한다.

## 4. 트랜잭션과 VACUUM

- 기본 격리수준은 Read Committed 다. **"읽고 판단해 쓰는" 두 트랜잭션은 Read Committed 에서
  오류 없이 둘 다 커밋된다.** 당직자가 최소 1명이어야 하는 규칙을 두 세션이 동시에 확인하고
  각자 빠지면 0명이 된다 (write skew).
- `SERIALIZABLE` 은 그중 하나를 SQLSTATE `40001` 로 실패시킨다. 격리수준을 올리면 **`40001` 을
  받아 트랜잭션 전체를 다시 실행하는 재시도 루프**가 짝이다. 재시도 없는 `SERIALIZABLE` 은
  오류를 사용자에게 던질 뿐이다.
- **xid 를 받은 채 열려 있는 트랜잭션은 VACUUM 을 막는다.** 그 뒤에 생긴 죽은 튜플은
  `dead but not yet removable` 로 남고 테이블이 부푼다. REPEATABLE READ 이상에서 스냅숏을
  쥔 트랜잭션도 같다. 배치는 잘라서 커밋한다.
- 읽기만 하고 멈춘 Read Committed 트랜잭션은 VACUUM 을 막지 않는다. 그래도 잠금은 쥐고 있어
  3장의 `ALTER` 줄 세우기를 일으킨다. `idle in transaction` 은 어느 쪽이든 정리 대상이다.

## 5. 공유 클러스터 운영

단일 클러스터를 여러 서비스가 공유하는 환경이다.
**내 서비스 하나가 클러스터 전체를 마비시킬 수 있다는 전제**로 다룬다.

- **`max_connections` 를 여럿이 나눠 쓴다.** 커넥션 풀 상한을 정하지 않은 서비스는
  다른 서비스의 접속을 굶긴다. 애플리케이션마다 상한을 명시한다.
- 같은 호스트의 컨테이너에서는 `host.docker.internal`(host-gateway)로 접근한다.
- 계정·비밀번호는 저장소 밖 비밀 저장소에 둔다. **값을 채팅·로그·이슈에 노출하지 않는다.**

### 쓰기 작업 규율

- 조회는 자유롭게. **INSERT/UPDATE/DELETE·DDL 은 사용자의 명시 실행 신호 후에만** 한다.
- 대량 변경 전에 **영향 행 수를 먼저 센다.** `SELECT count(*)` 로 확인하고 보고한 뒤 실행한다.
- `UPDATE`/`DELETE` 에 `WHERE` 가 없으면 실행하지 않는다. 예외 없다.
- 운영 데이터 이동·삭제는 범위가 확정되지 않으면 시작하지 않는다.
- 쓰기 문의 실행계획은 2장대로 `BEGIN … ROLLBACK` 안에서 본다.

### 진단 시작점

```sql
-- 지금 무엇이 돌고 있는가 (오래된 것부터)
SELECT pid, now() - query_start AS dur, state, left(query, 80)
FROM pg_stat_activity WHERE state <> 'idle' ORDER BY dur DESC LIMIT 20;

-- 커넥션을 누가 쓰고 있는가
SELECT datname, count(*) FROM pg_stat_activity GROUP BY 1 ORDER BY 2 DESC;

-- 테이블 부풀림·죽은 튜플
SELECT relname, n_live_tup, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10;
```

`idle in transaction` 이 오래 떠 있으면 애플리케이션이 커밋을 안 하고 있는 것이다 —
잠금을 쥐고, xid 가 있으면 VACUUM 까지 막으므로 우선 처리한다.

## 6. 완료 조건

- 시각 컬럼은 `timestamptz`, 금액 컬럼은 `numeric` 이다.
- FK 컬럼마다 인덱스가 있고, 느린 쿼리는 `EXPLAIN (ANALYZE, BUFFERS)` 로 확인했다.
  쓰기 문은 `ROLLBACK` 안에서 분석했다.
- 마이그레이션은 3장 표로 재작성 여부를 확인했고, `lock_timeout` 과 재시도가 있다.
  인덱스는 `CONCURRENTLY` 로 만든다.
- `SERIALIZABLE` 을 쓰면 `40001` 재시도 루프가 있다.
- 운영 클러스터를 만졌으면 영향 범위를 먼저 세어 보고했고, 커넥션 상한을 확인했다.
- 시크릿이 출력·로그·이슈에 노출되지 않았다.

## 7. 이 문서의 단언 재현

```bash
podman run -d --rm --name ydpg-verify -e POSTGRES_PASSWORD=verify postgres:17
YD_PG_PSQL='podman exec -i ydpg-verify psql -U postgres' \
  python3 .claude/skills/yd-pg-expert/scripts/verify_pg_claims.py
podman stop ydpg-verify
```

`YD_PG_PSQL` 은 표준입력으로 SQL 을 읽는 psql 명령 앞부분이다. **버리는 서버만 가리킨다** —
단언마다 스키마를 만들고 지우며, 일부러 잠금을 잡고 타임아웃을 낸다. 운영 클러스터에
돌리지 않는다. 하나라도 문서와 다르면 exit 1 이다. 변수가 없으면 테스트는 skip 하고,
CI 는 `.github/workflows/pg.yml` 의 별도 job 에서 skip 없이 돈다. 단언과 테스트의 대응은
`tests/claims.json` 이 갖는다.
