#!/usr/bin/env python3
"""yd-writer-kr 글 검사기 (stdlib only).

Markdown 이나 평문 한국어 글을 읽어 기계로 잡을 수 있는 위반을 줄 번호와 함께
보고한다. 판단이 필요한 것(근거 유무, 독자에게 필요한 내용인가)은 잡지 않는다 —
그건 SKILL.md 점검표로 사람이 본다.

    오류  금지 표현, 문어체에 섞인 명사형 종결, ISO 8601 시각, 이모지
    경고  긴 문장 (--max-len, 기본 60자). --strict 면 오류로 센다

금지 표현의 원본은 references/banned-expressions.md 의 `검사` 열이다. 여기에
목록을 따로 두지 않는다.

검사하지 않는 곳: frontmatter, 코드 블록, 인라인 코드, 표, 인용(>), HTML 주석,
URL. 표 안의 값과 인용문은 고치지 않는다는 SKILL.md 예외를 따른 것이다.
한 줄만 면제하려면 그 줄에 `writer:allow` 를 적는다(HTML 주석 안이어도 된다).

    python3 check_writing.py README.md docs/*.md
    python3 check_writing.py --chat reply.txt      # 채팅: 명사형 종결은 보지 않는다
    cat body.md | python3 check_writing.py -       # 표준 입력

exit 0 = 오류 없음, 1 = 오류 있음, 2 = 사용법 오류
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

BANNED_MD = Path(__file__).resolve().parents[1] / "references" / "banned-expressions.md"
NOUN_ENDING_SECTION = "명사형 종결"

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
ISO_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}|\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?[+-]\d{2}:\d{2}")
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
URL = re.compile(r"https?://\S+")
HTML_COMMENT = re.compile(r"<!--.*?-->")
EMPHASIS = re.compile(r"\*\*|__")
LIST_MARK = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?")
SENTENCE_END = re.compile(r"(?<=[.?!])\s+")
HEADING = re.compile(r"^\s*#{1,6}\s+")


@dataclass
class Rule:
    section: str
    banned: str
    replacement: str
    pattern: re.Pattern


@dataclass
class Finding:
    line: int
    level: str      # 오류 | 경고
    kind: str
    match: str
    hint: str
    context: str


def split_row(row: str) -> list[str]:
    """`| a | b \\| c |` 를 셀로 나눈다. `\\|` 는 셀 안의 문자다."""
    cells, cur, i = [], "", 0
    body = row.strip()[1:-1] if row.strip().endswith("|") else row.strip()[1:]
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if body[i] == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += body[i]
        i += 1
    cells.append(cur.strip())
    return cells


def load_rules(path: Path = BANNED_MD) -> list[Rule]:
    rules, section = [], ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("## "):
            section = raw[3:].strip()
            continue
        if not raw.startswith("|") or set(raw.replace("|", "").strip()) <= {"-"}:
            continue
        cells = split_row(raw)
        if len(cells) < 3 or cells[0] == "금지":
            continue
        check = cells[2]
        if check == "-" or not check:
            continue
        rules.append(Rule(section, cells[0], cells[1], re.compile(check.strip("`"))))
    return rules


def prose_lines(text: str):
    """검사 대상 줄만 (줄번호, 정리된 본문, 제목 여부) 로 내준다."""
    lines = text.splitlines()
    i, fence = 0, None
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    in_comment = False
    for n in range(i, len(lines)):
        raw = lines[n]
        stripped = raw.strip()
        if fence:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            continue
        if in_comment:
            if "-->" in raw:
                in_comment = False
            continue
        if stripped.startswith("<!--") and "-->" not in stripped:
            in_comment = True
            continue
        if not stripped or stripped.startswith(("|", ">")) or "writer:allow" in raw:
            continue
        clean = HTML_COMMENT.sub("", raw)
        clean = INLINE_CODE.sub("", clean)
        clean = LINK.sub(r"\1", clean)
        clean = URL.sub("", clean)
        clean = EMPHASIS.sub("", clean)
        heading = bool(HEADING.match(clean))
        clean = LIST_MARK.sub("", HEADING.sub("", clean).rstrip())
        if clean.strip():
            yield n + 1, raw, clean.strip(), heading


def check(text: str, rules: list[Rule], chat: bool = False, max_len: int = 60) -> list[Finding]:
    out: list[Finding] = []
    for no, raw, clean, heading in prose_lines(text):
        ctx = clean[:40]
        for m in EMOJI.finditer(raw):
            out.append(Finding(no, "오류", "이모지", m.group(), "Phosphor 아이콘이나 글로 바꾼다", ctx))
        for m in ISO_TIME.finditer(raw):
            out.append(Finding(no, "오류", "시각 표기", m.group(), "YYYY-MM-DD HH:MM:SS.mmm (KST)", ctx))
        for sentence in SENTENCE_END.split(clean):
            sentence = sentence.strip()
            if not sentence:
                continue
            for r in rules:
                if chat and r.section.startswith(NOUN_ENDING_SECTION):
                    continue
                if heading and r.section.startswith(NOUN_ENDING_SECTION):
                    continue
                for m in r.pattern.finditer(sentence):
                    out.append(Finding(no, "오류", r.section, m.group(), f"{r.banned} → {r.replacement}", sentence[:40]))
            if not heading and len(sentence) > max_len:
                out.append(Finding(no, "경고", "긴 문장", f"{len(sentence)}자", f"{max_len}자 이하로 나눈다", sentence[:40]))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="yd-writer-kr 글 검사기")
    ap.add_argument("paths", nargs="+", help="검사할 파일. - 는 표준 입력")
    ap.add_argument("--chat", action="store_true", help="채팅 대화체: 명사형 종결을 보지 않는다")
    ap.add_argument("--max-len", type=int, default=60, help="긴 문장 경고 기준 (기본 60자)")
    ap.add_argument("--strict", action="store_true", help="경고도 실패로 센다")
    args = ap.parse_args(argv)

    rules = load_rules()
    errors = warnings = 0
    for p in args.paths:
        if p == "-":
            name, text = "<stdin>", sys.stdin.read()
        else:
            path = Path(p)
            if not path.is_file():
                print(f"{p}: 파일이 없다", file=sys.stderr)
                return 2
            name, text = p, path.read_text(encoding="utf-8")
        for f in check(text, rules, chat=args.chat, max_len=args.max_len):
            print(f"{name}:{f.line}: {f.level} [{f.kind}] '{f.match}' — {f.hint}  | {f.context}")
            if f.level == "오류":
                errors += 1
            else:
                warnings += 1
    failed = errors + (warnings if args.strict else 0)
    print(f"오류 {errors}건, 경고 {warnings}건" + (" (--strict)" if args.strict else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
