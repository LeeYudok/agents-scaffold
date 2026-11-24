#!/usr/bin/env python3
"""badge-audit 실측 결과(JSON)를 산출물 HTML 의 인라인 top 에 일괄 반영한다.

`resources/badge-audit.js` 를 브라우저에서 실행해 반환값을 JSON 파일로 저장한
뒤 이 스크립트에 넘긴다. 반환값의 `fixes[]` 는 배지 자신의 인라인 top
좌표계(positioned ancestor 기준 · scale/zoom 보정 완료)로 환산된 값이므로,
컨테이너가 mock-body 든 바텀시트 내부든 그대로 치환하면 된다 — `measured/0.9`
수동 환산은 부분 목업에서 틀린다 (이슈 #72).

반영 후 같은 스킬의 정적 검증기 두 개(check_badge_overflow / check_badge_alignment)
를 재실행해 결과를 함께 보고한다. stdlib 만 사용한다.

사용법:
    python3 scripts/apply_badge_audit.py <산출물.html> <audit.json> [--dry-run] [--tolerance N]

종료 코드: 반영(또는 dry-run 예고)이 전부 성공하고 재검증도 통과하면 0, 아니면 1.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

#: 이보다 작은 차이는 렌더 오차로 보고 건너뛴다 (badge-audit.js 와 동일 기본값).
DEFAULT_TOLERANCE = 3


def slide_sections(html):
    """상단 바 앵커로 자른 {번호: (시작, 끝)} — 첫 등장 기준."""
    heads = list(re.finditer(r'class="ppt-top-no">NO\.\s*([\d.]+)<', html))
    out = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(html)
        out.setdefault(m.group(1), (m.end(), end))
    return out


def badge_pattern(inline_top, label):
    """슬라이드 구간 안에서 배지 하나를 특정하는 정규식.

    라벨은 desc-num 과 1:1 이라 슬라이드 안에서 유일하고, 현재 inline top 을
    함께 맞춰 이미 고쳐진 배지를 이중 치환하지 않는다.
    """
    top = re.escape(f"{inline_top:g}")
    return re.compile(
        r'(class="pointer-badge"[^>]*style="[^"]*top:\s*)' + top +
        r'(px[^"]*"[^>]*>' + re.escape(label) + r'(?:</span>|<))')


def apply_fixes(html, fixes, tolerance=DEFAULT_TOLERANCE):
    """(수정된 html, 적용 목록, 실패 목록) 을 반환한다. html 은 실패가 있어도
    적용 가능한 것은 반영된 상태다."""
    sections = slide_sections(html)
    applied, failed = [], []
    for fx in fixes:
        no, label = fx["slide"], fx["label"]
        cur, want = fx["inlineTop"], fx["suggestedTop"]
        if abs(want - cur) <= tolerance:
            continue
        if no not in sections:
            failed.append((no, label, "슬라이드 없음"))
            continue
        s, e = sections[no]
        seg = html[s:e]
        pat = badge_pattern(cur, label)
        matches = list(pat.finditer(seg))
        if len(matches) != 1:
            failed.append((no, label, f"배지 매칭 {len(matches)}건 (top:{cur:g})"))
            continue
        m = matches[0]
        seg = seg[:m.start()] + m.group(1) + f"{want:g}" + m.group(2) + seg[m.end():]
        html = html[:s] + seg + html[e:]
        sections = slide_sections(html)  # 길이가 변했으므로 구간 재계산
        applied.append((no, label, cur, want))
    return html, applied, failed


def revalidate(path):
    """정적 검증기 두 개를 재실행해 (성공 여부, 출력) 을 반환한다."""
    ok, out = True, []
    for script in ("check_badge_overflow.py", "check_badge_alignment.py"):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / script), str(path)],
            capture_output=True, text=True)
        ok = ok and proc.returncode == 0
        out.append(f"--- {script} (exit {proc.returncode})\n{proc.stdout.strip()}")
    return ok, "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("html", type=Path)
    ap.add_argument("audit_json", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="바꿀 내용만 출력하고 저장하지 않는다")
    ap.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE,
                    help=f"이 값(px) 이하 차이는 건너뛴다 (기본 {DEFAULT_TOLERANCE})")
    args = ap.parse_args()

    audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
    fixes = audit.get("fixes", audit if isinstance(audit, list) else [])
    if not fixes:
        print("fixes 가 비어 있다 — 반영할 것 없음")
        return 0

    html = args.html.read_text(encoding="utf-8")
    new_html, applied, failed = apply_fixes(html, fixes, args.tolerance)

    for no, label, cur, want in applied:
        print(f"{'예고' if args.dry_run else '반영'}  {no} 배지 {label}: top {cur:g} -> {want:g}")
    for no, label, why in failed:
        print(f"실패  {no} 배지 {label}: {why}")

    if not args.dry_run and applied:
        args.html.write_text(new_html, encoding="utf-8")
        ok, report = revalidate(args.html)
        print(report)
        if not ok:
            return 1
    print(f"적용 {len(applied)}건 / 실패 {len(failed)}건"
          + (" (dry-run — 저장 안 함)" if args.dry_run else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
