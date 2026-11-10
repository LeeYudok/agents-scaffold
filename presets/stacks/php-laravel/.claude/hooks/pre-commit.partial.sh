# --- php-laravel: secrets + composer validate + pint + phpunit gate ---
if [ -f composer.json ]; then
  # Composer 인증·Passport 키가 스테이징되면 즉시 차단 (base 의 .env 검사와 같은 계열)
  # shellcheck disable=SC2154  # staged 는 베이스 pre-commit.sh 가 설정한다
  if printf '%s\n' "$staged" | grep -qE '(^|/)(auth\.json|oauth-(private|public)\.key)$'; then
    echo "Blocked: Composer credentials (auth.json) or a Passport key (oauth-*.key) is staged. Add it to .gitignore and unstage it." >&2
    exit 2
  fi

  # composer.json 문법·composer.lock 동기화 (composer 가 설치돼 있을 때만)
  if command -v composer >/dev/null 2>&1; then
    echo "composer validate..." >&2
    if ! composer validate --no-check-publish --no-interaction 2>&1 | tail -20; then
      echo "Blocked: composer validate failed. Fix composer.json or run 'composer update --lock', then commit again." >&2
      exit 2
    fi
  else
    echo "pre-commit: composer not installed — skipping composer.json check" >&2
  fi

  if command -v php >/dev/null 2>&1; then
    # pint (프로젝트에 설치돼 있을 때만)
    if [ -x vendor/bin/pint ]; then
      echo "pint --test..." >&2
      if ! vendor/bin/pint --test 2>&1 | tail -20; then
        echo "Blocked: style differs. Run 'vendor/bin/pint' and commit again." >&2
        exit 2
      fi
    else
      echo "pre-commit: pint not installed — skipping style check" >&2
    fi

    # phpunit (테스트 디렉터리가 있고 설치돼 있을 때만)
    if [ -d tests ] && [ -x vendor/bin/phpunit ]; then
      echo "phpunit..." >&2
      if ! vendor/bin/phpunit --stop-on-failure 2>&1 | tail -20; then
        echo "Blocked: phpunit failed." >&2
        exit 2
      fi
    fi
  else
    echo "pre-commit: php not installed — skipping pint and phpunit" >&2
  fi
fi
