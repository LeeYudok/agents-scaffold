#!/usr/bin/env python3
"""Codex CLI status line — ~/.codex/config.toml 의 [tui] status_line 키 하나만 관리한다.

Codex CLI 는 Claude Code 와 달리 외부 명령을 실행하는 status line 이 없고,
[tui] 테이블의 status_line 에 내장 항목 ID 배열을 적는 방식만 지원한다.
그래서 스크립트를 배치하는 대신 이 키를 Claude statusline 과 같은 순서로 맞춘다.

사용법 (install.sh / uninstall.sh 가 호출):
  status-line.py check     # 쓰지 않고 apply 가 가능한지만 검사 (깨진 TOML·미지원 표기면 exit 1)
  status-line.py apply     # status_line 키를 WANT 로 맞춤. 최초 1회 설치 전 상태를 ~/.config/dotfiles/backup 에 기록
  status-line.py restore   # 기록해 둔 설치 전 값으로 되돌림 (없던 키면 제거)

python3 표준 라이브러리에는 TOML writer 가 없어 status_line 키의 줄만 교체한다 — 다른 테이블·키·주석은
그대로 둔다. tomllib(3.11+)이 있으면 쓰기 전에 결과를 다시 파싱해 status_line 외에는 바뀌지 않았는지 확인한다.
"""
import copy, os, re, sys, tempfile

try:
    import tomllib
except ImportError:          # python < 3.11 — 검증 없이 줄 단위 편집만 한다
    tomllib = None

# codex-cli 가 인식하는 항목 중 상시 유효한 것을 모두 싣되, 폭이 좁으면 뒤에서부터 잘리므로 중요한 것을 앞에 둔다.
#   위치(경로) → 비용(크레딧) → 한도(주간·5시간) → 모델 → 컨텍스트 → 브랜치 → 부가 정보(입출력 토큰·fast·버전)
# 비용·크레딧은 Enterprise 워크스페이스에서만 값이 오고 없으면 생략된다 — 그 밖의 로그인은 codex/cost-hook.py 가
# 턴마다 API 환산 비용을 따로 보여준다.
# 지원 ID 전체: app-name, project-name, current-dir, run-state, thread-title, thread-name, git-branch,
#   context-remaining, context-used, five-hour-limit, weekly-limit, thread-credits, estimated-thread-cost,
#   codex-version, used-tokens, total-input-tokens, total-output-tokens, thread-id, fast-mode,
#   model-with-reasoning, task-progress (codex-cli 0.156.0 기준)
WANT = [
    "current-dir",
    "estimated-thread-cost",
    "thread-credits",
    "weekly-limit",
    "five-hour-limit",
    "model-with-reasoning",
    "context-used",
    "git-branch",
    "total-input-tokens",
    "total-output-tokens",
    "fast-mode",
    "codex-version",
]

HOME = os.path.expanduser("~")
CONFIG = os.path.join(HOME, ".codex", "config.toml")
BACKUP = os.path.join(HOME, ".config", "dotfiles", "backup")
ORIG = os.path.join(BACKUP, "codex-config.toml.orig")
ABSENT = os.path.join(BACKUP, "codex-config.toml.absent")

TUI_HEADER = re.compile(r"^\s*\[\s*tui\s*\]\s*(#.*)?$")
ANY_HEADER = re.compile(r"^\s*\[{1,2}[^\[\]]+\]{1,2}\s*(#.*)?$")
KEY = re.compile(r"^\s*status_line\s*=")
UNSUPPORTED = re.compile(r"^\s*tui\s*(\.|=)")   # tui.status_line = ... / tui = { ... }


class Abort(Exception):
    pass


def bracket_delta(line):
    """문자열·주석 밖의 '[' 와 ']' 개수 차이 — 여러 줄 배열의 끝을 찾는 데 쓴다."""
    depth, quote, i = 0, None, 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#":
            break
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        i += 1
    return depth


def locate(lines):
    """(tui 헤더 줄, 테이블 끝, status_line 시작, status_line 끝) — 없으면 None. 끝은 exclusive."""
    hdr = next((i for i, l in enumerate(lines) if TUI_HEADER.match(l)), None)
    if hdr is None:
        return None, None, None, None
    end, key_start, key_end, depth, i = len(lines), None, None, 0, hdr + 1
    while i < len(lines):
        line = lines[i]
        if depth == 0 and ANY_HEADER.match(line):
            end = i
            break
        if depth == 0 and key_start is None and KEY.match(line):
            key_start = i
            depth = bracket_delta(line.split("=", 1)[1])
            while depth > 0 and i + 1 < len(lines):
                i += 1
                depth += bracket_delta(lines[i])
            key_end, depth = i + 1, 0
        else:
            depth = max(0, depth + bracket_delta(line))
        i += 1
    return hdr, end, key_start, key_end


def parse(text, path):
    if tomllib is None:
        return None
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise Abort(f"{path} 이 올바른 TOML 이 아님 ({e}) — 원본을 건드리지 않고 중단")


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def atomic_write(path, text):
    """같은 디렉터리의 임시 파일에 쓰고 os.replace 로 교체 — 중단돼도 원본은 온전. 기존 mode 보존."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    mode = os.stat(path).st_mode & 0o777 if os.path.exists(path) else 0o600
    fd, tmp = tempfile.mkstemp(prefix=".config.", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def verify(old, new_text, status_line):
    """수정 결과가 status_line 외에는 원본과 같은지 확인 (tomllib 있을 때만)."""
    if old is None:
        return
    expected = copy.deepcopy(old)
    if status_line is None:
        expected.get("tui", {}).pop("status_line", None)
    else:
        expected.setdefault("tui", {})["status_line"] = status_line
    new = parse(new_text, "수정 결과")
    for d in (expected, new):
        if d.get("tui") == {}:
            del d["tui"]
    if new != expected:
        raise Abort(f"{CONFIG} 을 안전하게 편집할 수 없음 (status_line 외의 값이 바뀜) — 원본을 건드리지 않고 중단")


def plan_apply(text):
    """(새 내용, 바뀌었는지). 편집할 수 없으면 Abort."""
    old = parse(text, CONFIG)
    if old is not None and not isinstance(old.get("tui", {}), dict):
        raise Abort(f"{CONFIG} 의 tui 가 테이블이 아님 — 원본을 건드리지 않고 중단")
    if old is not None and old.get("tui", {}).get("status_line") == WANT:
        return text, False
    lines = text.splitlines(keepends=True)
    hdr, _, ks, ke = locate(lines)
    if hdr is None and (any(UNSUPPORTED.match(l) for l in lines) or (old or {}).get("tui")):
        raise Abort(f"{CONFIG} 의 tui 설정이 [tui] 테이블 표기가 아님 — [tui] 로 바꾼 뒤 다시 실행 (원본은 건드리지 않았음)")
    eol = "\r\n" if "\r\n" in text else "\n"
    want_line = "status_line = [" + ", ".join(f'"{x}"' for x in WANT) + "]" + eol
    if ks is not None:
        lines[ks:ke] = [want_line]
    elif hdr is not None:
        if not lines[hdr].endswith(("\n", "\r")):
            lines[hdr] += eol
        lines.insert(hdr + 1, want_line)
    else:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += eol
        if lines:
            lines.append(eol)
        lines += ["[tui]" + eol, want_line]
    new_text = "".join(lines)
    verify(old, new_text, WANT)
    return new_text, new_text != text


def cmd_check():
    if os.path.exists(CONFIG):
        plan_apply(read(CONFIG))


def cmd_apply():
    existed = os.path.exists(CONFIG)
    text = read(CONFIG) if existed else ""
    new_text, changed = plan_apply(text)
    # 최초 1회: config.toml 유무와 이전 내용을 기록 (uninstall 복원용)
    if not os.path.exists(ORIG) and not os.path.exists(ABSENT):
        os.makedirs(BACKUP, exist_ok=True)
        if existed:
            atomic_write(ORIG, text)
        else:
            open(ABSENT, "w").close()
    if changed:
        atomic_write(CONFIG, new_text)
        print("[install] codex config.toml tui.status_line 키 갱신")
    else:
        print("[install] codex config.toml tui.status_line 이미 최신")


def cmd_restore():
    if not os.path.exists(ORIG) and not os.path.exists(ABSENT):
        return                       # install.sh 가 Codex 단계를 건너뛴 머신 — 손대지 않는다
    if not os.path.exists(CONFIG):
        print("[uninstall] codex config.toml 없음 — 건너뜀")
        return
    text = read(CONFIG)
    old = parse(text, CONFIG)
    orig_text = read(ORIG) if os.path.exists(ORIG) else ""
    orig_lines = orig_text.splitlines(keepends=True)
    ohdr, _, oks, oke = locate(orig_lines)
    prev_raw = orig_lines[oks:oke] if oks is not None else None
    lines = text.splitlines(keepends=True)
    hdr, end, ks, ke = locate(lines)
    eol = "\r\n" if "\r\n" in text else "\n"
    if prev_raw is not None:
        if not prev_raw[-1].endswith(("\n", "\r")):
            prev_raw[-1] += eol
        if ks is not None:
            lines[ks:ke] = prev_raw
        elif hdr is not None:
            lines[hdr + 1:hdr + 1] = prev_raw
        else:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += eol
            lines += ([eol] if lines else []) + ["[tui]" + eol] + prev_raw
        prev = (parse(orig_text, ORIG) or {}).get("tui", {}).get("status_line")
        msg = "codex config.toml tui.status_line 키를 설치 전 값으로 복원"
    else:
        if ks is not None:
            del lines[ks:ke]
            end -= ke - ks
            # install.sh 가 만든 [tui] 테이블이 비면 헤더와 그 앞의 빈 줄까지 제거
            if ohdr is None and not "".join(lines[hdr + 1:end]).strip():
                start = hdr - 1 if hdr > 0 and not lines[hdr - 1].strip() else hdr
                del lines[start:end]
        prev = None
        msg = "codex config.toml tui.status_line 키 제거 (다른 키는 유지)"
    new_text = "".join(lines)
    verify(old, new_text, prev)
    if new_text.rstrip() == orig_text.rstrip():
        new_text = orig_text         # 끝 공백까지 설치 전과 같게
    if os.path.exists(ABSENT) and not new_text.strip():
        os.remove(CONFIG)
        print("[uninstall] codex config.toml 삭제 (설치 전에는 없던 파일이고 남은 키 없음)")
    else:
        if new_text != text:
            atomic_write(CONFIG, new_text)
        print(f"[uninstall] {msg}")


if __name__ == "__main__":
    cmds = {"check": cmd_check, "apply": cmd_apply, "restore": cmd_restore}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit(f"사용법: {sys.argv[0]} check|apply|restore")
    try:
        cmds[sys.argv[1]]()
    except Abort as e:
        print(f"[codex] 오류: {e}", file=sys.stderr)
        sys.exit(1)
