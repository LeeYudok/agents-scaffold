#!/usr/bin/env python3
"""dev 서버를 띄우고 실제로 응답하는지까지 확인한다 (이슈 #138).

"서버를 기동했다"를 프로세스 생존으로 판정하면 거의 항상 틀린다 — Next.js도
Vite도 포트를 잡기 전에 프로세스가 먼저 살아 있고, 빌드 에러가 나도 프로세스는
남는다. 사용자에게 URL 을 알려 주기 전에 그 URL 이 실제로 HTTP 를 돌려주는지,
핵심 라우트가 404 가 아닌지까지 확인하는 것이 이 스크립트의 역할이다.

포트 충돌도 여기서 끝낸다. 3000·5173 은 다른 세션이 이미 쓰고 있는 경우가
흔하고, 그때 Next.js 는 조용히 다음 포트로 옮겨 가므로 **에이전트가 안내한
URL 과 실제 URL 이 어긋난다**. 비어 있는 포트를 먼저 골라 명령에 주입하고,
확인된 포트만 보고한다.

stdlib 만 사용한다.

사용법:
    python3 scripts/serve_and_check.py --cmd "pnpm dev -- --port {port}" \
        [--dir <프로젝트>] [--port 3000] [--route / --route /order] \
        [--timeout 90] [--keep]

    --cmd 안의 `{port}` 는 확정된 포트로 치환된다. 자리표시자가 없으면 환경변수
    PORT 로만 전달되므로, 프레임워크가 PORT 를 읽지 않는다면(예: Vite) 반드시
    `{port}` 를 쓴다.

종료 코드: 헬스체크까지 통과하면 0, 기동·응답 실패면 1, 인자 문제면 2.
"""
import argparse
import contextlib
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

#: 프레임워크 관례 포트. 비어 있지 않으면 그 다음 빈 포트로 옮긴다.
DEFAULT_PORTS = {"next": 3000, "vite": 5173}
#: dev 서버는 첫 요청에서 컴파일한다. 이 시간은 그 컴파일까지 포함한 값이다.
DEFAULT_TIMEOUT = 90.0
POLL_INTERVAL = 0.5


def port_is_free(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def pick_port(preferred, span=20):
    """선호 포트가 비었으면 그대로, 아니면 그 위에서 빈 포트를 찾는다."""
    for candidate in range(preferred, preferred + span):
        if port_is_free(candidate):
            return candidate
    raise RuntimeError(
        f"{preferred}~{preferred + span - 1} 에 빈 포트가 없다 — 남은 dev 서버를 정리할 것")


def probe(url, timeout=3.0):
    """(status, error) 를 돌려준다. 연결 자체가 안 되면 status 는 None."""
    request = urllib.request.Request(url, headers={"User-Agent": "serve-and-check"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, None
    except urllib.error.HTTPError as exc:
        # 404·500 도 "서버는 살아서 응답한다" 는 신호다. 판정은 호출부가 한다.
        return exc.code, None
    except Exception as exc:  # URLError, socket.timeout, ConnectionReset 등
        return None, str(exc)


def wait_for_ready(url, deadline, is_alive=lambda: True, sleep=time.sleep):
    """서버가 HTTP 를 돌려줄 때까지 기다린다. (status, 마지막오류) 반환.

    프로세스가 먼저 죽으면 기다릴 이유가 없다 — is_alive 로 즉시 빠져나온다.
    타임아웃 전체를 죽은 프로세스에 쓰는 것이 이 계열 스크립트의 흔한 낭비다.
    """
    last = "요청을 한 번도 보내지 못했다"
    while time.monotonic() < deadline:
        if not is_alive():
            return None, "dev 서버 프로세스가 먼저 종료됐다"
        status, error = probe(url)
        if status is not None:
            return status, None
        last = error
        sleep(POLL_INTERVAL)
    return None, last


def launch(command, port, cwd):
    """dev 서버를 별도 세션으로 띄운다. 자식까지 한 번에 정리하기 위해서다."""
    resolved = command.replace("{port}", str(port))
    env = dict(os.environ, PORT=str(port), BROWSER="none")
    return resolved, subprocess.Popen(
        shlex.split(resolved), cwd=str(cwd), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        start_new_session=True)


def stop(process):
    """프로세스 그룹째 정리한다. dev 서버는 자식(esbuild·swc)을 남긴다."""
    if process.poll() is not None:
        return
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)


def tail(process, limit=40):
    """죽은 서버의 마지막 출력. 원인을 추측하지 않고 원문을 보여 준다."""
    if process.stdout is None:
        return ""
    with contextlib.suppress(Exception):
        return "\n".join(process.stdout.read().splitlines()[-limit:])
    return ""


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="dev 서버 기동 + HTTP 헬스체크")
    parser.add_argument("--cmd", required=True,
                        help='dev 명령. `{port}` 는 확정 포트로 치환된다')
    parser.add_argument("--dir", default=".", help="프로젝트 디렉터리")
    parser.add_argument("--port", type=int, default=DEFAULT_PORTS["next"],
                        help="선호 포트. 사용 중이면 위쪽 빈 포트로 옮긴다")
    parser.add_argument("--route", action="append", default=[],
                        help="추가로 확인할 경로. 여러 번 줄 수 있다")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="첫 응답까지 기다릴 초")
    parser.add_argument("--keep", action="store_true",
                        help="확인 후에도 서버를 남긴다 (PID 와 종료 방법을 출력)")
    args = parser.parse_args(argv)

    cwd = Path(args.dir).resolve()
    if not cwd.is_dir():
        print(f"오류: 디렉터리가 없다 — {cwd}", file=sys.stderr)
        return 2
    try:
        port = pick_port(args.port)
    except RuntimeError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    if port != args.port:
        print(f"알림: {args.port} 가 사용 중이라 {port} 로 띄운다")

    base = f"http://127.0.0.1:{port}"
    resolved, process = launch(args.cmd, port, cwd)
    print(f"기동: {resolved} (cwd={cwd})")
    failed = False
    try:
        status, error = wait_for_ready(
            base + "/", time.monotonic() + args.timeout,
            is_alive=lambda: process.poll() is None)
        if status is None:
            print(f"  X 헬스체크 실패: {error}")
            output = tail(process)
            if output:
                print("  --- dev 서버 출력 ---")
                print("  " + output.replace("\n", "\n  "))
            return 1
        print(f"  ok {base}/ → HTTP {status}")
        if status >= 500:
            print("  X 루트가 서버 오류를 돌려준다 — 빌드 에러를 먼저 확인할 것")
            failed = True
        for route in args.route:
            path = route if route.startswith("/") else "/" + route
            code, error = probe(base + path, timeout=15)
            if code is None:
                print(f"  X {path} → 응답 없음 ({error})")
                failed = True
            elif code >= 400:
                print(f"  X {path} → HTTP {code}")
                failed = True
            else:
                print(f"  ok {path} → HTTP {code}")
    finally:
        if args.keep and not failed:
            print(f"  서버를 남긴다 — URL {base} · PID {process.pid} · "
                  f"종료 `kill -TERM -{process.pid}`")
        else:
            stop(process)
    print(f"  => 헬스체크 {'실패' if failed else '통과'} ({base})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
