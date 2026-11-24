#!/usr/bin/env python3
"""skills/ 단일 원본(SSOT)과 플러그인 디렉터리 계약을 검증한다 (#82, 구조 개편 2/3).

스킬 원본은 skills/{core,yd-skills/skills,yd-skills-personal/skills}/ 한 곳뿐이며
plugins/, .claude/skills/, presets/skills/personal/.claude/skills/ 중복 디렉터리는 두지 않는다.

사용:
  python3 scripts/dev/build-plugins.py --check
  python3 scripts/dev/build-plugins.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOTS = (
    ROOT / "skills" / "core",
    ROOT / "skills" / "yd-skills" / "skills",
    ROOT / "skills" / "yd-skills-personal" / "skills",
)
FORBIDDEN_DUPES = (
    ROOT / "plugins",
    ROOT / ".claude" / "skills",
    ROOT / "presets" / "skills" / "personal" / ".claude" / "skills",
)


def check() -> list[str]:
    errors: list[str] = []
    for dupe in FORBIDDEN_DUPES:
        if dupe.exists() or dupe.is_symlink():
            errors.append(f"[DUPLICATE] 중복 디렉터리/링크가 남아 있다: {dupe.relative_to(ROOT)}")

    seen: dict[str, Path] = {}
    for root in SKILL_ROOTS:
        if not root.is_dir():
            errors.append(f"[MISSING] 스킬 루트가 없다: {root.relative_to(ROOT)}")
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            name = skill_md.parent.name
            if name in seen:
                errors.append(
                    f"[COLLISION] 스킬 이름 중복 '{name}': {seen[name].relative_to(ROOT)} vs {skill_md.parent.relative_to(ROOT)}"
                )
            else:
                seen[name] = skill_md.parent

    for plugin in ("yd-skills", "yd-skills-personal"):
        pdir = ROOT / "skills" / plugin
        for p in pdir.rglob("*"):
            if p.is_symlink():
                errors.append(f"[SYMLINK] 플러그인 안에 심링크 금지: {p.relative_to(ROOT)}")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true")
    ap.parse_args(argv)
    errors = check()
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    total = sum(len(list(r.glob("*/SKILL.md"))) for r in SKILL_ROOTS if r.is_dir())
    print(f"OK: skills/ 단일 원본 {total}개 스킬 계약 통과 (중복 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
