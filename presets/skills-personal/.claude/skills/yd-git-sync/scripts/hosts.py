"""호스트 접근 공통 부분 (stdlib only, Python 3.9+).

호스트 이름 `local` 은 이 맥(또는 지금 셸)을, 그 밖의 이름은 ssh 별칭을 뜻한다.
원격 명령은 `ssh <host> 'cd <repo> && ...'` 로 돈다. 저장소 경로는 호스트마다
`$HOME` 기준 상대 경로가 같다고 본다(`~/workspace/<forge>/<repo>`).
"""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

LOCAL = "local"


def local_root() -> Path:
    """지금 디렉터리가 속한 git 저장소의 루트."""
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True, capture_output=True, text=True,
    )
    return Path(out.stdout.strip())


def default_rel_path(root: Path) -> str:
    """로컬 저장소 경로를 `$HOME` 기준 상대 경로로 바꾼다."""
    home = Path.home().resolve()
    try:
        return str(root.resolve().relative_to(home))
    except ValueError as exc:
        raise SystemExit(f"오류: 저장소가 $HOME 아래에 없다 — {root}. --repo-path 로 지정한다") from exc


def shell_cmd(host: str, rel_path: str, script: str) -> list[str]:
    """`host` 의 저장소 루트에서 `script` 를 실행하는 argv."""
    inner = f"cd ~/{shlex.quote(rel_path)} && {script}"
    if host == LOCAL:
        return ["bash", "-c", inner]
    return ["ssh", "-o", "ConnectTimeout=10", host, inner]


def run(host: str, rel_path: str, script: str, stdin: bytes | None = None) -> bytes:
    proc = subprocess.run(shell_cmd(host, rel_path, script), input=stdin, capture_output=True)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"{host}: 명령 실패 (exit {proc.returncode}) — {err}")
    return proc.stdout


def local_path(rel_path: str) -> Path:
    return Path(os.path.expanduser("~")) / rel_path
