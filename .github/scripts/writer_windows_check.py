"""윈도우에서 yd-writer-kr 의 Python 호환 계층이 Go 바이너리와 UTF-8 로 말하는지 본다 (#137).

test.yml 의 writer-windows 잡이 CHECK_WRITING_BIN 을 지정하고 부른다. bash 는 쓰지 않는다.
"""
import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills" / "yd-skills" / "skills" / "yd-writer-kr"
sys.path.insert(0, str(SKILL / "scripts"))
import check_writing as cw  # noqa: E402

assert os.environ.get("CHECK_WRITING_BIN"), "CHECK_WRITING_BIN 이 필요하다"
rules = cw.load_rules()
found = cw.check("서버의 설정의 기본값의 출처를 찾는다. 배포를 완료함.", rules)
got = [(f.level, f.match) for f in found]
assert got == [("경고", "3회"), ("오류", "함.")], got
off = SKILL / "tests" / "fixtures" / "profile-iso-off.md"
iso = "배포 시각은 2026-11-17T09:00:00+09:00 이다."
assert [f.kind for f in cw.check(iso, rules)] == ["시각 표기"]
assert cw.check(iso, rules, profile=str(off)) == []
print("ok")
