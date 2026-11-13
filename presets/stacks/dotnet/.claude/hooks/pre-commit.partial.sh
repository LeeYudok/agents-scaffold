# --- dotnet: secrets + build + format + test gate ---
dotnet_proj="$(git ls-files '*.sln' '*.slnx' '*.csproj' 2>/dev/null | head -1 || true)"
if [ -n "$dotnet_proj" ]; then
  # user-secrets 파일이 스테이징되면 즉시 차단 (base 의 .env 검사와 같은 계열)
  # shellcheck disable=SC2154  # staged 는 베이스 pre-commit.sh 가 설정한다
  if printf '%s\n' "$staged" | grep -qE '(^|/)(secrets\.json|[^/]+\.pubxml\.user)$'; then
    echo "Blocked: a .NET secrets file (secrets.json / *.pubxml.user) is staged. Add it to .gitignore and unstage it." >&2
    exit 2
  fi

  if command -v dotnet >/dev/null 2>&1; then
    echo "dotnet build..." >&2
    if ! dotnet build --nologo 2>&1 | tail -20; then
      echo "Blocked: dotnet build failed." >&2
      exit 2
    fi

    # dotnet format (SDK 6+ 내장, 없으면 skip)
    if dotnet format --version >/dev/null 2>&1; then
      echo "dotnet format --verify-no-changes..." >&2
      if ! dotnet format --verify-no-changes --no-restore 2>&1 | tail -20; then
        echo "Blocked: formatting differs. Run 'dotnet format' and commit again." >&2
        exit 2
      fi
    else
      echo "pre-commit: dotnet format unavailable — skipping format check" >&2
    fi

    # 테스트 프로젝트가 있을 때만 실행
    if [ -n "$(git ls-files '*Tests.csproj' '*Test.csproj' '*.Tests/*.csproj' 2>/dev/null | head -1 || true)" ]; then
      echo "dotnet test..." >&2
      if ! dotnet test --nologo --no-build 2>&1 | tail -20; then
        echo "Blocked: dotnet test failed." >&2
        exit 2
      fi
    fi
  else
    echo "pre-commit: dotnet SDK not installed — skipping .NET checks" >&2
  fi
fi
