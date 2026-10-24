#!/usr/bin/env python3
"""지원 매트릭스 manifest 검사 (#37, a-1).

CI 게이트다. 문서를 자동으로 고치지 않는다 — 어긋나면 실패시키고 사람이 PR 로 반영한다.

검사 항목
  1. 스키마 — 필수 키, verdict 어휘, 날짜 형식
  2. 만료   — tier=full 인데 last_measured 가 policy.full_max_age_days 를 넘으면 실패
  3. 정합성 — tier 가 실제 capability 판정과 모순되면 실패
              (full 인데 fail/unverified 가 있으면 안 된다)
  4. 문서 대조 — README 가 주장하는 CLI 버전이 manifest 와 일치하는가

사용:  python3 scripts/dev/check-harness-matrix.py [--today YYYY-MM-DD]
"""
import json
import pathlib
import re
import sys
from datetime import date, datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "harness-matrix.json"
VERDICTS = {"pass", "partial", "fail", "unverified", "inconclusive", "n/a"}
TIERS = {"full", "baseline", "experimental", "unsupported"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fail(msgs):
    for m in msgs:
        print(f"FAIL: {m}", file=sys.stderr)
    return 1


def main(argv):
    today = date.today()
    if "--today" in argv:
        today = datetime.strptime(argv[argv.index("--today") + 1], "%Y-%m-%d").date()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors = []
    max_age = data["policy"]["full_max_age_days"]
    known_caps = set(data["capabilities"])

    for h in data["harnesses"]:
        hid = h.get("id", "<no id>")
        for key in ("id", "name", "cli_version", "last_measured", "tier", "capabilities"):
            if key not in h:
                errors.append(f"{hid}: 필수 키 누락 '{key}'")
        if h.get("tier") not in TIERS:
            errors.append(f"{hid}: 알 수 없는 tier '{h.get('tier')}'")
        if not DATE_RE.match(h.get("last_measured", "")):
            errors.append(f"{hid}: last_measured 형식 오류 '{h.get('last_measured')}'")
            continue

        measured = datetime.strptime(h["last_measured"], "%Y-%m-%d").date()
        age = (today - measured).days
        if age < 0:
            errors.append(f"{hid}: last_measured 가 미래다 ({h['last_measured']})")

        caps = h["capabilities"]
        missing = known_caps - set(caps)
        if missing:
            errors.append(f"{hid}: capability 항목 누락 {sorted(missing)}")
        for name, c in caps.items():
            if name not in known_caps:
                errors.append(f"{hid}: 정의되지 않은 capability '{name}'")
            if c.get("verdict") not in VERDICTS:
                errors.append(f"{hid}.{name}: 알 수 없는 verdict '{c.get('verdict')}'")
            if not c.get("evidence"):
                errors.append(f"{hid}.{name}: evidence 가 비어 있다 — 근거 없는 판정 금지")

        if h.get("tier") == "full":
            if age > max_age:
                errors.append(
                    f"{hid}: tier=full 인데 마지막 실측이 {age}일 전이다 "
                    f"(한도 {max_age}일). 재측정하고 last_measured 를 갱신하거나 tier 를 강등할 것"
                )
            bad = [n for n, c in caps.items()
                   if c.get("verdict") in {"fail", "unverified", "inconclusive"}]
            if bad:
                errors.append(f"{hid}: tier=full 인데 미확정/실패 capability 가 있다 {sorted(bad)}")

    # 문서 대조 — README 가 주장하는 버전이 manifest 와 같아야 한다
    for h in data["harnesses"]:
        ver = h["cli_version"].split()[-1]
        hits = [p.name for p in ROOT.glob("README*.md")
                if ver in p.read_text(encoding="utf-8")]
        docs = [p.name for p in (ROOT / "docs").glob("OPTIONS*.md")
                if ver in p.read_text(encoding="utf-8")]
        if not hits and not docs:
            errors.append(
                f"{h['id']}: manifest 의 cli_version '{ver}' 이 README/docs 어디에도 없다 "
                f"— 문서가 낡았거나 manifest 가 낡았다"
            )

    if errors:
        return fail(errors)
    print(f"OK: {len(data['harnesses'])} harnesses, 기준일 {today}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
