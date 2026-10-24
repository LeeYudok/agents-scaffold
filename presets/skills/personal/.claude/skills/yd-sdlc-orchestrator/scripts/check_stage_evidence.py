#!/usr/bin/env python3
"""파이프라인 단계 증거 기록을 검증한다 (stdlib only).

오케스트레이터는 "게이트를 통과했다" 고 보고하지만, 어느 게이트를 어떤 명령으로
돌렸는지 남지 않으면 그 보고는 확인할 수 없다. 이 검사기는 단계마다 남긴 증거
기록을 읽어 순서·통과 근거·건너뜀을 판정한다. 단계별 입출력과 중단 조건의 원본은
.claude/skills/yd-finguard/references/ai-sdlc.md 이며 여기에는 그 규칙을 복제하지 않는다.
이 파일이 보는 것은 "기록이 SKILL.md 의 게이트 명령을 포함하는가" 까지다.

    python3 check_stage_evidence.py <evidence.json | ->  [--root DIR] [--verify-files]
    python3 check_stage_evidence.py hash <경로>          # 기록에 넣을 sha256 을 계산한다

기록 형식:

    {"stages": [{"stage": "planning", "status": "pass",
                 "artifact": "docs/storyboard.html", "sha256": "<64 hex>",
                 "checks": [{"command": "python3 .../validate_storyboard.py ...", "exit_code": 0}]}]}

종료 코드: 위반이 없으면 0, 있으면 1, 입력을 읽지 못하면 2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# 단계 순서와, 그 단계의 checks 에 들어 있어야 하는 게이트 명령 조각.
STAGES = ["planning", "implementation", "security", "local-run"]
REQUIRED_COMMANDS = {
    "planning": ["validate_storyboard.py", "check_badge_overflow.py", "check_badge_alignment.py"],
    "implementation": ["pnpm build", "validate_traceability.py"],
    "security": ["run_gate.py"],
    "local-run": ["serve_and_check.py"],
}
MAX_SECURITY_ATTEMPTS = 4  # 최초 1회 + 재검증 최대 3회
TODO_WORDS = ("추가 예정", "미구현", "TODO")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def hash_path(path: Path) -> str:
    """파일은 내용, 디렉터리는 (상대경로, 내용) 목록의 sha256 이다."""
    h = hashlib.sha256()
    if path.is_dir():
        for p in sorted(x for x in path.rglob("*") if x.is_file() and ".git" not in x.parts
                        and "node_modules" not in x.parts):
            h.update(p.relative_to(path).as_posix().encode() + b"\0")
            h.update(p.read_bytes() + b"\0")
    else:
        h.update(path.read_bytes())
    return h.hexdigest()


def check_entry(i: int, e: dict, errors: list[str]) -> None:
    where = f"stages[{i}] {e.get('stage', '?')}"
    if not isinstance(e.get("artifact"), str) or not e["artifact"].strip():
        errors.append(f"{where}: artifact 경로가 없다")
    if not isinstance(e.get("sha256"), str) or not SHA_RE.match(e["sha256"]):
        errors.append(f"{where}: sha256 이 64자리 소문자 hex 가 아니다")
    checks = e.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append(f"{where}: checks(명령·exit code)가 비어 있다")
        checks = []
    for c in checks:
        if not isinstance(c, dict) or not str(c.get("command", "")).strip() \
                or not isinstance(c.get("exit_code"), int) or isinstance(c.get("exit_code"), bool):
            errors.append(f"{where}: check 는 command 와 정수 exit_code 가 필요하다")
    text = json.dumps(e, ensure_ascii=False)
    if e.get("status") == "skipped":
        errors.append(f"{where}: 건너뛴 단계는 통과가 아니다 (실패로 센다)")
    elif any(w in text for w in TODO_WORDS):
        errors.append(f"{where}: 미구현·추가 예정 표기가 남아 있다")
    elif e.get("status") not in ("pass", "fail"):
        errors.append(f"{where}: status 는 pass/fail 이어야 한다")
    if e.get("status") == "pass":
        bad = [c for c in checks if isinstance(c, dict) and c.get("exit_code") != 0]
        if bad:
            errors.append(f"{where}: pass 인데 exit_code 가 0 이 아닌 명령이 있다")
        joined = " ".join(str(c.get("command", "")) for c in checks if isinstance(c, dict))
        for need in REQUIRED_COMMANDS.get(e.get("stage"), []):
            if need not in joined:
                errors.append(f"{where}: 게이트 명령 {need} 의 기록이 없다")


def check(data: dict) -> list[str]:
    errors: list[str] = []
    entries = data.get("stages") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        return ["stages 목록이 없다"]
    latest: dict[str, str] = {}
    last_index: dict[str, int] = {}
    for i, e in enumerate(entries):
        s = e.get("stage") if isinstance(e, dict) else None
        if s not in STAGES:
            errors.append(f"stages[{i}]: 알 수 없는 단계 {s!r} (허용: {', '.join(STAGES)})")
            continue
        check_entry(i, e, errors)
        # 앞 단계가 한 번도 기록되지 않았거나 마지막 기록이 fail 이면 이 단계는 통과할 수 없다.
        if e.get("status") == "pass":
            for prev in STAGES[:STAGES.index(s)]:
                if latest.get(prev) != "pass":
                    why = "기록이 없다" if prev not in latest else f"마지막 기록이 {latest[prev]}"
                    errors.append(f"stages[{i}]: {s} 가 pass 인데 앞 단계 {prev} 는 {why}")
        latest[s] = e.get("status")
        last_index[s] = i
    for s in STAGES:
        if s not in latest:
            errors.append(f"단계 {s} 의 기록이 없다")
        elif latest[s] != "pass":
            errors.append(f"단계 {s} 의 마지막 기록이 {latest[s]} 이다")
    sec = sum(1 for e in entries if isinstance(e, dict) and e.get("stage") == "security")
    if sec > MAX_SECURITY_ATTEMPTS:
        errors.append(f"security 기록이 {sec}회다 — 재검증은 최대 3회(총 {MAX_SECURITY_ATTEMPTS}회)까지다")
    order = [last_index[s] for s in STAGES if s in last_index]
    if order != sorted(order):
        errors.append("단계 순서가 planning → implementation → security → local-run 이 아니다")
    return errors


def verify_files(data: dict, root: Path) -> list[str]:
    errors = []
    for i, e in enumerate(data.get("stages", [])):
        if not isinstance(e, dict) or not isinstance(e.get("artifact"), str):
            continue
        p = Path(e["artifact"])
        p = p if p.is_absolute() else root / p
        if not p.exists():
            errors.append(f"stages[{i}] {e.get('stage')}: artifact {e['artifact']} 가 없다")
        elif hash_path(p) != e.get("sha256"):
            errors.append(f"stages[{i}] {e.get('stage')}: artifact 내용이 기록된 sha256 과 다르다")
    return errors


def main(argv: list[str]) -> int:
    if argv[:1] == ["hash"]:
        if len(argv) != 2 or not Path(argv[1]).exists():
            print("사용법: check_stage_evidence.py hash <존재하는 경로>", file=sys.stderr)
            return 2
        print(hash_path(Path(argv[1])))
        return 0
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("evidence", help="증거 JSON 파일, - 는 stdin")
    ap.add_argument("--root", default=".", help="상대 artifact 경로의 기준 (기본: 현재 디렉터리)")
    ap.add_argument("--verify-files", action="store_true", help="artifact 를 다시 해시해 대조한다")
    args = ap.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.evidence == "-" else Path(args.evidence).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError) as e:
        print(f"오류: 증거 기록을 읽지 못했다 ({e})", file=sys.stderr)
        return 2
    errors = check(data)
    if args.verify_files:
        errors += verify_files(data, Path(args.root))
    for e in errors:
        print(f"위반: {e}")
    print(f"위반 {len(errors)}건")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
