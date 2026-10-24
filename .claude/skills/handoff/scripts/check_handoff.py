#!/usr/bin/env python3
"""핸드오프 본문·포인터가 SKILL.md 의 형식을 지키는지 검사한다 (stdlib only).

핸드오프는 "재개 가능한 상태" 여야 하는데, 템플릿을 덜 채우거나 시각을 ISO 8601 로 쓰거나
토큰을 본문에 남겨도 겉보기엔 멀쩡하다. 게시 전에 이 검사기를 돌린다. 형식의 원본은
SKILL.md 의 "본문"·"포인터" 템플릿이며 여기서는 그 항목이 채워졌는지만 본다.

    python3 check_handoff.py <파일 | ->                  본문(이슈·코멘트·파일 모드)
    python3 check_handoff.py HANDOFF.md --as-file         레포의 HANDOFF.md: 트래커가 있으면 포인터여야 한다
    python3 check_handoff.py <본문> --verify-git <레포>   기록한 브랜치·HEAD 를 git 과 대조한다(읽기 전용)
    python3 check_handoff.py HANDOFF.yaml --yaml          기계 판독용 짝 파일(파일 모드)
    python3 check_handoff.py HANDOFF.yaml --yaml --pair HANDOFF.md   md 와 yaml 이 같은 상태를 적었는지 본다

형식은 첫 제목으로 고른다: `# HANDOFF (포인터)` 면 포인터, 그 밖엔 본문.
본문에 `## 기계 판독용 상태` 섹션이 있으면 그 안의 ```yaml 블록도 같은 규칙으로 보고 본문의 작성·브랜치·HEAD 와 맞춰 본다.
섹션이 없으면 통과한다(하위 호환). 섹션만 있고 닫힌 블록이 없으면 위반이다.
yaml 검사는 어휘 수준이다: 필수 키, 따옴표 없는 날짜·소수·yes/no 값(YAML 이 조용히 형을 바꾼다), 탭 들여쓰기.
PyYAML 이 있으면 `safe_load` 로 실제 파싱과 문자열 칸의 형 변환도 확인한다(없으면 어휘 검사만).
시크릿은 줄 번호와 패턴 이름만 출력하고 값은 출력하지 않는다.

종료 코드: 위반이 없으면 0, 있으면 1, 입력·git 을 쓸 수 없으면 2.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TS = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}$")
ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}|\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})\b")
SECTIONS = ["지금 어디까지", "검증 결과 (원문)", "실행 중인 것", "미결 판단", "다음에 칠 명령", "함정"]
FIELDS = ["이슈", "작성", "작업 이슈/PR", "브랜치", "HEAD"]
POINTER_FIELDS = ["현재 핸드오프", "작성", "요약", "전체 목록"]
PLACEHOLDER = re.compile(r"<[^<>\n]*[가-힣][^<>\n]*>|<(?:YYYY[^<>\n]*|sha|branch|path|command|URL|N|M)>")
YAML_REQUIRED = ["schema_version", "meta", "state", "last_verification", "next_steps"]
YAML_META = ["written_at", "branch", "head"]
YAML_SECTION = "기계 판독용 상태"
YAML_KEY = re.compile(r"^(\s*)(?:-\s+)?([A-Za-z_][\w-]*):(?:\s+(.*?))?\s*$")
YAML_TOP = re.compile(r"^([A-Za-z_][\w-]*):(?:\s|$)")
# 따옴표 없이 쓰면 YAML 1.1 이 문자열이 아닌 것으로 바꾸는 값: 날짜·시각, 소수(버전 1.10 → 1.1), yes/no/on/off.
# 소수는 버전 이름이 붙은 키에서만 본다 — `progress: 0.5` 같은 진짜 소수 값은 따옴표를 붙이면 오히려 문자열이 된다.
VERSION_KEY = re.compile(r"(?i)version|release|revision|tag")
YAML_COERCED = [
    (re.compile(r"\d{4}-\d{2}-\d{2}(?:[Tt ]\d{2}:\d{2}.*)?"), "날짜·시각", None),
    (re.compile(r"[-+]?\d+\.\d+"), "소수(버전 번호가 깨진다)", VERSION_KEY),
    (re.compile(r"(?i:yes|no|on|off|y|n)"), "불리언", None),
]
SECRETS = [
    ("glpat", re.compile(r"glpat-[A-Za-z0-9_-]{8,}")),
    ("ghp", re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}")),
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{16,}")),
    ("sk-key", re.compile(r"sk-[A-Za-z0-9]{20}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer", re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("url-credentials", re.compile(r"://[^/\s:@<$]+:[^/\s@<$]+@")),
    ("password/token/secret", re.compile(r"(?:password|secret|token)\s*[:=]\s*[^<$(\s`\"']", re.I)),
]


def fields(lines: list[str], names: list[str]) -> dict[str, tuple[int, str]]:
    out = {}
    for i, line in enumerate(lines, 1):
        m = re.match(r"^- (%s):\s*(.*)$" % "|".join(map(re.escape, names)), line)
        if m and m.group(1) not in out:
            out[m.group(1)] = (i, m.group(2).strip())
    return out


def sections(lines: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur, fence = None, False
    for line in lines:
        if line.startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def fenced(body: list[str]) -> list[list[str]]:
    blocks, cur = [], None
    for line in body:
        if line.startswith("```"):
            if cur is None:
                cur = []
            else:
                blocks.append(cur)
                cur = None
        elif cur is not None:
            cur.append(line)
    return blocks


def common(lines: list[str], errors: list[str]) -> None:
    for i, line in enumerate(lines, 1):
        for name, rx in SECRETS:
            if rx.search(line):
                errors.append(f"줄 {i}: 시크릿 모양 [{name}] — 값은 출력하지 않는다. 키 이름까지만 적는다")
        if ISO.search(line):
            errors.append(f"줄 {i}: ISO 8601 시각(T·Z·+09:00)은 쓰지 않는다 — YYYY-MM-DD HH:MM:SS.mmm")
        if PLACEHOLDER.search(line):
            errors.append(f"줄 {i}: 템플릿 자리표시자가 남아 있다")


def check_body(lines: list[str], errors: list[str]) -> dict[str, tuple[int, str]]:
    f = fields(lines, FIELDS)
    for name in FIELDS:
        if name not in f or not f[name][1]:
            errors.append(f"필드 `{name}` 이 없거나 비어 있다")
    if "작성" in f and f["작성"][1] and not TS.match(f["작성"][1]):
        errors.append(f"줄 {f['작성'][0]}: 작성 시각이 YYYY-MM-DD HH:MM:SS.mmm 형식이 아니다")
    if "이슈" in f and f["이슈"][1] and not re.match(r"https?://|없음", f["이슈"][1]):
        errors.append(f"줄 {f['이슈'][0]}: 이슈는 URL 이거나 \"없음 — 이 파일이 원본\" 이어야 한다")
    if "이슈" in f and f["이슈"][1].startswith("없음") and "이 파일이 원본" not in f["이슈"][1]:
        errors.append(f"줄 {f['이슈'][0]}: 파일 모드는 \"없음 — 이 파일이 원본\" 으로 적는다")
    if "작업 이슈/PR" in f and f["작업 이슈/PR"][1] and not re.search(r"#\d+|없음", f["작업 이슈/PR"][1]):
        errors.append(f"줄 {f['작업 이슈/PR'][0]}: 작업 이슈/PR 에 #번호 또는 없음이 필요하다")
    if "브랜치" in f and f["브랜치"][1] and not re.search(r"`[^`\s]+`|없음", f["브랜치"][1]):
        errors.append(f"줄 {f['브랜치'][0]}: 브랜치를 백틱으로 적는다")
    if "HEAD" in f and f["HEAD"][1] and not re.search(r"`[0-9a-f]{7,40}`", f["HEAD"][1]):
        errors.append(f"줄 {f['HEAD'][0]}: HEAD 는 백틱 안의 커밋 해시(7~40자리)여야 한다")
    secs = sections(lines)
    for name in SECTIONS:
        if name not in secs:
            errors.append(f"섹션 `## {name}` 이 없다")
        elif not any(l.strip() for l in secs[name]):
            errors.append(f"섹션 `## {name}` 이 비어 있다")
    if "검증 결과 (원문)" in secs:
        blocks = fenced(secs["검증 결과 (원문)"])
        if not blocks or not any(l.strip() for b in blocks for l in b):
            errors.append("`검증 결과 (원문)` 에 코드블록 원문이 없다 (안 돌렸으면 \"안 돌림\" 이라고 적는다)")
    if "다음에 칠 명령" in secs:
        cmds = [l for b in fenced(secs["다음에 칠 명령"]) for l in b]
        if not any(re.match(r"\s*cd\s+(/|~)", l) for l in cmds):
            errors.append("`다음에 칠 명령` 은 절대경로 `cd` 로 실행 디렉터리를 포함해야 한다")
    return f


def plain_scalar(raw: str) -> str | None:
    """따옴표·구조 표시가 없는 평문 스칼라면 주석을 뗀 값을, 아니면 None."""
    raw = raw.strip()
    if not raw or raw[0] in "\"'[{|>&*!#-" and not re.match(r"-\d", raw):
        return None
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip() or None


def top_blocks(lines: list[str]) -> dict[str, tuple[int, list[tuple[int, str]]]]:
    """최상위 키 → (시작 줄 인덱스, [(원본 줄 인덱스, 줄)])."""
    out: dict[str, tuple[int, list[tuple[int, str]]]] = {}
    cur = None
    for i, line in enumerate(lines):
        m = YAML_TOP.match(line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, (i, []))
        elif cur is not None:
            out[cur][1].append((i, line))
    return out


def yaml_value(entries: list[tuple[int, str]], key: str) -> tuple[int, str] | None:
    for i, line in entries:
        m = YAML_KEY.match(line)
        if m and m.group(2) == key and m.group(3):
            return i, m.group(3).strip().strip("\"'")
    return None


def list_items(body: list[str]) -> list[list[str]]:
    """블록 스타일 목록을 항목별 줄 묶음으로 나눈다. 첫 `- ` 의 들여쓰기를 항목 경계로 쓴다."""
    first = next((re.match(r"^(\s*)-\s", l) for l in body if re.match(r"^\s*-\s", l)), None)
    if not first:
        return []
    items: list[list[str]] = []
    for line in body:
        if re.match(rf"^{re.escape(first.group(1))}-\s", line):
            items.append([line])
        elif items:
            items[-1].append(line)
    return items


def check_yaml(lines: list[str], errors: list[str], offset: int = 0) -> dict[str, str]:
    """HANDOFF.yaml 어휘 검사. offset 은 본문 안 블록일 때 원본 줄 번호를 맞추는 값. meta 값을 돌려준다."""
    def at(i: int) -> int:
        return i + offset + 1

    blocks = top_blocks(lines)
    for key in YAML_REQUIRED:
        if key not in blocks:
            errors.append(f"yaml: 최상위 키 `{key}` 가 없다")
    seen: dict[str, int] = {}
    for i, line in enumerate(lines):
        t = YAML_TOP.match(line)
        if t:
            if t.group(1) in seen:
                errors.append(f"줄 {at(i)}: 최상위 키 `{t.group(1)}` 가 줄 {at(seen[t.group(1)])} 에 이어 또 나온다 — 파서는 마지막 값을 쓴다")
            seen.setdefault(t.group(1), i)
    for i, line in enumerate(lines):
        if re.match(r"^ *\t", line):
            errors.append(f"줄 {at(i)}: YAML 은 탭 들여쓰기를 쓰지 않는다")
        m = YAML_KEY.match(line)
        key = m.group(2) if m else ""
        raw = m.group(3) if m else None
        if raw is None:
            m2 = re.match(r"^\s*-\s+(.+?)\s*$", line)
            raw = m2.group(1) if m2 and not YAML_KEY.match(line) else None
        value = plain_scalar(raw) if raw else None
        if value:
            for rx, what, only_keys in YAML_COERCED:
                if rx.fullmatch(value) and (only_keys is None or only_keys.search(key)):
                    errors.append(f"줄 {at(i)}: 따옴표 없는 값 `{value}` 는 YAML 이 {what}(으)로 바꾼다 — 문자열은 따옴표로 감싼다")
                    break
    if "schema_version" in blocks:
        i = blocks["schema_version"][0]
        if not re.match(r"^schema_version:\s+([\"']).+\1\s*$", lines[i]):
            errors.append(f"줄 {at(i)}: schema_version 은 따옴표로 감싼 문자열이다 (예: \"1\")")
    meta: dict[str, str] = {}
    if "meta" in blocks:
        for key in YAML_META:
            got = yaml_value(blocks["meta"][1], key)
            if got is None:
                errors.append(f"yaml: meta.{key} 가 없거나 비어 있다")
            else:
                meta[key] = got[1]
        for key in YAML_META:
            if sum(1 for _, l in blocks["meta"][1] if re.match(rf"^\s+{key}:\s", l)) > 1:
                errors.append(f"yaml: meta.{key} 가 두 번 나온다 — 파서는 마지막 값을 쓴다")
        head_line = next((l for _, l in blocks["meta"][1] if re.match(r"^\s+head:\s", l)), "")
        if head_line and not re.match(r"^\s+head:\s+([\"']).+\1\s*$", head_line):
            errors.append("yaml: meta.head 는 따옴표로 감싼다 — 숫자만 있는 짧은 해시는 정수로 바뀐다")
        if "written_at" in meta and not TS.match(meta["written_at"]):
            errors.append("yaml: meta.written_at 이 YYYY-MM-DD HH:MM:SS.mmm 형식이 아니다")
    if "last_verification" in blocks:
        results = [1 for _, l in blocks["last_verification"][1] if re.match(r"^\s*(?:-\s+)?result:\s+\S", l)]
        if not results:
            errors.append("yaml: last_verification 에 result 가 없다 (안 돌렸으면 \"안 돌림\" 이라고 적는다)")
    if "next_steps" in blocks:
        items = list_items([l for _, l in blocks["next_steps"][1]])
        if not items:
            errors.append("yaml: next_steps 에 항목이 없다 — 다음에 할 일이 없으면 핸드오프를 쓰지 않는다 (목록은 `- ` 블록 스타일로 적는다)")
        for n, item in enumerate(items):
            for key, what in (("do", "할 일"), ("check", "대조할 명령")):
                if not any(re.match(rf"^\s*(?:-\s+)?{key}:\s+\S", l) for l in item):
                    errors.append(f"yaml: next_steps[{n}] 에 `{key}`({what})가 없다 — 항목마다 do 와 check 가 있어야 한다")
    try:
        import yaml  # PyYAML 이 있으면 실제 파싱한다
    except ImportError:
        return meta
    try:
        data = yaml.safe_load("\n".join(lines))
    except yaml.YAMLError as e:
        errors.append(f"yaml: 파싱 실패 ({str(e).splitlines()[0]})")
        return meta
    if isinstance(data, dict) and isinstance(data.get("meta"), dict):
        for key, v in data["meta"].items():
            if key in YAML_META and not isinstance(v, str):
                errors.append(f"yaml: meta.{key} 가 문자열이 아니다 ({type(v).__name__}) — 따옴표로 감싼다")
    return meta


def yaml_block(lines: list[str]) -> tuple[int, list[str]] | None:
    """본문의 `## 기계 판독용 상태` 섹션 안 첫 ```yaml 블록: (블록 첫 줄의 0-기준 인덱스, 줄들)."""
    in_section, start, cur = False, None, []
    for i, line in enumerate(lines):
        if line.startswith("```") and start is None and in_section and line.strip() in ("```yaml", "```yml"):
            start, cur = i + 1, []
        elif line.startswith("```") and start is not None:
            return start, cur
        elif start is not None:
            cur.append(line)
        elif line.startswith("## "):
            in_section = line[3:].strip() == YAML_SECTION
    return None


def check_pair(md_lines: list[str], meta: dict[str, str], errors: list[str]) -> None:
    """HANDOFF.md 와 HANDOFF.yaml 이 같은 상태를 적었는지 — 둘은 함께 갱신한다."""
    f = fields(md_lines, FIELDS)
    md_branch = re.search(r"`([^`\s]+)`", f.get("브랜치", (0, ""))[1])
    md_head = re.search(r"`([0-9a-f]{7,40})`", f.get("HEAD", (0, ""))[1])
    pairs = [("작성", f.get("작성", (0, ""))[1], meta.get("written_at"), "written_at"),
             ("브랜치", md_branch.group(1) if md_branch else "", meta.get("branch"), "branch"),
             ("HEAD", md_head.group(1) if md_head else "", meta.get("head"), "head")]
    for name, md_v, y_v, key in pairs:
        if md_v and y_v and md_v != y_v and not (name == "HEAD" and (md_v.startswith(y_v) or y_v.startswith(md_v))):
            errors.append(f"HANDOFF.md 의 {name}({md_v}) 과 HANDOFF.yaml 의 meta.{key}({y_v}) 가 다르다 — 둘은 함께 갱신한다")


def check_pointer(lines: list[str], errors: list[str]) -> None:
    f = fields(lines, POINTER_FIELDS)
    for name in POINTER_FIELDS:
        if name not in f or not f[name][1]:
            errors.append(f"포인터 필드 `{name}` 이 없거나 비어 있다")
    for name in ("현재 핸드오프", "전체 목록"):
        if name in f and f[name][1] and not re.search(r"https?://", f[name][1]):
            errors.append(f"줄 {f[name][0]}: `{name}` 는 URL 이어야 한다")
    if "작성" in f and f["작성"][1] and not TS.match(f["작성"][1]):
        errors.append(f"줄 {f['작성'][0]}: 작성 시각이 YYYY-MM-DD HH:MM:SS.mmm 형식이 아니다")
    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.startswith("```"):
            in_fence = not in_fence
            errors.append(f"줄 {i}: 포인터에 코드블록을 두지 않는다 — 본문은 이슈에 있다")
        elif line.startswith("## "):
            errors.append(f"줄 {i}: 포인터에 본문 섹션(`{line.strip()}`)을 두지 않는다 — 본문은 이슈에 있다")
    if sum(1 for l in lines if l.strip()) > 15:
        errors.append("포인터가 15줄을 넘는다 — URL·시각·요약·목록 링크만 남긴다")


def git(repo: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr.strip().splitlines() or ["git 실패"])[-1])
    return r.stdout.strip()


def git_ok(repo: str, *args: str) -> bool:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True).returncode == 0


def verify_git(f: dict, repo: str, errors: list[str], warnings: list[str]) -> None:
    git(repo, "rev-parse", "--git-dir")  # 레포가 아니면 RuntimeError → 도구 오류
    bm = re.search(r"`([^`\s]+)`", f.get("브랜치", (0, ""))[1])
    hm = re.search(r"`([0-9a-f]{7,40})`", f.get("HEAD", (0, ""))[1])
    if not bm or not hm:
        errors.append("--verify-git: 브랜치·HEAD 를 본문에서 읽지 못했다")
        return
    branch, sha = bm.group(1), hm.group(1)
    if not git_ok(repo, "cat-file", "-e", f"{sha}^{{commit}}"):
        errors.append(f"기록한 HEAD {sha} 커밋이 이 레포에 없다")
        return
    tip = next((git(repo, "rev-parse", ref) for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}")
                if git_ok(repo, "rev-parse", "--verify", "-q", ref)), None)
    if tip is None:
        errors.append(f"기록한 브랜치 {branch} 가 로컬·origin 어디에도 없다")
        return
    if tip.startswith(sha):
        return
    if git_ok(repo, "merge-base", "--is-ancestor", sha, tip):
        n = git(repo, "rev-list", "--count", f"{sha}..{tip}")
        warnings.append(f"브랜치 {branch} 가 기록한 HEAD 보다 {n}커밋 앞서 있다 — 기록이 낡았다")
    else:
        errors.append(f"기록한 HEAD {sha} 가 브랜치 {branch} 의 조상이 아니다 (되감겼거나 갈라졌다)")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", help="검사할 파일, - 는 stdin")
    ap.add_argument("--as-file", action="store_true", help="레포의 HANDOFF.md 로 본다")
    ap.add_argument("--verify-git", metavar="REPO")
    ap.add_argument("--yaml", action="store_true", help="HANDOFF.yaml(기계 판독용 짝 파일)로 본다")
    ap.add_argument("--pair", metavar="HANDOFF_MD", help="--yaml 과 함께: 짝인 HANDOFF.md 와 상태가 같은지 본다")
    args = ap.parse_args(argv)
    try:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"오류: 입력을 읽지 못했다 ({e})", file=sys.stderr)
        return 2
    lines = text.splitlines()
    errors: list[str] = []
    warnings: list[str] = []
    first = next((l for l in lines if l.strip()), "")
    f = {}
    if not text.strip():
        errors.append("내용이 비어 있다")
    elif args.yaml:
        meta = check_yaml(lines, errors)
        common(lines, errors)
        f = {"브랜치": (0, f"`{meta['branch']}`"), "HEAD": (0, f"`{meta['head']}`")} if len(meta) == len(YAML_META) else {}
        if args.pair:
            try:
                check_pair(Path(args.pair).read_text(encoding="utf-8").splitlines(), meta, errors)
            except (OSError, UnicodeDecodeError) as e:
                print(f"오류: 짝 파일을 읽지 못했다 ({e})", file=sys.stderr)
                return 2
    elif first.startswith("# HANDOFF (포인터)"):
        check_pointer(lines, errors)
        common(lines, errors)
    else:
        if not re.match(r"#{1,2} (HANDOFF — |착수 메모 — )", first):
            errors.append("첫 제목이 `# HANDOFF — <요약>` 또는 `## 착수 메모 — <날짜>` 가 아니다")
        f = check_body(lines, errors)
        common(lines, errors)
        block = yaml_block(lines)
        if block:
            check_pair(lines, check_yaml(block[1], errors, offset=block[0]), errors)
        elif YAML_SECTION in sections(lines):
            errors.append(f"`## {YAML_SECTION}` 섹션에 닫힌 ```yaml 블록이 없다 — 블록을 채우거나 섹션을 지운다")
        if args.as_file and f.get("이슈", (0, ""))[1].startswith("http"):
            errors.append("트래커 이슈가 있는데 HANDOFF.md 에 본문이 있다 — 인프라가 있으면 포인터만 둔다")
    if args.verify_git:
        try:
            verify_git(f, args.verify_git, errors, warnings)
        except (RuntimeError, OSError) as e:
            print(f"오류: git 대조를 하지 못했다 ({e})", file=sys.stderr)
            return 2
    for e in errors:
        print(f"위반: {e}")
    for w in warnings:
        print(f"경고: {w}")
    print(f"위반 {len(errors)}건, 경고 {len(warnings)}건")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
