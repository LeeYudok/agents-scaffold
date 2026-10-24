#!/usr/bin/env python3
"""Codex CLI Stop 훅 — 턴이 끝날 때마다 현재 스레드의 API 환산 비용을 한 줄로 보여준다.

codex-cli 의 내장 status line 항목 estimated-thread-cost 는 Enterprise 워크스페이스에서만 값이 있고,
status line 은 외부 명령을 실행하지 못한다. 그래서 Stop 훅이 세션 기록(transcript_path 의 rollout jsonl)
의 token_count 이벤트를 읽어 OpenAI API 공시 단가로 환산한 뒤 {"systemMessage": ...} 로 돌려준다.

  입력(stdin): Codex 훅 JSON (transcript_path, model 등)
  출력(stdout): {"systemMessage": "API 환산 $1.23 · 이번 턴 +$0.04 · 입력 1.2M(캐시 82%) · 출력 23k"}
               단가를 모르는 모델(로컬 모델 등)만 쓴 스레드는 아무것도 출력하지 않는다.

계산 규칙
- total_token_usage 가 바뀐 token_count 이벤트마다 직전 값과의 차이를 그 시점 turn_context 의 모델 단가로 곱한다.
  (같은 합계가 반복 기록되는 이벤트는 한 번만 센다. 스레드 도중 모델을 바꿔도 구간별로 맞게 계산된다)
- input_tokens 는 cached_input_tokens·cache_write_input_tokens 를 포함한 값이다. 나머지를 일반 입력 단가로,
  output_tokens(추론 토큰 포함)를 출력 단가로 계산한다.
- 세션 기록에는 Fast mode 여부가 남지 않는다. ~/.codex/config.toml 의 service_tier 가 "fast"/"priority" 면
  Fast mode 단가를 쓰고, 그 외에는 Standard 단가를 쓴다. 긴 컨텍스트(long context) 할증은 반영하지 않는다.
- ChatGPT 구독 로그인이면 실제 청구액이 아니라 "같은 사용량을 API 로 썼을 때"의 추정치다.

실패해도 Codex 동작을 막지 않도록 모든 오류는 조용히 무시하고 exit 0 한다.
"""
import json, os, re, sys

# USD / 1M tokens: (input, cached input, cache write, output). cache write 가 없는 모델은 input 단가를 쓴다.
# 출처: https://developers.openai.com/api/docs/pricing (Short context, 2026-09-24 확인)
STANDARD = {
    "gpt-6-astra":   (10.00, 1.00, 12.50, 50.00),
    "gpt-6-sol":     (2.00, 0.20, 2.50, 10.00),
    "gpt-6-luna":    (0.10, 0.01, 0.125, 0.50),
    "gpt-5.6-sol":   (4.00, 0.40, 5.00, 20.00),
    "gpt-5.6-terra": (2.00, 0.20, 2.50, 12.00),
    "gpt-5.6-luna":  (0.20, 0.02, 0.25, 1.20),
    "gpt-5.5":       (5.00, 0.50, None, 30.00),
    "gpt-5.4":       (2.50, 0.25, None, 15.00),
    "gpt-5.3-codex": (1.75, 0.175, None, 14.00),
}
FAST = {
    "gpt-6-astra":   (20.00, 2.00, 25.00, 100.00),
    "gpt-6-sol":     (4.00, 0.40, 5.00, 20.00),
    "gpt-6-luna":    (0.20, 0.02, 0.25, 1.00),
    "gpt-5.6-sol":   (8.00, 0.80, 10.00, 40.00),
    "gpt-5.6-terra": (4.00, 0.40, 5.00, 24.00),
    "gpt-5.6-luna":  (0.40, 0.04, 0.50, 2.40),
    "gpt-5.5":       (12.50, 1.25, None, 75.00),
    "gpt-5.4":       (5.00, 0.50, None, 30.00),
}
FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens")


def fast_mode():
    try:
        with open(os.path.join(os.path.expanduser("~"), ".codex", "config.toml"), encoding="utf-8") as f:
            for line in f:
                if line.lstrip().startswith("["):
                    break                      # 최상위 키만 본다
                m = re.match(r'\s*service_tier\s*=\s*"([^"]*)"', line)
                if m:
                    return m.group(1) in ("fast", "priority")
    except OSError:
        pass
    return False


def price(model, usage, table):
    rate = table.get(model) or STANDARD.get(model)
    if rate is None:
        return None
    inp, cached, write, out = (usage.get(k, 0) or 0 for k in FIELDS)
    r_in, r_cached, r_write, r_out = rate
    if r_write is None:
        r_write = r_in
    plain = max(inp - cached - write, 0)
    return (plain * r_in + cached * r_cached + write * r_write + out * r_out) / 1e6


def human(n):
    for unit, div in (("M", 1e6), ("k", 1e3)):
        if n >= div:
            v = n / div
            return f"{v:.1f}{unit}" if v < 100 else f"{v:.0f}{unit}"
    return str(n)


def summarize(path, table):
    model = None
    prev = None
    total = turn = 0.0
    priced = False
    last = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"turn_context"' not in line and '"token_count"' not in line and '"task_started"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            p = rec.get("payload") or {}
            if rec.get("type") == "turn_context":
                model = p.get("model") or model
                continue
            if p.get("type") == "task_started":
                turn = 0.0
                continue
            if p.get("type") != "token_count":
                continue
            cur = ((p.get("info") or {}).get("total_token_usage")) or None
            if not cur or cur == prev:
                continue
            if prev and all((cur.get(k, 0) or 0) >= (prev.get(k, 0) or 0) for k in FIELDS):
                delta = {k: (cur.get(k, 0) or 0) - (prev.get(k, 0) or 0) for k in FIELDS}
            else:
                delta = cur                    # 첫 이벤트이거나 합계가 초기화된 경우
            prev = last = cur
            c = price(model, delta, table)
            if c is None:
                continue
            priced = True
            total += c
            turn += c
    return priced, total, turn, last


def main():
    try:
        data = json.load(sys.stdin)
        path = data.get("transcript_path")
        if not path or not os.path.isfile(path):
            return
        priced, total, turn, usage = summarize(path, FAST if fast_mode() else STANDARD)
        if not priced:
            return
        inp = usage.get("input_tokens", 0) or 0
        cached = usage.get("cached_input_tokens", 0) or 0
        hit = f"(캐시 {cached * 100 // inp}%)" if inp else ""
        msg = (f"API 환산 ${total:,.2f} · 이번 턴 +${turn:,.2f} · "
               f"입력 {human(inp)}{hit} · 출력 {human(usage.get('output_tokens', 0) or 0)}")
        print(json.dumps({"systemMessage": msg}, ensure_ascii=False))
    except Exception:
        pass


if __name__ == "__main__":
    main()
