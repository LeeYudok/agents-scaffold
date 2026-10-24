#!/usr/bin/env python3
"""화면설계서 HTML 하나에서 PDF 와 PPTX 를 함께 만든다.

    python3 export_deck.py <프로젝트명>_storyboard.html
    # -> <프로젝트명>_storyboard.pdf, <프로젝트명>_storyboard.pptx

두 형식은 렌더 경로가 다르다. 의도된 것이다.

    PDF   인쇄 CSS + Chrome --print-to-pdf   텍스트가 벡터라 선택·검색된다
    PPTX  슬라이드별 PNG + OOXML 조립        텍스트가 이미지다

같은 HTML 을 같은 렌더 엔진으로 그리므로 내용은 동일하다. PDF 까지 이미지로
만들면 텍스트 선택·검색과 인쇄 선명도를 잃으므로 그렇게 하지 않는다.

PPT 를 편집 가능한 도형·텍스트로 만드는 것은 HTML/CSS 레이아웃을 PPT 오브젝트
모델로 다시 짜는 별개의 작업이며 이 스크립트의 범위가 아니다.

stdlib 만 쓴다 — 이 저장소의 검증·생성 스크립트 공통 규약이다.
"""
import argparse
import html
import math
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 슬라이드 설계 기준. 목업 크기와 배지 인라인 top 이 전부 이 폭에서 나온
# 절대 픽셀값이라, 다른 폭으로 렌더하면 목업이 넘치거나 배지가 어긋난다.
# 높이는 16:9 로 787.5px 이고, 창 크기는 정수라야 하므로 올려서 쓴다.
DESIGN_W = 1400
DESIGN_H = DESIGN_W * 9 / 16          # 787.5 — EMU 환산의 기준
WINDOW_H = math.ceil(DESIGN_H)        # 788 — --window-size 용

# PPTX 슬라이드 크기 (EMU). 16:9 와이드스크린 = 13.333 x 7.5 inch.
EMU_W, EMU_H = 12192000, 6858000

# mermaid 는 JS 렌더다. 이 시간을 주지 않으면 IA·흐름도·시퀀스 슬라이드가
# 빈 칸으로 캡처·인쇄된다.
RENDER_WAIT_MS = 15000

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)

XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
# 관계 타입의 네임스페이스는 패키지 네임스페이스(REL_NS)와 다르다. 둘을 문자열
# 조작으로 파생시키면 package/2006/officeDocument/2006/... 같은 무효 URL 이 나오는데,
# XML 은 여전히 well-formed 라 파싱 검사로는 잡히지 않는다 — 열 때야 실패한다.
REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def find_chrome(explicit=None):
    """Chrome 실행 파일을 찾는다. 경로를 하드코딩하지 않는다."""
    for cand in filter(None, (explicit, os.environ.get("CHROME"), *CHROME_CANDIDATES)):
        found = cand if os.path.isfile(cand) else shutil.which(cand)
        if found:
            return found
    sys.exit(
        "오류: Chrome 을 찾을 수 없다. --chrome 으로 경로를 주거나 CHROME 환경변수를 "
        "설정할 것 (macOS 는 'Google Chrome.app', 리눅스는 google-chrome/chromium)"
    )


def run_chrome(chrome, *args):
    result = subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
         f"--virtual-time-budget={RENDER_WAIT_MS}", *args],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"오류: Chrome 실행 실패 (exit {result.returncode})\n{result.stderr[-600:]}")


def split_slides(html):
    """`<div class="ppt-slide">` 블록을 문서 순서대로 잘라낸다.

    반환값은 (슬라이드 번호, 블록 HTML) 목록. 파서를 쓰지 않고 div 깊이를
    세는 이유는 stdlib 의 HTMLParser 로 원문을 그대로 되돌리기 어려워서다 —
    인라인 style 과 SVG 가 많은 문서라 재직렬화하면 렌더가 달라진다.
    """
    slides = []
    tag = re.compile(r"<div\b|</div>")
    for match in re.finditer(r'<div class="ppt-slide">', html):
        depth, cursor = 0, match.start()
        while cursor < len(html):
            found = tag.search(html, cursor)
            if not found:
                break
            depth += 1 if found.group() != "</div>" else -1
            cursor = found.end()
            if depth == 0:
                break
        block = html[match.start():cursor]
        no = re.search(r'class="ppt-top-no">NO\.\s*([\d.]+)<', block)
        slides.append((no.group(1) if no else str(len(slides) + 1), block))
    return slides


def isolated_page(head, block, ordinal):
    """슬라이드 하나만 담은 문서. 캡처 크기를 슬라이드에 정확히 맞춘다.

    Page No. 는 CSS counter 라 슬라이드를 떼어내면 1부터 다시 센다.
    counter-reset 으로 원본 순번을 유지한다.
    """
    return (
        f'{head}<body style="margin:0;padding:0;background:#fff;">'
        f'<div class="docwrap" style="max-width:none;gap:0;'
        f'counter-reset:slide {ordinal};">{block}</div></body></html>'
    )


# 인쇄 CSS 블록의 시작 표식. 템플릿 안에서 이 주석부터 </style> 까지가
# @page 와 @media print 규칙이다.
PRINT_CSS_MARKER = "인쇄 · PDF 저장 (A4 가로"


def template_print_css():
    """템플릿에서 인쇄 CSS 블록을 떼어 온다.

    인쇄 CSS 의 원본은 resources/template.html 한 곳이다. 여기에 복제해 두면
    템플릿이 바뀔 때 조용히 어긋난다.
    """
    template = Path(__file__).resolve().parent.parent / "resources" / "template.html"
    if not template.is_file():
        return None
    text = template.read_text(encoding="utf-8")
    start = text.find(PRINT_CSS_MARKER)
    end = text.find("</style>", start)
    if start == -1 or end == -1:
        return None
    # 주석 여는 기호까지 포함되도록 앞으로 되짚는다
    start = text.rfind("/*", 0, start)
    return text[start:end]


def export_pdf(chrome, src, dest, workdir):
    """인쇄 CSS 를 태워 A4 가로 PDF 를 만든다.

    인쇄 CSS 가 없는 예전 산출물이면 템플릿의 것을 임시 사본에 주입해 쓴다.
    그러지 않으면 기본 용지(US Letter 세로)로 떨어지고 슬라이드가 페이지
    경계에서 잘린 PDF 가 조용히 나온다 — 46슬라이드 문서가 20페이지로 나온
    실측 사례가 있다. 사용자의 원본 파일은 건드리지 않는다.
    """
    source = src
    if "@media print" not in src.read_text(encoding="utf-8"):
        css = template_print_css()
        if css is None:
            print("경고: 인쇄 CSS 가 없고 템플릿에서도 찾지 못했다 — "
                  "PDF 가 기본 용지로 떨어진다", file=sys.stderr)
        else:
            patched = workdir / f"{src.stem}_print.html"
            patched.write_text(
                src.read_text(encoding="utf-8").replace("</style>", css + "</style>", 1),
                encoding="utf-8")
            source = patched
            print("알림: 인쇄 CSS 가 없는 산출물이라 템플릿의 것을 주입해 PDF 를 만든다 "
                  "(원본 파일은 바꾸지 않는다)")
    run_chrome(chrome, "--no-pdf-header-footer",
               f"--print-to-pdf={dest}", f"file://{source.resolve()}")
    if not dest.is_file():
        sys.exit(f"오류: PDF 가 생성되지 않았다 — {dest}")
    return dest


def default_jobs():
    """동시 캡처 수. 기계를 다 먹지 않도록 코어 두 개는 남긴다."""
    return max(1, min(8, (os.cpu_count() or 4) - 2))


def _shoot_one(chrome, head, workdir, scale, index, block, blank_desc=False):
    """슬라이드 하나를 캡처한다. 병렬로 호출되므로 파일을 공유하지 않는다.

    임시 HTML 을 한 파일에 덮어쓰며 재사용하면 병렬 실행에서 서로의 내용을
    덮어써 엉뚱한 슬라이드가 찍힌다 — 슬라이드마다 별도 파일을 쓴다.
    """
    page = workdir / f"_slide{index + 1}.html"
    markup = isolated_page(head, block, index)
    if blank_desc:
        # 본문만 감춘다 — visibility 라 레이아웃은 그대로여서 헤더 위치가 안 밀린다
        markup = markup.replace("</style>", DESC_BLANK_CSS + "</style>", 1)
    page.write_text(markup, encoding="utf-8")
    shot = workdir / f"image{index + 1}.png"
    run_chrome(chrome,
               f"--window-size={DESIGN_W},{WINDOW_H}",
               f"--force-device-scale-factor={scale}",
               f"--screenshot={shot}", f"file://{page.resolve()}")
    page.unlink(missing_ok=True)
    if not shot.is_file():
        sys.exit(f"오류: 슬라이드 {index + 1} 캡처 실패")
    return index, shot


def shoot_slides(chrome, head, slides, workdir, scale, jobs=None, blank=None):
    """슬라이드마다 PNG 를 뜬다. 캡처는 서로 독립이므로 병렬로 돌린다.

    비용은 대기가 아니라 Chrome 기동이다 — virtual time 은 타이머를 빨리 감을
    뿐 벽시계 시간을 쓰지 않아, 대기를 줄여도 1회 3.4초에서 3.1초가 될 뿐이다.
    그래서 동시 실행이 유일하게 의미 있는 개선이다.

    subprocess 대기 중에는 GIL 이 풀리므로 스레드로 충분하다.
    """
    jobs = jobs or default_jobs()
    shots = [None] * len(slides)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [
            pool.submit(_shoot_one, chrome, head, workdir, scale, index, block,
                        bool(blank and blank[index]))
            for index, (_, block) in enumerate(slides)
        ]
        for future in as_completed(futures):
            index, shot = future.result()
            shots[index] = shot
    return shots


# ---- Description 패널을 PPT 객체로 (--editable-desc) ----
#
# 기본 pptx 는 슬라이드마다 전면 이미지 한 장이라 PPT 에서 글자를 고칠 수 없다.
# 화면 상세(09.x)의 우측 설명 패널만 PPT 도형으로 얹으면 기획자가 실제로 고치고
# 싶어하는 문구가 편집 가능해진다. 목업은 이미지로 둔다.
#
# 핵심은 이미지 쪽 패널 본문을 비운 채 캡처하는 것이다. 안 그러면 래스터 글자
# 위에 텍스트 상자가 겹쳐 두 번 보인다.
DESC_BLANK_CSS = ".ppt-desc-body{visibility:hidden !important;}"

# 기준 산출물에서 확인한 서식. 좌표는 실측하고 서식만 여기서 고정한다.
BADGE_PT, DESC_PT = 700, 840          # 100 = 1pt
DESC_TITLE_RGB, DESC_BODY_RGB = "111827", "374151"
DESC_LINE_SPACING = 145000            # 145%

# 설계 px -> EMU. 고정 dpi(914400/96 = 9525)를 쓰면 안 된다 — 슬라이드는
# 13.333in(=96dpi 기준 1280px)인데 설계 폭은 1400px 이라 9.4% 어긋나 도형이
# 오른쪽으로 밀려 슬라이드 밖으로 나간다. 실측 사례가 있다.
EMU_PER_PX = EMU_W / DESIGN_W         # 8708.57 — 세로(EMU_H/787.5)와 같다


def _emu(px):
    return int(round(px * EMU_PER_PX))


def _xml_escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def measure_desc(chrome, head, slides, workdir, jobs, accent):
    """슬라이드마다 설명 패널을 실측한다. 패널이 없으면 None."""
    script = (Path(__file__).resolve().parent.parent
              / "resources" / "desc-measure.js")
    if not script.is_file():
        print("경고: desc-measure.js 가 없어 설명 패널을 객체로 만들지 못한다",
              file=sys.stderr)
        return [None] * len(slides)
    snippet = script.read_text(encoding="utf-8").strip().rstrip(";")
    inject = ('<script>window.addEventListener("load",()=>{setTimeout(()=>{'
              f"const r={snippet};"
              'const p=document.createElement("pre");p.id="__desc__";'
              'p.textContent=JSON.stringify(r);document.body.appendChild(p);'
              '},1200)});</script>')

    def one(index, block):
        page = workdir / f"_measure{index + 1}.html"
        page.write_text(
            isolated_page(head, block, index).replace("</body>", inject + "</body>"),
            encoding="utf-8")
        dom = workdir / f"_measure{index + 1}.html.dom"
        result = subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--virtual-time-budget={RENDER_WAIT_MS}",
             f"--window-size={DESIGN_W},{WINDOW_H}",
             "--dump-dom", f"file://{page.resolve()}"],
            capture_output=True, text=True)
        page.unlink(missing_ok=True)
        dom.unlink(missing_ok=True)
        found = re.search(r'<pre id="__desc__">(.*?)</pre>', result.stdout, re.DOTALL)
        if not found:
            return index, None
        import html as _html
        data = json.loads(_html.unescape(found.group(1)))
        return index, (data if data.get("hasPanel") and data.get("items") else None)

    measured = [None] * len(slides)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(one, i, block)
                   for i, (_, block) in enumerate(slides)]
        for future in as_completed(futures):
            index, data = future.result()
            measured[index] = data
    return measured


def desc_shapes(data, accent):
    """실측값을 PPT 도형 XML 로 바꾼다. 배지 칩 + 설명 텍스트 상자 한 쌍씩."""
    if not data:
        return ""
    out = []
    for n, item in enumerate(data["items"]):
        badge, text = item["badge"], item["text"]
        shape_id = 10 + n * 2
        out.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="badge {_xml_escape(item["label"])}"/>'
            '<p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{_emu(badge["x"])}" y="{_emu(badge["y"])}"/>'
            f'<a:ext cx="{_emu(badge["w"])}" cy="{_emu(badge["h"])}"/></a:xfrm>'
            '<a:prstGeom prst="roundRect"><a:avLst>'
            '<a:gd name="adj" fmla="val 30000"/></a:avLst></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{accent}"/></a:solidFill>'
            '<a:ln><a:noFill/></a:ln></p:spPr><p:txBody>'
            '<a:bodyPr anchor="ctr" anchorCtr="1" lIns="0" tIns="0" rIns="0" bIns="0"/>'
            '<a:lstStyle/><a:p><a:pPr algn="ctr"/>'
            f'<a:r><a:rPr lang="ko-KR" sz="{BADGE_PT}" b="1">'
            '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:rPr>'
            f'<a:t>{_xml_escape(item["label"])}</a:t></a:r></a:p></p:txBody></p:sp>')

        runs = []
        for i, line in enumerate(item["lines"]):
            if i:
                runs.append("<a:br/>")
            bold = ' b="1"' if i == 0 and item.get("boldFirst") else ""
            rgb = DESC_TITLE_RGB if i == 0 and item.get("boldFirst") else DESC_BODY_RGB
            runs.append(
                f'<a:r><a:rPr lang="ko-KR" sz="{DESC_PT}"{bold}>'
                f'<a:solidFill><a:srgbClr val="{rgb}"/></a:solidFill></a:rPr>'
                f'<a:t>{_xml_escape(line)}</a:t></a:r>')
        out.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id + 1}" name="desc {_xml_escape(item["label"])}"/>'
            '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{_emu(text["x"])}" y="{_emu(text["y"])}"/>'
            f'<a:ext cx="{_emu(text["w"])}" cy="{_emu(text["h"])}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>'
            '<a:ln><a:noFill/></a:ln></p:spPr><p:txBody>'
            '<a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0"><a:noAutofit/></a:bodyPr>'
            f'<a:lstStyle/><a:p><a:pPr><a:lnSpc><a:spcPct val="{DESC_LINE_SPACING}"/>'
            f'</a:lnSpc></a:pPr>{"".join(runs)}</a:p></p:txBody></p:sp>')
    return "".join(out)


def slide_accent(html):
    """산출물의 --accent 값을 6자리 대문자 HEX 로."""
    found = re.search(r"--accent:\s*#([0-9a-fA-F]{6})", html)
    return found.group(1).upper() if found else "1B64DA"


def _rels(entries):
    body = "".join(
        f'<Relationship Id="{rid}" Type="{REL_TYPE}/{kind}" Target="{target}"/>'
        for rid, kind, target in entries
    )
    return f'{XML_DECL}<Relationships xmlns="{REL_NS}">{body}</Relationships>'


def build_pptx(shots, dest, overlays=None):
    """PNG 목록으로 최소 구조의 pptx 를 조립한다.

    골격은 PowerPoint·Keynote·LibreOffice 가 여는 최소 집합이다 — 마스터 1개,
    빈 레이아웃 1개, 테마 1개, 슬라이드마다 전면 이미지 1개.
    """
    count = len(shots)
    grp = ('<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
           '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
           '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>')

    content_types = (
        f'{XML_DECL}<Types xmlns="{CT_NS}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        + "".join(
            f'<Override PartName="/ppt/slides/slide{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
            for i in range(1, count + 1))
        + "</Types>")

    slide_ids = "".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, count + 1))
    presentation = (
        f'{XML_DECL}<p:presentation xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f'<p:sldIdLst>{slide_ids}</p:sldIdLst>'
        f'<p:sldSz cx="{EMU_W}" cy="{EMU_H}"/>'
        f'<p:notesSz cx="{EMU_H}" cy="{EMU_W}"/></p:presentation>')

    presentation_rels = _rels(
        [("rId1", "slideMaster", "slideMasters/slideMaster1.xml")]
        + [(f"rId{i + 1}", "slide", f"slides/slide{i}.xml") for i in range(1, count + 1)])

    master = (
        f'{XML_DECL}<p:sldMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
        '<p:cSld><p:bg><p:bgPr><a:solidFill><a:schemeClr val="lt1"/></a:solidFill>'
        f'<a:effectLst/></p:bgPr></p:bg><p:spTree>{grp}</p:spTree></p:cSld>'
        '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" '
        'accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
        'accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        '</p:sldMaster>')

    layout = (
        f'{XML_DECL}<p:sldLayout xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}" type="blank">'
        f'<p:cSld name="Blank"><p:spTree>{grp}</p:spTree></p:cSld>'
        '<p:clrMapOvr><a:overrideClrMapping bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" '
        'accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" '
        'accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '</p:clrMapOvr></p:sldLayout>')

    theme = (
        f'{XML_DECL}<a:theme xmlns:a="{NS_A}" name="Theme"><a:themeElements>'
        '<a:clrScheme name="Office">'
        '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
        '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="1E2A5C"/></a:dk2><a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>'
        '<a:accent1><a:srgbClr val="1B64DA"/></a:accent1><a:accent2><a:srgbClr val="0F9D58"/></a:accent2>'
        '<a:accent3><a:srgbClr val="F59E0B"/></a:accent3><a:accent4><a:srgbClr val="E5484D"/></a:accent4>'
        '<a:accent5><a:srgbClr val="7C3AED"/></a:accent5><a:accent6><a:srgbClr val="94A3B8"/></a:accent6>'
        '<a:hlink><a:srgbClr val="1B64DA"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink>'
        '</a:clrScheme><a:fontScheme name="Office">'
        '<a:majorFont><a:latin typeface="Calibri"/><a:ea typeface="Apple SD Gothic Neo"/><a:cs typeface=""/></a:majorFont>'
        '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface="Apple SD Gothic Neo"/><a:cs typeface=""/></a:minorFont>'
        '</a:fontScheme><a:fmtScheme name="Office">'
        '<a:fillStyleLst>' + '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>' * 3 + '</a:fillStyleLst>'
        '<a:lnStyleLst>' + "".join(
            f'<a:ln w="{w}"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
            for w in (6350, 12700, 19050)) + '</a:lnStyleLst>'
        '<a:effectStyleLst>' + '<a:effectStyle><a:effectLst/></a:effectStyle>' * 3 + '</a:effectStyleLst>'
        '<a:bgFillStyleLst>' + '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>' * 3 + '</a:bgFillStyleLst>'
        '</a:fmtScheme></a:themeElements></a:theme>')

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as pkg:
        pkg.writestr("[Content_Types].xml", content_types)
        pkg.writestr("_rels/.rels", _rels([("rId1", "officeDocument", "ppt/presentation.xml")]))
        pkg.writestr("ppt/presentation.xml", presentation)
        pkg.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        pkg.writestr("ppt/theme/theme1.xml", theme)
        pkg.writestr("ppt/slideMasters/slideMaster1.xml", master)
        pkg.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _rels([
            ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
            ("rId2", "theme", "../theme/theme1.xml")]))
        pkg.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
        pkg.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _rels([
            ("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")]))
        for i, shot in enumerate(shots, start=1):
            pkg.writestr(f"ppt/slides/slide{i}.xml",
                         f'{XML_DECL}<p:sld xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
                         f'<p:cSld><p:spTree>{grp}'
                         f'<p:pic><p:nvPicPr><p:cNvPr id="2" name="Slide Image {i}"/>'
                         '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
                         '<p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
                         f'<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{EMU_W}" cy="{EMU_H}"/></a:xfrm>'
                         '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
                         + ((overlays or {}).get(i - 1) or "")
                         + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')
            pkg.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", _rels([
                ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
                ("rId2", "image", f"../media/image{i}.png")]))
            pkg.write(shot, f"ppt/media/image{i}.png")
    return dest


def main():
    parser = argparse.ArgumentParser(
        description="화면설계서 HTML 에서 PDF 와 PPTX 를 만든다")
    parser.add_argument("storyboard", help="<프로젝트명>_storyboard.html")
    parser.add_argument("--outdir", help="출력 디렉터리 (기본: 입력과 같은 곳)")
    parser.add_argument("--pdf-only", action="store_true")
    parser.add_argument("--pptx-only", action="store_true")
    parser.add_argument("--scale", type=float, default=2.0,
                        help="PPTX 캡처 배율 (기본 2.0 = 2800x1576px, A4 기준 약 240dpi)")
    parser.add_argument("--jobs", type=int,
                        help=f"동시 캡처 수 (기본: {default_jobs()})")
    parser.add_argument("--editable-desc", action="store_true",
                        help="화면 상세의 설명 패널을 PPT 텍스트 상자로 만든다 "
                             "(슬라이드당 Chrome 이 2회 돈다)")
    parser.add_argument("--chrome", help="Chrome 실행 파일 경로")
    args = parser.parse_args()

    if args.pdf_only and args.pptx_only:
        sys.exit("오류: --pdf-only 와 --pptx-only 는 함께 쓸 수 없다")

    src = Path(args.storyboard)
    if not src.is_file():
        sys.exit(f"오류: 파일이 없다 — {src}")
    outdir = Path(args.outdir) if args.outdir else src.parent
    outdir.mkdir(parents=True, exist_ok=True)

    html = src.read_text(encoding="utf-8")
    if "<body>" not in html:
        sys.exit("오류: <body> 가 없다 — 화면설계서 산출물이 맞는지 확인할 것")
    chrome = find_chrome(args.chrome)
    made = []

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if not args.pptx_only:
            made.append(export_pdf(chrome, src, outdir / f"{src.stem}.pdf", work))

        if not args.pdf_only:
            slides = split_slides(html)
            if not slides:
                sys.exit("오류: ppt-slide 를 찾을 수 없다")
            head = html[:html.index("<body>")]
            jobs = args.jobs or default_jobs()

            measured, overlays = None, None
            if args.editable_desc:
                accent = slide_accent(html)
                measured = measure_desc(chrome, head, slides, work, jobs, accent)
                overlays = {i: desc_shapes(data, accent)
                            for i, data in enumerate(measured) if data}
                print(f"설명 패널 실측: {len(overlays)}장 "
                      f"(항목 {sum(len(m['items']) for m in measured if m)}개)")

            shots = shoot_slides(chrome, head, slides, work, args.scale, jobs,
                                 blank=measured)
            made.append(build_pptx(shots, outdir / f"{src.stem}.pptx", overlays))
            print(f"슬라이드 {len(slides)}장 캡처 (배율 {args.scale}, 동시 {jobs})")

    for path in made:
        print(f"생성: {path}  ({path.stat().st_size // 1024:,}KB)")
    if len(made) == 2:
        print("PDF 는 텍스트가 벡터라 선택·검색된다. PPTX 는 슬라이드별 이미지다.")


if __name__ == "__main__":
    main()
