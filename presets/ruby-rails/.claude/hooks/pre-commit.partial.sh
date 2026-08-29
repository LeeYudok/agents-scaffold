# --- ruby-rails: master.key + rubocop + rspec gate ---
if [ -f Gemfile ]; then
  # Rails credentials 키가 스테이징되면 즉시 차단 (base 의 .env 검사와 같은 계열)
  if printf '%s\n' "$staged" | grep -qE '(^|/)(master\.key|credentials/[^/]+\.key)$'; then
    echo "차단: Rails credentials 키(master.key)가 스테이징됐다. .gitignore 에 추가하고 언스테이징할 것." >&2
    exit 2
  fi

  rb_cmd=""
  if command -v bundle >/dev/null 2>&1 && [ -f Gemfile.lock ]; then
    rb_cmd="bundle exec"
  fi

  # rubocop (설치돼 있을 때만)
  if $rb_cmd rubocop --version >/dev/null 2>&1; then
    echo "rubocop..." >&2
    if ! $rb_cmd rubocop --force-exclusion --fail-level convention 2>&1 | tail -20; then
      echo "차단: rubocop 실패. 'bundle exec rubocop -A' 실행 후 재커밋." >&2
      exit 2
    fi
  else
    echo "rubocop 미설치 — 스타일 검사 skipping" >&2
  fi

  # rspec (스펙 디렉터리가 있고 설치돼 있을 때만)
  if [ -d spec ] && $rb_cmd rspec --version >/dev/null 2>&1; then
    echo "rspec..." >&2
    if ! $rb_cmd rspec --fail-fast 2>&1 | tail -20; then
      echo "차단: rspec 실패." >&2
      exit 2
    fi
  fi
fi
