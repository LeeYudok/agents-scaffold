#!/usr/bin/env python3
"""글쓰기 품질 평가 과제를 채점한다 (stdlib only, #139). 모델을 부르지 않는다.

과제는 tests/writing-tasks/tasks.json, 원자료는 tests/writing-tasks/materials/<id>.md 다.
결과 폴더에는 과제마다 <id>.md 한 파일을 둔다. 글은 사람이나 에이전트가 쓴다.

    score_writing_tasks.py --list                      # 과제 목록
    score_writing_tasks.py --prompt issue-01           # 글 쓰는 쪽에 줄 지시문과 원자료
    score_writing_tasks.py 결과폴더                    # 채점
    score_writing_tasks.py 결과폴더 --compare 다른폴더  # 두 결과 비교 (예: 스킬 없이 / 스킬로)
    score_writing_tasks.py --blind 폴더A 폴더B -o 비교지.md --key 열쇠.json   # 사람이 가린 채 고를 비교지

채점 항목은 과제마다 한 점씩이다.
  검사기 오류 0건 · 원문 대조 오류 0건 · 꼭 들어갈 사실 · 첫머리에 올 결론 · 넣으면 안 되는 내용 · 필요한 절 · 분량
검사기 경고는 점수에 넣지 않고 수만 보여 준다. 채점기는 사실이 있는지만 본다. 읽기 쉬운지는 비교지로 사람이 본다.

exit 0 = 채점함, 2 = 실행 불가
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_writing  # noqa: E402

TASK_DIR = HERE.parent / "tests" / "writing-tasks"
SOURCE_KIND = "원문 대조"
QUESTIONS = (
    "첫 문단만 읽고 무엇을 알고 무엇을 할지 아는 쪽",
    "원자료와 다른 사실·수치가 없고, 정하지 않은 것을 정한 것처럼 쓰지 않은 쪽",
    "읽다가 막히거나 다시 읽은 문장이 적은 쪽",
)
HEADING = re.compile(r"^\s*(?:#{1,6}\s*(.+?)|\*\*(.+?)\*\*:?|(.{1,20}?)\s*[:：])\s*$")
LIST_MARK = re.compile(r"^\s*(?:[-*+>]|\d+[.)])\s+")


def load_tasks(path: Path | None = None) -> dict:
    return json.loads((path or TASK_DIR / "tasks.json").read_text(encoding="utf-8"))


def material(task_id: str) -> str:
    return (TASK_DIR / "materials" / f"{task_id}.md").read_text(encoding="utf-8")


def norm(text: str) -> str:
    """천 단위 쉼표와 공백 차이를 없앤다. 610,110 과 610110 은 같은 값이다."""
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    return re.sub(r"\s+", " ", text).lower()


def has(text: str, item: dict) -> bool:
    haystack = norm(text)
    return any(norm(alt) in haystack for alt in item["any"])


def heading_of(line: str) -> str | None:
    """제목처럼 쓴 줄의 글자. `## 결정`, `**결정**`, `결정:` 을 모두 제목으로 본다."""
    match = HEADING.match(line)
    return next((g for g in match.groups() if g), None) if match else None


def section_text(text: str, aliases: list[str]) -> str:
    """aliases 가운데 하나가 든 제목 아래의 글. 다음 제목 앞에서 끝난다."""
    out, inside = [], False
    for line in text.splitlines():
        title = heading_of(line)
        if title is not None:
            inside = any(alias.lower() in title.lower() for alias in aliases)
            continue
        if inside:
            out.append(line)
    return "\n".join(out)


def lead_text(text: str, lines: int) -> str:
    """제목과 빈 줄을 뺀 앞 lines 줄."""
    out = []
    for line in text.splitlines():
        if not line.strip() or heading_of(line) is not None or set(line.strip()) <= set("-=|"):
            continue
        out.append(LIST_MARK.sub("", line))
        if len(out) == lines:
            break
    return "\n".join(out)


def score(task: dict, kind: dict, text: str | None, rules, profile: str = "") -> dict:
    """한 과제의 채점 결과. text 가 None 이면 글이 없는 것이다."""
    checks: list[tuple[str, bool]] = []
    result = {"id": task["id"], "kind": task["kind"], "missing": text is None, "warnings": 0}
    if text is None:
        text = ""
    findings = check_writing.check(text, rules, source=material(task["id"]), profile=profile) if text.strip() else []
    errors = [f for f in findings if f.level == "오류"]
    source = [f for f in errors if f.kind == SOURCE_KIND]
    result["warnings"] = len(findings) - len(errors)
    result["checker_errors"] = len(errors) - len(source)
    result["source_errors"] = len(source)
    filled = bool(text.strip())
    checks.append(("검사기 오류 0건", filled and len(errors) == len(source)))
    checks.append(("원문 대조 오류 0건", filled and not source))
    lead = lead_text(text, kind.get("lead_lines", 3))
    for item in task.get("lead", []):
        checks.append((f"첫머리: {item['label']}", has(lead, item)))
    for item in task.get("must_have", []):
        where = section_text(text, kind["sections"][item["section"]]) if item.get("section") else text
        label = f"{item['section']} 절: {item['label']}" if item.get("section") else f"사실: {item['label']}"
        checks.append((label, has(where, item)))
    for item in task.get("must_not", []):
        checks.append((f"금지: {item['label']}", filled and not has(text, item)))
    for name, aliases in kind.get("sections", {}).items():
        found = any(any(a.lower() in t.lower() for a in aliases) for t in map(heading_of, text.splitlines()) if t)
        checks.append((f"절: {name}", found))
    if kind.get("max_chars"):
        checks.append((f"분량: {kind['max_chars']}자 이하", filled and len(text.strip()) <= kind["max_chars"]))
    result["passed"] = sum(ok for _, ok in checks)
    result["total"] = len(checks)
    result["failed"] = [label for label, ok in checks if not ok]
    result["chars"] = len(text.strip())
    return result


def score_dir(folder: Path, data: dict, rules, profile: str = "") -> list[dict]:
    out = []
    for task in data["tasks"]:
        path = folder / f"{task['id']}.md"
        text = path.read_text(encoding="utf-8-sig") if path.is_file() else None
        out.append(score(task, data["kinds"][task["kind"]], text, rules, profile))
    return out


def totals(results: list[dict]) -> tuple[int, int]:
    return sum(r["passed"] for r in results), sum(r["total"] for r in results)


def percent(passed: int, total: int) -> str:
    return f"{passed}/{total} ({passed * 100 // total if total else 0}%)"


def report(results: list[dict], data: dict, name: str) -> str:
    lines = [f"# 채점 결과: {name}", "", "| 과제 | 점수 | 검사기 오류 | 원문 대조 오류 | 경고 | 글자 수 | 놓친 항목 |", "|---|---|---|---|---|---|---|"]
    for r in results:
        failed = "글 없음" if r["missing"] else ("; ".join(r["failed"]) or "-")
        lines.append(f"| {r['id']} | {r['passed']}/{r['total']} | {r['checker_errors']} | {r['source_errors']} | {r['warnings']} | {r['chars']} | {failed} |")
    lines += ["", "| 종류 | 점수 |", "|---|---|"]
    for key, kind in data["kinds"].items():
        lines.append(f"| {kind['name']} | {percent(*totals([r for r in results if r['kind'] == key]))} |")
    lines.append(f"| 전체 | {percent(*totals(results))} |")
    return "\n".join(lines)


def compare(first: list[dict], second: list[dict], data: dict, names: tuple[str, str]) -> str:
    lines = [f"# 비교: {names[0]} 대 {names[1]}", "", f"| 과제 | {names[0]} | {names[1]} | 차이 | 경고 ({names[0]}/{names[1]}) |", "|---|---|---|---|---|"]
    for a, b in zip(first, second):
        lines.append(f"| {a['id']} | {a['passed']}/{a['total']} | {b['passed']}/{b['total']} | {b['passed'] - a['passed']:+d} | {a['warnings']}/{b['warnings']} |")
    lines += ["", f"| 종류 | {names[0]} | {names[1]} |", "|---|---|---|"]
    for key, kind in data["kinds"].items():
        pick = lambda rs: percent(*totals([r for r in rs if r["kind"] == key]))  # noqa: E731
        lines.append(f"| {kind['name']} | {pick(first)} | {pick(second)} |")
    lines.append(f"| 전체 | {percent(*totals(first))} | {percent(*totals(second))} |")
    return "\n".join(lines)


def prompt(task: dict, kind: dict) -> str:
    return f"{kind['instruction']}\n독자: {task['reader']}\n\n--- 원자료 ---\n{material(task['id'])}"


def blind(folder_a: Path, folder_b: Path, data: dict, seed: int) -> tuple[str, dict]:
    """(비교지, 열쇠). 비교지에는 어느 폴더의 글인지 적지 않는다. 열쇠는 따로 저장한다."""
    rng = random.Random(seed)
    sheet = ["# 글쓰기 비교지", "",
             "과제마다 글 두 편이 있다. 어느 쪽이 어떤 방법으로 쓴 글인지는 가려 두었다.",
             "질문마다 `가`, `나`, `같음` 가운데 하나에 표시한다. 열쇠 파일은 다 고른 뒤에 연다.", ""]
    key = {"seed": seed, "folders": {"A": str(folder_a), "B": str(folder_b)}, "tasks": {}}
    for task in data["tasks"]:
        texts = {}
        for name, folder in (("A", folder_a), ("B", folder_b)):
            path = folder / f"{task['id']}.md"
            texts[name] = path.read_text(encoding="utf-8-sig").strip() if path.is_file() else "(글 없음)"
        order = ["A", "B"]
        rng.shuffle(order)
        key["tasks"][task["id"]] = {"가": order[0], "나": order[1]}
        kind = data["kinds"][task["kind"]]
        sheet += [f"## {task['id']} — {kind['name']}: {task['title']}", "", f"독자: {task['reader']}", ""]
        for label, name in zip(("가", "나"), order):
            sheet += [f"### 글 {label}", "", "~~~text", texts[name], "~~~", ""]
        for question in QUESTIONS:
            sheet += [f"- {question}: [ ] 가  [ ] 나  [ ] 같음"]
        sheet.append("")
    return "\n".join(sheet), key


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="yd-writer-kr 글쓰기 과제 채점")
    ap.add_argument("folder", nargs="?", help="결과 폴더 (<과제 id>.md)")
    ap.add_argument("--compare", metavar="폴더", help="비교할 다른 결과 폴더")
    ap.add_argument("--list", action="store_true", help="과제 목록")
    ap.add_argument("--prompt", metavar="ID", help="글 쓰는 쪽에 줄 지시문과 원자료")
    ap.add_argument("--blind", nargs=2, metavar=("폴더A", "폴더B"), help="가린 비교지를 만든다")
    ap.add_argument("-o", "--output", help="비교지나 채점 결과를 쓸 파일")
    ap.add_argument("--key", help="--blind 의 열쇠 파일 (필수)")
    ap.add_argument("--seed", type=int, default=139, help="--blind 의 섞는 순서")
    ap.add_argument("--json", action="store_true", help="채점 결과를 JSON 으로")
    ap.add_argument("--profile", default="", help="표기 프로필 (기본 doksam)")
    args = ap.parse_args(argv)

    data = load_tasks()
    by_id = {t["id"]: t for t in data["tasks"]}

    def emit(text: str) -> None:
        if args.output:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        else:
            print(text)

    if args.list:
        emit("\n".join(f"{t['id']}\t{data['kinds'][t['kind']]['name']}\t{t['title']}" for t in data["tasks"]))
        return 0
    if args.prompt:
        if args.prompt not in by_id:
            print(f"없는 과제: {args.prompt}", file=sys.stderr)
            return 2
        emit(prompt(by_id[args.prompt], data["kinds"][by_id[args.prompt]["kind"]]))
        return 0
    if args.blind:
        folders = [Path(p) for p in args.blind]
        if not args.key or not args.output:
            print("--blind 는 -o 비교지와 --key 열쇠 파일을 함께 지정한다", file=sys.stderr)
            return 2
        if not all(p.is_dir() for p in folders):
            print("--blind 의 두 폴더가 있어야 한다", file=sys.stderr)
            return 2
        sheet, key = blind(folders[0], folders[1], data, args.seed)
        emit(sheet)
        Path(args.key).write_text(json.dumps(key, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return 0
    if not args.folder or not Path(args.folder).is_dir():
        print("결과 폴더를 지정한다. 과제 목록은 --list", file=sys.stderr)
        return 2
    try:
        rules = check_writing.load_rules()
        first = score_dir(Path(args.folder), data, rules, args.profile)
        second = None
        if args.compare:
            if not Path(args.compare).is_dir():
                print(f"폴더가 없다: {args.compare}", file=sys.stderr)
                return 2
            second = score_dir(Path(args.compare), data, rules, args.profile)
    except RuntimeError as error:
        print(f"검사기를 실행할 수 없다: {error}", file=sys.stderr)
        return 2
    names = (Path(args.folder).name, Path(args.compare).name if args.compare else "")
    if args.json:
        emit(json.dumps({names[0]: first, **({names[1]: second} if second else {})}, ensure_ascii=False, indent=1))
    elif second:
        emit(compare(first, second, data, names) + "\n\n" + report(first, data, names[0]) + "\n\n" + report(second, data, names[1]))
    else:
        emit(report(first, data, names[0]))
    return 0


if __name__ == "__main__":
    check_writing.utf8_stdio()
    sys.exit(main())
