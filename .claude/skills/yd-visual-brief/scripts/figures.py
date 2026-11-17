#!/usr/bin/env python3
"""yd-visual-brief 그림 생성기 — 자료(dict)를 받아 SVG 문자열을 돌려준다. stdlib only.

그림마다 함수가 하나다. 색은 팔레트(dict)에서만 가져온다.
  architecture(p, spec)   층별 전체 구성도
  metro(p, spec)          노선도식 흐름도
  compare_rows(p, spec)   행별 대비 그림
  gantt(p, spec)          일정 막대그림
  dumbbell(p, spec)       같은 항목의 두 값
자료 형식은 references/figures.md 에 있다.
"""
import datetime as dt
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT = 'font-family="Pretendard Variable,Pretendard,-apple-system,Apple SD Gothic Neo,Noto Sans KR,sans-serif"'
WHITE = "#ffffff"


def palette(name="ink-cobalt"):
    data = json.loads((ROOT / "assets" / "palettes.json").read_text(encoding="utf-8"))
    return {k: v for k, v in data["palettes"][name].items() if v.startswith("#")}


class Canvas:
    def __init__(self, p, width, height, kind):
        self.p, self.o = p, []
        self.head = (f'<svg data-figure="{kind}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" {FONT}>'
                     f'<defs>{self._markers()}</defs>')

    def _markers(self):
        out = ""
        for key in ("ink", "signal"):
            c = self.p[key]
            out += (f'<marker id="e-{key}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
                    f'<path d="M0 0L10 5L0 10z" fill="{c}"/></marker>'
                    f'<marker id="s-{key}" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
                    f'<path d="M10 0L0 5L10 10z" fill="{c}"/></marker>')
        return out

    def text(self, x, y, s, size=12, weight=400, fill=None, anchor="start", spacing=None):
        extra = f' letter-spacing="{spacing}"' if spacing else ""
        self.o.append(f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" font-weight="{weight}" '
                      f'fill="{fill or self.p["ink"]}" text-anchor="{anchor}"{extra}>{escape(str(s))}</text>')

    def box(self, x, y, w, h, fill=WHITE, stroke=None, width=1.2, dash=None, rx=4):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.o.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{rx}" fill="{fill}" '
                      f'stroke="{stroke or self.p["line"]}" stroke-width="{width}"{extra}/>')

    def path(self, d, stroke, width, dash=None, end=None):
        extra = (f' stroke-dasharray="{dash}"' if dash else "") + (f' marker-end="url(#e-{end})"' if end else "")
        self.o.append(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" '
                      f'stroke-linecap="round" stroke-linejoin="round"{extra}/>')

    def arrow(self, x1, y1, x2, y2, key="ink", dash=None, both=False):
        extra = (f' stroke-dasharray="{dash}"' if dash else "") + (f' marker-start="url(#s-{key})"' if both else "")
        self.o.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{self.p[key]}" '
                      f'stroke-width="1.6" marker-end="url(#e-{key})"{extra}/>')

    def flag(self, x, y, mark):
        """결정이 필요한 곳. mark 는 번호나 느낌표."""
        self.o.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="10" fill="{self.p["signal"]}"/>')
        self.text(x, y + 4, mark, 11.5, 800, WHITE, "middle")

    def stop(self, x, y, color, r=8.5):
        self.o.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{WHITE}" stroke="{color}" stroke-width="3.5"/>')

    def badge(self, x, y, s, color):
        w = len(s) * 12 + 24
        self.o.append(f'<rect x="{x:.0f}" y="{y - 13:.0f}" width="{w}" height="22" rx="11" fill="{color}"/>')
        self.text(x + w / 2, y + 3, s, 11.5, 700, WHITE, "middle")

    def svg(self):
        return self.head + "".join(self.o) + "</svg>"


def architecture(p, spec):
    """층별 전체 구성도. 가운데 층을 위에서 아래로 쌓고 왼쪽에 입력, 오른쪽에 연계 시스템을 둔다."""
    layers = spec["layers"]
    heights = [154 if layer.get("steps") else 118 for layer in layers]
    top, gap = 100, 26
    body = sum(heights) + gap * (len(layers) - 1)
    systems, outside = spec.get("systems", []), spec.get("outside")
    right_rows = len(systems) + (1 if outside else 0)
    body = max(body, right_rows * 74 + 20, len(spec.get("inputs", [])) * 66 + 20)
    target_y = top + body + 30
    infra_y = target_y + 96
    height = infra_y + 64
    c = Canvas(p, 1084, height, "architecture")
    X, W, RX = 250, 550, 846
    # 사용자
    actors = spec.get("actors", [])
    for i, (name, sub) in enumerate(actors):
        x = X + (W - len(actors) * 190 + 20) / 2 + i * 190
        c.box(x, 8, 170, 44, fill=p["ink"], stroke=p["ink"], rx=22)
        c.text(x + 85, 27, name, 14, 700, WHITE, "middle")
        c.text(x + 85, 43, sub, 11, 400, p["line"], "middle")
        c.arrow(x + 85, 52, x + 85, top - 2)
    # 경계 — outside 가 있으면 그 자리를 경계 밖으로 판다
    bottom = height - 20
    if outside:
        oy = top + 26 + len(systems) * 74
        d = f"M20 74 H1060 V{oy - 16} H832 V{oy + 82} H1060 V{bottom} H20 Z"
    else:
        d = f"M20 74 H1060 V{bottom} H20 Z"
    c.o.append(f'<path d="{d}" fill="none" stroke="{p["ink"]}" stroke-width="1.4" stroke-dasharray="6 5"/>')
    label = spec.get("boundary", "")
    if label:
        c.o.append(f'<rect x="36" y="64" width="{len(label) * 13 + 18}" height="20" fill="{WHITE}"/>')
        c.text(44, 79, label, 12, 700, spacing=".06em")
    # 입력
    if spec.get("inputs"):
        c.text(40, top + 16, spec.get("inputs_label", "입력"), 11, 700, p["muted"], spacing=".12em")
    for i, (name, sub) in enumerate(spec.get("inputs", [])):
        y = top + 26 + i * 66
        c.box(40, y, 170, 54)
        c.text(54, y + 23, name, 14, 700)
        c.text(54, y + 41, sub, 12, 400, p["muted"])
        c.arrow(210, y + 27, X - 4, y + 27)
    # 층
    y = top
    for layer, h in zip(layers, heights):
        accent = layer.get("accent")
        edge = p["accent"] if accent else p["ink"]
        c.box(X, y, W, h, stroke=edge, width=1.6)
        c.text(X + 16, y + 26, layer["title"], 17, 800, edge)
        c.text(X + W - 16, y + 26, layer.get("note", ""), 12, 400, p["muted"], "end")
        items = layer["items"]
        iw = (W - 32 - 12 * (len(items) - 1)) / len(items)
        for i, item in enumerate(items):
            x = X + 16 + i * (iw + 12)
            name, lines, mark = item[0], item[1], (item[2] if len(item) > 2 else None)
            if accent:
                c.box(x, y + 38, iw, 50, fill=p["accent"], stroke=p["accent"])
                c.text(x + iw / 2, y + 59, name, 14, 700, WHITE, "middle")
                c.text(x + iw / 2, y + 77, lines[0] if lines else "", 11.5, 400, p["tint"], "middle")
            else:
                c.box(x, y + 38, iw, 66, fill=p["soft"], stroke="none")
                c.text(x + 12, y + 60, name, 14, 700)
                for j, line in enumerate(lines[:2]):
                    c.text(x + 12, y + 78 + j * 16, line, 12, 400, p["muted"])
            if mark:
                c.flag(x + iw - 16, y + 52, mark)
        steps = layer.get("steps")
        if steps:
            sw = (W - 32) / len(steps)
            for i, step in enumerate(steps):
                x, last = X + 16 + i * sw, i == len(steps) - 1
                c.box(x, y + 102, sw - 6, 38, fill=p["ink"] if last else WHITE, stroke=p["ink"] if last else p["accent"], rx=19)
                c.text(x + 15, y + 126, i + 1, 12, 800, WHITE if last else p["accent"], "middle")
                c.text(x + (sw - 6) / 2 + 9, y + 126, step, 11.5, 600, WHITE if last else p["ink"], "middle")
        if layer is not layers[-1]:
            c.arrow(X + W / 2, y + h, X + W / 2, y + h + gap - 2, both=True)
        y += h + gap
    # 연계 시스템
    if systems:
        c.text(RX, top + 16, spec.get("systems_label", "연계 시스템"), 11, 700, p["muted"], spacing=".12em")
    for i, system in enumerate(systems):
        sy = top + 26 + i * 74
        c.box(RX, sy, 198, 62)
        c.text(RX + 12, sy + 22, system[0], 14, 700)
        c.text(RX + 12, sy + 39, system[1], 11.5, 400, p["muted"])
        c.text(RX + 12, sy + 54, system[2], 11.5, 400, p["muted"])
        if len(system) > 3 and system[3]:
            c.flag(RX + 184, sy + 14, system[3])
        c.arrow(X + W + 2, sy + 31, RX - 2, sy + 31, both=True)
    if outside:
        oy = top + 26 + len(systems) * 74
        c.box(RX, oy, 198, 66, stroke=p["signal"], dash="5 4")
        c.text(RX + 12, oy + 24, outside[0], 14, 700)
        c.text(RX + 12, oy + 42, outside[1], 11.5, 400, p["muted"])
        c.text(RX + 12, oy + 57, outside[2], 11.5, 400, p["muted"])
        if len(outside) > 3 and outside[3]:
            c.flag(RX + 184, oy + 14, outside[3])
        c.arrow(X + W + 2, oy + 33, RX - 2, oy + 33, key="signal", dash="5 4")
    # 대상 시스템
    target = spec.get("target")
    if target:
        c.box(40, target_y, 1004, 62, fill=p["ink"], stroke=p["ink"])
        c.text(58, target_y + 26, target.get("label", "대상 시스템"), 11, 700, p["line"], spacing=".12em")
        c.text(58, target_y + 48, target["title"], 16, 800, WHITE)
        chips = target.get("chips", [])
        for i, chip in enumerate(chips):
            x = 1028 - (len(chips) - i) * 128
            c.box(x, target_y + 16, 118, 30, fill="none", stroke=p["muted"], rx=15)
            c.text(x + 59, target_y + 36, chip, 12.5, 600, WHITE, "middle")
    # 인프라
    infra = spec.get("infra", [])
    if infra:
        c.text(40, infra_y - 8, spec.get("infra_label", "인프라"), 11, 700, p["muted"], spacing=".12em")
    iw = (1004 - 12 * (len(infra) - 1)) / max(len(infra), 1)
    for i, (name, unsure) in enumerate(infra):
        x = 40 + i * (iw + 12)
        c.box(x, infra_y, iw, 34, fill=p["soft"], stroke=p["signal"] if unsure else "none", dash="4 3" if unsure else None)
        c.text(x + iw / 2, infra_y + 22, name + (" — 확인 필요" if unsure else ""), 12.5, 600, anchor="middle")
    return c.svg()


def metro(p, spec):
    """노선도식 흐름도. 본선 정거장, 왼쪽 지선, 위쪽 환승 노선, 아래 연계선을 그린다."""
    stations = spec["stations"]
    lower = spec.get("lower")
    Y = 340
    height = 655 if lower else 470
    c = Canvas(p, 1200, height, "flow")
    step = 750 / max(len(stations) - 1, 1)
    X = [250 + i * step for i in range(len(stations))]
    gray = p["line"]
    if spec.get("zone"):
        c.o.append(f'<rect x="196" y="{Y - 62}" width="858" height="176" rx="88" fill="{p["soft"]}"/>')
        c.text(1000, Y + 94, spec["zone"], 11.5, 500, p["muted"], "end")
    feeders = spec.get("feeders", [])
    for i, (name, sub) in enumerate(feeders):
        y0 = Y + (i - (len(feeders) - 1) / 2) * 84
        d = f"M118 {y0:.0f} H{X[0]:.0f}" if y0 == Y else f"M118 {y0:.0f} H150 L{150 + abs(y0 - Y):.0f} {Y} H{X[0]:.0f}"
        c.path(d, p["muted"], 6)
        c.stop(118, y0, p["muted"], 7)
        c.text(100, y0 - 2, name, 13, 700, anchor="end")
        c.text(100, y0 + 14, sub, 11, 400, p["muted"], "end")
    transfers = spec.get("transfers")
    at = transfers["at"] if transfers else -1
    if transfers:
        lines = transfers["lines"]
        colors = [p["ink"], p["muted"], p["accent"]]
        for i, line in enumerate(lines):
            name, sub = line[0], line[1]
            cut = len(line) > 2 and line[2]
            k = i - (len(lines) - 1) / 2
            x0, xe = X[at] + k * 110, X[at] + k * 12
            d = f"M{x0:.0f} 96 V{Y - 8}" if k == 0 else f"M{x0:.0f} 96 V{Y - 128} L{xe:.0f} {Y - 128 + abs(x0 - xe):.0f} V{Y - 8}"
            color = p["signal"] if cut else colors[i % len(colors)]
            c.path(d, color, 8, "2 13" if cut else None)
            c.stop(x0, 96, color)
            c.text(x0, 62, name, 14, 700, anchor="middle")
            c.text(x0, 79, sub, 11, 400, p["muted"], "middle")
            if cut:
                c.flag(x0 + 92, 62, "!")
                c.text(x0 + 107, 66, line[2], 12, 500, p["signal"])
        if transfers.get("label"):
            c.badge(X[at] - (len(lines) - 1) * 55 - 58, 30, transfers["label"], p["ink"])
    c.path(f"M{X[0]:.0f} {Y} H{X[-1]:.0f}", p["accent"], 14)
    beyond = spec.get("beyond")
    if beyond:
        c.path(f"M{X[-1]:.0f} {Y} H1150", gray, 6, "1 12")
        c.stop(1150, Y, p["muted"], 7)
        c.text(1150, Y + 34, beyond[0], 12.5, 700, p["muted"], "middle")
        c.text(1150, Y + 50, beyond[1], 11, 400, p["muted"], "middle")
    notes = spec.get("notes", {})
    for i, (x, name) in enumerate(zip(X, stations)):
        last = i == len(stations) - 1
        if last:
            c.o.append(f'<circle cx="{x:.0f}" cy="{Y}" r="17" fill="{p["ink"]}"/><circle cx="{x:.0f}" cy="{Y}" r="6" fill="{WHITE}"/>')
        elif i == at:
            c.o.append(f'<rect x="{x - 24:.0f}" y="{Y - 13}" width="48" height="26" rx="13" fill="{WHITE}" stroke="{p["ink"]}" stroke-width="3.5"/>')
        else:
            c.stop(x, Y, p["ink"], 9)
        c.text(x, Y + 40, name, 14.5, 700, anchor="middle")
        if i != at:
            c.text(x, Y - 26, f"{i + 1:02d}", 11, 700, p["ink"] if last else p["accent"], "middle", ".08em")
        if str(i) in notes:
            c.text(x, Y + 58, notes[str(i)], 11.5, 700 if last else 400, p["ink"] if last else p["muted"], "middle")
    for flag in spec.get("flags", []):
        x = X[flag["at"]] - 70
        c.flag(x, Y - 52, "!")
        c.text(x + 15, Y - 48, flag["text"], 12, 500, p["signal"])
    if spec.get("zone_flag"):
        c.flag(262, Y + 90, "!")
        c.text(277, Y + 94, spec["zone_flag"], 12, 500, p["signal"])
    if lower:
        Y2 = 535
        stops = lower["stations"]
        ex = [340 + i * 660 / max(len(stops) - 1, 1) for i in range(len(stops))]
        c.path(f"M{ex[0] - 60:.0f} {Y2} H{ex[-1] + 60:.0f}", p["ink"], 8)
        mid = (X[0] + X[-1]) / 2
        c.path(f"M{mid:.0f} {Y + 122} V{Y2 - 6}", p["ink"], 3, "2 8")
        if lower.get("link"):
            c.text(mid + 12, Y + 158, lower["link"], 11, 600, p["muted"])
        c.badge(ex[0] - 60 - len(lower["label"]) * 12 - 34, Y2 + 4, lower["label"], p["ink"])
        for x, stop in zip(ex, stops):
            c.stop(x, Y2, p["ink"])
            c.text(x, Y2 + 34, stop[0], 14, 700, anchor="middle")
            c.text(x, Y2 + 51, stop[1], 11, 400, p["muted"], "middle")
            c.text(x, Y2 + 67, stop[2], 11, 500, p["accent"], "middle")
            if len(stop) > 3 and stop[3]:
                c.flag(x - 70, Y2 + 90, "!")
                c.text(x - 55, Y2 + 94, stop[3], 12, 500, p["signal"])
    return c.svg()


def compare_rows(p, spec):
    """행별 대비 그림. 왼쪽은 작고 흐리게, 오른쪽은 크고 진하게 놓는다."""
    rows = spec["rows"]
    height = 78 + len(rows) * 98
    c = Canvas(p, 1100, height, "compare")
    PX, RX = 150, 400
    c.text(PX, 30, spec["left"][0], 15, 800, p["muted"])
    c.text(PX, 50, spec["left"][1], 12, 400, p["muted"])
    c.text(RX, 30, spec["right"][0], 15, 800, p["accent"])
    c.text(RX, 50, spec["right"][1], 12, 400, p["muted"])
    c.o.append(f'<rect x="{RX - 24}" y="66" width="{1100 - RX + 24}" height="{height - 66}" fill="{p["tint"]}"/>')
    for i, row in enumerate(rows):
        y = 78 + i * 98
        c.o.append(f'<line x1="0" y1="{y}" x2="1100" y2="{y}" stroke="{p["ink"] if i == 0 else p["line"]}" stroke-width="{2 if i == 0 else 1}"/>')
        c.text(0, y + 54, row["label"], 15, 800)
        c.box(PX, y + 30, 150, 38, stroke=p["muted"], width=1.6, dash=None if row["left"] else "5 4")
        c.text(PX + 75, y + 54, row["left"] or "없음", 13, 600, p["muted"], "middle")
        items = row["right"]
        iw = min(150, (1100 - RX - 12 * len(items)) / len(items))
        for j, item in enumerate(items):
            x = RX + j * (iw + 12)
            if row.get("chain"):
                c.box(x, y + 30, iw, 38, fill=p["accent"], stroke=p["accent"])
                c.text(x + iw / 2, y + 54, item, 13, 700, WHITE, "middle")
            else:
                c.box(x, y + 30, iw, 38, stroke=p["ink"], width=1.8)
                c.text(x + iw / 2, y + 54, item, 13, 700, anchor="middle")
        if row.get("note"):
            c.text(RX, y + 88, row["note"], 11.5, 400, p["muted"])
    return c.svg()


def gantt(p, spec):
    """일정 막대그림. 과제 막대, 마일스톤, 선행 조건을 같은 시간축에 놓는다."""
    day = dt.date.fromisoformat
    start, end = day(spec["start"]), day(spec["end"])
    tasks, miles, prereqs = spec["tasks"], spec.get("milestones", []), spec.get("prereqs", [])
    L, W = 200, 870
    gx = lambda s: L + (day(s) - start).days / (end - start).days * W
    top = 66 + len(prereqs) * 20 + (20 if prereqs else 0)
    bottom = top + len(tasks) * 40 + 12
    c = Canvas(p, 1100, bottom + 70, "schedule")
    weeks = ((end - start).days + 6) // 7
    for w in range(weeks):
        x = L + w * 7 / (end - start).days * W
        c.o.append(f'<rect x="{x:.0f}" y="34" width="{W / weeks - 2:.0f}" height="22" rx="4" fill="{p["soft"]}"/>')
        c.text(x + W / weeks / 2, 50, f"W{w + 1}", 11, 400, p["muted"], "middle")
    month = start.replace(day=1)
    while month <= end:
        at = max(month, start)
        c.text(gx(at.isoformat()), 24, f"{at.month}월" if at.year == start.year else f"{at.year}년 {at.month}월", 12.5, 700)
        month = (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    if prereqs:
        c.text(0, 84, spec.get("prereq_label", "선행 조건"), 13, 700, p["signal"])
    for i, (label, date) in enumerate(prereqs):
        x = gx(date)
        c.o.append(f'<circle cx="{x:.0f}" cy="{80 + i * 20}" r="6" fill="{p["signal"]}"/>')
        c.text(x + 12, 84 + i * 20, label, 12)
    for i, task in enumerate(tasks):
        y = top + i * 40
        x1, x2 = gx(task["from"]), gx(task["to"])
        own = task.get("primary")
        c.text(0, y + 19, f'{i + 1}. {task["name"]}', 13.5, 700)
        c.box(x1, y, x2 - x1, 28, fill=p["accent"] if own else p["tint"], stroke=p["accent"], width=1 if not own else 0, rx=14)
        note = f'{task["from"][5:]} ~ {task["to"][5:]} · {task["owner"]}'
        inside = x2 > L + W - 190
        c.text(x1 + 12 if inside else x2 + 8, y + 19, note, 11.5, 400, WHITE if inside and own else p["muted"])
    for i, (label, date) in enumerate(miles):
        x = gx(date)
        c.o.append(f'<line x1="{x:.0f}" y1="{top - 10}" x2="{x:.0f}" y2="{bottom}" stroke="{p["signal"]}" stroke-width="1.5" stroke-dasharray="3 4"/>'
                   f'<path d="M{x:.0f} {bottom} l8 10 l-8 10 l-8 -10z" fill="{p["signal"]}"/>')
        c.text(x, bottom + (38 if i % 2 == 0 else 56), f"{label} {date[5:]}", 12, 700, anchor="end" if x > L + W - 120 else "middle")
    return c.svg()


def dumbbell(p, spec):
    """같은 항목에 값이 둘일 때. 두 점을 선으로 잇는다."""
    rows, lo, hi = spec["rows"], spec["min"], spec["max"]
    c = Canvas(p, 1100, 34 + len(rows) * 48 + 30, "compare")
    bx = lambda v: 330 + (v - lo) / (hi - lo) * 640
    bottom = 20 + len(rows) * 48
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        c.o.append(f'<line x1="{bx(v):.0f}" y1="14" x2="{bx(v):.0f}" y2="{bottom}" stroke="{p["line"]}"/>')
        c.text(bx(v), bottom + 16, f'{v:g}{spec.get("unit", "")}', 11, 400, p["muted"], "middle")
    for i, row in enumerate(rows):
        y = 38 + i * 48
        (v1, s1), (v2, s2) = row["a"], row["b"]
        unit = spec.get("unit", "")
        c.text(0, y + 5, row["label"], 14, 700)
        c.o.append(f'<line x1="{bx(v1):.0f}" y1="{y}" x2="{bx(v2):.0f}" y2="{y}" stroke="{p["signal"]}" stroke-width="6" stroke-linecap="round"/>'
                   f'<circle cx="{bx(v1):.0f}" cy="{y}" r="11" fill="{p["accent"]}"/><circle cx="{bx(v2):.0f}" cy="{y}" r="11" fill="{p["signal"]}"/>')
        c.text(bx(v1) - 18, y + 5, f"{v1:g}{unit} · {s1}", 12, 400, p["accent"], "end")
        c.text(bx(v2) + 18, y + 5, f"{v2:g}{unit} · {s2}", 12, 400, p["signal"])
    return c.svg()


if __name__ == "__main__":
    import sys
    spec = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    builder = {"architecture": architecture, "metro": metro, "compare_rows": compare_rows, "gantt": gantt, "dumbbell": dumbbell}[sys.argv[1]]
    print(builder(palette(spec.get("palette", "ink-cobalt")), spec))
