#!/usr/bin/env python3
"""git 이 관리하지 않는 폴더를 여러 호스트에서 합집합으로 맞춘다.

    python3 union_sync.py local pig doksam --dir docs            # 계획만 (dry-run)
    python3 union_sync.py local pig doksam --dir docs --apply    # 복사 후 재검증

규칙:
- 지우지 않고 덮어쓰지 않는다. 없는 파일만 채운다.
- 같은 경로인데 내용이 다르면 충돌이다. 어느 쪽에도 복사하지 않고 보고만 한다.
- 경로는 NFC 로 정규화해 비교한다. 맥에서 만든 한글 이름(NFD)과 리눅스 이름(NFC)을
  같은 파일로 본다. 원격에는 NFC 이름으로 쓴다.
- 한 호스트에 NFC·NFD 두 이름이 같이 있으면 중복으로 보고한다. 지우지 않는다.
- 머신마다 다른 캐시(.DS_Store, __pycache__, *.pyc, .git)는 기본으로 뺀다.
- 심링크는 비교·복사하지 않고 개수만 보고한다.

복사는 `local` 을 허브로 쓴다. 원격에만 있는 파일을 먼저 로컬로 받고, 로컬에서
나머지 원격으로 보낸다. 그래서 `--apply` 에는 호스트 목록에 `local` 이 있어야 한다.
원격 압축 해제는 GNU tar(`--skip-old-files`)를 쓴다. 원격은 리눅스라고 본다.

종료 코드: 맞춰야 할 파일이 없고 충돌도 없으면 0, 남아 있으면 1, 접속 실패는 2.
"""
from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import shlex
import subprocess
import sys
import tarfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from hosts import LOCAL, default_rel_path, local_path, local_root, run, shell_cmd

DEFAULT_EXCLUDES = (".DS_Store", "__pycache__", "*.pyc", ".git")

# 원격에서 `python3 - <dir>` 로 돈다. 한 줄에 파일 하나, JSON.
MANIFEST_CODE = r"""
import hashlib, json, os, sys
top = sys.argv[1]
for root, dirs, files in os.walk(top):
    for name in dirs + files:
        p = os.path.join(root, name)
        if os.path.islink(p):
            print(json.dumps({"p": p, "link": True}, ensure_ascii=False))
    for name in files:
        p = os.path.join(root, name)
        if os.path.islink(p) or not os.path.isfile(p):
            continue
        h = hashlib.sha1()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        print(json.dumps({"p": p, "h": h.hexdigest(), "s": os.path.getsize(p)}, ensure_ascii=False))
"""


def nfc(path: str) -> str:
    return unicodedata.normalize("NFC", path)


def excluded(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(part, pat) for part in path.split("/") for pat in patterns)


@dataclass
class Manifest:
    files: dict[str, str] = field(default_factory=dict)   # 실제 이름 → 해시
    links: list[str] = field(default_factory=list)


@dataclass
class Plan:
    copies: dict[str, list[tuple[str, str]]]   # 대상 호스트 → [(원본 호스트, 원본 실제 이름)]
    conflicts: dict[str, dict[str, str]]       # NFC 경로 → {호스트: 해시}
    duplicates: dict[str, list[str]]           # 호스트 → NFC·NFD 가 겹친 NFC 경로
    union: int


def parse_manifest(text: str) -> Manifest:
    m = Manifest()
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("link"):
            m.links.append(row["p"])
        else:
            m.files[row["p"]] = row["h"]
    return m


def make_plan(manifests: dict[str, Manifest], excludes: tuple[str, ...] = DEFAULT_EXCLUDES) -> Plan:
    """호스트 순서가 원본 우선순위다. 앞에 있는 호스트의 파일을 원본으로 고른다."""
    keyed: dict[str, dict[str, tuple[str, str]]] = {}
    duplicates: dict[str, list[str]] = {}
    for host, man in manifests.items():
        table: dict[str, tuple[str, str]] = {}
        for raw, digest in sorted(man.files.items()):
            if excluded(raw, excludes):
                continue
            key = nfc(raw)
            if key in table:
                duplicates.setdefault(host, []).append(key)
                # NFC 이름을 원본으로 남긴다. 리눅스로 보낼 때 그 이름이 맞다.
                if raw == key:
                    table[key] = (digest, raw)
                continue
            table[key] = (digest, raw)
        keyed[host] = table

    union = set().union(*(t.keys() for t in keyed.values())) if keyed else set()
    conflicts = {}
    for key in union:
        digests = {h: t[key][0] for h, t in keyed.items() if key in t}
        if len(set(digests.values())) > 1:
            conflicts[key] = digests

    copies: dict[str, list[tuple[str, str]]] = {h: [] for h in keyed}
    for key in sorted(union - conflicts.keys()):
        src = next(h for h in keyed if key in keyed[h])
        for host, table in keyed.items():
            if key not in table:
                copies[host].append((src, keyed[src][key][1]))
    return Plan(copies=copies, conflicts=conflicts, duplicates=duplicates, union=len(union))


def collect(hosts: list[str], rel: str, top: str) -> dict[str, Manifest]:
    out = {}
    for host in hosts:
        text = run(host, rel, f"python3 - {shlex.quote(top)}", stdin=MANIFEST_CODE.encode())
        out[host] = parse_manifest(text.decode("utf-8", "surrogateescape"))
    return out


def safe_member(name: str, top: str) -> bool:
    parts = Path(name).parts
    return bool(parts) and not Path(name).is_absolute() and ".." not in parts and parts[0] == top.strip("/").split("/")[0]


def extract_stream(stream: io.BufferedIOBase, root: Path, top: str) -> tuple[int, int]:
    """tar 스트림에서 일반 파일만 꺼낸다. 이미 있는 이름은 건너뛴다. (쓴 수, 건너뛴 수)."""
    written = skipped = 0
    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            if not member.isfile() or not safe_member(member.name, top):
                skipped += 1
                continue
            dest = root / member.name
            if dest.exists():
                skipped += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(member)
            with open(dest, "xb") as out:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            os.utime(dest, (member.mtime, member.mtime))
            written += 1
    return written, skipped


def pull_to_local(src: str, names: list[str], rel: str, top: str) -> tuple[int, int]:
    listing = b"".join(n.encode("utf-8", "surrogateescape") + b"\0" for n in names)
    proc = subprocess.Popen(shell_cmd(src, rel, "tar --null -T - -cf -"), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    proc.stdin.write(listing)
    proc.stdin.close()
    result = extract_stream(proc.stdout, local_path(rel), top)
    if proc.wait() != 0:
        raise RuntimeError(f"{src}: tar 묶기 실패")
    return result


def push_from_local(dst: str, names: list[str], rel: str) -> int:
    root = local_path(rel)
    proc = subprocess.Popen(shell_cmd(dst, rel, "tar --skip-old-files --no-same-owner -xf -"),
                            stdin=subprocess.PIPE)
    seen = set()
    with tarfile.open(fileobj=proc.stdin, mode="w|", format=tarfile.PAX_FORMAT) as tar:
        for name in names:
            arc = nfc(name)
            if arc in seen:
                continue
            seen.add(arc)
            info = tar.gettarinfo(str(root / name), arcname=arc)
            info.mode, info.uid, info.gid, info.uname, info.gname = 0o644, 0, 0, "", ""
            with open(root / name, "rb") as f:
                tar.addfile(info, f)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"{dst}: tar 풀기 실패")
    return len(seen)


def report(plan: Plan, manifests: dict[str, Manifest], verbose: bool) -> None:
    print(f"합집합 {plan.union}개 (캐시 제외)")
    for host, man in manifests.items():
        print(f"  {host:<10} 파일 {len(man.files):>6}  심링크 {len(man.links):>3}  "
              f"채울 것 {len(plan.copies.get(host, [])):>5}")
    routes: dict[str, list[str]] = {}
    for dst, items in plan.copies.items():
        for src, name in items:
            routes.setdefault(f"{src} -> {dst}", []).append(name)
    for route, names in sorted(routes.items()):
        print(f"  {route}: {len(names)}개")
        for n in names if verbose else names[:5]:
            print(f"      {n}")
        if not verbose and len(names) > 5:
            print(f"      … 외 {len(names) - 5}개 (--verbose)")
    for key, digests in sorted(plan.conflicts.items()):
        print(f"  ! 충돌 {key}: " + ", ".join(f"{h}={d[:8]}" for h, d in digests.items()))
    for host, keys in plan.duplicates.items():
        for key in keys:
            print(f"  ! {host} NFC/NFD 중복: {key}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hosts", nargs="+", help="local 또는 ssh 별칭. 앞 호스트가 원본 우선")
    ap.add_argument("--dir", required=True, help="저장소 루트 기준 맞출 폴더 (예: docs)")
    ap.add_argument("--repo-path", help="$HOME 기준 저장소 경로 (기본: 지금 저장소)")
    ap.add_argument("--exclude", action="append", default=[], help="추가 제외 패턴 (경로 조각 fnmatch)")
    ap.add_argument("--apply", action="store_true", help="실제로 복사한다")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    rel = args.repo_path or default_rel_path(local_root())
    top = args.dir.strip("/")
    excludes = DEFAULT_EXCLUDES + tuple(args.exclude)
    if args.apply and LOCAL not in args.hosts:
        print("오류: --apply 는 local 을 허브로 쓴다. 호스트 목록에 local 을 넣는다", file=sys.stderr)
        return 2

    try:
        manifests = collect(args.hosts, rel, top)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 2
    plan = make_plan(manifests, excludes)
    print(f"repo: ~/{rel}  dir: {top}/  ({'apply' if args.apply else 'dry-run'})")
    report(plan, manifests, args.verbose)

    if args.apply and any(plan.copies.values()):
        by_src: dict[str, list[str]] = {}
        for src, name in plan.copies.get(LOCAL, []):
            by_src.setdefault(src, []).append(name)
        for src, names in by_src.items():
            w, s = pull_to_local(src, names, rel, top)
            print(f"  받음 {src} -> local: {w}개 (건너뜀 {s})")
        # 로컬이 이제 합집합을 갖는다. 원격마다 빠진 것을 로컬 이름으로 보낸다.
        local_names = {nfc(n): n for n in collect([LOCAL], rel, top)[LOCAL].files}
        for dst, items in plan.copies.items():
            if dst == LOCAL or not items:
                continue
            names = [local_names[nfc(n)] for _, n in items if nfc(n) in local_names]
            print(f"  보냄 local -> {dst}: {push_from_local(dst, names, rel)}개")
        manifests = collect(args.hosts, rel, top)
        plan = make_plan(manifests, excludes)
        print("재검증:")
        report(plan, manifests, args.verbose)

    left = sum(len(v) for v in plan.copies.values())
    ok = left == 0 and not plan.conflicts
    print("판정: 같음" if ok else f"판정: 다름 (채울 것 {left}, 충돌 {len(plan.conflicts)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
