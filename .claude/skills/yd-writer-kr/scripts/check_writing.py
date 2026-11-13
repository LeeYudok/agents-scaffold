#!/usr/bin/env python3
"""Rust 검사기의 Python 호환 계층 (#115).

기존 python3 check_writing.py CLI와 Upstage의 import 인터페이스를 유지한다.
글 전처리·규칙 파싱·위반 판정은 scripts/check-writing의 Rust 엔진이 담당한다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED_MD = ROOT / "references" / "banned-expressions.md"
NOUN_ENDING_SECTION = "명사형 종결"
# Upstage의 기존 문체 집계 코드와 호환되는 인터페이스다. 분리는 Rust에 위임한다.


def _command() -> list[str]:
    binary = os.environ.get("CHECK_WRITING_BIN")
    if binary:
        return [binary, "--rules", str(BANNED_MD)]
    return ["bash", str(ROOT / "scripts" / "check-writing")]


def _request(action: str, **fields):
    result = subprocess.run(
        [*_command(), "--bridge"],
        input=json.dumps(dict(action=action, **({"rules_path": str(BANNED_MD)} | fields)), ensure_ascii=False),
        capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Rust 검사기를 실행할 수 없다")
    return json.loads(result.stdout)


class _Sentences:
    @staticmethod
    def split(text: str):
        return _request("sentences", text=text)


SENTENCE_END = _Sentences()


@dataclass
class Rule:
    section: str
    banned: str
    replacement: str
    pattern: re.Pattern


@dataclass
class Finding:
    line: int
    level: str
    kind: str
    match: str
    hint: str
    context: str


def split_row(row: str) -> list[str]:
    return _request("split_row", text=row)


def load_rules(path: Path = BANNED_MD) -> list[Rule]:
    records = _request("rules", rules_path=str(path))
    return [Rule(r["section"], r["banned"], r["replacement"], re.compile(r["pattern"])) for r in records]


def prose_lines(text: str):
    return (tuple(line) for line in _request("prose", text=text))


def check(text: str, rules: list[Rule], chat: bool = False, max_len: int = 60) -> list[Finding]:
    specs = [dict(section=r.section, banned=r.banned, replacement=r.replacement, pattern=r.pattern.pattern) for r in rules]
    return [Finding(**row) for row in _request("check", text=text, rules=specs, chat=chat, max_len=max_len)]


def main(argv: list[str] | None = None) -> int:
    try:
        # stdout/stderr remain the Python CLI streams for callers using redirect_stdout.
        result = subprocess.run([*_command(), *(sys.argv[1:] if argv is None else argv)], capture_output=True, text=True)
    except OSError as error:
        print(f"check-writing: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
