---
name: yd-sqlite-expert
description: SQLite 파일을 직접 읽고 쓰거나, 읽기 전용 조회·WAL·잠금·마이그레이션·동적 테이블명 주입 같은 SQLite 고유 문제를 다룰 때 사용한다. 스키마 설계 일반은 yd-db-expert, PostgreSQL 고유 주제는 yd-pg-expert 를 쓴다.
---

# yd-sqlite-expert

SQLite **엔진 고유의 문제**가 대상이다. 스키마 설계 이론은 `yd-db-expert`, PostgreSQL 은 `yd-pg-expert`,
Go 코드 관용구는 `yd-go-expert` 가 맡는다.

SQLite 는 "작은 RDB"가 아니라 **파일 하나가 데이터베이스인 라이브러리**다. 서버가 없다는
사실에서 이 문서의 거의 모든 항목이 파생된다.

## 1. 남의 파일을 읽을 때 — 원본을 바꾸지 않는다

앱이 쓰고 있는 캐시·데이터 파일을 조회하는 작업이 흔하다. **원본을 건드리면 그 앱의 데이터가
깨진다.** 기본은 읽기 전용이다.

```go
dsn := "file:" + path + "?mode=ro&_pragma=busy_timeout(5000)"
```

- **`mode=ro`** — 쓰기를 엔진 수준에서 막는다. 애플리케이션 규율에 기대지 않는다.
- **`busy_timeout`** — 다른 프로세스가 쓰는 중이면 즉시 실패하지 않고 기다린다.
  없으면 산발적인 `database is locked` 로 나타난다.
- **URI 파일명에서 `?`·`#` 은 구분자다.** 경로에 들어 있으면 퍼센트 인코딩한다.
  그냥 이어붙이면 `?` 앞까지를 경로로 읽어 **엉뚱한 빈 파일을 새로 만들고, 뒤의 `mode=ro` 도
  무시된다.** 오류는 `no such table` 로만 나온다.

### 곁 파일까지 확인한다

읽기만 해도 `-wal`·`-shm`·`-journal` 이 생기면 **원본 폴더를 오염시킨 것**이다.
롤백 저널 DB 는 `mode=ro` 로 조회해도 곁 파일이 생기지 않는다. **WAL 모드 DB 는 `mode=ro`
만으로 안 된다.** 곁 파일이 없는 WAL DB 를 `mode=ro` 로 열면 SQLite 3.51.0 은 열기 자체가
`unable to open database file` 로 실패하고, 3.53.4 는 열리지만 `-wal`·`-shm` 을 만든다
(2026-10-04 실측). 읽기·쓰기 모드로 열면 조회만 해도 둘 다 생긴다.

정말 건드리면 안 되는 파일은 `immutable=1` 을 고려한다. 곁 파일 없이 읽힌다. 다만 이건
"파일이 변하지 않는다"는 약속이므로 앱이 쓰는 중이면 쓰지 않는다.

**가장 안전한 순서**: 사본을 떠서 사본을 연다. WAL DB 의 사본은 본 파일만으로는 모자란다
(7장). 그럴 수 없으면 `mode=ro` + 곁 파일 검사.

### 이건 테스트로 고정한다

문서에만 적힌 "읽기 전용"은 다음 리팩터링에서 사라진다. 회귀 테스트로 못 박는다.

```go
// 조회란 조회를 다 돌린 뒤 파일 해시가 같은지, 곁 파일이 안 생겼는지
before := sha256sum(path)
// ... Rooms / Messages / Count / Search ...
if after := sha256sum(path); after != before { t.Error("원본이 바뀌었다") }
for _, s := range []string{"-wal", "-shm", "-journal"} {
    if _, err := os.Stat(path + s); !os.IsNotExist(err) { t.Error("곁 파일이 생겼다") }
}
```

쓰기가 실제로 막히는지도 확인한다 — `mode=ro` 로 연 뒤 `DELETE` 가 실패해야 한다.

## 2. 동적 테이블·컬럼명 — 유일한 방어선

테이블명은 **플레이스홀더로 넘길 수 없다.** 스키마가 `Chat_<방ID>` 처럼 데이터에 따라
갈리는 구조면 문자열 조립이 불가피하다. 그러면 검증이 유일한 방어선이 된다.

```go
var roomIDRe = regexp.MustCompile(`^[0-9a-f]{12}-[0-9]{3}$`)

func tableName(id string) (string, error) {
    if !roomIDRe.MatchString(id) {   // 통과 못 하면 절대 쿼리에 넣지 않는다
        return "", fmt.Errorf("%w: %q", ErrInvalidRoomID, id)
    }
    return "Chat_" + id, nil
}
// 조립 시 반드시 인용부호로 감싼다 — 이름의 '-' 가 연산자로 파싱되는 것도 막는다
q := fmt.Sprintf(`SELECT ... FROM %q WHERE Sequence > ?`, table)
```

**규칙**: 화이트리스트(정규식 또는 `sqlite_master` 조회 결과)를 통과한 값만 쓰고, `%q` 로
감싸고, **주입 시도 케이스를 테스트에 넣는다.** 값은 언제나 플레이스홀더(`?`)로 넘긴다.

### LIKE 검색

```go
r := strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`)
pattern := "%" + r.Replace(query) + "%"
// ... WHERE Content LIKE ? ESCAPE '\'
```

이스케이프를 빠뜨리면 사용자가 `%` 만 넣어도 전부 걸린다. `ESCAPE` 절을 함께 줘야 한다.

`LIKE` 는 ASCII 만 대소문자를 무시한다. 한글은 대소문자가 없어 문제되지 않지만,
라틴 문자 검색에서 유니코드 대소문자를 맞추려면 애플리케이션에서 정규화한다.

## 3. 타입과 NULL

- **동적 타입**이다. 컬럼 선언이 `INTEGER` 여도 문자열이 들어가 있을 수 있다.
  남의 파일을 읽을 때는 **전 컬럼을 `sql.NullXxx` 로 받는다.** 스키마 선언을 믿지 않는다.
- **날짜 전용 타입이 없다.** `TEXT`(`2026-07-29 10:55:20`)·정수 epoch 가 섞여 있다.
  타임존 정보가 없으면 로컬로 해석하고 **그 가정을 주석에 남긴다.**
- `WITHOUT ROWID` 는 TEXT 기본키에서 흔하다. 읽기에는 영향 없다.
- 불리언은 정수 0/1 이다.

## 4. 쓰기가 있는 경우

- **기본이 자동 커밋이라 대량 INSERT 가 극단적으로 느리다.** 트랜잭션으로 감싸면
  수십~수백 배 차이가 난다. 이건 최적화가 아니라 기본이다.
- **동시 쓰기는 한 번에 하나**다. 여러 프로세스가 쓰면 `SQLITE_BUSY` 를 각오하고
  `busy_timeout` + 재시도를 둔다.
- WAL(`journal_mode=WAL`)은 읽기와 쓰기를 겹치게 해준다. 대신 곁 파일이 생기고,
  **네트워크 파일시스템에서는 쓰지 않는다**(잠금이 깨진다).
- Go 에서 쓰기 커넥션은 `SetMaxOpenConns(1)` 이 안전한 기본이다. 읽기 전용이면 불필요.
- `PRAGMA foreign_keys = ON` 은 **커넥션마다** 켜야 한다. 기본이 꺼져 있다.

## 5. 인덱스

- 기본키가 아닌 조회 조건에는 인덱스를 만든다. 다만 **테이블이 작으면 의미 없다** —
  수백 행짜리에 인덱스를 붙이며 시간 쓰지 않는다.
- 복합 인덱스는 **앞 컬럼부터** 쓰인다. `(RoomId, Sequence)` 는 `RoomId` 단독 조회에는
  쓰이지만 `Sequence` 단독에는 안 쓰인다.
- 앞 컬럼이 상수 하나뿐인 인덱스는 뒤 컬럼 인덱스와 같다 — 그런 구조를 발견하면 지적한다.
- `EXPLAIN QUERY PLAN <쿼리>` 로 확인한다. `SCAN` 이 보이면 인덱스를 안 탄 것이다.

## 6. 드라이버 선택 (Go)

| | `modernc.org/sqlite` | `mattn/go-sqlite3` |
|---|---|---|
| CGO | 불필요 (순수 Go) | 필요 |
| 크로스컴파일 | 쉬움 | C 툴체인 필요 |
| 속도 | 조금 느림 | 빠름 |

**조회 위주·크로스컴파일 배포면 `modernc.org/sqlite`** 를 기본으로 한다. 대량 쓰기 성능이
병목으로 측정된 경우에만 CGO 판을 고려한다. 드라이버 이름은 `"sqlite"`(modernc) /
`"sqlite3"`(mattn) 으로 다르다.

## 7. 마이그레이션

- `ALTER TABLE` 지원이 제한적이다. 컬럼 삭제·타입 변경은 **새 테이블 생성 → 복사 → 교체**가
  정석이다. 이 절차 전체를 하나의 트랜잭션에 넣는다.
- `PRAGMA user_version` 으로 스키마 버전을 관리하면 의존성 없이 충분하다.
- 마이그레이션 전 백업한다. **WAL 모드에서는 본 파일만 복사하면 체크포인트 전에 커밋된 행이
  빠진다** — 그 행은 아직 `-wal` 에만 있다. `sqlite3 .backup`·백업 API·`VACUUM INTO` 처럼
  엔진을 거치는 방법을 쓰거나, 쓰는 쪽을 모두 닫고 체크포인트한 뒤 복사한다.

## 8. 완료 조건

- 남의 파일을 읽는 코드면 `mode=ro` 와 원본 불변 회귀 테스트(해시·곁 파일)가 있다.
- 동적 테이블·컬럼명이 있으면 화이트리스트 검증, 인용, 주입 시도 테스트가 있다.
- LIKE 를 쓰면 와일드카드 이스케이프와 `ESCAPE` 절이 있다.
- 남의 파일을 읽으면 전 컬럼을 NULL 로 방어한다.
- 대량 쓰기는 트랜잭션으로 묶는다.
- 느린 쿼리는 `EXPLAIN QUERY PLAN` 으로 확인한다.

## 9. 이 문서의 단언 재현

```bash
python3 .claude/skills/yd-sqlite-expert/scripts/verify_sqlite_claims.py
```

위 단언 가운데 엔진 동작에 관한 것(읽기 전용 쓰기 거부, 곁 파일, `?` 경로, WAL 백업, 연결별
FK, LIKE 이스케이프, 복합 인덱스, `busy_timeout`, 트랜잭션, `user_version`)을 지금 설치된
SQLite 로 재현한다. 하나라도 다르면 exit 1 이다. SQLite 를 올린 뒤 돌려 보고, 결과가 다르면
문서를 고치거나 단언에 버전을 적는다. 단언과 테스트의 대응은 `tests/claims.json` 이 갖는다.
