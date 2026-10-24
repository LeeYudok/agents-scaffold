#!/usr/bin/env python3
"""세션 녹음 보조 도구 (stdlib only). SKILL.md 의 인라인 셸을 옮긴 것이다.

    session_ctl.py check-tools
    session_ctl.py new <기준디렉터리>
    session_ctl.py glossary [--project-dir DIR]
    session_ctl.py run <세션디렉터리> <이름> -- <명령...>
    session_ctl.py stop <세션디렉터리>
    session_ctl.py delta <transcript> <오프셋>

원칙은 하나다. **이 세션이 기록한 PID 에만 신호를 보낸다.** pkill -f 처럼 이름으로
찾지 않는다 — 같은 머신의 다른 녹음까지 죽는다. PID 파일이 낡아 다른 프로세스가
그 번호를 쓰고 있을 수 있으므로, 신호 전에 명령줄이 기대한 도구인지도 확인한다.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
MODEL = Path("~/models/whisper/ggml-large-v3-turbo.bin")

# 이름 -> (종료 신호, 명령줄에 있어야 하는 도구). ffmpeg 는 SIGINT 라야 마무리 쓰기가 일어난다.
STOP_PLAN = {"whisper": (signal.SIGTERM, "whisper-stream"), "ffmpeg": (signal.SIGINT, "ffmpeg")}

# 무음 구간에서 whisper 가 지어내는 자막풍 문장. 줄 전체가 이것일 때만 거른다.
HALLUCINATION = re.compile(
    r"^\s*-?\s*(감사합니다|다음 영상에서 만나요|시청해주셔서 감사합니다|-끝-|- 네\.|고춧가루|양념장.*)\s*!?\.?\s*$")


def check_tools(path: str | None = None) -> int:
    """whisper-stream 과 모델이 없으면 1, ffmpeg 만 없으면 0(전사만으로 진행)."""
    ok = True
    if shutil.which("whisper-stream", path=path):
        print("whisper-stream: 있음")
    else:
        print("whisper-stream: 없음 — 설치 여부를 사용자에게 먼저 묻는다")
        ok = False
    model = MODEL.expanduser()
    if model.is_file():
        print(f"모델: 있음 ({model})")
    else:
        print(f"모델: 없음 ({MODEL}) — 경로를 사용자에게 확인한다. 임의로 내려받지 않는다")
        ok = False
    if shutil.which("ffmpeg", path=path):
        print("ffmpeg: 있음")
    else:
        print("ffmpeg: 없음 — 설치를 원치 않으면 전사만으로 진행한다 (오디오 재청취·재전사 불가)")
    return 0 if ok else 1


def new_session(base: Path, now: time.struct_time | None = None) -> Path:
    """session-<YYYY-MM-DD_HHMM>. 같은 분에 또 만들면 -2, -3 을 붙여 파일이 섞이지 않게 한다."""
    stamp = time.strftime("%Y-%m-%d_%H%M", now or time.localtime())
    path = base / f"session-{stamp}"
    n = 2
    while path.exists():
        path = base / f"session-{stamp}-{n}"
        n += 1
    path.mkdir(parents=True)
    return path


def glossary_terms(project_dir: Path) -> str:
    """공용 + 개인 전역 + 프로젝트 사전을 합쳐 정식표기만 콤마로 잇는다."""
    files = sorted((SKILL / "resources" / "glossary.d").glob("*.txt"))
    files += sorted((Path.home() / ".config" / "session-recording" / "glossary.d").glob("*.txt"))
    files += [project_dir / "glossary.txt"]
    terms: list[str] = []
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue  # 없는 사전은 건너뛴다
        for line in lines:
            if not line.strip() or line.startswith("#"):
                continue
            term = line.split("|")[0].strip()
            if term:
                terms.append(term)
    return ",".join(terms)


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def command_of(pid: int) -> str:
    r = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
    return r.stdout.strip()


def stop_pidfile(pidfile: Path, sig: int, expect: str, wait: float = 10.0) -> str:
    """pid 파일의 프로세스에만 sig 를 보낸다. 결과를 한 단어로 돌려준다.

    no-pidfile | bad-pidfile | already-exited | not-ours | stopped | still-running
    """
    if not pidfile.is_file():
        return "no-pidfile"
    try:
        pid = int(pidfile.read_text().strip())
    except ValueError:
        return "bad-pidfile"
    if pid <= 1 or not pid_alive(pid):
        return "already-exited"
    if expect not in command_of(pid):
        return "not-ours"  # PID 가 재사용됐다. 남의 프로세스는 건드리지 않는다
    os.kill(pid, sig)
    deadline = time.time() + wait
    while time.time() < deadline:
        if not pid_alive(pid) or "Z" in subprocess.run(
                ["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True).stdout:
            return "stopped"
        time.sleep(0.1)
    return "still-running"


def run_tracked(session: Path, name: str, cmd: list[str]) -> int:
    """세션 디렉터리에서 cmd 를 띄우고 <name>.pid 에 PID 를 적은 뒤 끝나길 기다린다.

    런타임의 백그라운드 실행 수단(Claude Code 는 run_in_background)이 이 래퍼를 추적한다.
    래퍼가 신호를 받으면 자식에게 그대로 넘긴다.
    """
    if not session.is_dir():
        print(f"세션 디렉터리가 없다: {session}", file=sys.stderr)
        return 2
    try:
        child = subprocess.Popen(cmd, cwd=session)
    except OSError as e:
        print(f"실행하지 못했다: {cmd[0]} ({e.strerror})", file=sys.stderr)
        return 127
    (session / f"{name}.pid").write_text(f"{child.pid}\n")
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda signum, _f: child.send_signal(signum))
    return child.wait()


def delta(transcript: Path, offset: int) -> tuple[str, int]:
    """바이트 오프셋(1 부터) 이후만 읽어 환각 줄을 거른다. (텍스트, 다음 오프셋)."""
    data = transcript.read_bytes()
    chunk = data[max(offset, 1) - 1:].decode("utf-8", errors="replace")
    kept = [ln for ln in chunk.splitlines() if not HALLUCINATION.match(ln)]
    return "\n".join(kept) + ("\n" if kept else ""), len(data) + 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-tools")
    p = sub.add_parser("new"); p.add_argument("base")
    p = sub.add_parser("glossary"); p.add_argument("--project-dir", default=".")
    p = sub.add_parser("run"); p.add_argument("session"); p.add_argument("name")
    p.add_argument("command", nargs=argparse.REMAINDER)
    p = sub.add_parser("stop"); p.add_argument("session")
    p = sub.add_parser("delta"); p.add_argument("transcript"); p.add_argument("offset", type=int)
    a = ap.parse_args(argv)

    if a.cmd == "check-tools":
        return check_tools()
    if a.cmd == "new":
        print(new_session(Path(a.base)))
        return 0
    if a.cmd == "glossary":
        print(glossary_terms(Path(a.project_dir)))
        return 0
    if a.cmd == "run":
        cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
        if not cmd:
            print("실행할 명령이 없다", file=sys.stderr)
            return 2
        return run_tracked(Path(a.session), a.name, cmd)
    if a.cmd == "stop":
        session = Path(a.session)
        if not session.is_dir():
            print(f"세션 디렉터리가 없다: {session}", file=sys.stderr)
            return 2
        for name in ("whisper", "ffmpeg"):  # whisper 먼저, ffmpeg 는 SIGINT
            sig, expect = STOP_PLAN[name]
            print(f"{name}: {stop_pidfile(session / f'{name}.pid', sig, expect)}")
        return 0
    if a.cmd == "delta":
        t = Path(a.transcript)
        if not t.is_file():
            print(f"전사 파일이 없다: {t}", file=sys.stderr)
            return 2
        text, nxt = delta(t, a.offset)
        sys.stdout.write(text)
        print(f"next-offset={nxt}", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
