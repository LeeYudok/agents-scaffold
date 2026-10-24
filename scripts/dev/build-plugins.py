#!/usr/bin/env python3
"""플러그인 디렉터리(plugins/<이름>/skills/)를 원본 스킬에서 생성한다 (#82).

원본은 .claude/skills/ 와 presets/skills/personal/.claude/skills/ 하나다. 플러그인 안의 스킬은
실파일 사본이다 — 심링크는 쓰지 않는다(2026-10-24 실측: codex-cli 0.164.0 의 `codex plugin add` 는
캐시로 복사할 때 심링크를 버려 skills/ 가 비고, Claude Code 2.1.310 은 심링크한 에이전트 파일을 읽지 않는다).
사본은 git 이 같은 blob 으로 저장하므로 저장소 크기는 거의 늘지 않는다.

사용:
  python3 scripts/dev/build-plugins.py           # 생성(바뀐 파일만 쓰고, 원본에 없는 파일은 지운다)
  python3 scripts/dev/build-plugins.py --check   # 드리프트만 검사 — 어긋나면 exit 1 (CI)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ".claude/skills"
PERSONAL = "presets/skills/personal/.claude/skills"
MERGED = (
    "handoff",
    "docs-sync",
    "memory-factcheck",
    "skill-evolve",
)  # #78 에서 doksam 판으로 합친 범용 스킬


def tracked(prefix: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", prefix],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def skill_name(path: str, prefix: str) -> str:
    return path[len(prefix) + 1 :].split("/", 1)[0]


def plan() -> dict[Path, Path]:
    """{플러그인 안 경로: 원본 경로}."""
    wanted: dict[Path, Path] = {}
    for path in tracked(BASE):
        name = skill_name(path, BASE)
        if name.startswith("yd-") or name in MERGED:
            wanted[Path("plugins/yd-skills/skills") / path[len(BASE) + 1 :]] = Path(
                path
            )
    for path in tracked(PERSONAL):
        wanted[
            Path("plugins/yd-skills-personal/skills") / path[len(PERSONAL) + 1 :]
        ] = Path(path)
    return wanted


def existing() -> set[Path]:
    found = set()
    for plugin in ("yd-skills", "yd-skills-personal"):
        skills = ROOT / "plugins" / plugin / "skills"
        if skills.exists():
            found |= {
                p.relative_to(ROOT)
                for p in skills.rglob("*")
                if p.is_file() or p.is_symlink()
            }
    return {p for p in found if "__pycache__" not in p.parts and p.suffix != ".pyc"}


def same(dst: Path, src: Path) -> bool:
    if dst.is_symlink() or not dst.is_file():
        return False
    if dst.read_bytes() != src.read_bytes():
        return False
    return os.access(dst, os.X_OK) == os.access(src, os.X_OK)


def diff(wanted: dict[Path, Path]) -> tuple[list[Path], list[Path]]:
    stale = [d for d, s in sorted(wanted.items()) if not same(ROOT / d, ROOT / s)]
    extra = sorted(existing() - set(wanted))
    return stale, extra


def build(wanted: dict[Path, Path], stale: list[Path], extra: list[Path]) -> None:
    for d in stale:
        dst = ROOT / d
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        shutil.copy2(ROOT / wanted[d], dst)
    for d in extra:
        (ROOT / d).unlink()
    for plugin in ("yd-skills", "yd-skills-personal"):  # 비게 된 디렉터리 정리
        skills = ROOT / "plugins" / plugin / "skills"
        for p in sorted(skills.rglob("*"), reverse=True) if skills.exists() else []:
            if p.is_dir() and not any(p.iterdir()):
                p.rmdir()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    wanted = plan()
    stale, extra = diff(wanted)
    if args.check:
        for d in stale:
            print(f"[DRIFT] {d} != {wanted[d]}")
        for d in extra:
            print(f"[EXTRA] {d} (원본에 없음)")
        if stale or extra:
            print(
                "플러그인 사본이 원본과 다르다 — python3 scripts/dev/build-plugins.py 로 다시 생성해 함께 커밋한다",
                file=sys.stderr,
            )
            return 1
        print(f"OK: 플러그인 사본 {len(wanted)}개 파일이 원본과 같다")
        return 0
    build(wanted, stale, extra)
    print(f"생성: 갱신 {len(stale)}, 삭제 {len(extra)}, 전체 {len(wanted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
