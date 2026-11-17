#!/usr/bin/env python3
"""yd-visual-brief 검사기 — 그림 중심 문서(HTML)의 색·글자·그림 규칙을 본다. stdlib only.

  check_brief.py 문서.html        문서 한 편 검사
  check_brief.py --palettes       assets/palettes.json 의 팔레트 전부 검사
종료 코드: 0 오류 없음, 1 오류 있음, 2 사용법·파일 문제
"""
import colorsys
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ("paper", "ink", "accent", "signal", "muted")
# (앞, 뒤, 최소 대비, 이름)
CONTRAST = (("ink", "paper", 7.0, "본문 글자"), ("muted", "paper", 4.5, "보조 글자"),
            ("accent", "paper", 4.5, "강조색"), ("signal", "paper", 3.0, "경고색"),
            ("#ffffff", "accent", 4.5, "강조색 위 흰 글자"))
HUE_GAP = 60        # 강조색과 경고색의 색상 차(도)
HUE_NEAR = 30       # 유채색이 강조색·경고색 계열로 인정되는 범위(도)
SATURATED = 0.2     # 이 채도 이상이면 유채색으로 본다
MIN_SVG_FONT = 11
HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF️]")


def rgb(value):
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(value):
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hue_sat(value):
    h, l, s = colorsys.rgb_to_hls(*rgb(value))
    return h * 360, s, l


def hue_distance(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def palette_problems(p, name=""):
    out = []
    tag = f"{name}: " if name else ""
    missing = [k for k in REQUIRED if k not in p]
    if missing:
        return [("오류", "팔레트", f"{tag}색 역할이 없다: {', '.join(missing)}")]
    for fg, bg, need, label in CONTRAST:
        got = contrast(p.get(fg, fg), p.get(bg, bg))
        if got < need:
            out.append(("오류", "색 대비", f"{tag}{label} 대비 {got:.2f} — {need} 이상이어야 한다"))
    gap = hue_distance(hue_sat(p["accent"])[0], hue_sat(p["signal"])[0])
    if gap < HUE_GAP:
        out.append(("오류", "색 구별", f"{tag}강조색과 경고색의 색상 차 {gap:.0f}도 — {HUE_GAP}도 이상이어야 한다"))
    return out


def root_palette(html):
    block = re.search(r":root\s*\{([^}]*)\}", html)
    if not block:
        return {}
    return {k: v for k, v in re.findall(r"--([a-z]+)\s*:\s*(#[0-9a-fA-F]{3,6})", block.group(1))}


def brief_problems(html):
    out = []
    p = root_palette(html)
    out += palette_problems(p)
    if all(k in p for k in ("accent", "signal")):
        anchors = [hue_sat(p["accent"])[0], hue_sat(p["signal"])[0]]
        stray, own = set(), {v.lower() for v in p.values()}
        for m in HEX.finditer(html):
            value = "#" + m.group(1).lower()
            if value in own:
                continue
            hue, sat, light = hue_sat(value)
            if sat >= SATURATED and 0.08 < light < 0.97 and min(hue_distance(hue, a) for a in anchors) > HUE_NEAR:
                stray.add(value)
        for value in sorted(stray):
            out.append(("오류", "색 가짓수", f"{value} — 강조색·경고색 계열이 아닌 유채색이다"))
    for m in re.finditer(r"<svg\b[\s\S]*?</svg>", html):
        for size in re.findall(r'font-size="([0-9.]+)"', m.group(0)):
            if float(size) < MIN_SVG_FONT:
                out.append(("오류", "글자 크기", f"SVG 글자 {size}px — {MIN_SVG_FONT}px 이상이어야 한다"))
    text = re.sub(r"<(script|style)\b[\s\S]*?</\1>", "", html)
    found = sorted(set(EMOJI.findall(text)))
    if found:
        out.append(("오류", "이모지", f"이모지 {len(found)}종 — 글이나 SVG 도형으로 바꾼다"))
    for src in re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', html):
        if re.search(r"\.(png|jpe?g|gif|webp)(\?|$)", src, re.I) or src.startswith("data:image/png") or src.startswith("data:image/jp"):
            out.append(("오류", "캡처 이미지", f"{src[:60]} — 그림은 SVG 로 직접 그린다"))
    kinds = re.findall(r'data-figure="([a-z-]+)"', html)
    if "architecture" not in kinds:
        out.append(("오류", "구성도", '전체 구성도가 없다 — data-figure="architecture" 그림을 넣는다'))
    if len(re.findall(r"<h1\b", html)) != 1:
        out.append(("오류", "결론", "h1 은 결론 한 문장으로 하나만 둔다"))
    if len(kinds) < 3:
        out.append(("경고", "그림 수", f"그림 {len(kinds)}개 — 장마다 그림 하나를 권한다"))
    if not re.search(r"<details\b", html):
        out.append(("경고", "글 전문", "글 전문을 접어 둔 details 가 없다"))
    if re.search(r'(src|href)="https?://', html):
        out.append(("경고", "외부 자원", "외부 주소를 불러온다 — 폐쇄망에서는 글꼴·스크립트를 문서에 넣는다"))
    return out


def report(name, problems):
    for level, kind, message in problems:
        print(f"{name}: {level} [{kind}] {message}")
    errors = sum(level == "오류" for level, _, _ in problems)
    print(f"오류 {errors}건, 경고 {len(problems) - errors}건")
    return 1 if errors else 0


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if argv[1] == "--palettes":
        data = json.loads((ROOT / "assets" / "palettes.json").read_text(encoding="utf-8"))
        problems = [x for name, p in data["palettes"].items() for x in palette_problems(p, name)]
        return report("palettes.json", problems)
    path = Path(argv[1])
    if not path.is_file():
        print(f"파일이 없다: {path}", file=sys.stderr)
        return 2
    return report(path.name, brief_problems(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
