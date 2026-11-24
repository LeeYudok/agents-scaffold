#!/usr/bin/env python3
"""yd-visual-brief 조립기 — brief.json 하나를 읽어 그림 중심 문서(HTML 한 장)를 만든다. stdlib only.

  build_brief.py brief.json -o 문서.html
자료 형식은 references/brief-format.md, 예제는 assets/example/brief.json 에 있다.
종료 코드: 0 만들었다, 2 사용법·자료 문제
"""
import json
import re
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figures  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIGURES = {"architecture": figures.architecture, "metro": figures.metro, "compare_rows": figures.compare_rows,
           "gantt": figures.gantt, "dumbbell": figures.dumbbell, "receipt": figures.receipt,
           "waterfall": figures.waterfall}


def mark(text):
    """*강조* 를 em 으로 바꾼다. 나머지는 그대로 글자로 넣는다."""
    return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escape(text)).replace("\n", "<br>")


def block_html(block, p):
    kind = block["type"]
    if kind == "figure":
        if block["kind"] not in FIGURES:
            raise ValueError(f'모르는 그림: {block["kind"]}')
        out = f'<div class="card">{FIGURES[block["kind"]](p, block["spec"])}</div>'
        if block.get("keys"):
            out += '<ol class="keys">' + "".join(f"<li><b>{escape(k['title'])}</b>{escape(k['text'])}</li>" for k in block["keys"]) + "</ol>"
        return out
    if kind == "cards":
        return '<div class="cols why">' + "".join(f"<div><b>{escape(i['title'])}</b><p>{escape(i['text'])}</p></div>" for i in block["items"]) + "</div>"
    if kind == "docs":
        out = '<div class="cols docs">'
        for i, item in enumerate(block["items"]):
            rows = "".join(f"<dt>{escape(k)}</dt><dd>{mark(v)}</dd>" for k, v in item.get("rows", []))
            chips = "".join(f'<span class="chip cut">{escape(c)}</span>' for c in item.get("cut", []))
            chips += "".join(f'<span class="chip ask">{escape(c)}</span>' for c in item.get("ask", []))
            out += (f'<div class="doc{" main" if item.get("main") else ""}"><div class="tab">{escape(item["title"])}'
                    f'<small>{escape(item.get("sub", ""))}</small></div><dl>{rows}</dl>'
                    + (f'<div class="chips">{chips}</div>' if chips else "") + "</div>")
        return out + "</div>"
    if kind == "pairs":
        rows = "".join(f'<b>{escape(r["label"])}</b><div class="a">{escape(r["a"][0])}<small>{escape(r["a"][1])}</small></div>'
                       f'<div class="b">{escape(r["b"][0])}<small>{escape(r["b"][1])}</small></div>' for r in block["rows"])
        return f'<div class="ab">{rows}</div>'
    if kind == "waffle":
        cells = "".join(f'<i class="{g["style"]}"></i>' * len(g["items"]) for g in block["groups"])
        total = sum(len(g["items"]) for g in block["groups"])
        cols = "".join(f'<div><span class="n {g["style"]}">{len(g["items"])}</span><h3>{escape(g["label"])}</h3><ul>'
                       + "".join(f"<li>{escape(i)}</li>" for i in g["items"]) + "</ul></div>" for g in block["groups"])
        return f'<div class="card have"><div class="waffle" style="grid-template-columns:repeat({total},minmax(0,64px))">{cells}</div><div class="cols">{cols}</div></div>'
    if kind == "org":
        top = "".join(f"<span><small>{escape(k)}</small>{escape(v)}</span>" for k, v in block.get("top", []))
        rest = "".join(f"<div><small>{escape(k)}</small>{escape(v)}</div>" for k, v in block.get("items", []))
        return f'<div class="org"><div class="top">{top}</div>{rest}</div>'
    if kind == "decisions":
        out = '<div class="dec">'
        for n, item in enumerate(block["items"], 1):
            opts = '<u>또는</u>'.join(f"<span>{escape(o)}</span>" for o in item["options"])
            out += (f'<div><div class="n">결정 {n:02d}</div><b>{escape(item["title"])}</b><div class="opt">{opts}</div>'
                    + (f'<p>{escape(item["note"])}</p>' if item.get("note") else "") + "</div>")
        return out + "</div>"
    if kind == "note":
        return f'<p class="note">{escape(block["text"])}</p>'
    raise ValueError(f"모르는 블록: {kind}")


def build(brief):
    p = figures.palette(brief.get("palette", "ink-cobalt"))
    kpis = "".join(f'<div{" class=\"q\"" if k.get("warn") else ""}><b>{escape(k["value"])}</b><span>{mark(k["label"])}</span></div>'
                   for k in brief.get("kpis", []))
    body = ""
    for n, section in enumerate(brief["sections"], 1):
        blocks = "".join(block_html(b, p) for b in section.get("blocks", []))
        body += (f'<section><div class="no">{n:02d} · {escape(section["label"])}</div><h2>{escape(section["title"])}</h2>'
                 + (f'<p class="lead">{escape(section["lead"])}</p>' if section.get("lead") else "") + blocks + "</section>")
    full = brief.get("full_text")
    tail = f'<details><summary>글로 된 전문 보기 (그림의 근거)</summary><pre id="full">{escape(full)}</pre></details>' if full else ""
    html = (ROOT / "assets" / "template.html").read_text(encoding="utf-8")
    values = {"TITLE": escape(brief.get("doc_title", "문서")), "ROOT": ";".join(f"--{k}:{v}" for k, v in p.items()),
              "EYEBROW": escape(brief.get("eyebrow", "")), "H1": mark(brief["title"]), "LEAD": escape(brief.get("lead", "")),
              "KPIS": kpis, "KPI_COUNT": str(max(len(brief.get("kpis", [])), 1)), "BODY": body, "TAIL": tail}
    for key, value in values.items():
        html = html.replace("{{" + key + "}}", value)
    return html


def main(argv):
    if len(argv) != 4 or argv[2] != "-o":
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        brief = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        html = build(brief)
    except (OSError, ValueError, KeyError) as error:
        print(f"자료 문제: {error!r}", file=sys.stderr)
        return 2
    Path(argv[3]).write_text(html, encoding="utf-8")
    print(f"만들었다: {argv[3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
