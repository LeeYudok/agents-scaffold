#!/usr/bin/env python3
"""pointer-badge 배치를 정적으로 점검한다 — 겹침과 순서 역전.

배지가 "의도한 요소를 가리키는가" 는 렌더해야만 알 수 있다(목업이 0.9배로
축소되고 콘텐츠 높이가 런타임에 정해진다). 그건 `resources/badge-audit.js` 를
브라우저에서 돌려 잡는다. 이 스크립트는 렌더 없이 잡히는 두 가지만 본다.

1. **겹침** — 같은 목업 안에서 배지 top 이 24px(배지 높이) 미만으로 붙으면
   서로 가린다.
2. **순서 역전** — 배지 라벨은 위에서 아래로 매기는 것이 규약이므로
   (1, 2, 3 / 1-1, 1-2), 라벨 순서와 top 순서가 어긋나면 좌표를 잘못 적은 것이다.
   설명 리스트는 라벨 순으로 읽히는데 목업은 그 반대로 읽히게 된다.

`check_badge_overflow.py` 와 역할이 다르다 — 그쪽은 가시 영역 이탈만 본다.

stdlib 만 사용한다.

사용법:
    python3 scripts/check_badge_alignment.py <산출물.html> [...]

종료 코드: 문제가 없으면 0, 있으면 1.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_storyboard import detail_slides, markup_only  # noqa: E402

#: 배지 높이(px). 이보다 가까우면 시각적으로 겹친다.
BADGE_HEIGHT = 24

BADGE_RE = re.compile(
    r'<span class="pointer-badge"[^>]*style="([^"]*)"[^>]*>([^<]*)<')


#: 배지를 담을 수 있는 컨테이너. 각각이 별도의 좌표 원점(position:relative)이므로
#: 서로 다른 컨테이너의 top 값은 비교 대상이 아니다 — mock-footer 의 `top:9px` 는
#: mock-body 의 `top:9px` 와 전혀 다른 위치다. mock-footer-pill 도 자체
#: position:relative 원점이므로 별도 컨테이너다 (이슈 #69).
CONTAINER_RE = re.compile(r'class="mock-(?:body|header|footer|footer-pill)"')


def badge_groups(slide_body):
    """슬라이드 본문을 (목업 번호, 컨테이너 번호, 블록) 단위로 자른다.

    목업 경계는 `class="mock"` / `class="mock mock-partial"` 이고, 그 안에서
    다시 mock-body·mock-header·mock-footer 로 나눈다. 좌표 비교는 같은
    컨테이너 안에서만 뜻이 있다.
    """
    mock_starts = [m.start() for m in re.finditer(r'class="mock[\s"]', slide_body)]
    groups = []
    for mi, s in enumerate(mock_starts):
        end = mock_starts[mi + 1] if mi + 1 < len(mock_starts) else len(slide_body)
        mock = slide_body[s:end]
        cont = [m.start() for m in CONTAINER_RE.finditer(mock)]
        for ci, cs in enumerate(cont):
            ce = cont[ci + 1] if ci + 1 < len(cont) else len(mock)
            groups.append((mi, ci, mock[cs:ce]))
    return groups


def badges_in(block):
    """(라벨, top) 목록을 문서 등장 순서대로 반환한다. top 이 없으면 건너뛴다."""
    out = []
    for style, label in BADGE_RE.findall(block):
        m = re.search(r"top:\s*(-?\d+)px", style)
        if m:
            out.append((label.strip(), int(m.group(1))))
    return out


def label_key(label):
    """'1-2' -> (1, 2), '3' -> (3,). 규약 밖 라벨은 정렬에서 제외한다."""
    parts = label.split("-")
    if not all(p.isdigit() for p in parts) or not parts:
        return None
    return tuple(int(p) for p in parts)


def check(path):
    """한 산출물을 점검해 문제 목록을 반환한다."""
    markup = markup_only(Path(path).read_text(encoding="utf-8"))
    problems = []

    for no, body in detail_slides(markup):
        for mi, _ci, block in badge_groups(body):
            badges = badges_in(block)

            for (la, ta), (lb, tb) in zip(badges, badges[1:]):
                if abs(tb - ta) < BADGE_HEIGHT:
                    problems.append(
                        f"{no} 목업{mi}: 배지 {la}({ta}px) 와 {lb}({tb}px) 가 "
                        f"{abs(tb - ta)}px 간격으로 겹친다 (배지 높이 {BADGE_HEIGHT}px)")

            # 음수 top 은 mock-body 위쪽(헤더 영역) 요소를 가리키는 관용 패턴이라
            # 라벨 순서와 어긋나는 것이 정상이다. 순서 검사에서 제외한다.
            keyed = [(label_key(l), l, t) for l, t in badges if t >= 0]
            keyed = [k for k in keyed if k[0] is not None]
            ordered = sorted(keyed)
            for (_ka, la, ta), (_kb, lb, tb) in zip(ordered, ordered[1:]):
                if tb < ta:
                    problems.append(
                        f"{no} 목업{mi}: 배지 {la}({ta}px) 보다 {lb}({tb}px) 가 위에 있다 "
                        "— 라벨은 위에서 아래로 매긴다")

    return problems


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    total = 0
    for path in sys.argv[1:]:
        problems = check(path)
        total += len(problems)
        print(f"===== {path} =====")
        for p in problems:
            print(f"  X {p}")
        print("  => 배치 문제 없음" if not problems else f"  => 문제 {len(problems)}건")
        print()
    if total:
        print("정적 점검은 겹침·순서까지다. 배지가 의도한 요소를 가리키는지는")
        print("resources/badge-audit.js 를 브라우저에서 실행해 확인한다.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
