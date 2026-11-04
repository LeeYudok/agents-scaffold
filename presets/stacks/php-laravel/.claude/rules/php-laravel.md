---
paths:
  - "**/*.php"
  - "app/**/*.php"
  - "routes/**/*.php"
  - "config/**/*.php"
  - "database/**/*.php"
  - "tests/**/*.php"
  - "resources/views/**/*.blade.php"
  - "composer.json"
---

# PHP · Laravel 규칙

## 런타임 & 패키지 관리
- PHP 버전은 `composer.json` 의 `require.php` 제약으로 고정하고 CI·운영 런타임과 맞춘다.
- 의존성은 `composer require`/`composer update <패키지>` 로만 바꾸고 **`composer.lock` 을 커밋**한다.
- 툴은 프로젝트 로컬 바이너리로 실행한다(`vendor/bin/pint`, `vendor/bin/phpunit`, `php artisan`) — 전역 설치본 호출 금지.

## 코드 컨벤션
- `pint`(Laravel 프리셋)를 단일 스타일 소스로 삼는다. 커밋 전 `vendor/bin/pint`.
- 파일마다 `declare(strict_types=1);` 와 파라미터·반환 타입을 명시한다.
- 컨트롤러는 얇게: 요청 검증은 Form Request, 도메인 로직은 `app/Actions/`·`app/Services/` 로.
- 설정값은 `config()` 로 읽는다. `env()` 는 `config/*.php` 안에서만 — `config:cache` 뒤에는 그 밖의 `env()` 가 `null` 이 된다.
- N+1 은 `with()`/`load()` 로 해소. 로컬에서 `Model::preventLazyLoading()` 을 켠다.
- 큐 작업·이벤트 리스너는 멱등하게 — 재시도로 두 번 실행돼도 결과가 같아야 한다.

## 테스트
- PHPUnit(또는 Pest) — `tests/Feature` 는 HTTP·DB 경계, `tests/Unit` 은 순수 로직.
- DB 를 쓰는 테스트는 `RefreshDatabase`(또는 `DatabaseTransactions`)로 격리하고, 테스트 데이터는 모델 팩토리로 만든다.
- 외부 HTTP·메일·큐는 `Http::fake()`·`Mail::fake()`·`Queue::fake()` 로 막는다.
- 새 기능·버그픽스마다 최소 1개 테스트 동반(P1).

## 마이그레이션 & DB
- 마이그레이션은 되돌릴 수 있게 `down()` 을 채운다. 이미 배포된 마이그레이션 파일은 고치지 않고 새로 추가한다.
- 운영 테이블에 `NOT NULL` 컬럼 추가는 nullable 추가 → 백필 → 제약 추가로 나눈다.
- 대량 데이터 변경은 마이그레이션이 아니라 청크(`chunkById`) 단위 커맨드로.

## 보안
- 시크릿은 `.env`(커밋 금지)와 운영 환경변수로만. `APP_KEY`·`auth.json`(Composer 인증)·`storage/oauth-*.key`(Passport)는 **절대 커밋 금지**.
- SQL 은 Eloquent·쿼리 빌더 바인딩만. `DB::raw`·`whereRaw`·`orderByRaw` 에 요청 값을 보간하지 않는다.
- 대량 할당은 `$fillable` 화이트리스트로. `$guarded = []`·`forceFill($request->all())` 금지.
- Blade 출력은 `{{ }}`(이스케이프). `{!! !!}` 를 쓰면 입력 출처를 주석으로 근거 남길 것.
- 운영에서 `APP_DEBUG=false`. 상태를 바꾸는 라우트는 `auth`(또는 `auth:sanctum`) 미들웨어와 CSRF 보호 아래에 둔다.

## P0
- 시크릿 하드코딩 금지 — `.env`·`auth.json`·`storage/oauth-*.key` 스테이징 금지
- SQL 문자열 결합 금지 — 바인딩 파라미터만
- `composer validate` + `vendor/bin/pint --test` 통과 후 커밋

## P1
- `composer.lock` 과 마이그레이션을 변경과 같은 커밋에 포함
- 새 기능·버그픽스에 테스트 최소 1개 동반
- 요청 입력은 Form Request(또는 `$request->validate()`)로 검증한 값만 사용
