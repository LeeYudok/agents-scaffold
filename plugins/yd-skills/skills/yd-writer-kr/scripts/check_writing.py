#!/usr/bin/env python3
"""Go 검사기의 Python 호환 계층 (#115, #117).

기존 python3 check_writing.py CLI와 Upstage의 import 인터페이스를 유지한다.
글 전처리·규칙 파싱·위반 판정은 scripts/check-writing의 Go 엔진이 담당한다.
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
# Upstage의 기존 문체 집계 코드와 호환되는 인터페이스다. 분리는 Go 엔진에 위임한다.


def _command() -> list[str]:
    binary = os.environ.get("CHECK_WRITING_BIN")
    if binary:
        return [binary, "--rules", str(BANNED_MD)]
    return ["bash", str(ROOT / "scripts" / "check-writing")]


def _request(action: str, **fields):
    # encoding 을 정해 둔다. 윈도우의 기본 인코딩(CP949)으로는 Go 엔진의 UTF-8 JSON 을 읽지 못한다 (#137).
    result = subprocess.run(
        [*_command(), "--bridge"],
        input=json.dumps(dict(action=action, **({"rules_path": str(BANNED_MD)} | fields)), ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Go 검사기를 실행할 수 없다")
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
    level: str = "오류"
    min_count: int = 1  # 2 이상이면 한 문장 안에서 그 횟수만큼 나올 때만 잡는다 (#137)


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
    return [Rule(r["section"], r["banned"], r["replacement"], re.compile(r["pattern"]),
                 r.get("level") or "오류", r.get("min_count") or 1) for r in records]


def prose_lines(text: str):
    return (tuple(line) for line in _request("prose", text=text))


def check(text: str, rules: list[Rule], chat: bool = False, max_len: int = 60,
          source: str | None = None, lines: int = 0, prose: bool = False, profile: str = "") -> list[Finding]:
    """글 검사. source 를 주면 요약으로 보고 원문과 대조하고, lines 는 요약 줄 수 상한이다 (#118).

    prose 는 소설·에세이 같은 문학 산문이다. 번역투·피동·중복 수식만 보고 긴 문장 경고를 끈다 (#126).
    profile 은 표기 프로필 이름이나 경로다. 비우면 doksam 이다 (#137).
    """
    specs = [dict(section=r.section, banned=r.banned, replacement=r.replacement, pattern=r.pattern.pattern,
                  level=r.level, min_count=r.min_count) for r in rules]
    extra = {"source": source} if source is not None else {}
    rows = _request("check", text=text, rules=specs, chat=chat, prose=prose, max_len=max_len, lines=lines,
                    profile=profile, **extra)
    return [Finding(**row) for row in rows]


# kiwipiepy 0.24.1 은 준말 건·게·걸을 NNB `거`·`건`·`것` 으로 푼다 (2026-11-15 실측).
BOUND_NOUNS = {"것", "거", "건", "수", "점"}
BOUND_NOUN_MAX = 3
VALUE_FLAGS = {"--max-len", "--rules", "--profile", "--source", "--lines"}
GO_BOUND_NOTE = re.compile(r"^(.*):(\d+): 참고 \[의존명사\]", re.M)


def _input_paths(args: list[str]) -> list[str]:
    """검사 대상 경로만 고른다. 값을 받는 옵션의 값과 플래그는 뺀다."""
    paths, skip = [], False
    for arg in args:
        if skip:
            skip = False
        elif arg in VALUE_FLAGS:
            skip = True
        elif arg == "-" or not arg.startswith("-"):
            paths.append(arg)
    return paths


def morph_notes(text: str, flagged: set[int] = frozenset()) -> list[Finding]:
    """kiwipiepy 형태소 분석으로 의존명사 것·수·점을 문장마다 센다 (#132).

    Go 엔진은 어절 모양만 봐서 준말(건·게·걸)을 놓친다. 형태소 분석은 이를 `것` 으로 푼다.
    kiwipiepy 가 없으면 ImportError 를 그대로 올린다. flagged 는 Go 가 이미 알린 줄이다.
    """
    from kiwipiepy import Kiwi

    kiwi = Kiwi()
    notes = []
    for no, _raw, clean, heading in _request("prose", text=text):
        if heading or no in flagged:
            continue
        for sentence in kiwi.split_into_sents(clean, return_tokens=True):
            count = sum(1 for token in sentence.tokens if token.tag == "NNB" and token.form in BOUND_NOUNS)
            if count >= BOUND_NOUN_MAX:
                notes.append(Finding(no, "참고", "의존명사(형태소)", f"{count}회",
                                     "것·수·점이 한 문장에 몰렸다. 가리키는 대상을 명사로 쓰거나 서술어로 푼다",
                                     sentence.text[:40]))
    return notes


def _morph_report(args: list[str], stdin_text: str | None, go_stdout: str) -> None:
    if "--json" in args or "--prose" in args:
        print("check-writing: --morph 는 --json·--prose 와 함께 쓰지 않는다. 형태소 검사를 건너뛴다", file=sys.stderr)
        return
    flagged: dict[str, set[int]] = {}
    for name, no in GO_BOUND_NOTE.findall(go_stdout):
        flagged.setdefault(name, set()).add(int(no))
    total = 0
    try:
        for path in _input_paths(args):
            name = "<stdin>" if path == "-" else path
            text = stdin_text or "" if path == "-" else Path(path).read_text(encoding="utf-8")
            for f in morph_notes(text, flagged.get(name, set())):
                total += 1
                print(f"{name}:{f.line}: {f.level} [{f.kind}] '{f.match}' — {f.hint}  | {f.context}")
    except ImportError:
        print("check-writing: kiwipiepy 가 없어 형태소 검사를 건너뛴다 (pip install kiwipiepy)", file=sys.stderr)
        return
    print(f"형태소 참고 {total}건")


def utf8_stdio() -> None:
    """파이프로 나가는 출력을 UTF-8 로 맞춘다. 윈도우의 기본값(CP949·CP1252)은 한글이나 화살표에서 실패한다 (#137)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    morph = "--morph" in args
    args = [a for a in args if a != "--morph"]
    # --morph 는 표준 입력을 두 번 읽어야 해서 먼저 받아 둔다.
    stdin_text = sys.stdin.read() if morph and "-" in _input_paths(args) else None
    try:
        # stdout/stderr remain the Python CLI streams for callers using redirect_stdout.
        result = subprocess.run([*_command(), *args], capture_output=True, text=True, encoding="utf-8",
                                input=stdin_text)
    except OSError as error:
        print(f"check-writing: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if morph and result.returncode in (0, 1):
        _morph_report(args, stdin_text, result.stdout)
    return result.returncode


if __name__ == "__main__":
    utf8_stdio()
    sys.exit(main())
