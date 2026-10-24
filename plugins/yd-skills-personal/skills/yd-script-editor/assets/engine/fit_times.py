#!/usr/bin/env python3
"""음성 합성 뒤 실제 음성 길이로 대본 시각을 다시 맞춘다.

- 입력: <콘텐츠>/audio/<라벨>/NN.m4a 길이, 대본 md 머리말 '목표 길이'
- 계산: 에디터 '목표 길이에 시각 맞춤'(app/src/client/common/timing.ts fitTimes)과 같다.
  첫 줄 시작 시각을 두고, 줄마다 음성 길이에 같은 여유를 붙여 마지막 줄이 목표 길이에서 끝나게 한다.
- 출력: 기본은 바뀔 시각만 보여 준다. --apply 면 md 표 '시각' 칸과 합성 입력 json 의 start·max 를 고친다.

사용: python3 fit_times.py <라벨|주소 번호> [--target 140] [--hold 2=2.0] [--apply] [--config <script-editor.json>]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from se_config import Config  # noqa: E402
from script import fmt, probe  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('label')
    ap.add_argument('--config')
    ap.add_argument('--target', type=float, help='목표 길이(초). 없으면 md 머리말 값')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--hold', action='append', default=[], metavar='줄=초',
                    help='그 줄에만 여유를 더 준다(예: 2=2.0, 화면 연출이 긴 줄). 여러 번 쓸 수 있다')
    a = ap.parse_args()
    cfg = Config(a.config)
    label = cfg.resolve_label(a.label)
    md_path, js_path = cfg.script_md(label), cfg.script_json(label)
    md = md_path.read_text()
    target = a.target or float(re.search(r'목표\s*길이\s*[:：]\s*(\d+(?:\.\d+)?)\s*초', md).group(1))
    rows = [ln for ln in md.splitlines() if re.match(r'^\| \d+ \|', ln)]
    durs = [probe(cfg.content / 'audio' / label / f'{i:02d}.m4a') for i in range(1, len(rows) + 1)]
    start = float(re.match(r'^\| \d+ \| (\d+):(\d+(?:\.\d+)?) \|', rows[0]).group(2)) + \
        60 * int(re.match(r'^\| \d+ \| (\d+):', rows[0]).group(1))
    hold = {int(k): float(v) for k, v in (h.split('=') for h in a.hold)}
    spare = target - start - sum(durs) - sum(hold.values())
    if spare < 0:
        raise SystemExit(f'음성 합계 {sum(durs):.1f}초가 목표 {target:g}초보다 길다 — 목표를 늘리거나 대본을 줄인다')
    gap = spare / len(durs)
    times, t = [], start
    for d in durs:
        times.append(round(t * 10) / 10)
        t += d + gap + hold.get(len(times), 0.0)
    for i, (row, d, tt) in enumerate(zip(rows, durs, times), 1):
        old = row.split(' | ')[1]
        print(f'{i:02d} {old:>7} → {fmt(tt):>7}  음성 {d:4.1f}초')
    print(f'음성 합계 {sum(durs):.1f}초 · 목표 {target:g}초 · 줄마다 여유 {gap:.2f}초')
    if not a.apply:
        return
    new_rows = []
    for row, tt in zip(rows, times):
        c = row.split(' | ')
        c[1] = fmt(tt)
        new_rows.append(' | '.join(c))
    for old, new in zip(rows, new_rows):
        md = md.replace(old, new, 1)
    md = re.sub(r'- 읽기 합계 [^\n]*', f'- 음성 합계 {sum(durs):.1f}초 · 줄마다 여유 {gap:.1f}초 · {len(rows)}장면', md, count=1)
    md = re.sub(r'(목표\s*길이\s*[:：]\s*)\d+(?:\.\d+)?(\s*초)', rf'\g<1>{target:g}\g<2>', md, count=1)
    md_path.write_text(md)
    doc = json.loads(js_path.read_text())
    ends = times[1:] + [target]
    for line, tt, end in zip(doc['lines'], times, ends):
        line['start'] = tt
        line['max'] = round(end - tt, 1)
    js_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    print('적용', md_path.name, js_path.name)


if __name__ == '__main__':
    main()
