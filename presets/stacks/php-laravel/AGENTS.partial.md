
**php-laravel**

- 시크릿 하드코딩 금지 — 값은 `.env` 에서 `config()` 경유로만 읽고, `.env`·`auth.json`·`storage/oauth-*.key` 스테이징 금지
- SQL 문자열 결합 금지 — Eloquent·쿼리 빌더의 바인딩만(`DB::raw`·`whereRaw` 에 입력 보간 금지)
- `composer validate` + `vendor/bin/pint --test` 통과 후 커밋
