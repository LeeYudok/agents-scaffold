#!/usr/bin/env python3
"""문서의 숫자·등급·버전이 레포의 실제 값과 같은지 검사한다 (#105 #107).

사실은 레포에서 뽑는다 — 문서에 적힌 값을 기준으로 삼지 않는다.

  스택 수        presets/stacks/ 의 디렉터리 수
  한국어 스킬 수  .claude/skills/*/SKILL.md 수 (기본 설치)
  영어 스킬 수    위에서 yd-* 를 뺀 수 (--lang en 설치)
  하네스          docs/harness-matrix.json 의 tier · cli_version

대상: README*.md, docs/index.html, docs/llms.txt

규칙은 일부러 단순하다. 아래 "알아볼 수 있는 문구" 옆의 값만 본다. 문구를 바꾸면 검사에서 빠지므로,
문구를 바꿀 때는 이 표도 함께 고친다.

  1. 스택 수     "<N> stack presets" · "스택 프리셋 <N>종" · "<N> 种技术栈预设" · "スタックプリセット <N> 種"
  2. 스킬 수     "<N> skills" 는 영어 수나 한국어 수여야 한다.
                 README 표의 행 "| `--lang en` | <N> |" · "| `--lang ko` … | <N> |" 는 그 언어의 수여야 한다.
  3. CLI 버전    "Claude Code <x.y.z>" · "codex-cli <x.y.z>" · "agy <x.y.z>" 는 manifest 의 버전이어야 한다.
  4. 등급        (텍스트) 같은 줄에서 위 버전 문구 뒤에 처음 나오는 full / baseline 이 그 하네스의 tier 여야 한다.
                 (index.html) <tr data-harness=… data-tier=… data-version=…> 가 세 하네스 모두 있고 manifest 와 같아야 한다.

사용: python3 scripts/dev/check-doc-numbers.py [--root <레포 루트>]
종료 코드: 0 = 일치, 1 = 불일치(파일:줄 과 기대값을 출력)
"""

import argparse
import json
import re
import sys
from pathlib import Path

STACK_PATTERNS = [
    re.compile(r"(\d+) stack presets"),
    re.compile(r"스택 프리셋 (\d+)종"),
    re.compile(r"(\d+) 种技术栈预设"),
    re.compile(r"スタックプリセット (\d+) 種"),
]
SKILLS_PATTERN = re.compile(r"(\d+) skills\b")
LANG_ROW_PATTERN = re.compile(r"^\| `--lang (en|ko)`[^|]*\| (\d+) \|")
VERSION_PATTERNS = {
    "claude": re.compile(r"Claude Code (\d+\.\d+\.\d+)"),
    "codex": re.compile(r"codex-cli (\d+\.\d+\.\d+)"),
    "agy": re.compile(r"agy (\d+\.\d+\.\d+)"),
}
TIER_PATTERN = re.compile(r"\b(full|baseline)\b")
HTML_ROW_PATTERN = re.compile(
    r'data-harness="([^"]+)"\s+data-tier="([^"]+)"\s+data-version="([^"]+)"'
)


def load_facts(root: Path) -> dict:
    stacks = sorted(
        p.name for p in (root / "presets" / "stacks").iterdir() if p.is_dir()
    )
    skills = sorted(
        p.parent.name for p in (root / ".claude" / "skills").glob("*/SKILL.md")
    )
    yd = [s for s in skills if s.startswith("yd-")]
    matrix = json.loads(
        (root / "docs" / "harness-matrix.json").read_text(encoding="utf-8")
    )
    harnesses = {
        h["id"]: {
            "tier": h["tier"],
            "cli_version": h["cli_version"],
            "number": h["cli_version"].split()[-1],
        }
        for h in matrix["harnesses"]
    }
    return {
        "stacks": len(stacks),
        "skills_ko": len(skills),
        "skills_en": len(skills) - len(yd),
        "harnesses": harnesses,
    }


def targets(root: Path) -> list:
    files = sorted(root.glob("README*.md"))
    files += [root / "docs" / "index.html", root / "docs" / "llms.txt"]
    return [f for f in files if f.is_file()]


def check_text(rel: str, text: str, facts: dict) -> list:
    errors = []
    harnesses = facts["harnesses"]
    for lineno, line in enumerate(text.splitlines(), 1):
        where = f"{rel}:{lineno}"
        for pat in STACK_PATTERNS:
            for m in pat.finditer(line):
                if int(m.group(1)) != facts["stacks"]:
                    errors.append(
                        f"{where}: 스택 수 {m.group(1)} — presets/stacks 는 {facts['stacks']}개 ('{m.group(0)}')"
                    )
        for m in SKILLS_PATTERN.finditer(line):
            if int(m.group(1)) not in (facts["skills_en"], facts["skills_ko"]):
                errors.append(
                    f"{where}: 스킬 수 {m.group(1)} — 영어 설치 {facts['skills_en']}개, "
                    f"한국어 설치 {facts['skills_ko']}개 ('{m.group(0)}')"
                )
        m = LANG_ROW_PATTERN.match(line)
        if m:
            want = facts["skills_en"] if m.group(1) == "en" else facts["skills_ko"]
            if int(m.group(2)) != want:
                errors.append(
                    f"{where}: --lang {m.group(1)} 스킬 수 {m.group(2)} — 실제 {want}개"
                )
        for hid, pat in VERSION_PATTERNS.items():
            if hid not in harnesses:
                continue
            for m in pat.finditer(line):
                if m.group(1) != harnesses[hid]["number"]:
                    errors.append(
                        f"{where}: {hid} 버전 {m.group(1)} — manifest 는 {harnesses[hid]['number']}"
                    )
                tier = TIER_PATTERN.search(line, m.end())
                if tier and tier.group(1) != harnesses[hid]["tier"]:
                    errors.append(
                        f"{where}: {hid} 등급 {tier.group(1)} — manifest 는 {harnesses[hid]['tier']}"
                    )
    return errors


def check_html_rows(rel: str, text: str, facts: dict) -> list:
    errors = []
    seen = {}
    for m in HTML_ROW_PATTERN.finditer(text):
        seen[m.group(1)] = (m.group(2), m.group(3))
    for hid, h in facts["harnesses"].items():
        if hid not in seen:
            errors.append(f'{rel}: 하네스 표에 data-harness="{hid}" 행이 없다')
            continue
        tier, version = seen[hid]
        if tier != h["tier"]:
            errors.append(f"{rel}: {hid} data-tier={tier} — manifest 는 {h['tier']}")
        if version != h["cli_version"]:
            errors.append(
                f"{rel}: {hid} data-version={version} — manifest 는 {h['cli_version']}"
            )
    for hid in seen:
        if hid not in facts["harnesses"]:
            errors.append(f'{rel}: manifest 에 없는 하네스 행 data-harness="{hid}"')
    return errors


def run(root: Path) -> list:
    facts = load_facts(root)
    errors = []
    for path in targets(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        errors += check_text(rel, text, facts)
        if path.suffix == ".html":
            errors += check_html_rows(rel, text, facts)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors = run(root)
    if errors:
        print("FAIL: 문서의 숫자·등급·버전이 레포와 다르다", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    facts = load_facts(root)
    print(
        f"OK: {len(targets(root))} files — stacks {facts['stacks']}, "
        f"skills en {facts['skills_en']} / ko {facts['skills_ko']}, "
        f"harnesses {len(facts['harnesses'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
