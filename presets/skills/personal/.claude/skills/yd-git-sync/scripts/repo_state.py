#!/usr/bin/env python3
"""여러 호스트에 있는 같은 저장소의 git 상태를 한 표로 비교한다.

    python3 repo_state.py local pig doksam            # 비교만
    python3 repo_state.py local pig doksam --pull     # 깨끗한 클론만 ff-only 로 당긴 뒤 비교

호스트마다 HEAD·브랜치·고친 파일 수·추적 파일 수·심링크 수·목록 해시를 낸다.
목록 해시는 `git ls-files -s | git hash-object --stdin` 이다. 경로·모드·blob 해시를
모두 담으므로, 이 값이 같으면 추적 파일의 이름과 내용이 같다.

`--pull` 은 고친 파일이 없는 클론만 당긴다. 고친 파일이 있으면 건너뛰고 표에
그 사실을 남긴다. 병합 커밋을 만들지 않도록 항상 `--ff-only` 다.
종료 코드: 모든 호스트의 HEAD·목록 해시·추적 파일 수가 같으면 0, 아니면 1.
"""
from __future__ import annotations

import argparse
import sys

from hosts import default_rel_path, local_root, run

PROBE = r"""
git fetch -q origin 2>/dev/null || echo "fetch=fail"
dirty=$(git status --porcelain | wc -l | tr -d ' ')
if [ "$PULL" = 1 ]; then
  if [ "$dirty" = 0 ]; then
    git pull -q --ff-only 2>/dev/null && echo "pull=ok" || echo "pull=fail"
  else
    echo "pull=skip-dirty"
  fi
fi
echo "branch=$(git branch --show-current)"
echo "head=$(git rev-parse HEAD)"
echo "upstream=$(git rev-parse @{u} 2>/dev/null || echo -)"
echo "dirty=$(git status --porcelain | wc -l | tr -d ' ')"
echo "tracked=$(git ls-files | wc -l | tr -d ' ')"
echo "symlinks=$(git ls-files -s | awk '$1==120000' | wc -l | tr -d ' ')"
echo "listhash=$(git ls-files -s | git hash-object --stdin)"
"""

FIELDS = ("branch", "head", "upstream", "dirty", "tracked", "symlinks", "listhash", "pull", "fetch")


def parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, val = line.partition("=")
        if sep and key in FIELDS:
            out[key] = val.strip()
    return out


def verdict(states: dict[str, dict[str, str]]) -> list[str]:
    """어긋난 항목을 문장으로 돌려준다. 빈 목록이면 전부 같다."""
    problems = []
    for key in ("head", "listhash", "tracked"):
        vals = {h: s.get(key, "?") for h, s in states.items()}
        if len(set(vals.values())) > 1:
            problems.append(f"{key} 가 다르다: " + ", ".join(f"{h}={v[:12]}" for h, v in vals.items()))
    for host, s in states.items():
        if s.get("dirty", "0") != "0":
            problems.append(f"{host}: 고친 파일 {s['dirty']}개")
        if s.get("upstream", "-") not in ("-", s.get("head")):
            problems.append(f"{host}: origin 과 HEAD 가 다르다")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hosts", nargs="+", help="local 또는 ssh 별칭")
    ap.add_argument("--repo-path", help="$HOME 기준 저장소 경로 (기본: 지금 저장소)")
    ap.add_argument("--pull", action="store_true", help="깨끗한 클론만 git pull --ff-only")
    args = ap.parse_args(argv)

    rel = args.repo_path or default_rel_path(local_root())
    states: dict[str, dict[str, str]] = {}
    for host in args.hosts:
        script = f"PULL={1 if args.pull else 0}\n{PROBE}"
        try:
            states[host] = parse(run(host, rel, script).decode("utf-8", "replace"))
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2

    print(f"repo: ~/{rel}")
    print(f"{'host':<10} {'branch':<14} {'head':<10} {'dirty':>5} {'tracked':>7} {'links':>5}  listhash      pull")
    for host, s in states.items():
        print(f"{host:<10} {s.get('branch', '?'):<14} {s.get('head', '?')[:9]:<10} "
              f"{s.get('dirty', '?'):>5} {s.get('tracked', '?'):>7} {s.get('symlinks', '?'):>5}  "
              f"{s.get('listhash', '?')[:12]:<13} {s.get('pull', '-')}")
    problems = verdict(states)
    for p in problems:
        print(f"  ! {p}")
    print("판정: 같음" if not problems else "판정: 다름")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
