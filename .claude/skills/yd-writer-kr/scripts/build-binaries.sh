#!/usr/bin/env bash
# 반입용 check-writing 바이너리를 교차 빌드한다 (#137). 릴리스 워크플로가 이 스크립트로 세 플랫폼용을 만든다.
# Go 1.22 이상이 필요하다. 표준 라이브러리만 쓰므로 네트워크는 필요 없다.
#
#   build-binaries.sh <출력 폴더>                       # windows/amd64, linux/amd64, darwin/arm64
#   build-binaries.sh <출력 폴더> linux/arm64 ...       # 고른 플랫폼만 (GOOS/GOARCH)
#
# 결과 이름은 check-writing-<os>-<arch>[.exe] 다. 정적 바이너리라 받은 쪽에서 설치할 것이 없다.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [ "$#" -lt 1 ]; then
  echo 'build-binaries: 출력 폴더를 지정한다' >&2
  exit 2
fi
mkdir -p "$1"
out="$(cd "$1" && pwd -P)"
shift
[ "$#" -gt 0 ] || set -- windows/amd64 linux/amd64 darwin/arm64
for target in "$@"; do
  os="${target%/*}"
  arch="${target#*/}"
  name="check-writing-$os-$arch"
  [ "$os" != windows ] || name="$name.exe"
  # -buildvcs=false·-trimpath 는 빌드한 PC 의 경로와 커밋 상태가 바이너리에 남지 않게 한다.
  (cd "$root/go" && GOOS="$os" GOARCH="$arch" GOTOOLCHAIN=local GOWORK=off GOFLAGS=-mod=readonly CGO_ENABLED=0 \
    go build -trimpath -buildvcs=false -ldflags='-s -w' -o "$out/$name" .)
  echo "$out/$name"
done
