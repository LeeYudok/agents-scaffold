#!/usr/bin/env python3
"""skill-evolve 의 기계적 게이트 (stdlib only).

    evolve_guard.py clean    [--repo DIR]
    evolve_guard.py check    <스킬명> [--repo DIR] [--base REF] [--require-section] [--allow-removal]
    evolve_guard.py verify   <스킬명> [--repo DIR] [--test-cmd CMD]
    evolve_guard.py rollback <스킬명> [--repo DIR]

clean     워킹 트리가 비어 있지 않으면 exit 1 (Phase 1).
check     SKILL.md 가 편집 규칙을 지켰는지 본다 (Phase 3). frontmatter 는 name·description 과 base 에 이미 있던 키뿐이고
          name 이 디렉터리명과 같은지, 이모지가 없는지, Learned warnings 줄이 `- (YYYY-MM-DD) ...`
          형식인지, base 에 있던 경고가 그대로 남았는지.
verify    테스트(기본: scripts/dev/run-skill-tests.sh, 없으면 scripts/run_tests.sh)를 돌리고, 실패하면 **그 스킬의 SKILL.md 만** 되돌린다 (Phase 4).
rollback  그 스킬의 SKILL.md 만 되돌린다. 경로 없는 `git restore .` 는 다른 에이전트의 변경까지 지운다.

종료 코드: 0 통과, 1 규칙 위반·테스트 실패, 2 사용 오류(스킬이 없음, git 저장소가 아님 등).
"""

from __future__ import annotations

import argparse
import datetime
import re
import shlex
import subprocess
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
WARN_HEAD = re.compile(r"^#{2,3}\s+Learned warnings\s*$", re.M)
WARN_LINE = re.compile(r"^- \((\d{4}-\d{2}-\d{2})\) \S")
# 이모지만 잡는다. 화살표·체크(U+2713)·케밥 같은 타이포그래피 문자는 허용한다 (AGENTS.md 8장).
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u26FF\u2705\u2728\u274C\u274E\u2753-\u2755"
                   "\u2757\u2795-\u2797\u27B0\u27BF\u2B50\u2B55\uFE0F]")


class UsageError(Exception):
    pass


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


# 스킬을 찾는 위치(agents-scaffold #78): 기본·옵트인 원본, 설치된 프로젝트의 원본, 예전 doksam-skills 배치.
SKILL_DIRS = (".claude/skills", "presets/skills/personal/.claude/skills", ".agents/skills", "skills")
DEFAULT_TEST_CMDS = ("scripts/dev/run-skill-tests.sh", "scripts/run_tests.sh")


def skill_file(repo: Path, skill: str) -> Path:
    if not NAME_RE.match(skill):
        raise UsageError(f"스킬 이름이 올바르지 않다: {skill!r}")
    for d in SKILL_DIRS:
        f = repo / d / skill / "SKILL.md"
        if f.is_file():
            return f
    raise UsageError(f"{skill}/SKILL.md 가 없다 ({', '.join(SKILL_DIRS)} 에서 찾음)")


def frontmatter_keys(text: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    fm = {}
    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", ln)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def warnings_section(text: str) -> list[str] | None:
    """Learned warnings 아래의 비어 있지 않은 줄. 섹션이 없으면 None."""
    m = WARN_HEAD.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^#{1,3}\s", rest, re.M)
    block = rest[:nxt.start()] if nxt else rest
    return [ln for ln in block.splitlines() if ln.strip()]


def check_text(skill: str, text: str, base_text: str | None = None, *,
               require_section=False, allow_removal=False) -> list[str]:
    problems: list[str] = []
    fm = frontmatter_keys(text)
    if fm is None:
        problems.append("frontmatter 가 없거나 닫히지 않았다")
    else:
        kept = set(frontmatter_keys(base_text) or {}) if base_text is not None else set()
        extra = sorted(set(fm) - {"name", "description"} - kept)
        if extra:
            problems.append(f"frontmatter 에 허용되지 않은 키: {', '.join(extra)}")
        if fm.get("name") != skill:
            problems.append(f"name 이 디렉터리명과 다르다: {fm.get('name')!r}")
        if not fm.get("description"):
            problems.append("description 이 비어 있다")
    for n, ln in enumerate(text.splitlines(), 1):
        if EMOJI.search(ln):
            problems.append(f"{n}행: 이모지 사용 금지")
    lines = warnings_section(text)
    if lines is None:
        if require_section:
            problems.append("Learned warnings 섹션이 없다")
        return problems
    for ln in lines:
        if ln.startswith((" ", "\t")):
            continue  # 앞 항목의 이어지는 줄
        m = WARN_LINE.match(ln)
        if not m:
            problems.append(f"경고 줄이 `- (YYYY-MM-DD) ...` 형식이 아니다: {ln[:40]}")
            continue
        try:
            datetime.date.fromisoformat(m.group(1))
        except ValueError:
            problems.append(f"경고 날짜가 달력에 없다: {m.group(1)}")
    if base_text is not None and not allow_removal:
        before = warnings_section(base_text) or []
        for ln in before:
            if ln not in lines:
                problems.append(f"기존 경고가 사라졌다: {ln[:40]}")
    return problems


def cmd_clean(repo: Path) -> int:
    r = git(repo, "status", "-s")
    if r.returncode != 0:
        raise UsageError("git 저장소가 아니다")
    if r.stdout.strip():
        print("워킹 트리가 깨끗하지 않다:\n" + r.stdout.rstrip())
        return 1
    print("워킹 트리 깨끗함")
    return 0


def cmd_check(repo: Path, skill: str, base: str, require, allow_removal) -> int:
    f = skill_file(repo, skill)
    rel = f.relative_to(repo).as_posix()
    shown = git(repo, "show", f"{base}:{rel}")
    base_text = shown.stdout if shown.returncode == 0 else None
    problems = check_text(skill, f.read_text(encoding="utf-8"), base_text,
                          require_section=require, allow_removal=allow_removal)
    for p in problems:
        print(f"위반: {p}")
    if not problems:
        print("규칙 위반 없음" + ("" if base_text is not None else " (base 가 없어 경고 보존은 건너뜀)"))
    return 1 if problems else 0


def cmd_rollback(repo: Path, skill: str) -> int:
    f = skill_file(repo, skill)
    r = git(repo, "restore", "--", f.relative_to(repo).as_posix())
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
        return 2
    print(f"되돌림: {f.relative_to(repo).as_posix()}")
    return 0


def cmd_verify(repo: Path, skill: str, test_cmd: str | None) -> int:
    f = skill_file(repo, skill)  # 스킬이 없으면 테스트 전에 멈춘다
    if test_cmd is None:
        found = next((c for c in DEFAULT_TEST_CMDS if (repo / c).is_file()), DEFAULT_TEST_CMDS[0])
        test_cmd = "./" + found
    try:
        r = subprocess.run(shlex.split(test_cmd), cwd=repo)
    except OSError as e:
        # 실행기를 못 찾은 것은 테스트 실패가 아니다. 검증을 못 했을 뿐이라 편집은 그대로 둔다.
        raise UsageError(f"테스트 실행기를 실행하지 못했다: {test_cmd} ({e.strerror})")
    if r.returncode == 0:
        print("테스트 통과")
        return 0
    print(f"테스트 실패 (exit {r.returncode}) — {f.relative_to(repo).as_posix()} 만 되돌린다")
    cmd_rollback(repo, skill)
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("clean", "check", "verify", "rollback"):
        p = sub.add_parser(name)
        p.add_argument("--repo", default=".")
        if name != "clean":
            p.add_argument("skill")
        if name == "check":
            p.add_argument("--base", default="HEAD")
            p.add_argument("--require-section", action="store_true")
            p.add_argument("--allow-removal", action="store_true")
        if name == "verify":
            p.add_argument("--test-cmd", default=None)
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    try:
        if a.cmd == "clean":
            return cmd_clean(repo)
        if a.cmd == "check":
            return cmd_check(repo, a.skill, a.base, a.require_section, a.allow_removal)
        if a.cmd == "rollback":
            return cmd_rollback(repo, a.skill)
        return cmd_verify(repo, a.skill, a.test_cmd)
    except UsageError as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
