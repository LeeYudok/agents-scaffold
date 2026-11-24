#!/usr/bin/env python3
"""미러 커밋 전 시크릿 스캔 — 걸린 줄의 값은 절대 출력하지 않는다 (stdlib only).

커밋 직전에 스테이징된 변경(또는 디렉터리 트리)을 훑어 시크릿 모양을 찾고,
**파일 이름·줄 번호·패턴 이름·건수만** 보고한다. 진짜 토큰이면 값이 터미널과 로그에
남기 때문이다. 패턴의 원본은 이 파일의 PATTERNS 한 곳이다.

    python3 scan_secrets.py --staged [--repo DIR] [--host NAME]
    python3 scan_secrets.py --tree DIR

--staged 는 `git diff --cached` 에서 **추가된 줄**만 본다(이미 커밋된 줄은 대상이 아니다).
추가로 두 가지를 파일 이름만으로 막는다 — 자격증명 파일(oauth_creds·auth.json)과,
이 호스트 것이 아닌 `hosts/<다른 호스트>/`·`hosts/_legacy-shared/` 아래의 변경.

종료 코드: 걸린 것이 없으면 0, 있으면 1, git 을 쓸 수 없는 등 도구 문제면 2.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

# 값이 `<`·`$`·`(` 로 시작하면 자리표시자·변수 참조로 보고 넘긴다.
PATTERNS = [
    ("glpat", re.compile(r"glpat-", re.I)),
    ("ghp", re.compile(r"ghp_", re.I)),
    ("github_pat", re.compile(r"github_pat_", re.I)),
    ("sk-key", re.compile(r"sk-[A-Za-z0-9]{20}")),
    ("password", re.compile(r"password\s*[:=]\s*[^<$(\s]", re.I)),
    ("secret", re.compile(r"secret\s*[:=]\s*[^<$(\s]", re.I)),
    ("token", re.compile(r"token\s*[:=]\s*[^<$(\s]", re.I)),
]
CREDENTIAL_FILES = re.compile(r"(^|/)(oauth_creds[^/]*|auth\.json)$")


def scan_line(text: str) -> list[str]:
    return [name for name, rx in PATTERNS if rx.search(text)]


def resolve_host(explicit: str | None) -> str:
    """AGENTS_MEM_HOST → LocalHostName → hostname -s 순서로 호스트명을 정한다.

    sync 쪽 detect_host 가 소문자로 미러 폴더(hosts/<host>/)를 만드니, 여기서도 소문자로 돌려준다.
    """
    if explicit:
        return explicit.lower()
    if os.environ.get("AGENTS_MEM_HOST"):
        return os.environ["AGENTS_MEM_HOST"].lower()
    for cmd in (["scutil", "--get", "LocalHostName"], ["hostname", "-s"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
        except OSError:
            continue
        if out:
            return out.lower()
    return ""


def foreign_host_path(path: str, host: str) -> bool:
    parts = PurePosixPath(path).parts
    return len(parts) >= 2 and parts[0] == "hosts" and (parts[1] == "_legacy-shared" or parts[1] != host)


def git(repo: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "git 실패")
    return r.stdout


def scan_staged(repo: str, host: str) -> tuple[list[tuple[str, int, str]], list[str]]:
    """(파일, 줄, 사유) 목록과 파일 이름 수준 위반을 돌려준다."""
    hits: list[tuple[str, int, str]] = []
    path, lineno = "", 0
    for raw in git(repo, "diff", "--cached", "-U0", "--no-color").splitlines():
        if raw.startswith("+++ "):
            p = raw[4:].split("\t")[0]
            path = p[2:] if p.startswith("b/") else ""
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
        elif raw.startswith("+") and path:
            for name in scan_line(raw[1:]):
                hits.append((path, lineno, name))
            lineno += 1
    names = [n for n in git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines() if n]
    file_issues = []
    for n in names:
        if CREDENTIAL_FILES.search(n):
            file_issues.append(f"{n}: 자격증명 파일은 커밋하지 않는다")
        if host and foreign_host_path(n, host):
            file_issues.append(f"{n}: 다른 호스트(이 호스트: {host}) 디렉터리는 손으로 고치지 않는다")
    return hits, file_issues


def scan_tree(root: Path) -> tuple[list[tuple[str, int, str]], list[str]]:
    hits, file_issues = [], []
    for p in sorted(x for x in root.rglob("*") if x.is_file() and ".git" not in x.parts):
        rel = p.relative_to(root).as_posix()
        if CREDENTIAL_FILES.search(rel):
            file_issues.append(f"{rel}: 자격증명 파일은 커밋하지 않는다")
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(lines, 1):
            for name in scan_line(line):
                hits.append((rel, i, name))
    return hits, file_issues


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--tree", metavar="DIR")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--host")
    args = ap.parse_args(argv)
    try:
        if args.staged:
            hits, issues = scan_staged(args.repo, resolve_host(args.host))
        else:
            if not Path(args.tree).is_dir():
                raise RuntimeError(f"{args.tree} 는 디렉터리가 아니다")
            hits, issues = scan_tree(Path(args.tree))
    except (RuntimeError, OSError) as e:
        print(f"오류: 스캔하지 못했다 ({e})", file=sys.stderr)
        return 2
    for path, line, name in hits:
        print(f"{path}:{line} [{name}]")
    for msg in issues:
        print(msg)
    files = len({h[0] for h in hits})
    print(f"걸린 줄 {len(hits)}건, 파일 {files}개, 파일 이름 위반 {len(issues)}건")
    return 1 if hits or issues else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
