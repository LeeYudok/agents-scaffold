# --- php-laravel: secrets + composer validate + pint + phpunit gate ---
if [ -f composer.json ]; then
  # Composer 인증·Passport 키가 스테이징되면 즉시 차단 (base 의 .env 검사와 같은 계열)
  if printf '%s\n' "$staged" | grep -qE '(^|/)(auth\.json|oauth-(private|public)\.key)$'; then
    echo "차단: Composer 인증(auth.json) 또는 Passport 키(oauth-*.key)가 스테이징됐다. .gitignore 에 추가하고 언스테이징할 것." >&2
    exit 2
  fi

  # composer.json 문법·composer.lock 동기화 (composer 가 설치돼 있을 때만)
  if command -v composer >/dev/null 2>&1; then
    echo "composer validate..." >&2
    if ! composer validate --no-check-publish --no-interaction 2>&1 | tail -20; then
      echo "차단: composer validate 실패. composer.json 을 고치거나 'composer update --lock' 후 재커밋." >&2
      exit 2
    fi
  else
    echo "composer 미설치 — composer.json 검사 skipping" >&2
  fi

  if command -v php >/dev/null 2>&1; then
    # pint (프로젝트에 설치돼 있을 때만)
    if [ -x vendor/bin/pint ]; then
      echo "pint --test..." >&2
      if ! vendor/bin/pint --test 2>&1 | tail -20; then
        echo "차단: 스타일 불일치. 'vendor/bin/pint' 실행 후 재커밋." >&2
        exit 2
      fi
    else
      echo "pint 미설치 — 스타일 검사 skipping" >&2
    fi

    # phpunit (테스트 디렉터리가 있고 설치돼 있을 때만)
    if [ -d tests ] && [ -x vendor/bin/phpunit ]; then
      echo "phpunit..." >&2
      if ! vendor/bin/phpunit --stop-on-failure 2>&1 | tail -20; then
        echo "차단: phpunit 실패." >&2
        exit 2
      fi
    fi
  else
    echo "php 미설치 — pint·phpunit 검사 skipping" >&2
  fi
fi
