---
paths:
  - "**/*.rb"
  - "app/**/*.rb"
  - "lib/**/*.rb"
  - "config/**/*.rb"
  - "db/**/*.rb"
  - "spec/**/*.rb"
  - "app/**/*.erb"
  - "Gemfile"
---

# Ruby on Rails 규칙

## 런타임 & 패키지 관리
- 루비 버전은 `.ruby-version` 으로 고정. `Gemfile` 의 `ruby` 지시자와 일치시킨다.
- 의존성은 항상 `bundle add`/`bundle update` 로 갱신하고 **`Gemfile.lock` 을 커밋**한다.
- 명령은 `bundle exec` 경유(`bundle exec rspec`, `bundle exec rubocop`) — 전역 젬 호출 금지.

## 코드 컨벤션
- `rubocop` (+ `rubocop-rails`, `rubocop-rspec`) 을 단일 스타일 소스로 삼는다. 커밋 전 `bundle exec rubocop -A`.
- 컨트롤러는 얇게: HTTP 변환·권한 확인만. 도메인 로직은 모델 또는 `app/services/` 로.
- 콜백(`before_save` 등)에 비즈니스 로직·외부 I/O 금지 — 서비스 객체로 뺀다.
- fat query 는 스코프/`ActiveRecord::Relation` 으로 모델에 둔다. 뷰에서 쿼리 금지.
- N+1 은 `includes`/`preload` 로 해소. `bullet` 젬 도입 권장.

## 테스트
- RSpec 기본(`spec/`). model·request 스펙 우선, system 스펙은 핵심 플로우만.
- 픽스처보다 `factory_bot`. `spec/rails_helper.rb` 에서 트랜잭션 롤백 유지.
- 새 기능·버그픽스마다 최소 1개 스펙 동반(P1).

## 마이그레이션 & DB
- 마이그레이션은 되돌릴 수 있게(`change` 로 표현 불가하면 `up`/`down` 명시).
- 운영 테이블에 `NOT NULL` + 디폴트 추가는 백필과 분리해 단계적으로.
- 인덱스 추가는 대용량 테이블에서 `algorithm: :concurrently`(PostgreSQL, `disable_ddl_transaction!` 동반).
- `schema.rb`(또는 `structure.sql`)를 마이그레이션과 같은 커밋에 포함.

## 보안
- 시크릿은 Rails credentials(`config/credentials.yml.enc`) 또는 환경변수. `config/master.key`·`config/credentials/*.key` 는 **절대 커밋 금지**.
- SQL 은 플레이스홀더 바인딩(`where("id = ?", id)`). 문자열 보간 금지.
- 대량 할당은 strong parameters 로 화이트리스트. `permit!` 금지.
- ERB 에서 `raw`/`html_safe` 사용 시 입력 출처를 주석으로 근거 남길 것.

## P0
- 시크릿 하드코딩 금지 — `config/master.key`·`config/credentials/*.key`·`.env` 스테이징 금지
- SQL 문자열 보간 금지 — 바인딩 파라미터만
- `bundle exec rubocop` 에러 없이 커밋

## P1
- `Gemfile.lock` 과 `schema.rb`/`structure.sql` 를 변경과 같은 커밋에 포함
- 새 기능·버그픽스에 스펙 최소 1개 동반
- 컨트롤러 파라미터는 strong parameters 화이트리스트로만 수신
