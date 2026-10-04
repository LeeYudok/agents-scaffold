#!/usr/bin/env python3
"""스킬·에이전트 frontmatter 가 엄격한 YAML 로 읽히는지 검사 (#67) — stdlib unittest 전용.

agy 는 frontmatter 를 엄격한 YAML 로 파싱하고, 실패한 파일은 조용히 건너뛴다(1.2.16 실측:
따옴표 없는 description 안의 ": " 때문에 search-first 가 등록되지 않았다). Claude Code·Codex 는
관대해서 증상이 드러나지 않으므로 여기서 막는다. CI 에 PyYAML 이 없을 수 있어 의존성 없이
"따옴표 없는 평이한 값 안의 ': '·' #'" 를 잡고, PyYAML 이 있으면 safe_load 로도 확인한다.

실행: python3 -m unittest discover -s tests -p 'test_*.py'
"""
import glob
import os
import re
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PATTERNS = (
    ".claude/skills/*/SKILL.md",
    ".claude/agents/*.md",
    "presets/**/.claude/skills/*/SKILL.md",
    "presets/**/.claude/agents/*.md",
)
KEY_VALUE = re.compile(r"^([A-Za-z0-9_-]+):[ \t]+(.+)$")
QUOTED_OR_BLOCK = ("'", '"', "[", "{", "|", ">")


def frontmatter_files():
    found = set()
    for pat in PATTERNS:
        found.update(glob.glob(os.path.join(REPO_ROOT, pat), recursive=True))
    return sorted(p for p in found if os.path.basename(p) != "README.md")


def frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    return parts[1] if len(parts) == 3 else None


def plain_scalar_problems(fm):
    problems = []
    for n, line in enumerate(fm.splitlines(), 2):
        m = KEY_VALUE.match(line)
        if not m:
            continue
        value = m.group(2).strip()
        if value.startswith(QUOTED_OR_BLOCK):
            continue
        if ": " in value or " #" in value or value.endswith(":"):
            problems.append(f"line {n}: {m.group(1)} — plain value contains ': ' or ' #' (quote it)")
    return problems


class FrontmatterIsStrictYaml(unittest.TestCase):
    def test_files_found(self):
        self.assertGreater(len(frontmatter_files()), 10)

    def test_plain_scalars_are_valid(self):
        bad = []
        for path in frontmatter_files():
            fm = frontmatter(path)
            if fm is None:
                continue
            for p in plain_scalar_problems(fm):
                bad.append(f"{os.path.relpath(path, REPO_ROOT)}: {p}")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_safe_load_when_pyyaml_available(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        bad = []
        for path in frontmatter_files():
            fm = frontmatter(path)
            if fm is None:
                continue
            try:
                data = yaml.safe_load(fm)
                if not isinstance(data, dict) or "name" not in data:
                    bad.append(f"{os.path.relpath(path, REPO_ROOT)}: no name mapping")
            except yaml.YAMLError as e:
                bad.append(f"{os.path.relpath(path, REPO_ROOT)}: {str(e).splitlines()[0]}")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_detector_catches_the_agy_failure(self):
        fm = "name: x\ndescription: (origin: somewhere) text\n"
        self.assertTrue(plain_scalar_problems(fm))
        self.assertFalse(plain_scalar_problems("name: x\ndescription: 'a: b'\n"))


if __name__ == "__main__":
    unittest.main()
