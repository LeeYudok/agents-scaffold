#!/usr/bin/env python3
"""문서가 가리키는 경로 중 실제로 없는 것을 찾는다 (stdlib only).

두 가지 방식이 있다.

* 기본: 추적 중인 문서에서 백틱(`...`)·마크다운 링크 안의 경로를 뽑아
  저장소 루트나 그 문서의 폴더 기준으로 존재하는지 본다.
* ``--removed-since REV``: REV 와 HEAD 사이에 지워지거나 옮겨진 파일·폴더를
  모으고, 문서 본문(백틱 밖 포함)에서 그 경로를 가리키는 줄만 보고한다.
  큰 삭제·이동 뒤 남은 참조를 정밀하게 찾을 때 쓴다.

찾은 줄은 두 갈래로 나눈다.

* ``current`` — 현행 지시처럼 읽히는 줄. 고칠 후보다.
* ``history`` — 같은 줄에 제거·이동·당시 같은 이력 표지가 있는 줄.
  날짜·이슈 번호가 붙은 기록은 고치지 않는 것이 원칙이라 따로 센다.

분류는 낱말 기반 추정이다. 최종 판단은 사람이나 에이전트가 줄을 읽고 한다.

레포별 범위는 루트 ``AGENTS.yaml`` 의 ``x-doc-sync`` 섹션에서 읽는다(있으면).

    x-doc-sync:
      history:            # 시점 기록 — 찾아도 history 로만 센다
        - CHANGELOG.md
        - docs/superpowers/{plans,specs}/**
      exclude:            # 아예 훑지 않는다
        - data/manual/**

glob 은 ``*``·``**``(둘 다 ``/`` 를 넘는다)와 ``{a,b}`` 를 쓴다. PyYAML 이 없어도
이 모양(블록 목록·흐름 목록)은 읽는다.

사용:
  python3 find_stale_refs.py [--root DIR] [--removed-since REV]
                             [--include GLOB ...] [--exclude GLOB ...]
                             [--ignore REGEX ...] [--json] [--strict]

종료 코드: current 가 하나라도 있으면 1(``--strict`` 면 history 도 셈), 없으면 0,
git 이나 인자 오류는 2.
"""
from __future__ import annotations

import argparse
import bisect
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

#: 기본으로 훑는 문서. 코드 파일은 넣지 않는다 — 코드의 경로 문자열은
#: 빌드·테스트가 잡는다.
DEFAULT_INCLUDE = (
    "*.md", "*.mdc", "*.markdown", "*.yaml", "*.yml", "*.toml", "*.txt",
    "AGENTS*", "CLAUDE*", "GEMINI*",
)
#: 기본 제외. 잠금 파일·벤더·생성물은 경로처럼 보이는 토큰이 많고 손으로 고치지 않는다.
DEFAULT_EXCLUDE = (
    "*lock.yaml", "*lock.yml", "*.lock", "node_modules/*", "*/node_modules/*",
    "vendor/*", "*/vendor/*", "dist/*", "*/dist/*",
)

#: 같은 줄에 있으면 이력으로 보는 표지. 날짜·이슈 번호만으로는 판정하지 않는다 —
#: 현행 지시에도 근거 이슈 번호가 붙는다.
HISTORY_MARKERS = re.compile(
    r"(제거|지웠|옮겼|옮긴|폐기|철거|없앴|없애|당시|이전에는|예전|옛 |#\d+\s*(?:전|이전)\b|"
    r"시점 기록|기록이다|removed|deleted|deprecated|renamed|formerly)",
    re.IGNORECASE,
)

#: 파일 전체가 이력인 문서. 지난 판본의 기록이라 경로가 사라져도 고치지 않는다.
HISTORY_FILES = re.compile(r"(^|/)(CHANGELOG|HISTORY|RELEASES?|NEWS)[^/]*$|(^|/)archive/", re.IGNORECASE)
#: 자리표시자. 실제 경로가 아니라 형식을 보여 주는 표기다.
PLACEHOLDER = re.compile(r"X\.Y|YYYY|NNNN|MM-DD|\.\.\.|…")

BACKTICK = re.compile(r"`([^`\n]+)`")
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
SKIP_TOKEN = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#|~|\$)|[<>{}*?|\s]", re.IGNORECASE)


@dataclass
class Finding:
    file: str
    line: int
    ref: str
    kind: str  # current | history
    reason: str  # missing | removed | renamed -> <new>
    text: str


def expand_braces(pattern: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    out = []
    for alt in m.group(1).split(","):
        out.extend(expand_braces(pattern[:m.start()] + alt + pattern[m.end():]))
    return out


def glob_match(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        for g in expand_braces(pat):
            # fnmatch 의 * 는 / 도 넘으므로 ** 는 * 로 충분하다.
            if fnmatch.fnmatch(path, g.replace("**", "*")):
                return True
    return False


def repo_config(root: Path) -> dict[str, list[str]]:
    """AGENTS.yaml 의 x-doc-sync.{history,exclude} 를 읽는다. 없으면 빈 값."""
    path = root / "AGENTS.yaml"
    cfg: dict[str, list[str]] = {"history": [], "exclude": []}
    if not path.is_file():
        return cfg
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = (yaml.safe_load(text) or {}).get("x-doc-sync") or {}
        for key in cfg:
            cfg[key] = [str(v) for v in (data.get(key) or [])]
        return cfg
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 — 깨진 YAML 은 경고만 하고 기본값으로 간다
        print(f"경고: AGENTS.yaml 을 읽지 못했다({exc}) — x-doc-sync 없이 진행", file=sys.stderr)
        return cfg
    # PyYAML 없이: 최상위 `x-doc-sync:` 블록 안의 history/exclude 목록만 읽는다.
    block = re.search(r"(?m)^x-doc-sync:[ \t]*\n((?:[ \t]+.*\n?|[ \t]*\n)*)", text)
    if not block:
        return cfg
    current = None
    for line in block.group(1).splitlines():
        line = line.split(" #", 1)[0].rstrip()
        m = re.match(r"^\s+(history|exclude):\s*(\[.*\])?\s*$", line)
        if m:
            current = m.group(1)
            if m.group(2):
                cfg[current] += [v.strip().strip("'\"") for v in m.group(2)[1:-1].split(",") if v.strip()]
                current = None
            continue
        m = re.match(r"^\s+-\s+(.+)$", line)
        if m and current:
            cfg[current].append(m.group(1).strip().strip("'\""))
    return cfg


def git(root: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], check=True,
                             capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise SystemExit(f"git {' '.join(args)} 실패: {detail.strip()}") from None
    return out.stdout


def tracked_docs(root: Path, include: list[str], exclude: list[str]) -> list[str]:
    files = git(root, "-c", "core.quotepath=false", "ls-files").splitlines()
    picked = []
    for f in files:
        name = PurePosixPath(f).name
        if not any(fnmatch.fnmatch(name, g) or fnmatch.fnmatch(f, g) for g in include):
            continue
        if any(fnmatch.fnmatch(f, g) for g in exclude):
            continue
        picked.append(f)
    return picked


def clean(token: str) -> str | None:
    """경로 후보 토큰을 다듬는다. 경로가 아니면 None."""
    token = token.strip().strip("'\"")
    token = re.sub(r"[),.;:]+$", "", token)
    token = token.split("#", 1)[0]
    token = re.sub(r":\d+(?:-\d+)?$", "", token)  # file.go:12
    if token.startswith("./"):
        token = token[2:]
    if not token or SKIP_TOKEN.search(token) or PLACEHOLDER.search(token) or token.startswith("/") or ".." in PurePosixPath(token).parts:
        return None
    if "/" not in token and "." not in token:
        return None
    if " " in token or len(token) > 200:
        return None
    return token


def removed_paths(root: Path, rev: str) -> tuple[set[str], dict[str, str]]:
    """REV..HEAD 에서 사라진 파일·폴더와 이동(옛 경로 → 새 경로)을 돌려준다."""
    gone: set[str] = set()
    renamed: dict[str, str] = {}
    diff = git(root, "-c", "core.quotepath=false", "diff", "--name-status", "-M", rev, "HEAD")
    for line in diff.splitlines():
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("D"):
            gone.add(parts[1])
        elif status.startswith("R") and len(parts) == 3:
            renamed[parts[1]] = parts[2]
    before = git(root, "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", rev).splitlines()
    now = set(git(root, "-c", "core.quotepath=false", "ls-files").splitlines())
    now_dirs = {str(p) for f in now for p in PurePosixPath(f).parents if str(p) != "."}
    for f in before:
        for p in PurePosixPath(f).parents:
            d = str(p)
            if d != "." and d not in now_dirs:
                gone.add(d)
    return gone, renamed


def match_removed(token: str, gone: set[str], renamed: dict[str, str]) -> str | None:
    t = token.rstrip("/")
    if t in renamed:
        return f"renamed -> {renamed[t]}"
    if t in gone:
        return "removed"
    for g in gone:
        if t.startswith(g + "/"):
            return "removed"
    return None


def known_paths(root: Path) -> tuple[set[str], set[str]]:
    """추적 중인 파일·폴더 경로와, 그 경로의 모든 꼬리(suffix)를 돌려준다.

    꼬리 집합은 하위 프로젝트 기준 상대경로(예: 팩 안의 `config/x.yaml`,
    `ews-v3/web/src` 를 가리키는 `web/src`)를 실재하는 경로로 인정하는 데 쓴다.
    """
    full: set[str] = set()
    for f in git(root, "-c", "core.quotepath=false", "ls-files").splitlines():
        full.add(f)
        full.update(str(p) for p in PurePosixPath(f).parents if str(p) != ".")
    tails: set[str] = set()
    for f in full:
        parts = f.split("/")
        for i in range(1, len(parts)):
            tails.add("/".join(parts[i:]))
    return full, tails


def scan(root: Path, docs: list[str], rev: str | None, ignore: list[re.Pattern],
         history_globs: list[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    full, tails = known_paths(root)
    top = {f.split("/", 1)[0] for f in full}
    ordered = sorted(full | tails)

    def exists_somewhere(cand: str) -> bool:
        """정확히 있거나, `docs/12` 처럼 마지막 조각이 실제 이름의 앞부분인 축약이면 참."""
        if cand in full or cand in tails:
            return True
        i = bisect.bisect_left(ordered, cand)
        return i < len(ordered) and ordered[i].startswith(cand) and "/" not in ordered[i][len(cand):]
    gone: set[str] = set()
    renamed: dict[str, str] = {}
    if rev:
        gone, renamed = removed_paths(root, rev)
        # 백틱 밖 맨 경로도 잡는다. 사라진 경로 이름과 겹치는 토큰만 보므로 오탐이 적다.
        names = sorted({*gone, *renamed}, key=len, reverse=True)
        if not names:
            return findings
        bare = re.compile(r"(?<![\w/.-])(" + "|".join(re.escape(n) for n in names) + r")(?=[/\s`'\")\],.:;]|$)")
    for doc in docs:
        path = root / doc
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        base = PurePosixPath(doc).parent
        history_file = bool(HISTORY_FILES.search(doc)) or glob_match(doc, history_globs or [])
        for no, text in enumerate(lines, 1):
            if any(p.search(text) for p in ignore):
                continue
            seen: set[str] = set()
            if rev:
                cands = [m.group(1) for m in bare.finditer(text)]
                cands += [m.group(1) for m in BACKTICK.finditer(text)] + [m.group(1) for m in MD_LINK.finditer(text)]
            else:
                cands = [m.group(1) for m in BACKTICK.finditer(text)] + [m.group(1) for m in MD_LINK.finditer(text)]
            for raw in cands:
                token = clean(raw)
                if not token:
                    continue
                token = token.rstrip("/")
                if token in seen:
                    continue
                seen.add(token)
                rel = str(base / token) if str(base) != "." else token
                if exists_somewhere(token) or exists_somewhere(rel):
                    continue  # 어딘가에 실제로 있다(하위 프로젝트 기준 상대경로·번호 축약 포함)
                if rev:
                    reason = match_removed(token, gone, renamed) or match_removed(rel, gone, renamed)
                    if not reason:
                        continue
                else:
                    # 첫 조각이 레포 루트나 문서 폴더에 실재할 때만 본다 — 다른 레포·하위
                    # 프로젝트 기준 경로까지 세면 결과가 소음에 묻힌다.
                    first = token.split("/", 1)[0]
                    if "/" not in token or (first not in top and not (root / base / first).exists()):
                        continue
                    if (root / token).exists() or (root / rel).exists():
                        continue
                    reason = "missing"
                kind = "history" if (history_file or HISTORY_MARKERS.search(text)) else "current"
                findings.append(Finding(doc, no, token, kind, reason, text.strip()[:240]))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".", help="저장소 루트 (기본: 현재 폴더)")
    ap.add_argument("--removed-since", metavar="REV", help="REV..HEAD 에서 지워지거나 옮겨진 경로만 본다")
    ap.add_argument("--include", nargs="*", default=list(DEFAULT_INCLUDE), help="훑을 문서 glob")
    ap.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDE), help="뺄 경로 glob")
    ap.add_argument("--ignore", nargs="*", default=[], help="이 정규식에 맞는 줄은 건너뛴다")
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    ap.add_argument("--strict", action="store_true", help="history 도 실패로 센다")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        top = git(root, "rev-parse", "--show-toplevel").strip()
        root = Path(top)
        if args.removed_since:
            git(root, "rev-parse", "--verify", args.removed_since + "^{commit}")
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2
    try:
        ignore = [re.compile(p) for p in args.ignore]
    except re.error as exc:
        print(f"--ignore 정규식 오류: {exc}", file=sys.stderr)
        return 2

    cfg = repo_config(root)
    docs = [d for d in tracked_docs(root, args.include, args.exclude) if not glob_match(d, cfg["exclude"])]
    findings = scan(root, docs, args.removed_since, ignore, cfg["history"])
    current = [f for f in findings if f.kind == "current"]
    history = [f for f in findings if f.kind == "history"]

    if args.json:
        print(json.dumps({"docs": len(docs), "current": [asdict(f) for f in current],
                          "history": [asdict(f) for f in history]}, ensure_ascii=False, indent=2))
    else:
        mode = f"--removed-since {args.removed_since}" if args.removed_since else "존재 검사"
        print(f"[{mode}] 문서 {len(docs)}개 — current {len(current)}건, history {len(history)}건")
        for title, group in (("current (고칠 후보)", current), ("history (이력 표지 있음 — 대개 둔다)", history)):
            if not group:
                continue
            print(f"\n## {title}")
            for f in group:
                print(f"{f.file}:{f.line}  {f.ref}  [{f.reason}]\n    {f.text}")
    failed = current + (history if args.strict else [])
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # `| head` 로 잘라 볼 때
        sys.exit(0)
