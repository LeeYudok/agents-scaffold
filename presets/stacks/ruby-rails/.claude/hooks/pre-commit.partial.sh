# --- ruby-rails: master.key + rubocop + rspec gate ---
if [ -f Gemfile ]; then
  # Rails credentials 키가 스테이징되면 즉시 차단 (base 의 .env 검사와 같은 계열)
  # shellcheck disable=SC2154  # staged 는 베이스 pre-commit.sh 가 설정한다
  if printf '%s\n' "$staged" | grep -qE '(^|/)(master\.key|credentials/[^/]+\.key)$'; then
    echo "Blocked: a Rails credentials key (master.key) is staged. Add it to .gitignore and unstage it." >&2
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
      echo "Blocked: rubocop failed. Run 'bundle exec rubocop -A' and commit again." >&2
      exit 2
    fi
  else
    echo "pre-commit: rubocop not installed — skipping style check" >&2
  fi

  # rspec (스펙 디렉터리가 있고 설치돼 있을 때만)
  if [ -d spec ] && $rb_cmd rspec --version >/dev/null 2>&1; then
    echo "rspec..." >&2
    if ! $rb_cmd rspec --fail-fast 2>&1 | tail -20; then
      echo "Blocked: rspec failed." >&2
      exit 2
    fi
  fi
fi
