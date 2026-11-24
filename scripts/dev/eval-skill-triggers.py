#!/usr/bin/env python3
"""스킬 발동 평가 (#131) — tests/triggers.json 의 질문으로 스킬이 제때 발동하는지 잰다.

모델을 호출하므로 CI 에서 돌리지 않는다. 형식만 tests/test_skill_triggers.py 가 검사한다.

  python3 scripts/dev/eval-skill-triggers.py --dry-run            # 케이스만 만든다(모델 호출 없음)
  python3 scripts/dev/eval-skill-triggers.py --skill yd-cve-check # 한 스킬만
  python3 scripts/dev/eval-skill-triggers.py -j 4                 # 전체, 4개씩 동시에

노출 스킬(metadata.internal 이 아닌 것) 전부를 임시 플러그인 하나로 묶어 `claude plugin eval` 에 넘긴다.
스킬끼리 경쟁하는 상태에서 재야 하므로 --skill 을 줘도 플러그인에는 전부 들어간다.
케이스는 임시 폴더에만 만든다 — plugins/ 아래에는 skills 만 둔다는 계약(tests/test_build_plugins.py)을 지킨다.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL_ROOTS = (REPO / "skills" / "core", REPO / "skills" / "yd-skills" / "skills")
INTERNAL = re.compile(r"^metadata:\n  internal: true$", re.M)
PLUGIN_NAME = "yd-trigger-eval"


def visible_skills() -> list[str]:
    names = []
    for root in SKILL_ROOTS:
        for path in sorted(root.glob("*/SKILL.md")):
            front = path.read_text(encoding="utf-8").split("---\n", 2)[1]
            if not INTERNAL.search(front):
                names.append(path.parent.name)
    return sorted(names)


def find_skill_dir(name: str) -> Path:
    for root in SKILL_ROOTS:
        if (root / name / "SKILL.md").is_file():
            return root / name
    raise FileNotFoundError(name)


def load_triggers(name: str) -> list[dict]:
    return json.loads((find_skill_dir(name) / "tests" / "triggers.json").read_text(encoding="utf-8"))


def grader_pattern(name: str) -> str:
    """Skill 도구 입력에서 이 스킬 이름을 찾는다. 플러그인 접두(`plugin:skill`)는 있어도 되고 없어도 된다."""
    return r'"skill"\s*:\s*"(?:[\w-]+:)?' + re.escape(name) + '"'


def build(out: Path, only: list[str] | None = None) -> dict[str, dict]:
    """임시 플러그인과 케이스를 만든다. 돌려주는 값은 {케이스 이름: {skill, query, should_trigger, expect}}."""
    plugin = out / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": PLUGIN_NAME, "description": "skill trigger eval (generated)"}), encoding="utf-8")
    names = visible_skills()
    for name in names:
        shutil.copytree(find_skill_dir(name), plugin / "skills" / name,
                        ignore=shutil.ignore_patterns("tests", "__pycache__", "node_modules"))
    cases = {}
    for name in names:
        if only and name not in only:
            continue
        for index, row in enumerate(load_triggers(name), 1):
            case = f"{name}-{index:02d}"
            folder = plugin / "evals" / case
            (folder / "graders").mkdir(parents=True)
            (folder / "prompt.md").write_text(
                f"---\nmax_turns: 2\nallowed_tools: [Skill]\n---\n{row['query']}\n", encoding="utf-8")
            (folder / "graders" / "trigger.md").write_text(
                "---\ntype: tool_used\ntool: Skill\n"
                f"input_match: '{grader_pattern(name)}'\n---\n{name} 스킬을 불렀는지 본다.\n", encoding="utf-8")
            cases[case] = {"skill": name, **row}
    return cases


def summarize(cases: dict[str, dict], result: dict) -> tuple[list[tuple], list[str]]:
    """스킬별 (이름, 발동 정답/전체, 비발동 정답/전체) 와 틀린 케이스 설명."""
    fired = {}
    for case in result.get("cases", []):
        runs = case.get("arms", {}).get("with", [])
        fired[case["name"]] = bool(runs) and all(run.get("passed") for run in runs)
    table, wrong = {}, []
    for name, meta in cases.items():
        if name not in fired:
            continue
        row = table.setdefault(meta["skill"], [0, 0, 0, 0])
        ok = fired[name] == meta["should_trigger"]
        if meta["should_trigger"]:
            row[0] += ok
            row[1] += 1
        else:
            row[2] += ok
            row[3] += 1
        if not ok:
            kind = "발동하지 않음" if meta["should_trigger"] else "잘못 발동"
            expect = f" (맞는 스킬: {meta['expect']})" if meta.get("expect") else ""
            wrong.append(f"{meta['skill']}: {kind} — {meta['query']}{expect}")
    return [(skill, *row) for skill, row in sorted(table.items())], wrong


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="스킬 발동 평가 (모델 호출, 수동 실행)")
    parser.add_argument("--skill", action="append", help="이 스킬의 질문만 돌린다(여러 번 줄 수 있다)")
    parser.add_argument("--out", type=Path, help="케이스와 결과를 둘 폴더(기본: 임시 폴더)")
    parser.add_argument("--dry-run", action="store_true", help="케이스만 만들고 끝낸다")
    parser.add_argument("--runs", type=int, default=1, help="케이스당 실행 횟수(기본 1)")
    parser.add_argument("-j", "--concurrency", type=int, default=4)
    parser.add_argument("--model", help="평가에 쓸 모델")
    parser.add_argument("--max-cost-usd", type=float, help="비용 상한")
    parser.add_argument("--threshold", type=float, default=0.9, help="전체 정답률이 이보다 낮으면 exit 1 (기본 0.9)")
    args = parser.parse_args(argv)

    unknown = sorted(set(args.skill or []) - set(visible_skills()))
    if unknown:
        print(f"노출 스킬이 아니다: {', '.join(unknown)}", file=sys.stderr)
        return 2
    out = args.out or Path(tempfile.mkdtemp(prefix="skill-triggers-"))
    if (out / "plugin").exists():
        shutil.rmtree(out / "plugin")
    out.mkdir(parents=True, exist_ok=True)
    cases = build(out, args.skill)
    print(f"케이스 {len(cases)}개: {out / 'plugin' / 'evals'}")
    if args.dry_run:
        return 0
    if not shutil.which("claude"):
        print("claude CLI 가 없다. `claude plugin eval` 은 Claude Code 2.1.269 이상이 필요하다.", file=sys.stderr)
        return 2
    result_path = out / "result.json"
    command = ["claude", "plugin", "eval", str(out / "plugin"), "--ablation", "none", "--runs", str(args.runs),
               "-j", str(args.concurrency), "--no-publish", "--trust-plugin", "--json", str(result_path)]
    if args.model:
        command += ["--model", args.model]
    if args.max_cost_usd:
        command += ["--max-cost-usd", str(args.max_cost_usd)]
    # 비발동 케이스는 채점기가 "실패"해야 정답이라 claude 의 종료 코드는 쓰지 않는다.
    subprocess.run(command, cwd=out, stdout=subprocess.DEVNULL)
    if not result_path.exists():
        print("결과 파일이 없다. 위 claude 출력을 확인한다.", file=sys.stderr)
        return 2
    result = json.loads(result_path.read_text(encoding="utf-8"))
    table, wrong = summarize(cases, result)
    print("\n| 스킬 | 발동 | 비발동 |\n|---|---|---|")
    right = total = 0
    for skill, hit, hits, quiet, quiets in table:
        print(f"| {skill} | {hit}/{hits} | {quiet}/{quiets} |")
        right += hit + quiet
        total += hits + quiets
    rate = right / total if total else 0.0
    print(f"\n정답 {right}/{total} ({rate:.0%}), 비용 ${result.get('costUsd', 0):.2f}, 결과 {result_path}")
    missing = len(cases) - total
    if missing:
        print(f"미실행 {missing}건 — 비용 상한이나 중단으로 돌지 않았다. 정답률은 실행한 케이스만 센 값이다.")
    for line in wrong:
        print(f"- {line}")
    return 0 if rate >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
