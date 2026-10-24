#!/usr/bin/env python3
"""finguard scan의 rdjsonl을 심각도 기반 exit code로 변환한다 (stdlib only)."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def severities(value: str) -> set[str]:
    return {item.strip().upper() for item in value.split(",") if item.strip()}


def build_command(args: argparse.Namespace) -> list[str]:
    command = [args.finguard, "scan", "--dir", str(args.dir), "--format", "rdjsonl"]
    if args.rules:
        command.extend(("--rules", str(args.rules)))
    if args.mapping:
        command.extend(("--mapping", str(args.mapping)))
    if args.semgrep:
        command.extend(("--semgrep", args.semgrep))
    return command


def parse_findings(output: str) -> list[dict]:
    findings = []
    for number, line in enumerate(output.splitlines(), 1):
        if not line.strip():
            continue
        try:
            finding = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"rdjsonl {number}번째 줄 파싱 실패: {exc.msg}") from exc
        if not isinstance(finding, dict) or not finding.get("severity"):
            raise ValueError(f"rdjsonl {number}번째 줄에 severity가 없다")
        findings.append(finding)
    return findings


def summary(finding: dict) -> str:
    location = finding.get("location") or {}
    start = (location.get("range") or {}).get("start") or {}
    path = location.get("path", "?")
    line = start.get("line", "?")
    message = str(finding.get("message", "")).splitlines()[0]
    return f"{path}:{line} [{str(finding['severity']).upper()}] {message}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FinGuard finding을 exit code 게이트로 변환")
    parser.add_argument("--dir", type=Path, required=True, help="점검할 소스 디렉터리")
    parser.add_argument("--block-on", default="ERROR", help="차단 심각도(쉼표 구분)")
    parser.add_argument("--finguard", default="finguard", help="finguard 실행 파일")
    parser.add_argument("--semgrep", help="semgrep 실행 파일")
    parser.add_argument("--rules", type=Path, help="FinGuard rules 디렉터리")
    parser.add_argument("--mapping", type=Path, help="FinGuard mapping/rules.yaml")
    args = parser.parse_args(argv)

    if not args.dir.is_dir():
        print(f"오류: 점검 디렉터리가 없다: {args.dir}", file=sys.stderr)
        return 2

    try:
        result = subprocess.run(build_command(args), text=True, capture_output=True, check=False)
    except OSError as exc:
        print(f"오류: FinGuard 실행 실패: {exc}", file=sys.stderr)
        return 2
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        print(f"오류: FinGuard가 exit {result.returncode}로 종료됨", file=sys.stderr)
        return 2

    try:
        findings = parse_findings(result.stdout)
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    blocked_on = severities(args.block_on)
    blocked = [f for f in findings if str(f["severity"]).upper() in blocked_on]
    for finding in findings:
        print(summary(finding))
    configured = ",".join(sorted(blocked_on)) or "없음"
    print(f"FinGuard: 매핑된 finding {len(findings)}건, 차단 대상 {len(blocked)}건 ({configured})")
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
