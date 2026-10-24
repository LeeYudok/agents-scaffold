# --- dotnet: secrets + build + format + test gate ---
dotnet_proj="$(git ls-files '*.sln' '*.slnx' '*.csproj' 2>/dev/null | head -1 || true)"
if [ -n "$dotnet_proj" ]; then
  # user-secrets 파일이 스테이징되면 즉시 차단 (base 의 .env 검사와 같은 계열)
  if printf '%s\n' "$staged" | grep -qE '(^|/)(secrets\.json|[^/]+\.pubxml\.user)$'; then
    echo "차단: .NET 시크릿 파일(secrets.json / *.pubxml.user)이 스테이징됐다. .gitignore 에 추가하고 언스테이징할 것." >&2
    exit 2
  fi

  if command -v dotnet >/dev/null 2>&1; then
    echo "dotnet build..." >&2
    if ! dotnet build --nologo 2>&1 | tail -20; then
      echo "차단: dotnet build 실패." >&2
      exit 2
    fi

    # dotnet format (SDK 6+ 내장, 없으면 skip)
    if dotnet format --version >/dev/null 2>&1; then
      echo "dotnet format --verify-no-changes..." >&2
      if ! dotnet format --verify-no-changes --no-restore 2>&1 | tail -20; then
        echo "차단: 포맷 불일치. 'dotnet format' 실행 후 재커밋." >&2
        exit 2
      fi
    else
      echo "dotnet format 미사용 가능 — 포맷 검사 skipping" >&2
    fi

    # 테스트 프로젝트가 있을 때만 실행
    if [ -n "$(git ls-files '*Tests.csproj' '*Test.csproj' '*.Tests/*.csproj' 2>/dev/null | head -1 || true)" ]; then
      echo "dotnet test..." >&2
      if ! dotnet test --nologo --no-build 2>&1 | tail -20; then
        echo "차단: dotnet test 실패." >&2
        exit 2
      fi
    fi
  else
    echo "dotnet SDK 미설치 — .NET 검사 skipping" >&2
  fi
fi
