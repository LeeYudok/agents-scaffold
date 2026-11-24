"""한 PC 의 Claude Code 로그인을 등록한 호스트에 맞춘다 (stdlib only, Python 3.9+).

    python3 sync_auth.py                 # 등록한 호스트 전부에 맞춘다
    python3 sync_auth.py --verify        # 맞춘 뒤 호스트마다 claude -p 로 확인한다
    python3 sync_auth.py --host h1 --dry-run

원본은 지금 PC 의 로그인이다. macOS 는 키체인 `Claude Code-credentials`,
리눅스는 `~/.claude/.credentials.json` 이다. 옮기는 값은 `claudeAiOauth`
하나이고, 대상 파일의 다른 키(MCP 서버 로그인 등)는 그대로 둔다.

토큰은 ssh 의 표준입력으로만 넘긴다. 화면·argv·로그에 찍지 않는다.
호스트 목록은 저장소 밖 로컬 파일이다(`DEFAULT_HOSTS_FILE`).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

KEYCHAIN_SERVICE = "Claude Code-credentials"
LINUX_CREDENTIALS = Path("~/.claude/.credentials.json")
DEFAULT_HOSTS_FILE = Path("~/.config/yd-claude-auth-sync/hosts")
HOSTS_ENV = "YD_CLAUDE_AUTH_HOSTS"
OAUTH_KEY = "claudeAiOauth"
REQUIRED_FIELDS = ("accessToken", "refreshToken")
VERIFY_PROMPT = "reply with exactly: pong"
# 원격 셸은 비대화형이라 ~/.local/bin 같은 사용자 경로가 PATH 에 없을 수 있다
REMOTE_PATH = "$HOME/.local/bin:$HOME/.npm-global/bin:$HOME/bin:/usr/local/bin:$PATH"

TOKEN_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")

# 원격에서 도는 병합 스크립트. 새 값은 stdin 으로 받는다. 출력은 상태 한 줄뿐이다.
MERGE_SCRIPT = r"""
import json, os, shutil, sys
ts = sys.argv[1]
new = json.load(sys.stdin)
d = os.path.expanduser("~/.claude")
os.makedirs(d, mode=0o700, exist_ok=True)
f = os.path.join(d, ".credentials.json")
cur = {}
if os.path.exists(f):
    try:
        with open(f) as fh:
            cur = json.load(fh)
    except ValueError:
        cur = {}
if cur.get("claudeAiOauth") == new["claudeAiOauth"]:
    print("same")
    sys.exit(0)
if os.path.exists(f):
    shutil.copy2(f, f + ".bak-" + ts)
cur["claudeAiOauth"] = new["claudeAiOauth"]
tmp = f + ".tmp-" + ts
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as fh:
    json.dump(cur, fh)
os.chmod(tmp, 0o600)
os.replace(tmp, f)
print("updated")
"""

Runner = Callable[[str, str, "bytes | None"], "tuple[int, str]"]


def redact(text: str) -> str:
    """혹시 섞여 나온 토큰 문자열을 가린다. 출력 경로의 마지막 방어선이다."""
    return TOKEN_RE.sub("sk-ant-<redacted>", text)


def hosts_file() -> Path:
    return Path(os.environ.get(HOSTS_ENV) or DEFAULT_HOSTS_FILE).expanduser()


def parse_hosts(text: str) -> list[str]:
    """한 줄에 ssh 별칭 하나. `#` 뒤와 빈 줄은 무시하고 중복은 한 번만 남긴다."""
    seen: list[str] = []
    for line in text.splitlines():
        name = line.split("#", 1)[0].strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def load_hosts(path: Path) -> list[str]:
    if not path.is_file():
        raise SystemExit(
            f"오류: 호스트 목록이 없다 — {path}\n"
            f"한 줄에 ssh 별칭 하나씩 적어 만든다(권한 600). 경로는 ${HOSTS_ENV} 로 바꿀 수 있다."
        )
    hosts = parse_hosts(path.read_text(encoding="utf-8"))
    if not hosts:
        raise SystemExit(f"오류: 호스트 목록이 비었다 — {path}")
    return hosts


def read_source_blob(platform: str = sys.platform) -> str:
    """지금 PC 에 저장된 Claude Code 인증 원문(JSON 문자열)."""
    if platform == "darwin":
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise SystemExit(f"오류: 키체인에 '{KEYCHAIN_SERVICE}' 가 없다. 이 PC 에서 먼저 claude 로 로그인한다")
        return proc.stdout.strip()
    path = LINUX_CREDENTIALS.expanduser()
    if not path.is_file():
        raise SystemExit(f"오류: {path} 가 없다. 이 PC 에서 먼저 claude 로 로그인한다")
    return path.read_text(encoding="utf-8")


def extract_payload(blob: str) -> tuple[str, dict]:
    """옮길 JSON 과 출력해도 되는 요약을 돌려준다. 요약에는 토큰이 없다."""
    try:
        data = json.loads(blob)
    except ValueError as exc:
        raise SystemExit("오류: 인증 원문이 JSON 이 아니다") from exc
    oauth = data.get(OAUTH_KEY) if isinstance(data, dict) else None
    if not isinstance(oauth, dict) or not all(oauth.get(k) for k in REQUIRED_FIELDS):
        raise SystemExit(f"오류: 인증 원문에 {OAUTH_KEY}.{'/'.join(REQUIRED_FIELDS)} 가 없다")
    expires = oauth.get("expiresAt")
    summary = {
        "subscription": oauth.get("subscriptionType") or "?",
        "expires": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expires / 1000)) if isinstance(expires, (int, float)) else "?",
    }
    return json.dumps({OAUTH_KEY: oauth}), summary


def merge_command(ts: str) -> str:
    """원격에서 실행할 명령. 토큰은 들어 있지 않다(stdin 으로 간다)."""
    return f"python3 -c {shlex.quote(MERGE_SCRIPT)} {shlex.quote(ts)}"


def verify_command() -> str:
    return (
        f'PATH="{REMOTE_PATH}"; command -v claude >/dev/null || {{ echo "claude-missing"; exit 0; }}; '
        f"timeout 120 claude -p {shlex.quote(VERIFY_PROMPT)} 2>&1 | tail -n 3"
    )


def ssh_runner(host: str, script: str, stdin: bytes | None) -> tuple[int, str]:
    proc = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host, script],
        input=stdin, capture_output=True,
    )
    out = (proc.stdout + proc.stderr).decode("utf-8", "replace").strip()
    return proc.returncode, redact(out)


def sync_host(host: str, payload: str, ts: str, run: Runner) -> str:
    code, out = run(host, merge_command(ts), payload.encode())
    status = out.splitlines()[-1] if out else ""
    if code != 0 or status not in ("same", "updated"):
        return f"failed (exit {code}) {out[-200:]}".strip()
    return status if status == "same" else f"updated (backup .credentials.json.bak-{ts})"


def verify_host(host: str, run: Runner) -> str:
    code, out = run(host, verify_command(), None)
    if "claude-missing" in out:
        return "claude 없음"
    if code == 0 and "pong" in out.lower():
        return "ok"
    return f"failed (exit {code}) {out[-200:]}".strip()


def main(argv: list[str] | None = None, run: Runner = ssh_runner, blob: str | None = None) -> int:
    ap = argparse.ArgumentParser(description="Claude Code 로그인을 등록한 호스트에 맞춘다")
    ap.add_argument("--host", action="append", help="이 호스트만 대상으로 한다(여러 번 가능)")
    ap.add_argument("--hosts-file", type=Path, help=f"호스트 목록 파일(기본 ${HOSTS_ENV} 또는 {DEFAULT_HOSTS_FILE})")
    ap.add_argument("--verify", action="store_true", help="맞춘 뒤 claude -p 응답을 확인한다")
    ap.add_argument("--verify-only", action="store_true", help="쓰지 않고 확인만 한다")
    ap.add_argument("--dry-run", action="store_true", help="대상과 원본 요약만 보여 준다")
    args = ap.parse_args(argv)

    hosts = args.host or load_hosts((args.hosts_file or hosts_file()).expanduser())
    payload, summary = extract_payload(blob if blob is not None else read_source_blob())
    print(f"원본: 이 PC 로그인 (구독 {summary['subscription']}, access 만료 {summary['expires']})")

    if args.dry_run:
        for h in hosts:
            print(f"  {h}: 대상")
        return 0

    ts = time.strftime("%Y%m%d%H%M%S")
    failed = 0
    for h in hosts:
        result = "skip" if args.verify_only else sync_host(h, payload, ts, run)
        line = f"  {h}: {result}"
        if result.startswith("failed"):
            failed += 1
        elif args.verify or args.verify_only:
            v = verify_host(h, run)
            line += f" / verify {v}"
            failed += v != "ok"
        print(redact(line))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
