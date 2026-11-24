#!/usr/bin/env python3
"""Business Rules와 traceability.json의 화면·규칙·파일 연결을 검증한다.

`--routes` 를 주면 라우터 소스와도 대조한다 (이슈 #139). SPA 모드에서 가장
흔한 이탈이 "매핑표에는 있는데 라우터에 등록되지 않은 화면" 이다 — 빌드도
타입 검사도 통과하고, 그 URL 로 들어갔을 때만 빈 화면이 된다. 반대 방향(라우터에는
있는데 문서에 없는 라우트)도 같이 본다.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


SCREEN_RE = re.compile(r"(?m)^##\s+([A-Z]{2,6}-[A-Z]{2,12}-\d{3})\b")
#: 라우터 소스에서 경로 리터럴을 뽑는다. route object(`path: "/x"`)와 JSX
#: (`<Route path="/x">`) 두 표기를 모두 쓴다 — 프로젝트마다 다르고, 하나만
#: 지원하면 검사가 조용히 0건이 된다.
ROUTE_OBJ_RE = re.compile(r"""\bpath\s*:\s*['"`]([^'"`]*)['"`]""")
ROUTE_JSX_RE = re.compile(r"""<Route\b[^>]*\bpath\s*=\s*['"{`]+([^'"`}]*)['"`}]+""")
#: 문서와 대조할 대상이 아닌 라우트. 404 와 index 는 화면 ID 를 갖지 않는다.
ROUTE_IGNORED = {"*", "", "/*"}
RULE_RE = re.compile(
    r"\b([A-Z]{2,6}-[A-Z]{2,12}-\d{3}\.(?:IN|OUT|INT|EDGE)-\d{2})\b")


def duplicates(values):
    return sorted(value for value, count in Counter(values).items() if count > 1)


def collect_routes(sources):
    """라우터 소스에서 선언된 경로 집합을 뽑는다."""
    found = set()
    for text in sources:
        found.update(ROUTE_OBJ_RE.findall(text))
        found.update(ROUTE_JSX_RE.findall(text))
    return {route for route in found if route not in ROUTE_IGNORED}


def normalize_route(route):
    """비교용 정규화. 끝 슬래시와 파라미터 이름 차이는 같은 라우트로 본다."""
    route = route.strip()
    if len(route) > 1:
        route = route.rstrip("/")
    if not route.startswith("/"):
        route = "/" + route
    return re.sub(r":[A-Za-z_][A-Za-z0-9_]*", ":param", route)


def validate(manifest, rules_md, repo_root, router_sources=None):
    violations = []
    br_screens = SCREEN_RE.findall(rules_md)
    br_rules = RULE_RE.findall(rules_md)
    if duplicates(br_screens):
        violations.append(f"Business Rules 중복 화면 ID: {', '.join(duplicates(br_screens))}")
    if duplicates(br_rules):
        violations.append(f"Business Rules 중복 규칙 ID: {', '.join(duplicates(br_rules))}")

    screens = manifest.get("screens") if isinstance(manifest, dict) else None
    if not isinstance(screens, list):
        return violations + ["traceability.json의 screens는 배열이어야 한다"]

    manifest_screens = []
    manifest_rules = []
    for index, screen in enumerate(screens, 1):
        if not isinstance(screen, dict) or not screen.get("screenId"):
            violations.append(f"screens[{index}]에 screenId가 없다")
            continue
        screen_id = screen["screenId"]
        manifest_screens.append(screen_id)
        implementations = screen.get("implementation")
        if not isinstance(implementations, list) or not implementations:
            violations.append(f"{screen_id}에 implementation 파일이 없다")
        else:
            for path in implementations:
                if not isinstance(path, str) or not (repo_root / path).is_file():
                    violations.append(f"{screen_id} 구현 파일 없음: {path}")

        rules = screen.get("rules")
        if not isinstance(rules, list):
            violations.append(f"{screen_id}의 rules는 배열이어야 한다")
            continue
        for rule in rules:
            if not isinstance(rule, dict) or not rule.get("ruleId"):
                violations.append(f"{screen_id}에 ruleId 없는 규칙 연결이 있다")
                continue
            rule_id = rule["ruleId"]
            manifest_rules.append(rule_id)
            if not rule_id.startswith(screen_id + "."):
                violations.append(f"규칙 ID가 다른 화면에 연결됨: {screen_id} → {rule_id}")
            tests = rule.get("tests")
            if not isinstance(tests, list) or not tests:
                violations.append(f"{rule_id}에 테스트 파일이 없다")
            else:
                for path in tests:
                    if not isinstance(path, str) or not (repo_root / path).is_file():
                        violations.append(f"{rule_id} 테스트 파일 없음: {path}")

    routes = [(screen.get("screenId"), screen.get("route"))
              for screen in screens
              if isinstance(screen, dict) and screen.get("route")]
    seen = {}
    for screen_id, route in routes:
        key = normalize_route(route)
        if key in seen:
            violations.append(
                f"라우트 중복: {seen[key]} 와 {screen_id} 가 모두 {route} 다")
        else:
            seen[key] = screen_id

    if router_sources is not None:
        declared = {normalize_route(route) for route in collect_routes(router_sources)}
        for screen_id, route in routes:
            if normalize_route(route) not in declared:
                violations.append(
                    f"{screen_id}의 라우트가 라우터에 등록되지 않았다: {route}")
        for orphan in sorted(declared - set(seen)):
            violations.append(f"문서에 없는 라우트가 라우터에 있다: {orphan}")

    for label, values in (("화면", manifest_screens), ("규칙", manifest_rules)):
        dup = duplicates(values)
        if dup:
            violations.append(f"traceability.json 중복 {label} ID: {', '.join(dup)}")

    missing_screens = sorted(set(br_screens) - set(manifest_screens))
    extra_screens = sorted(set(manifest_screens) - set(br_screens))
    missing_rules = sorted(set(br_rules) - set(manifest_rules))
    extra_rules = sorted(set(manifest_rules) - set(br_rules))
    if missing_screens:
        violations.append(f"traceability.json 화면 ID 누락: {', '.join(missing_screens)}")
    if extra_screens:
        violations.append(f"Business Rules에 없는 화면 ID: {', '.join(extra_screens)}")
    if missing_rules:
        violations.append(f"traceability.json 규칙 ID 누락: {', '.join(missing_rules)}")
    if extra_rules:
        violations.append(f"Business Rules에 없는 규칙 ID: {', '.join(extra_rules)}")
    return violations


def main(argv=None):
    parser = argparse.ArgumentParser(description="기획↔구현 traceability 검증")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("business_rules", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--routes", type=Path, nargs="*", default=None,
                        help="라우터 소스 파일. 주면 라우트 등록 여부까지 대조한다")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        rules_md = args.business_rules.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"오류: 입력을 읽을 수 없음: {exc}", file=sys.stderr)
        return 2
    sources = None
    if args.routes is not None:
        try:
            sources = [path.read_text(encoding="utf-8") for path in args.routes]
        except OSError as exc:
            print(f"오류: 라우터 소스를 읽을 수 없음: {exc}", file=sys.stderr)
            return 2
    violations = validate(manifest, rules_md, args.repo_root, sources)
    for violation in violations:
        print(f"[위반] {violation}")
    if violations:
        print(f"traceability 위반 {len(violations)}건")
        return 1
    print("traceability 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
