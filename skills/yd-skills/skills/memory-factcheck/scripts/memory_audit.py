#!/usr/bin/env python3
"""메모리 디렉터리 사전 점검기 (stdlib only, 읽기 전용).

    python3 memory_audit.py <메모리디렉터리> [--repo <레포루트>] [--json]

두 가지를 한다.

1. 구조 점검: 인덱스(MEMORY.md)가 가리키는 파일이 없는지, 인덱스에 빠진 파일이 있는지,
   frontmatter 가 깨졌는지, `[[링크]]` 가 없는 메모리를 가리키는지, name 이 겹치는지.
2. 단언 후보 추출과 1차 분류: 파일 경로·함수 이름·이슈 번호를 뽑아 `--repo` 의 파일시스템과
   대조한다. 원본에 닿지 못하면 fresh 가 아니라 unverified 다 — fresh 로 세면 다음 감사가
   그 메모리를 건너뛴다.

이 스크립트는 파일을 만들거나 고치거나 지우지 않는다. 판정은 후보를 좁히는 용도이고,
핵심 단언을 고르고 교정하는 일은 SKILL.md 절차대로 에이전트가 한다.
종료 코드: 0 구조 문제 없음, 1 구조 문제 있음, 2 사용 오류(디렉터리 없음 등).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

INDEX_NAME = "MEMORY.md"
PERSONAL_PREFIX = "user_"  # 소유자 개인 파일은 범위 밖이다
TYPES = {"user", "feedback", "project", "reference"}

INDEX_LINE = re.compile(r"^\s*[-*]\s*\[[^\]]*\]\(([^)\s]+)\)")
WIKILINK = re.compile(r"\[\[([^\]\n]+)\]\]")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
ISSUE_REF = re.compile(r"(?<![\w&])#(\d{1,6})\b")
SYMBOL = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)\(\)$")
PATH_LIKE = re.compile(r"^[~./A-Za-z0-9_@+-][A-Za-z0-9_@+./-]*$")
EXT = re.compile(r"\.[A-Za-z0-9]{1,6}$")


def parse_frontmatter(text: str):
    """(필드 dict, 오류 문자열|None). 최상위 키와 한 단계 중첩만 읽는다."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "frontmatter 없음"
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, "frontmatter 가 닫히지 않음"
    fields: dict = {}
    parent = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([A-Za-z_][\w-]*)\s*:\s*(.*)$", raw)
        if not m:
            return fields, f"해석할 수 없는 줄: {raw.strip()[:40]}"
        indent, key, val = m.groups()
        val = val.strip().strip("\"'")
        if indent and parent is not None:
            fields[parent][key] = val
        elif val == "":
            fields[key] = {}
            parent = key
        else:
            fields[key] = val
            parent = None
    return fields, None


def memory_type(fields: dict) -> str:
    """type 은 최상위 또는 metadata.type 어느 쪽에 있어도 인정한다."""
    t = fields.get("type")
    if not t and isinstance(fields.get("metadata"), dict):
        t = fields["metadata"].get("type")
    return t if isinstance(t, str) else ""


def body_of(text: str) -> str:
    parts = text.split("\n---", 2)
    return parts[-1] if text.startswith("---") and len(parts) == 3 else text


def structure_findings(root: Path):
    """구조 문제 목록과 메모리 파일 목록."""
    findings: list[dict] = []
    files = sorted(p for p in root.glob("*.md") if p.name != INDEX_NAME)
    scoped = [p for p in files if not p.name.startswith(PERSONAL_PREFIX)]
    names: dict[str, list[str]] = {}
    for p in scoped:
        fields, err = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        if err:
            findings.append({"kind": "bad-frontmatter", "file": p.name, "detail": err})
            continue
        for key in ("name", "description"):
            if not isinstance(fields.get(key), str) or not fields[key]:
                findings.append({"kind": "bad-frontmatter", "file": p.name,
                                 "detail": f"{key} 없음"})
        t = memory_type(fields)
        if not t:
            findings.append({"kind": "bad-frontmatter", "file": p.name, "detail": "type 없음"})
        elif t not in TYPES:
            findings.append({"kind": "bad-frontmatter", "file": p.name,
                             "detail": f"알 수 없는 type: {t}"})
        if isinstance(fields.get("name"), str) and fields["name"]:
            names.setdefault(fields["name"], []).append(p.name)
    for name, owners in names.items():
        if len(owners) > 1:
            findings.append({"kind": "duplicate-name", "file": ", ".join(owners),
                             "detail": f"name '{name}' 중복"})

    index = root / INDEX_NAME
    indexed: set[str] = set()
    if index.is_file():
        for line in index.read_text(encoding="utf-8", errors="replace").splitlines():
            m = INDEX_LINE.match(line)
            if not m:
                continue
            target = m.group(1)
            if "://" in target:
                continue
            indexed.add(target)
            if not (root / target).is_file():
                findings.append({"kind": "index-dangling", "file": target,
                                 "detail": "인덱스가 가리키는 파일이 없음"})
        for p in scoped:
            if p.name not in indexed:
                findings.append({"kind": "not-indexed", "file": p.name,
                                 "detail": "인덱스에 없음"})
    else:
        findings.append({"kind": "no-index", "file": INDEX_NAME, "detail": "인덱스 파일 없음"})

    stems = {p.stem for p in files}
    for p in scoped:
        text = body_of(p.read_text(encoding="utf-8", errors="replace"))
        text = INLINE_CODE.sub("", FENCE.sub("", text))  # 코드 안의 [[ ]] 는 링크가 아니다
        for link in WIKILINK.findall(text):
            if link.split("|")[0].strip() not in stems:
                findings.append({"kind": "broken-link", "file": p.name,
                                 "detail": f"[[{link}]] 대상 없음"})
    return findings, files


def extract_claims(text: str):
    """(종류, 값) 후보. 코드블록 밖 인라인 코드와 이슈 번호만 본다."""
    body = FENCE.sub("", body_of(text))
    claims: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind, value):
        if (kind, value) not in seen:
            seen.add((kind, value))
            claims.append((kind, value))

    for tok in INLINE_CODE.findall(body):
        tok = tok.strip()
        sym = SYMBOL.match(tok)
        if sym:
            add("symbol", sym.group(1))
        elif ("/" in tok or EXT.search(tok)) and PATH_LIKE.match(tok) and "://" not in tok \
                and not any(c in tok for c in "*?{}") and not tok.startswith("-"):
            add("path", tok)  # glob·URL·옵션은 경로가 아니다
    for n in ISSUE_REF.findall(INLINE_CODE.sub("", body)):
        add("issue", n)
    return claims


def check_claim(kind: str, value: str, repo: Path | None):
    """(상태, 근거). 상태 = fresh | stale | unverified."""
    if kind == "issue":
        return "unverified", "이슈 트래커를 조회하지 않음"
    if repo is None:
        return "unverified", "--repo 없음, 원본에 접근 못 함"
    if kind == "path":
        outside = value.startswith(("~", "/"))
        p = Path(value).expanduser() if outside else repo / value
        if p.exists():
            return "fresh", "경로 있음"
        if "/" not in value and not outside and next(
                (h for h in repo.rglob(value) if ".git" not in h.parts), None):
            return "fresh", "파일 이름이 레포 어딘가에 있음"  # 디렉터리 없이 적힌 파일명
        if outside:
            return "unverified", "레포 밖 경로는 이 머신에 없을 수 있음"
        return "stale", "경로 없음"
    if kind == "symbol":
        try:
            r = subprocess.run(["grep", "-rlF", "--exclude-dir=.git", "--", value + "(", str(repo)],
                               capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return "unverified", "grep 을 실행하지 못함"
        if r.returncode == 0 and r.stdout.strip():
            return "fresh", "심볼 있음"
        if r.returncode == 1:
            return "stale", "심볼 grep 결과 없음"
        return "unverified", "grep 실패"
    return "unverified", "알 수 없는 단언 종류"


def classify_file(claims_checked):
    """stale 이 하나라도 있으면 stale, 전부 fresh 일 때만 fresh, 나머지는 unverified."""
    states = [s for _, _, s, _ in claims_checked]
    if "stale" in states:
        return "stale"
    if states and all(s == "fresh" for s in states):
        return "fresh"
    return "unverified"  # 검증할 단언이 없어도 fresh 가 아니다


def audit(root: Path, repo: Path | None):
    findings, files = structure_findings(root)
    memories = []
    skipped = []
    for p in files:
        if p.name.startswith(PERSONAL_PREFIX):
            skipped.append(p.name)
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        checked = []
        for kind, value in extract_claims(text):
            state, why = check_claim(kind, value, repo)
            checked.append((kind, value, state, why))
        memories.append({"file": p.name, "class": classify_file(checked),
                         "claims": [dict(zip(("kind", "value", "state", "why"), c))
                                    for c in checked]})
    return {"structure": findings, "memories": memories, "skipped_personal": skipped}


def render(report) -> str:
    out = []
    s = report["structure"]
    out.append(f"구조 문제 {len(s)}건")
    out += [f"  [{f['kind']}] {f['file']}: {f['detail']}" for f in s]
    counts: dict[str, int] = {}
    for m in report["memories"]:
        counts[m["class"]] = counts.get(m["class"], 0) + 1
    out.append("분류 " + ", ".join(f"{k} {counts.get(k, 0)}" for k in ("fresh", "stale", "unverified")))
    for m in report["memories"]:
        if m["class"] != "fresh":
            bad = [c for c in m["claims"] if c["state"] != "fresh"]
            out.append(f"  {m['class']:<10} {m['file']}  " +
                       "; ".join(f"{c['kind']} {c['value']} ({c['why']})" for c in bad[:4]))
    if report["skipped_personal"]:
        out.append("개인 파일 제외: " + ", ".join(report["skipped_personal"]))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("memory_dir")
    ap.add_argument("--repo", help="단언을 대조할 레포 루트 (없으면 전부 unverified)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.memory_dir)
    if not root.is_dir():
        print(f"메모리 디렉터리가 없다: {root}", file=sys.stderr)
        return 2
    repo = Path(a.repo) if a.repo else None
    if repo is not None and not repo.is_dir():
        print(f"레포 경로가 없다: {repo}", file=sys.stderr)
        return 2
    report = audit(root, repo)
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json else render(report))
    return 1 if report["structure"] else 0


if __name__ == "__main__":
    sys.exit(main())
