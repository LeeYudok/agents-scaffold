#!/usr/bin/env python3
"""Upstage Solar 로 한국어 글을 요약한다 (stdlib only, #118).

흐름: Solar 요약 → check-writing 글 검사와 원문 대조(--source) → 오류나 긴 줄이 남으면 그 목록과
원문을 붙여 한 번 더 고친다 → 그래도 줄 수가 넘치면 앞에서 --lines 줄만 남긴다 → 최종 검사 결과와
함께 출력한다. 결과는 **요약 후보**다.
경고로 남은 수치는 부른 쪽(에이전트·사람)이 원문과 맞춰 본다.

긴 원문은 단락 경계에서 CHUNK_CHARS 이하로 나눠 부분 요약을 만든 뒤 합쳐 다시 요약한다.
원문 대조는 언제나 원문 전체와 한다.

    python3 upstage_summarize.py 원문.md                  # 세 줄 요약을 표준 출력으로
    python3 upstage_summarize.py 원문.md --lines 1        # 한 줄 요약
    python3 upstage_summarize.py 원문.md --chat -o 요약.txt

키·시크릿 차단·금지 표현 프롬프트는 upstage_proofread.py 와 같다. 본문이 외부 API 로 나간다.

exit 0 = 요약 완료(검사 오류 0), 1 = 요약했지만 검사 오류가 남음, 2 = 실행 불가
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_writing  # noqa: E402
import upstage_proofread as proof  # noqa: E402

# 요약 한 줄 길이 기준. 검사기의 긴 문장 경고 기준과 같다.
MAX_LEN = 60
# 한 번에 보내는 원문 글자 수. 넘으면 나눠 요약한다. 모델 한도가 아니라 응답 품질·시간을 보고 정한 보수적인 값이다.
CHUNK_CHARS = 12_000
call = proof.call  # 테스트가 바꿔 끼운다

SYSTEM = """너는 한국어 요약자다. 원문에서 독자가 알아야 할 것만 골라 {lines}줄로 쓴다.

줄 구성
{layout}

지킬 것
- 요약은 고르는 일이다. 원문을 다 담지 않는다. 줄을 늘리거나 쉼표·~며·~고 로 이어 붙이지 않는다.
- 한 줄은 "- " 로 시작하는 한 문장이고 {max_len}자 안팎이다.
- 원문에 없는 내용·해석·평가·추측을 더하지 않는다.
- 옮기는 수치·날짜·시각·이름·이슈 번호·경로·명령은 원문 표기 그대로 쓴다. 반올림하거나 단위를 바꾸지 않는다.
- 원문이 확인하지 못했다고 한 것은 그렇게 쓴다.
{style}
- 아래 금지 표현을 쓰지 않는다.

금지 표현 (왼쪽 → 오른쪽)
{banned}

예시 (세 줄)
원문: 로그인 API 응답이 2026-03-02 부터 평균 2.1초로 느려졌다. 세션 테이블에 인덱스가 없어 전체를 조회한다.
인덱스를 추가하면 0.2초가 된다. 2026-03-05 에 인덱스를 추가한다. 캐시 도입은 비용을 확인한 뒤 정한다.
요약:
- 2026-03-05 에 세션 테이블 인덱스를 추가해 로그인 지연을 고친다.
- 인덱스가 없어 2026-03-02 부터 응답이 평균 2.1초다.
- 캐시 도입은 비용을 확인한 뒤 정한다.

출력은 요약 본문만 쓴다. 머리말·제목·코드 펜스를 쓰지 않는다."""

LAYOUTS = {
    1: "- 1줄: 결론 하나. 원문이 정한 것이나 결과다.",
    2: "- 1줄: 결론 (정한 것·결과)\n- 2줄: 할 일·미결. 없으면 핵심 근거",
    3: "- 1줄: 결론 (정한 것·결과)\n- 2줄: 핵심 근거나 원인\n- 3줄: 할 일·미결. 없으면 다음 근거",
}
LAYOUT_MANY = "- 1줄: 결론 (정한 것·결과)\n- 이어서 근거를 중요한 순서로\n- 마지막 줄: 할 일·미결"


def layout(lines: int) -> str:
    return LAYOUTS.get(lines, LAYOUT_MANY)


STYLE_DOC = "- 문장은 ~한다·~이다 로 끝낸다. ~함·~임·~됨 으로 끝내지 않는다."
STYLE_CHAT = "- 채팅 대화체로 쓴다. ~요·~함 같은 종결을 써도 된다."

PART = """아래는 긴 글의 {index}/{total} 부분이다. 이 부분의 결론·근거·할 일·미결을 원문 표기 그대로
"- " 로 시작하는 줄 {lines}개 이하로 뽑는다. 다른 부분은 보지 못하니 짐작해 잇지 않는다.

---
{text}"""

FINAL = """아래는 한 글을 부분별로 요약한 것이다. 이것을 합쳐 전체 요약을 쓴다.

---
{text}"""

RETRY = """아래 요약에 검사 오류가 있다. 오류만 고치고 나머지는 그대로 둔다.
원문에 없는 값은 원문 값으로 고치거나 그 줄에서 뺀다. 긴 줄은 덜 중요한 내용을 빼서 줄인다.
줄 수는 {lines}줄 이하로 맞추고, 줄 구성은 처음 지시를 따른다.

오류
{errors}

---
원문
{source}

---
요약
{summary}"""


def chunks(text: str, limit: int | None = None) -> list[str]:
    """단락 경계에서 limit 글자 이하 묶음으로 나눈다. 한 단락이 넘치면 줄, 줄도 넘치면 글자 수로 자른다."""
    limit = limit or CHUNK_CHARS
    units: list[str] = []
    for para in re.split(r"\n[ \t]*\n", text.strip()):
        if len(para) <= limit:
            units.append(para)
            continue
        for line in para.split("\n"):
            units.extend(line[i:i + limit] for i in range(0, len(line), limit))
    out: list[str] = []
    current = ""
    for unit in units:
        if current and len(current) + 2 + len(unit) > limit:
            out.append(current)
            current = unit
        else:
            current = f"{current}\n\n{unit}" if current else unit
    if current:
        out.append(current)
    return out


def findings_text(findings) -> str:
    return "\n".join(f"- {f.line}행 '{f.match}': {f.hint}" for f in findings)


def keep_lines(summary: str, lines: int) -> str:
    return "\n".join([line for line in summary.splitlines() if line.strip()][:lines])


def summarize(key: str, system: str, text: str, lines: int, budget: int) -> tuple[str, str]:
    """(요약, 재시도 때 붙일 근거). 나눠 요약했으면 근거는 부분 요약을 이은 것이다."""
    parts = chunks(text)
    if len(parts) <= 1:
        return call(key, system, text, budget), text
    partials = [call(key, system, PART.format(index=i, total=len(parts), lines=max(lines, 5), text=part), budget)
                for i, part in enumerate(parts, 1)]
    joined = "\n\n".join(partials)
    return call(key, system, FINAL.format(text=joined), budget), joined


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Upstage Solar 한국어 요약 + 원문 대조 검사")
    ap.add_argument("path", help="요약할 원문 파일. - 는 표준 입력")
    ap.add_argument("-o", "--output", help="요약을 쓸 파일 (기본: 표준 출력)")
    ap.add_argument("--lines", type=int, default=3, help="요약 줄 수 상한 (기본 3)")
    ap.add_argument("--chat", action="store_true", help="채팅 대화체")
    args = ap.parse_args(argv)
    if args.lines < 1:
        print("--lines 는 1 이상이어야 한다", file=sys.stderr)
        return 2

    text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    if proof.SECRET.search(text):
        print("시크릿처럼 보이는 문자열이 있어 외부 API 로 보내지 않는다", file=sys.stderr)
        return 2
    key = proof.api_key()
    if not key:
        print("UPSTAGE_API_KEY 가 없다 (환경변수 또는 ~/workspace/.env.toml)", file=sys.stderr)
        return 2

    budget = max(proof.MIN_MAX_TOKENS, args.lines * 300 + 512)
    try:
        rules = check_writing.load_rules()
        style = STYLE_CHAT if args.chat else STYLE_DOC
        system = SYSTEM.format(lines=args.lines, layout=layout(args.lines), max_len=MAX_LEN, style=style,
                               banned=proof.banned_list(args.chat))

        def checked(summary: str):
            found = check_writing.check(summary, rules, chat=args.chat, max_len=MAX_LEN, source=text, lines=args.lines)
            if not summary.strip():
                found.append(check_writing.Finding(1, "오류", "요약 내용", "빈 요약", "원문에서 요약문을 작성한다", ""))
            return found, [f for f in found if f.level == "오류"]

        summary, basis = summarize(key, system, text, args.lines, budget)
        final, errors = checked(summary)
        # 원문에 없는 수치 경고는 세거나 계산한 값일 수 있어 다시 고치게 하지 않는다. 긴 줄은 요약 실패라 고치게 한다.
        fix = errors + [f for f in final if f.kind == "긴 문장"]
        if fix:
            retry = RETRY.format(errors=findings_text(fix), lines=args.lines, source=basis, summary=summary)
            summary = call(key, system, retry, budget)
            final, errors = checked(summary)
        if any(f.kind == "요약 분량" for f in errors):
            # 줄 구성상 앞줄이 결론이라 넘친 줄은 뒤에서 버린다 (2026-11-13 실측: 한 줄 요청에 재시도 뒤에도 2줄).
            summary = keep_lines(summary, args.lines)
            final, errors = checked(summary)
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, RuntimeError, OSError) as e:
        print(f"Upstage 호출 실패: {e}", file=sys.stderr)
        return 2

    if args.output:
        Path(args.output).write_text(summary + "\n", encoding="utf-8")
    else:
        print(summary)
    for f in final:
        print(f"검사 {f.line}: {f.level} [{f.kind}] '{f.match}' — {f.hint}", file=sys.stderr)
    print(f"검사: 오류 {len(errors)}건, 경고 {len(final) - len(errors)}건", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
