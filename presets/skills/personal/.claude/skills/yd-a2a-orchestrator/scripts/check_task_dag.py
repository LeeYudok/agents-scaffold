#!/usr/bin/env python3
"""작업 DAG 증거 기록을 검증한다 (stdlib only).

오케스트레이터는 "작업을 다 끝냈다" 고 보고하지만, 어떤 작업을 누가 맡아 어떤 명령으로
검증했는지 남지 않으면 그 보고는 확인할 수 없다. 이 검사기는 지휘권 리스·작업 DAG·검증
증거를 읽어 규칙 위반을 판정한다. 규칙의 원본은 SKILL.md 와 references/a2a-acp-contract.md
이며 여기에는 그 규칙을 복제하지 않는다.

    python3 check_task_dag.py <dag.json | ->  [--root DIR] [--verify-files]
    python3 check_task_dag.py hash <경로>          # 기록에 넣을 sha256 을 계산한다

DAG 형식(최소):

    {
      "coordinator": {"agent": "codex", "term": 7},
      "pool": ["codex-glm"],
      "tasks": [
        {"id": "t1", "owner": "codex-glm", "reviewer": "claude",
         "repo": "dok3search", "branch": "batch/codex-glm-20261122-ab12cd34",
         "worktree": "/abs/path", "depends_on": [], "state": "done",
         "artifact": "backend/rust/target/report.json", "sha256": "<64 hex>",
         "checks": [{"command": "cargo test ...", "exit_code": 0}]}
      ]
    }

종료 코드: 위반이 없으면 0, 있으면 1, 입력을 읽지 못하면 2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

STATES = ("todo", "working", "blocked", "done", "failed")
#: 아직 끝나지 않아 에이전트를 풀에 반환할 수 없는 상태.
ACTIVE_STATES = ("todo", "working", "blocked")
#: 끝나서 에이전트를 풀에 반환해야 하는 상태.
TERMINAL_STATES = ("done", "failed")
#: 실패 재배정 상한 — 최초 시도 1회 + 재배정 3회.
MAX_ATTEMPTS = 4
TODO_WORDS = ("추가 예정", "미구현", "TODO", "FIXME")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def hash_path(path: Path) -> str:
    """파일은 내용, 디렉터리는 (상대경로, 내용) 목록의 sha256 이다."""
    h = hashlib.sha256()
    if path.is_dir():
        for p in sorted(x for x in path.rglob("*") if x.is_file()
                        and ".git" not in x.parts and "node_modules" not in x.parts):
            h.update(p.relative_to(path).as_posix().encode() + b"\0")
            h.update(p.read_bytes() + b"\0")
    else:
        h.update(path.read_bytes())
    return h.hexdigest()


def check_coordinator(data: dict, errors: list[str]) -> None:
    coord = data.get("coordinator")
    if not isinstance(coord, dict):
        errors.append("coordinator(지휘자·term)가 없다 — 지휘권 리스를 잡은 에이전트와 term 을 적는다")
        return
    if not isinstance(coord.get("agent"), str) or not coord["agent"].strip():
        errors.append("coordinator.agent 가 없다")
    term = coord.get("term")
    if not isinstance(term, int) or isinstance(term, bool) or term < 1:
        errors.append("coordinator.term 은 1 이상의 정수여야 한다")


def check_task(i: int, t: dict, ids: set[str], errors: list[str]) -> None:
    where = f"tasks[{i}] {t.get('id', '?')}"
    tid = t.get("id")
    if not isinstance(tid, str) or not tid.strip():
        errors.append(f"tasks[{i}]: id 가 없다")
    elif tid in ids:
        errors.append(f"{where}: 작업 ID 가 DAG 안에서 유일하지 않다")
    owner, reviewer = t.get("owner"), t.get("reviewer")
    if not isinstance(owner, str) or not owner.strip():
        errors.append(f"{where}: owner(담당)가 없다")
    if not isinstance(reviewer, str) or not reviewer.strip():
        errors.append(f"{where}: reviewer(리뷰어)가 없다")
    if isinstance(owner, str) and owner.strip() and owner == reviewer:
        errors.append(f"{where}: 담당과 리뷰어가 같다 — 자기 작업을 자기가 리뷰할 수 없다")
    deps = t.get("depends_on")
    if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
        errors.append(f"{where}: depends_on 은 작업 ID 문자열 목록이어야 한다")
    if t.get("state") not in STATES:
        errors.append(f"{where}: state 는 {'·'.join(STATES)} 중 하나여야 한다")
    checks = t.get("checks")
    if not isinstance(checks, list):
        errors.append(f"{where}: checks(명령·exit code)가 목록이 아니다")
        checks = []
    for c in checks:
        if not isinstance(c, dict) or not str(c.get("command", "")).strip() \
                or not isinstance(c.get("exit_code"), int) or isinstance(c.get("exit_code"), bool):
            errors.append(f"{where}: check 는 command 와 정수 exit_code 가 필요하다")
    if t.get("state") == "done":
        if not checks:
            errors.append(f"{where}: 완료인데 검증 명령(checks)이 없다")
        bad = [c for c in checks if isinstance(c, dict) and c.get("exit_code") != 0]
        if bad:
            errors.append(f"{where}: 완료인데 exit_code 가 0 이 아닌 검증 명령이 있다")
        if not isinstance(t.get("artifact"), str) or not t["artifact"].strip():
            errors.append(f"{where}: 완료인데 산출물 artifact 경로가 없다")
        if not isinstance(t.get("sha256"), str) or not SHA_RE.match(t["sha256"]):
            errors.append(f"{where}: 완료인데 sha256 이 64자리 소문자 hex 가 아니다")
    attempts = t.get("attempts")
    if attempts is not None:
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
            errors.append(f"{where}: attempts 는 1 이상의 정수여야 한다")
        elif attempts > MAX_ATTEMPTS:
            errors.append(f"{where}: 재배정이 {attempts - 1}회다 — 같은 작업에서 최대 3회까지다")
    text = json.dumps(t, ensure_ascii=False)
    if any(w in text for w in TODO_WORDS):
        errors.append(f"{where}: 미구현·추가 예정 표기가 남아 있다")


def check_dependencies(tasks: list[dict], errors: list[str]) -> None:
    ids = {t.get("id") for t in tasks if isinstance(t.get("id"), str)}
    graph: dict[str, list[str]] = {}
    for i, t in enumerate(tasks):
        tid = t.get("id")
        deps = [d for d in t.get("depends_on", []) if isinstance(d, str)]
        for d in deps:
            if d not in ids:
                errors.append(f"tasks[{i}] {tid}: 의존 대상 {d} 가 DAG 에 없다")
        if isinstance(tid, str):
            graph[tid] = deps
    # 순환 판정 — 색칠 DFS. white=0, gray=1, black=2.
    color: dict[str, int] = {n: 0 for n in graph}

    def visit(node: str, stack: list[str]) -> None:
        color[node] = 1
        for nxt in graph.get(node, []):
            if nxt not in graph:
                continue
            if color[nxt] == 1:
                cycle = " → ".join(stack + [node, nxt])
                errors.append(f"의존 관계에 순환이 있다: {cycle}")
            elif color[nxt] == 0:
                visit(nxt, stack + [node])
        color[node] = 2

    for node in graph:
        if color[node] == 0:
            visit(node, [])


def check_pool(data: dict, tasks: list[dict], errors: list[str]) -> None:
    """에이전트 풀 목록과 작업 묶임·풀림을 검사한다 (SKILL.md §3)."""
    pool = data.get("pool")
    if pool is None:
        errors.append("pool(에이전트 풀) 목록이 없다 — 새 작업을 받을 수 있는 에이전트를 적는다")
        return
    if not isinstance(pool, list) or not all(isinstance(a, str) and a.strip() for a in pool):
        errors.append("pool 은 에이전트 ID 문자열 목록이어야 한다")
        return
    if len(pool) != len(set(pool)):
        errors.append("풀(pool)의 에이전트 ID 가 중복됐다")
    active = {t.get("owner") for t in tasks
              if isinstance(t, dict) and t.get("state") in ACTIVE_STATES}
    finished = {t.get("owner") for t in tasks
                if isinstance(t, dict) and t.get("state") in TERMINAL_STATES}
    for a in sorted(set(pool)):
        if a in active:
            errors.append(f"pool: {a} 가 아직 끝나지 않은 작업을 쥐고 있다 — 풀에 있으면 안 된다")
    for a in sorted(x for x in finished if isinstance(x, str) and x):
        if a not in active and a not in pool:
            errors.append(f"pool: {a} 가 작업을 끝냈는데 풀에 반환되지 않았다")


def check(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["DAG 최상위가 객체가 아니다"]
    check_coordinator(data, errors)
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return errors + ["tasks 목록이 없다"]
    seen: set[str] = set()
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            errors.append(f"tasks[{i}]: 객체가 아니다")
            continue
        check_task(i, t, seen, errors)
        if isinstance(t.get("id"), str):
            seen.add(t["id"])
    check_pool(data, tasks, errors)
    check_dependencies(tasks, errors)
    return errors


def verify_files(data: dict, root: Path) -> list[str]:
    errors = []
    for i, t in enumerate(data.get("tasks", [])):
        if not isinstance(t, dict) or t.get("state") != "done":
            continue
        if not isinstance(t.get("artifact"), str):
            continue
        p = Path(t["artifact"])
        p = p if p.is_absolute() else root / p
        if not p.exists():
            errors.append(f"tasks[{i}] {t.get('id')}: artifact {t['artifact']} 가 없다")
        elif hash_path(p) != t.get("sha256"):
            errors.append(f"tasks[{i}] {t.get('id')}: artifact 내용이 기록된 sha256 과 다르다")
    return errors


def main(argv: list[str]) -> int:
    if argv[:1] == ["hash"]:
        if len(argv) != 2 or not Path(argv[1]).exists():
            print("사용법: check_task_dag.py hash <존재하는 경로>", file=sys.stderr)
            return 2
        print(hash_path(Path(argv[1])))
        return 0
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dag", help="작업 DAG JSON 파일, - 는 stdin")
    ap.add_argument("--root", default=".", help="상대 artifact 경로의 기준 (기본: 현재 디렉터리)")
    ap.add_argument("--verify-files", action="store_true", help="artifact 를 다시 해시해 대조한다")
    args = ap.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.dag == "-" else Path(args.dag).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError) as e:
        print(f"오류: 작업 DAG 를 읽지 못했다 ({e})", file=sys.stderr)
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
