#!/usr/bin/env python3
"""template.html 의 head와 body runtime을 옮긴 빈 산출물 뼈대를 만든다.

산출물은 자체 완결형 단일 HTML 이라 `<head>` 전체와 배지↔설명 interaction
runtime을 매번 들고 가야 한다. 그걸
에이전트가 손으로 옮겨 적으면 토큰을 크게 쓰고, 오타 하나에 검증기가 미정의
클래스로 막는다. 이 스크립트가 head 를 기계적으로 복사해 그 경로를 없앤다.

만들어진 파일에는 슬라이드가 없다. 에이전트는 `INSERT_MARKER` 바로 앞에
슬라이드를 이어붙이면 된다 — 한 번에 다 쓰지 않고 나눠 붙이는 것이 정상 절차다
(SKILL.md 의 "분할 작성" 참고).

stdlib 만 사용한다.

사용법:
    python3 scripts/scaffold.py <출력.html> --project <프로젝트명> [--version 1.0.0]
                                [--accent '#1b64da'] [--accent-ink '#ffffff']
                                [--force]

종료 코드: 생성했으면 0, 인자·경로 문제면 2.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_storyboard import RULESET_VERSION  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "resources" / "template.html"

#: 슬라이드를 이어붙일 자리. 에이전트는 이 문자열 바로 앞에 슬라이드를 넣는다.
INSERT_MARKER = "</div>\n</body>"


def build(template_html, project, version, accent=None, accent_ink=None):
    """템플릿에서 head와 body script를 떼어 빈 docwrap 뼈대를 만든다."""
    head = re.search(r"<head>.*?</head>", template_html, re.S)
    if not head:
        raise ValueError("template.html 에 <head> 블록이 없다")
    head_html = head.group(0)
    body = re.search(r"<body>(.*?)</body>", template_html, re.S)
    if not body:
        raise ValueError("template.html 에 <body> 블록이 없다")
    body_scripts = "\n".join(re.findall(r"<script>.*?</script>", body.group(1), re.S))

    head_html = re.sub(
        r"<title>[^<]*</title>", f"<title>{project} 화면설계서</title>", head_html)
    # 생성 당시의 규칙 세트를 문서에 새긴다 — 검증기가 읽어 사후 도입 규칙을
    # 참고로 분리한다 (이슈 #77). 지우거나 값을 바꾸지 않는다.
    head_html = head_html.replace(
        "<head>", f'<head>\n<meta name="skill-ruleset" content="{RULESET_VERSION}">', 1)
    if accent:
        head_html = re.sub(
            r"(--accent:\s*)[^;]+;", lambda m: m.group(1) + accent + ";", head_html, count=1)
    if accent_ink:
        head_html = re.sub(
            r"(--accent-ink:\s*)[^;]+;", lambda m: m.group(1) + accent_ink + ";",
            head_html, count=1)

    # 템플릿 head 는 플레이스홀더를 쓰지 않지만, 앞으로 들어가더라도 채워지게 둔다.
    head_html = (head_html
                 .replace("{{PROJECT_NAME}}", project)
                 .replace("{{VERSION}}", version))

    return (
        "<!DOCTYPE html>\n<html lang=\"ko\">\n"
        f"{head_html}\n"
        "<body>\n"
        f"{body_scripts}\n"
        "<div class=\"docwrap\">\n\n"
        f"{INSERT_MARKER}\n</html>\n"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description="화면설계서 산출물 뼈대 생성")
    ap.add_argument("output", help="생성할 HTML 경로 (<이름>_storyboard.html 권장)")
    ap.add_argument("--project", required=True, help="프로젝트명 (상단 바·푸터에 쓰는 값)")
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--accent", help="강조색 (예: '#1b64da'). 생략하면 템플릿 기본값")
    ap.add_argument("--accent-ink", help="강조색 배경 위 글자색 (밝은 accent 면 어둡게)")
    ap.add_argument("--force", action="store_true", help="기존 파일을 덮어쓴다")
    args = ap.parse_args(argv)

    out = Path(args.output)
    if out.exists() and not args.force:
        print(f"이미 있는 파일이다: {out} (덮어쓰려면 --force)", file=sys.stderr)
        return 2
    if not TEMPLATE.exists():
        print(f"템플릿이 없다: {TEMPLATE}", file=sys.stderr)
        return 2

    html = build(TEMPLATE.read_text(encoding="utf-8"),
                 args.project, args.version, args.accent, args.accent_ink)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"생성: {out}")
    print(f"슬라이드는 {INSERT_MARKER!r} 바로 앞에 이어붙인다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
