#!/usr/bin/env python3
"""Upstage Solar 로 한국어 글을 1차 교정한다 (stdlib only).

흐름: Solar 교정 → check_writing.py 검사 → 오류가 남으면 그 목록을 붙여 한 번 더
교정 → 최종 검사 결과와 함께 출력한다. 결과는 **교정 후보**다. 뜻이 바뀌지 않았는지는
부른 쪽(에이전트·사람)이 원문과 비교해 판단한다.

금지 표현은 references/banned-expressions.md 를 그대로 프롬프트에 넣는다. 목록을
여기에 따로 두지 않는다.

    python3 upstage_proofread.py draft.md               # 고친 글을 표준 출력으로
    python3 upstage_proofread.py draft.md -o fixed.md   # 파일로
    python3 upstage_proofread.py --chat reply.txt       # 채팅 대화체 (~요 유지)

키는 환경변수 UPSTAGE_API_KEY 를 쓰고, 없으면 ~/workspace/.env.toml 의
UPSTAGE_API_KEY (최상위 또는 [llm]) 를 읽는다. 키를 출력하지 않는다.

본문이 외부 API 로 나간다. 시크릿처럼 보이는 문자열이 있으면 보내지 않고 멈춘다.
고객 데이터·비공개 문서인지는 이 스크립트가 판단할 수 없다 — 부르는 쪽이 정한다.

exit 0 = 교정 완료(검사 오류 0), 1 = 교정했지만 검사 오류가 남음, 2 = 실행 불가
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_writing  # noqa: E402

API = "https://api.upstage.ai/v1/chat/completions"
MODEL = "solar-pro4"
# solar-pro4 는 reasoning 과 본문이 토큰 상한을 함께 쓴다. 너무 낮으면 본문이 잘린다.
MIN_MAX_TOKENS = 1024
SECRET = re.compile(r"glpat-|ghp_|github_pat_|sk-[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY")

SYSTEM = """너는 한국어 교정자다. 아래 규칙으로 글을 고친다.

지킬 것
- 뜻과 사실(수치·날짜·이름·이슈 번호·경로)은 바꾸지 않는다. 내용을 더하거나 빼지 않는다.
- 코드 블록, `인라인 코드`, 표 안의 값, 인용(>), URL, Markdown 문법은 그대로 둔다.
- 한 문장에 생각 하나. 길면 마침표로 나눈다.
- 아래 금지 표현은 대체 표현으로 바꾼다. "현상이 발생한다" 같은 말은 증상을 직접 쓴다.
{style}

금지 표현 (왼쪽 → 오른쪽)
{banned}

출력은 고친 글 전체만 쓴다. 설명·머리말·코드 펜스로 감싸기를 하지 않는다."""

STYLE_DOC = "- 문체는 원문을 따른다. ~함·~임·~됨 으로 끝내지 않는다."
STYLE_POLITE = "- 이 글은 ~합니다 체다. 모든 문장을 ~합니다·~습니다 로 끝낸다. ~한다·~이다 로 바꾸지 않는다."
STYLE_PLAIN = "- 이 글은 ~한다 문어체다. 모든 문장을 ~한다·~이다 로 끝낸다."
POLITE_END = re.compile(r"(니다|세요|까요)[.?!]?\s*$")
PLAIN_END = re.compile(r"[다][.]\s*$")


def doc_style(text: str) -> str:
    """원문에서 많이 쓴 종결을 세어 문체를 명시한다.

    "원문을 따른다" 만 주면 Solar 가 ~합니다 체를 ~한다 로 바꾼다
    (2026-10-04 에이전트 시험에서 README 단락이 그렇게 바뀌었다).
    """
    polite = plain = 0
    for _, _, clean, heading in check_writing.prose_lines(text):
        if heading:
            continue
        for sentence in check_writing.SENTENCE_END.split(clean):
            if POLITE_END.search(sentence):
                polite += 1
            elif PLAIN_END.search(sentence):
                plain += 1
    if polite > plain:
        return STYLE_POLITE
    if plain > polite:
        return STYLE_PLAIN
    return STYLE_DOC
STYLE_CHAT = "- 채팅 대화체다. ~요·~함 같은 종결은 그대로 둔다."


def api_key() -> str | None:
    key = os.environ.get("UPSTAGE_API_KEY")
    if key:
        return key
    path = Path.home() / "workspace" / ".env.toml"
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return data.get("UPSTAGE_API_KEY") or (data.get("llm") or {}).get("UPSTAGE_API_KEY")


def banned_list(chat: bool) -> str:
    rows = []
    for r in check_writing.load_rules():
        if chat and r.section.startswith(check_writing.NOUN_ENDING_SECTION):
            continue
        rows.append(f"- {r.banned} → {r.replacement}")
    return "\n".join(rows)


def call(key: str, system: str, user: str, max_tokens: int) -> str:
    body = json.dumps({
        "model": MODEL,
        "temperature": 0,
        "max_tokens": max(max_tokens, MIN_MAX_TOKENS),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    return (data["choices"][0]["message"].get("content") or "").strip()


def findings_text(findings) -> str:
    return "\n".join(f"- {f.line}행 '{f.match}': {f.hint}" for f in findings if f.level == "오류")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Upstage Solar 한국어 교정 + 검사")
    ap.add_argument("path", help="교정할 파일. - 는 표준 입력")
    ap.add_argument("-o", "--output", help="고친 글을 쓸 파일 (기본: 표준 출력)")
    ap.add_argument("--chat", action="store_true", help="채팅 대화체")
    args = ap.parse_args(argv)

    text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    if SECRET.search(text):
        print("시크릿처럼 보이는 문자열이 있어 외부 API 로 보내지 않는다", file=sys.stderr)
        return 2
    key = api_key()
    if not key:
        print("UPSTAGE_API_KEY 가 없다 (환경변수 또는 ~/workspace/.env.toml)", file=sys.stderr)
        return 2

    rules = check_writing.load_rules()
    system = SYSTEM.format(style=STYLE_CHAT if args.chat else doc_style(text), banned=banned_list(args.chat))
    budget = len(text) * 2 + 512
    try:
        fixed = call(key, system, text, budget)
        left = [f for f in check_writing.check(fixed, rules, chat=args.chat) if f.level == "오류"]
        if left:
            retry = f"아래 글에 금지 표현이 남았다. 이것만 고치고 나머지는 그대로 둔다.\n\n{findings_text(left)}\n\n---\n{fixed}"
            fixed = call(key, system, retry, budget)
    except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
        print(f"Upstage 호출 실패: {e}", file=sys.stderr)
        return 2

    if args.output:
        Path(args.output).write_text(fixed + "\n", encoding="utf-8")
    else:
        print(fixed)
    final = check_writing.check(fixed, rules, chat=args.chat)
    errors = [f for f in final if f.level == "오류"]
    for f in final:
        print(f"검사 {f.line}: {f.level} [{f.kind}] '{f.match}' — {f.hint}", file=sys.stderr)
    print(f"검사: 오류 {len(errors)}건, 경고 {len(final) - len(errors)}건", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
