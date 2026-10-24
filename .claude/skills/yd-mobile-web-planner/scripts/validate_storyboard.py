#!/usr/bin/env python3
"""생성된 화면설계서 HTML 이 SKILL.md 의 계약을 지켰는지 판정한다.

`SKILL.md` 의 "저장 전 자체 점검" 항목과 그 외 기계적으로 판정 가능한
계약을 그대로 잰다. 위반으로 판정하는 것과, 참고로 보고만 하는 것을 구분한다
— 화면 순서와 목업 개수는 요청 맥락을 알아야 옳고 그름이 정해지므로
수치만 보고하고 판정은 사람이 한다. 런타임(Claude Code / Codex / Antigravity)이 만든
산출물을 같은 잣대로 비교하기 위한 도구다.

화면 ID 가 정의된 산출물은 짝을 이루는 Business Rules 문서
(`<이름>_business-rules.md`)도 함께 판정한다 — 화면 ID 커버리지, 필수
헤딩(입력 검증 / 출력 규칙 / 인터랙션 / 엣지케이스), 끊어진 ID 참조.

stdlib 만 사용한다 (이 환경의 Homebrew Python 3.14 는 외부 라이브러리
import 가 깨져 있다).

사용법:
    python3 scripts/validate_storyboard.py <산출물.html> [<산출물2.html> ...]

종료 코드: 위반이 하나도 없으면 0, 있으면 1.
"""
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "resources" / "template.html"
WHITELIST = frozenset({"mermaid"})

#: 검증기 규칙 세트 버전. 산출물에는 scaffold 가
#: `<meta name="skill-ruleset" content="N">` 으로 새긴다 (이슈 #77).
#: 규칙을 추가할 때는 AGENTS.md 의 "새 검증 규칙 추가 체크리스트" 를 따른다.
RULESET_VERSION = 3

#: 규칙 세트 v2 에서 도입된 위반 메시지의 식별 부분 문자열.
#: v1 문서(메타 없음 포함)에는 기본 모드에서 "신규 규칙 참고" 로만 보고한다.
V2_RULE_MARKERS = (
    "인터랙션 표에 배지 번호 인용",
    "원문자 사용",
    "이벤트 표기(탭:/스와이프:/롱프레스:/입력:)",
    "유형(화면/팝업/바텀시트) 표기 없는 행",
    "유형이 '화면' 인데",
    "05 Screen List",
    "06 Service Flow",
    "07.x Sequence Diagram",
    "mermaid sequenceDiagram",
    "시퀀스에 화면 ID",
    "시퀀스가 사실상 동일",
    "목업 본문이 자리표시자",
    "재탕",
    "데이터 신호",
    "Cover 버전",
    "Document History 최신 행",
)

#: 규칙 세트 v3에서 도입된 규칙 단위 추적성 계약. 구문서는 기본 모드에서
#: 참고로만 보고하고 --strict에서만 위반으로 처리한다.
V3_RULE_MARKERS = (
    "규칙 ID 누락",
    "규칙 ID 형식 오류",
    "중복 규칙 ID",
    "규칙 ID 화면 불일치",
    "규칙 ID 구분 불일치",
)


def doc_ruleset(html):
    """문서에 새겨진 규칙 세트 버전. 메타가 없으면 1 (메타 도입 전 문서)."""
    m = re.search(r'<meta\s+name="skill-ruleset"\s+content="(\d+)"', html)
    return int(m.group(1)) if m else 1


def rule_introduced_in(violation):
    """위반이 처음 도입된 규칙 세트 버전."""
    if any(marker in violation for marker in V3_RULE_MARKERS):
        return 3
    if any(marker in violation for marker in V2_RULE_MARKERS):
        return 2
    return 1



def extract_style(html):
    """첫 번째 style 블록의 CSS를 반환한다."""
    match = re.search(r"<style[^>]*>(.*?)</style>", html, re.S | re.I)
    if not match:
        raise ValueError("template.html 에 <style> 블록이 없다")
    return match.group(1)


def defined_classes(css):
    """CSS selector에 정의된 클래스 이름을 반환한다."""
    selectors = re.sub(r"\{[^{}]*\}", " ", css)
    selectors = re.sub(r"@[\w-]+[^;{}]*;", " ", selectors)
    return set(re.findall(r"\.(-?[A-Za-z_][A-Za-z0-9_-]*)", selectors))


def used_classes(html):
    """HTML class 속성에서 사용한 클래스 이름을 반환한다."""
    names = set()
    for raw in re.findall(r'class\s*=\s*"([^"]*)"', html, re.I):
        names.update(raw.split())
    return names


def undefined_classes(html, css):
    """CSS에 정의되지 않은 HTML 클래스 이름을 정렬해 반환한다."""
    return sorted(used_classes(html) - defined_classes(css) - WHITELIST)

#: 이모지 코드포인트 구간. 타이포그래피 문자(‹ ⋮ 등)는 포함하지 않는다.
EMOJI_RANGES = ((0x1F000, 0x1F2FF), (0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF))


def markup_only(html):
    """<style> 블록과 HTML 주석을 걷어낸 마크업만 반환한다.

    템플릿 CSS 주석에는 `<div class="mock mock-partial">` 같은 사용 예시가
    들어 있다. 마크업 판정을 원문 전체에 대고 돌리면 그 예시를 실제 목업으로
    세어 오탐이 난다.

    HTML 주석도 같은 이유로 걷어낸다. 슬라이드를 `<!-- ==== NO. 09.1 홈 ==== -->`
    처럼 구분하는 것은 흔한 관례인데, 그 문자열이 슬라이드 구간 경계로 잡히면
    한 슬라이드가 둘로 쪼개진다. 쪼개진 자리에서 배지와 desc-num 이 서로 다른
    구간으로 갈리면 불일치를 놓친다(미탐).
    """
    stripped = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    return re.sub(r"<style\b[^>]*>.*?</style>", "", stripped, flags=re.S | re.I)


def emoji_in(text):
    """텍스트에 등장하는 이모지를 원문 순서대로 반환한다."""
    return [c for c in text if any(lo <= ord(c) <= hi for lo, hi in EMOJI_RANGES)]


def slide_numbers(html):
    """상단 바의 NO. 값을 등장 순서대로 반환한다."""
    return re.findall(r'class="ppt-top-no">NO\.\s*([\d.]+)<', html)


def badge_lefts(html):
    """pointer-badge 의 인라인 left 값(px)을 반환한다."""
    lefts = []
    for style in re.findall(r'class="pointer-badge"[^>]*style="([^"]*)"', html):
        m = re.search(r"left:\s*(-?\d+)px", style)
        if m:
            lefts.append(int(m.group(1)))
    return lefts


def slide_sections(html, pattern=r"[\d.]+"):
    """상단 바 앵커로 자른 (번호, 본문) 목록. 번호가 pattern 에 완전일치하는 것만.

    구간은 `ppt-top-no` 앵커로만 잡고 **바로 다음 슬라이드**에서 끊는다. 두 가지를
    동시에 막는다.

    1. 본문 텍스트나 목차 표에 등장하는 "NO. 09.1" 같은 문자열은 슬라이드가 아니다.
    2. 09.x 뒤에 다른 번호의 슬라이드가 오더라도 그 내용이 마지막 화면 상세에
       합산되지 않는다 — 09.x 가 문서 마지막이어야 한다는 암묵 전제를 없앤다.
    """
    heads = list(re.finditer(r'class="ppt-top-no">NO\.\s*([\d.]+)<', html))
    out = []
    for i, m in enumerate(heads):
        if not re.fullmatch(pattern, m.group(1)):
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(html)
        out.append((m.group(1), html[m.end():end]))
    return out


def detail_slides(html):
    """09.x 화면 상세 슬라이드의 (번호, 본문) 목록."""
    return slide_sections(html, r"09\.\d+")


def badge_desc_mismatch(html):
    """슬라이드별 pointer-badge 수와 desc-num 수가 다른 슬라이드를 반환한다."""
    bad = []
    for no, body in detail_slides(html):
        b = body.count('class="pointer-badge"')
        d = body.count('class="desc-num"')
        if b != d:
            bad.append((no, b, d))
    return bad


def screen_order(html):
    """09.x 슬라이드의 (번호, 제목) 을 등장 순서대로 반환한다."""
    return re.findall(
        r'ppt-top-no">NO\.\s*(09\.\d+)</div>\s*<div class="ppt-top-title">([^<]+)', html)


def mock_counts(html):
    """09.x 슬라이드별 mock 개수를 반환한다."""
    return [(no, body.count('class="mock"')) for no, body in detail_slides(html)]



ID_RE = r"\b[A-Z]{2,6}-[A-Z]{2,12}-\d{3}\b"


def screen_ids(html):
    """정의된 화면 ID 집합을 반환한다.

    정의 자리는 두 곳이다 — 슬라이드 대표 화면의 `ppt-meta-id`, 그리고 목업이
    2개 이상인 슬라이드에서 각 목업의 `mock-caption`. 캡션까지 정의로 세는
    이유는 `ppt-meta-id` 가 슬라이드당 한 칸뿐이어서 두 번째 목업의 화면 ID 를
    담을 자리가 없기 때문이다.
    """
    ids = set()
    for raw in re.findall(r'class="ppt-meta-id">([^<]+)<', html):
        ids.update(re.findall(ID_RE, raw))
    for raw in re.findall(r'class="mock-caption">([^<]*)<', html):
        ids.update(re.findall(ID_RE, raw))
    return ids


def referenced_ids(html):
    """본문에서 언급된 화면 ID 후보를 반환한다.

    형식은 <서비스약어>-<기능>-<3자리> 다. 정의 자리(ppt-meta-id 와
    mock-caption)는 제외하고, 설명 문장에서 참조된 것만 센다.
    """
    stripped = re.sub(r'class="ppt-meta-id">[^<]+<', 'class="ppt-meta-id"><', html)
    stripped = re.sub(r'class="mock-caption">[^<]*<', 'class="mock-caption"><', stripped)
    return set(re.findall(ID_RE, stripped))



def caption_mismatch(html):
    """09.x 슬라이드별 목업 수와 mock-caption 수가 다른 슬라이드를 반환한다.

    캡션은 모든 목업에 필수다 — 단일 목업 슬라이드만 캡션이 없으면 문서
    전체에서 표현이 어긋난다. 목업 프레임은 `class="mock"` 과
    `class="mock mock-partial"` 두 형태라 접두 매칭으로 센다
    (`mock-caption` 등 하이픈 파생 클래스는 매칭되지 않는다).
    """
    bad = []
    for no, body in detail_slides(html):
        mocks = len(re.findall(r'class="mock[\s"]', body))
        caps = body.count('class="mock-caption"')
        if mocks != caps:
            bad.append((no, mocks, caps))
    return bad


def sequence_slides(html):
    """07.x 시퀀스 슬라이드의 (번호, 본문) 목록을 반환한다."""
    return slide_sections(html, r"07\.\d+")


def check_sequence_slides(markup):
    """07.x Sequence Diagram 계약을 판정한다.

    필요한 트랜잭션이 전부 그려졌는지는 기계로 잴 수 없다(자체 점검 소관).
    기계 판정은 하한선과 형식이다 — 최소 1장 존재, 각 장에 mermaid
    `sequenceDiagram` 과 관련 화면 ID. ID 정합은 기존 끊어진 참조 판정이
    함께 잡는다.
    """
    violations = []
    seqs = sequence_slides(markup)
    if not seqs:
        violations.append(
            "07.x Sequence Diagram 슬라이드 없음 — 상태 변경 트랜잭션당 1장을 그릴 것")
    for no, body in seqs:
        if 'class="mermaid"' not in body or "sequenceDiagram" not in body:
            violations.append(f"{no} 에 mermaid sequenceDiagram 이 없다")
        elif not re.findall(ID_RE, body):
            violations.append(
                f"{no} 시퀀스에 화면 ID 가 없다 — participant 라벨이나 note 에 적을 것")
    return violations


SCREEN_TYPES = ("바텀시트", "팝업", "화면")


def detail_defined_ids(html):
    """09.x 슬라이드 안에서 정의된 화면 ID 집합 (ppt-meta-id · mock-caption)."""
    ids = set()
    for _no, body in detail_slides(html):
        for raw in re.findall(r'class="ppt-meta-id">([^<]+)<', body):
            ids.update(re.findall(ID_RE, raw))
        for raw in re.findall(r'class="mock-caption">([^<]*)<', body):
            ids.update(re.findall(ID_RE, raw))
    return ids


def row_cells(row):
    """표 행의 셀 텍스트 목록. 태그를 걷어내고 공백을 정리한다."""
    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip() for c in cells]


def row_screen_type(row):
    """행의 유형(화면/팝업/바텀시트)을 반환한다. 판정 불가면 None.

    우선 **유형만 담은 셀**을 찾는다 — 셀 값이 유형 단어와 정확히 같아야 한다.
    그런 셀이 없으면 행 텍스트 매칭으로 되돌아가되, `화면` 은 다른 두 유형의
    설명 문구에도 흔히 섞이므로 마지막에 본다.
    """
    for cell in row_cells(row):
        if cell in SCREEN_TYPES:
            return cell
    return next((k for k in SCREEN_TYPES if k in row), None)


def check_screen_list_types(markup):
    """05 Screen List 의 유형 표기·정합을 판정한다.

    모든 행에 유형(화면/팝업/바텀시트)이 있어야 하고, 유형이 `화면` 인 ID 는
    09.x 슬라이드에 정의돼 있어야 한다 — 목록에만 있고 그려지지 않은 화면은
    구현 단계에서 범위를 즉석 결정하게 만든다(실구현 회고, 이슈 #41).
    유형은 **유형 열의 셀 값**으로 판정한다. 행 전체를 키워드 매칭하면
    "주요 내용" 칸의 설명 문구("화면 일부를 덮는 팝업" 등)에 걸려 오판한다.
    열 순서를 SKILL.md 와 다르게 쓴 문서를 위해, 유형만 담은 셀을 못 찾으면
    행 텍스트 매칭으로 되돌아간다 — 그때는 `바텀시트`·`팝업` 을 먼저 본다.
    """
    body = slide_body(markup, "05")
    if body is None:
        return []  # 슬라이드 존재 위반은 check_overview_slides 가 잰다
    violations = []
    detail_ids = detail_defined_ids(markup)
    untyped, undrawn = [], []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        ids = re.findall(ID_RE, row)
        if not ids:
            continue  # 헤더 행
        kind = row_screen_type(row)
        if kind is None:
            untyped += ids
        elif kind == "화면":
            undrawn += [i for i in ids if i not in detail_ids]
    if untyped:
        violations.append(
            f"05 Screen List 에 유형(화면/팝업/바텀시트) 표기 없는 행: {', '.join(untyped)}")
    if undrawn:
        violations.append(
            f"05 Screen List 유형이 '화면' 인데 09.x 에 정의되지 않은 ID: {', '.join(sorted(set(undrawn)))}")
    return violations


EVENT_LABELS = ("탭:", "스와이프:", "롱프레스:", "입력:")


def event_coverage(html):
    """09.x 슬라이드별 (번호, 이벤트 표기 항목 수, 전체 설명 항목 수).

    설명 항목(<li>)에 고정 이벤트 라벨(탭:/스와이프:/롱프레스:/입력:)이
    있는지 센다. 터치 요소가 있는 화면 상세에 이벤트 표기가 하나도 없으면
    동작 정의가 통째로 빠진 것이다 (이슈 #43).
    """
    out = []
    for no, body in detail_slides(html):
        items = re.findall(r"<li\b.*?</li>", body, re.S)
        ev = sum(1 for it in items if any(lb in it for lb in EVENT_LABELS))
        out.append((no, ev, len(items)))
    return out


def slide_body(html, number):
    """지정한 NO. 슬라이드의 본문을 반환한다. 없으면 None.

    `05` 처럼 점 없는 번호를 찾을 때 `05.1` 같은 하위 번호와 헷갈리지
    않도록 번호 전체를 정확히 비교한다.
    """
    heads = list(re.finditer(r'class="ppt-top-no">NO\.\s*([\d.]+)<', html))
    for i, m in enumerate(heads):
        if m.group(1) == number:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(html)
            return html[m.end():end]
    return None


def check_overview_slides(markup, defined):
    """05 Screen List · 06 Service Flow 슬라이드 계약을 판정한다.

    Screen List 는 정의된 모든 화면 ID(팝업·바텀시트 포함)를 한 행씩 담는
    ID↔화면 매핑 기준표이고, Service Flow 는 정상 케이스 전체 흐름을 담는
    mermaid flowchart 다. 표·흐름도가 참조하는 ID 가 정의 집합 밖이면
    기존의 끊어진 참조 판정이 함께 잡는다.
    """
    violations = []
    screen_list = slide_body(markup, "05")
    if screen_list is None:
        violations.append(
            "05 Screen List 슬라이드 없음 — 화면 ID↔화면 매핑표를 추가할 것")
    else:
        missing = sorted(defined - set(re.findall(ID_RE, screen_list)))
        if missing:
            violations.append(
                f"05 Screen List 에 없는 화면 ID: {', '.join(missing)}")

    flow = slide_body(markup, "06")
    if flow is None:
        violations.append(
            "06 Service Flow 슬라이드 없음 — 정상 케이스 전체 흐름도를 추가할 것")
    elif 'class="mermaid"' not in flow:
        violations.append("06 Service Flow 에 mermaid 흐름도가 없다")
    elif not re.findall(ID_RE, flow):
        violations.append(
            "06 Service Flow 흐름도에 화면 ID 가 없다 — 노드 라벨에 화면명과 ID 를 함께 적을 것")
    return violations


PLACEHOLDER_RE = re.compile(
    r"Mockup Content|Lorem\b|\bTODO\b|여기에 내용|내용 삽입|콘텐츠 영역", re.I)

#: 목업 본문의 도메인 데이터 신호 — 숫자 리터럴(금액·수량·날짜·시각·비율).
NUM_SIGNAL_RE = re.compile(r"\d[\d,.:%~]*")

#: 이 비율을 넘는 화면 상세가 신호 없는 목업이면 문서 전체 위반이다.
#: 온보딩·약관처럼 숫자가 적은 화면이 한둘 있는 것은 정상이다 — runtime-parity
#: 실측에서 claude 4% / codex 19% / agy 100% 로 갈렸다 (이슈 #75).
LOW_DENSITY_DOC_RATIO = 0.3
LOW_DENSITY_FLOOR = 2

#: 설명 항목 제목이 목업 본문에 이 비율 이상 그대로 나타나면 재탕이다.
#: 버튼 라벨과 항목 제목이 겹치는 정상 케이스(60% 안팎)를 통과시키기 위해 80%.
ECHO_RATIO = 0.8
ECHO_MIN_TITLES = 4

#: 07.x 시퀀스 슬라이드 간 토큰 유사도 상한 — 이 이상이면 보일러플레이트 복제다.
#: runtime-parity 실측: 정상 문서 최대 0.44, 보일러플레이트 문서 0.73~0.83.
SEQ_SIMILARITY_LIMIT = 0.7


def mock_body_text(slide_body):
    """09.x 슬라이드 본문에서 mock-body 들의 텍스트만 모아 반환한다.

    여는 태그 끝(>) 뒤부터 mock-caption/mock-footer/desc-panel 전까지를 취하고,
    pointer-badge 라벨은 목업 콘텐츠가 아니므로 제거한다. 인라인 style 값은
    태그 안에 있으므로 태그 제거로 함께 사라진다.
    """
    import html as _html
    bodies = []
    for bm in re.finditer(r'class="mock-body"', slide_body):
        tag_end = slide_body.find(">", bm.end())
        if tag_end == -1:
            continue
        rest = slide_body[tag_end + 1:]
        cut = len(rest)
        for stop in ('class="mock-caption"', 'class="mock-footer', 'class="ppt-desc-panel"'):
            p = rest.find(stop)
            if p != -1:
                cut = min(cut, p)
        blk = re.sub(r'<span class="pointer-badge".*?</span>', " ", rest[:cut], flags=re.S)
        bodies.append(_html.unescape(re.sub(r"<[^>]*>?", " ", blk)))
    return re.sub(r"\s+", " ", " ".join(bodies)).strip()


def desc_titles(slide_body):
    """설명 리스트 항목의 굵은 제목 목록."""
    import html as _html
    return [_html.unescape(x).strip() for x in re.findall(
        r'<li><span class="desc-num">[^<]*</span>\s*<div><b>([^<]+)</b>', slide_body)]


def check_mock_content(markup):
    """목업 본문의 실질을 판정한다 (이슈 #75) — (위반, 정보) 반환.

    구조 계약만 재던 시절에는 "validator 0건" 이 최소 비용 경로(자리표시자·
    설명 재탕·빈 목업)로 수렴했다. 산문 지시 중 기계로 셀 수 있는 것을
    위반으로 승격한다. 임계값은 tests/fixtures/runtime-parity 의 세 런타임
    실측 산출물로 캘리브레이션했다 — claude 0건 유지, codex·agy 는 잡힌다.
    """
    violations, info = [], []
    placeholder_slides, echo_slides, retype_slides, low_density = [], [], [], []
    total = 0
    for no, body in detail_slides(markup):
        if 'class="mock-body"' not in body:
            continue  # 목업 없는 슬라이드는 본문 실질을 판정할 수 없다
        total += 1
        text = mock_body_text(body)
        if PLACEHOLDER_RE.search(text):
            placeholder_slides.append(no)
        if text.count("탭 ›") + text.count("탭›") >= 2:
            retype_slides.append(no)
        titles = [x for x in desc_titles(body) if len(re.sub(r"\s+", "", x)) >= 3]
        if len(titles) >= ECHO_MIN_TITLES:
            tn = re.sub(r"\s+", "", text)
            echoed = sum(1 for x in titles if re.sub(r"\s+", "", x) in tn)
            if echoed >= len(titles) * ECHO_RATIO:
                echo_slides.append(f"{no}({echoed}/{len(titles)})")
        if len(NUM_SIGNAL_RE.findall(text)) < LOW_DENSITY_FLOOR:
            low_density.append(no)

    if placeholder_slides:
        violations.append(
            "목업 본문이 자리표시자다 (Mockup Content/TODO/Lorem 류): "
            + ", ".join(placeholder_slides[:8])
            + (f" 외 {len(placeholder_slides) - 8}장" if len(placeholder_slides) > 8 else ""))
    if retype_slides:
        violations.append(
            "목업 안에 설명 패널의 이벤트 표기('탭 ›')를 재탕한 슬라이드: "
            + ", ".join(retype_slides[:8])
            + (f" 외 {len(retype_slides) - 8}장" if len(retype_slides) > 8 else ""))
    if echo_slides:
        violations.append(
            "설명 항목 제목 대부분이 목업 본문에 그대로 복사된 슬라이드"
            f" (재탕 의심, {int(ECHO_RATIO * 100)}%+): " + ", ".join(echo_slides[:8]))
    if total and len(low_density) / total > LOW_DENSITY_DOC_RATIO:
        violations.append(
            f"도메인 데이터 신호(숫자 리터럴 {LOW_DENSITY_FLOOR}개 미만) 없는 목업이 "
            f"{len(low_density)}/{total}장 — 더미데이터를 Figma 시안급으로 채울 것: "
            + ", ".join(low_density[:8])
            + (f" 외 {len(low_density) - 8}장" if len(low_density) > 8 else ""))
    info.append(f"목업 데이터 신호 부족 {len(low_density)}/{total}장"
                + (f" ({', '.join(low_density[:5])})" if low_density else ""))
    return violations, info


def check_sequence_boilerplate(markup):
    """07.x 시퀀스 간 토큰 유사도가 임계를 넘는 쌍을 위반으로 보고한다."""
    import html as _html
    from itertools import combinations
    seqs = []
    for no, body in sequence_slides(markup):
        mm = re.search(r'class="mermaid">\s*(.*?)\s*</div>', body, re.S)
        if not mm:
            continue
        toks = set(re.findall(r"[가-힣A-Za-z]{2,}", _html.unescape(mm.group(1))))
        if toks:
            seqs.append((no, toks))
    violations = []
    for (a, ta), (b, tb) in combinations(seqs, 2):
        j = len(ta & tb) / max(1, len(ta | tb))
        if j >= SEQ_SIMILARITY_LIMIT:
            violations.append(
                f"{a} 와 {b} 의 시퀀스가 사실상 동일하다 (유사도 {j:.2f}) — "
                "트랜잭션별로 participant·메시지가 달라야 한다")
    return violations


def ia_subgraph_info(markup):
    """04 IA 의 노드 수와 subgraph 사용 여부를 참고로 보고한다.

    노드 13개 이상 + subgraph 미사용은 세로 1열 붕괴 위험 신호지만, 렌더
    없이는 붕괴를 단정할 수 없어 위반이 아니라 정보로만 낸다 (이슈 #75).
    """
    body = slide_body(markup, "04")
    if body is None:
        return None
    mm = re.search(r'class="mermaid">\s*(.*?)\s*</div>', body, re.S)
    if not mm:
        return None
    nodes = len(re.findall(r"\w+\[", mm.group(1)))
    has_sub = "subgraph" in mm.group(1)
    note = "" if has_sub or nodes < 13 else " — 세로 붕괴 위험, subgraph 권장"
    return f"04 IA 노드 {nodes}개 / subgraph {'사용' if has_sub else '미사용'}{note}"


VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+)\b")


def history_rows(hist_body):
    """02 Document History 표에서 버전이 있는 데이터 행을 (버전, 행 텍스트) 로 반환."""
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", hist_body, re.S):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)).strip()
        m = VERSION_RE.search(text)
        if m:
            rows.append((m.group(1), text))
    return rows


def check_version_history(markup):
    """Cover 버전과 Document History 최신 행의 정합을 판정한다 (이슈 #74).

    콜드 재생성에서 이력 행을 치환해 버전과 "최초 작성" 설명이 어긋나는
    사고를 막는다. Cover(01)·History(02) 슬라이드나 버전 표기가 없으면
    측정 불가로 보고 판정하지 않는다 — 슬라이드 존재는 별개 계약이다.
    """
    cover = slide_body(markup, "01")
    hist = slide_body(markup, "02")
    if cover is None or hist is None:
        return []
    cover_vers = VERSION_RE.findall(cover)
    rows = history_rows(hist)
    if not cover_vers or not rows:
        return []
    violations = []
    cover_ver, latest_ver = cover_vers[0], rows[-1][0]
    if cover_ver != latest_ver:
        violations.append(
            f"Cover 버전({cover_ver})과 Document History 최신 행({latest_ver})이 다르다"
            " — 재생성/수정 시 이력 행을 추가하고 Cover 버전을 함께 올릴 것")
    if len(rows) > 1 and "최초 작성" in rows[-1][1]:
        violations.append(
            "Document History 최신 행이 '최초 작성' 이다 — 재생성/수정 행에는"
            " 사유와 변경 요약을 적을 것 (최초 작성은 첫 행 전용)")
    return violations


def meta_locations(html):
    """09.x 슬라이드의 (번호, Location) 을 반환한다."""
    out = []
    for no, body in detail_slides(html):
        loc = re.search(r'class="ppt-meta-value">([^<]*)<', body)
        out.append((no, loc.group(1).strip() if loc else ""))
    return out


def badge_labels(html):
    """pointer-badge 라벨을 반환한다."""
    return re.findall(r'class="pointer-badge"[^>]*>([^<]+)<', html)


STORYBOARD_SUFFIX = "_storyboard.html"
RULES_SUFFIX = "_business-rules.md"
RULES_REQUIRED_HEADINGS = ("입력 검증", "출력 규칙", "인터랙션", "엣지케이스")


def rules_path_for(html_path):
    """산출물 HTML 과 짝을 이루는 Business Rules 문서 경로를 만든다.

    `<이름>_storyboard.html` → `<이름>_business-rules.md`. 접미사가 계약과
    다른 파일은 `<이름>.html` → `<이름>_business-rules.md` 로 유도한다.
    """
    p = Path(html_path)
    name = p.name
    if name.endswith(STORYBOARD_SUFFIX):
        stem = name[: -len(STORYBOARD_SUFFIX)]
    else:
        stem = p.stem
    return p.with_name(stem + RULES_SUFFIX)


def rules_sections(md):
    """`## <화면 ID> <이름>` 섹션을 (ID, 본문) 목록으로 반환한다.

    같은 ID 의 섹션이 여러 번 나오면 나온 만큼 목록에 들어간다 — 중복
    판정은 호출부가 한다.
    """
    heads = list(re.finditer(r"(?m)^##\s+(%s)[^\n]*$" % ID_RE, md))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(md)
        out.append((m.group(1), md[m.end():end]))
    return out


def rules_subsection_bodies(body):
    """섹션 본문을 `### 헤딩` 별로 나눠 {헤딩: 내용} 으로 반환한다."""
    heads = list(re.finditer(r"(?m)^###\s+([^\n]+)$", body))
    out = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        out[m.group(1).strip()] = body[m.end():end].strip()
    return out


#: 인터랙션 표 트리거 칸의 배지 인용. 목업 1개면 (1), 2개 이상이면 (1-2).
BADGE_CITE_RE = re.compile(r"\(\s*\d+(?:-\d+)?\s*\)")
RULE_ID_RE = re.compile(
    rf"\b({ID_RE}\.(IN|OUT|INT|EDGE)-\d{{2}})\b")
RULE_KIND = {
    "입력 검증": "IN",
    "출력 규칙": "OUT",
    "인터랙션": "INT",
    "엣지케이스": "EDGE",
}


def interaction_rows_without_badge(section_body):
    """`### 인터랙션` 표에서 트리거 칸에 배지 번호 인용이 없는 행의 트리거 텍스트.

    인용이 없으면 그 규칙이 화면의 어느 요소를 말하는지 추적할 수 없다 —
    storyboard 의 배지와 Business Rules 를 잇는 유일한 끈이다.
    표가 없거나 "해당 없음" 으로 적힌 섹션은 검사 대상이 아니다.
    """
    subs = rules_subsection_bodies(section_body)
    body = subs.get("인터랙션", "")
    if not body or body.lstrip().startswith("해당 없음"):
        return []

    bad = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        trigger = cells[0]
        # 헤더 행과 구분선 행은 건너뛴다.
        if trigger in ("트리거", "") or set(trigger) <= {"-", ":"}:
            continue
        if not BADGE_CITE_RE.search(trigger):
            bad.append(trigger)
    return bad


def rule_id_violations(sections):
    """Business Rules의 데이터 행·목록 항목에 안정적인 규칙 ID가 있는지 판정."""
    violations = []
    seen = []
    for sid, body in sections:
        for heading, kind in RULE_KIND.items():
            sub = rules_subsection_bodies(body).get(heading, "")
            if not sub or sub.lstrip().startswith("해당 없음"):
                continue
            table_row = 0
            for line in sub.splitlines():
                stripped = line.strip()
                candidate = None
                if stripped.startswith("|"):
                    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
                    if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
                        continue
                    table_row += 1
                    if table_row == 1:  # 표 헤더
                        continue
                    candidate = stripped
                elif re.match(r"^[-*+]\s+", stripped):
                    candidate = stripped
                if candidate is None:
                    continue

                matches = list(RULE_ID_RE.finditer(candidate))
                if not matches:
                    violations.append(
                        f"{sid} {heading} 규칙 ID 누락: {candidate[:80]}")
                    continue
                for match in matches:
                    rule_id, actual_kind = match.groups()
                    rule_sid = rule_id.split(".", 1)[0]
                    seen.append(rule_id)
                    if rule_sid != sid:
                        violations.append(
                            f"{sid} 규칙 ID 화면 불일치: {rule_id}")
                    if actual_kind != kind:
                        violations.append(
                            f"{sid} {heading} 규칙 ID 구분 불일치: {rule_id}")

    duplicates = sorted({rule_id for rule_id in seen if seen.count(rule_id) > 1})
    if duplicates:
        violations.append(f"Business Rules 중복 규칙 ID: {', '.join(duplicates)}")
    return violations


def check_rules(md, storyboard_ids, enforce_rule_ids=False):
    """Business Rules 문서를 판정해 (위반 목록, 정보 목록) 을 반환한다.

    storyboard_ids 는 storyboard 에 정의된 화면 ID 집합이다. SKILL.md 의
    계약 — 모든 화면 ID 가 정확히 하나의 `##` 섹션을 갖고, 각 섹션에 네
    필수 헤딩이 내용과 함께 있으며, 본문 참조 ID 가 전부 storyboard 에
    정의돼 있다 — 를 그대로 잰다.
    """
    violations, info = [], []
    sections = rules_sections(md)
    section_ids = [sid for sid, _ in sections]
    id_set = set(section_ids)

    dup = sorted({sid for sid in id_set if section_ids.count(sid) > 1})
    if dup:
        violations.append(f"Business Rules 에 중복 섹션: {', '.join(dup)}")

    missing = sorted(storyboard_ids - id_set)
    if missing:
        violations.append(
            f"Business Rules 에 섹션이 없는 화면 ID: {', '.join(missing)}")

    extra = sorted(id_set - storyboard_ids)
    if extra:
        violations.append(
            f"storyboard 에 정의되지 않은 화면 ID 섹션: {', '.join(extra)}")

    for sid, body in sections:
        subs = rules_subsection_bodies(body)
        absent = [h for h in RULES_REQUIRED_HEADINGS if h not in subs]
        if absent:
            violations.append(f"{sid} 섹션에 필수 헤딩 누락: {', '.join(absent)}")
        empty = [h for h in RULES_REQUIRED_HEADINGS
                 if h in subs and not subs[h]]
        if empty:
            violations.append(
                f"{sid} 섹션의 내용 없는 헤딩: {', '.join(empty)}"
                " — 해당 없으면 '해당 없음 — <이유>' 를 적을 것")

    for sid, body in sections:
        missing_cite = interaction_rows_without_badge(body)
        if missing_cite:
            shown = ", ".join(f'"{t}"' for t in missing_cite[:3])
            more = f" 외 {len(missing_cite) - 3}건" if len(missing_cite) > 3 else ""
            violations.append(
                f"{sid} 인터랙션 표에 배지 번호 인용이 없는 행: {shown}{more}"
                " — 트리거 칸에 (1) 또는 (1-2) 처럼 적을 것")

    if enforce_rule_ids:
        violations.extend(rule_id_violations(sections))

    body_only = re.sub(r"(?m)^##\s+[^\n]*$", "", md)
    dangling = sorted(set(re.findall(ID_RE, body_only)) - storyboard_ids)
    if dangling:
        violations.append(
            f"Business Rules 가 정의되지 않은 화면 ID 를 참조한다: "
            f"{', '.join(dangling)}")

    matrix = "있음" if re.search(r"(?m)^##\s+권한 매트릭스", md) else "없음"
    info.append(f"권한 매트릭스: {matrix} (역할 2개 이상이면 필수 — 판정은 자체 점검 소관)")
    info.append(f"Business Rules 섹션 {len(sections)}개 / {len(md):,} bytes")
    return violations, info


def check(path, css, strict=False):
    """한 산출물을 판정해 (위반 목록, 정보 목록) 을 반환한다.

    문서의 규칙 세트(doc_ruleset)가 현재보다 낮으면, 그 이후 도입된 규칙의
    위반은 기본 모드에서 위반이 아니라 "신규 규칙 참고" 로 info 에 실린다 —
    작성 당시 존재하지 않던 규칙으로 옛 문서를 뒤집지 않기 위해서다 (이슈 #77).
    strict=True 면 전수 위반 처리한다.
    """
    html = Path(path).read_text(encoding="utf-8")
    markup = markup_only(html)
    violations, info = [], []

    undefined = undefined_classes(html, css)
    if undefined:
        violations.append(f"미정의 클래스 {len(undefined)}종: {', '.join(undefined)}")

    emoji = emoji_in(markup)
    if emoji:
        kinds = sorted(set(emoji))
        violations.append(f"이모지 {len(emoji)}개 / {len(kinds)}종: {''.join(kinds)}")

    lefts = badge_lefts(markup)
    off = sorted({v for v in lefts if v != 2})
    if off:
        violations.append(f"배지 left 가 2px 아닌 값 {off} (전체 {len(lefts)}개 중)")

    mism = badge_desc_mismatch(markup)
    if mism:
        detail = ", ".join(f"{no}({b}/{d})" for no, b, d in mism)
        violations.append(f"배지-desc_num 불일치: {detail}")

    cap = caption_mismatch(markup)
    if cap:
        detail = ", ".join(f"{no}(목업{m}/캡션{c})" for no, m, c in cap)
        violations.append(
            f"목업-캡션 불일치 — 모든 목업에 mock-caption 필수: {detail}")

    circled = re.findall(
        r'class="desc-num"[^>]*>([^<]*[\u2460-\u2473][^<]*)<', markup)
    if circled:
        violations.append(
            f"desc-num 원문자 사용 {len(circled)}건 — 배지와 같은 평문 표기(1, 1-1)로 바꿀 것")

    if "mermaid.min.js" not in html:
        violations.append("mermaid 런타임 누락 — IA 다이어그램이 원문 텍스트로 남는다")

    if "{{" in html:
        violations.append(f"치환 안 된 플레이스홀더 {html.count('{{')}건")

    defined = screen_ids(markup)
    dangling = sorted(referenced_ids(markup) - defined)
    if defined and dangling:
        violations.append(
            f"정의되지 않은 화면 ID 를 참조한다: {', '.join(dangling)}"
        )
    if defined:
        violations += check_version_history(markup)
        violations += check_overview_slides(markup, defined)
        violations += check_sequence_slides(markup)
        violations += check_sequence_boilerplate(markup)
        violations += check_screen_list_types(markup)
        mc_viol, mc_info = check_mock_content(markup)
        violations += mc_viol
        info += mc_info
        ia_note = ia_subgraph_info(markup)
        if ia_note:
            info.append(ia_note)
        cov = event_coverage(markup)
        no_event = [no for no, ev, total in cov if total and not ev]
        if no_event:
            violations.append(
                "이벤트 표기(탭:/스와이프:/롱프레스:/입력:) 없는 화면 상세: "
                + ", ".join(no_event))
        if cov:
            info.append(
                f"이벤트 표기 항목 {sum(e for _, e, _ in cov)}"
                f"/{sum(t for _, _, t in cov)}개")

    nums = slide_numbers(markup)
    info.append(f"슬라이드 {len(nums)}장: {' '.join(nums)}")
    info.append(f"크기 {len(html):,} bytes / 배지 {len(lefts)}개")
    accent = re.search(r"--accent:\s*([^;]+);", html)
    info.append(f"accent {accent.group(1).strip() if accent else '변수 없음'}")

    order = screen_order(markup)
    info.append("화면 순서: " + " / ".join(f"{n} {t.strip()}" for n, t in order))
    if defined:
        info.append(f"화면 ID {len(defined)}개: {' '.join(sorted(defined))}")
    mocks = mock_counts(markup)
    multi = [f"{n}({c})" for n, c in mocks if c >= 2]
    info.append(f"목업 2개 이상 슬라이드 {len(multi)}개" + (f": {' '.join(multi)}" if multi else ""))

    locs = meta_locations(markup)
    filled = [n for n, v in locs if v]
    info.append(f"Location {len(filled)}/{len(locs)} 슬라이드"
                + (f" (미기입 {', '.join(n for n, v in locs if not v)})" if len(filled) != len(locs) else ""))

    # class 속성만 센다 — 본문 텍스트나 CSS 주석에 등장하는 같은 문자열은 목업이 아니다.
    partial = len(re.findall(r'class="[^"]*\bmock-partial\b[^"]*"', markup))
    info.append(f"부분 목업(팝업) {partial}개")

    labels = badge_labels(markup)
    two = [x for x in labels if "-" in x]
    info.append(f"2단 배지 {len(two)}/{len(labels)}개")

    doc_ver = doc_ruleset(html)
    if defined:
        rules_file = rules_path_for(path)
        if rules_file.exists():
            r_viol, r_info = check_rules(
                rules_file.read_text(encoding="utf-8"), defined,
                enforce_rule_ids=(strict or doc_ver >= 3))
            violations += r_viol
            info += r_info
        else:
            violations.append(
                f"Business Rules 문서 없음: {rules_file.name}"
                " — storyboard 와 같은 디렉터리에 생성할 것")

    info.insert(0, f"규칙 세트: 문서 v{doc_ver} / 검증기 v{RULESET_VERSION}"
                + ("" if doc_ver >= RULESET_VERSION else " — 신규 규칙은 참고로만 보고 (--strict 로 위반 처리)"))
    if not strict and doc_ver < RULESET_VERSION:
        advisory = [v for v in violations if rule_introduced_in(v) > doc_ver]
        if advisory:
            violations = [v for v in violations if rule_introduced_in(v) <= doc_ver]
            info.append(f"참고: 신규 규칙 위반 {len(advisory)}건 — 문서 작성 이후 도입")
            info.extend(f"  (신규) {v}" for v in advisory)
    return violations, info


def main():
    args = [a for a in sys.argv[1:] if a != "--strict"]
    strict = "--strict" in sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2

    css = extract_style(TEMPLATE.read_text(encoding="utf-8"))
    total = 0
    for path in args:
        violations, info = check(path, css, strict=strict)
        total += len(violations)
        print(f"===== {path} =====")
        for line in info:
            print(f"  · {line}")
        if violations:
            for v in violations:
                print(f"  X {v}")
            print(f"  => 위반 {len(violations)}건")
        else:
            print("  => 계약 위반 없음")
        print()

    print(f"총 위반 {total}건")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
