"""serve_and_check.py 계약 테스트 (이슈 #138).

실제 dev 서버 대신 stdlib http.server 를 `--cmd` 로 띄운다 — Next.js/Vite 를
설치하지 않고도 "포트 선택 → 기동 → 첫 응답 대기 → 라우트 판정 → 정리"
전 경로가 그대로 돈다.
"""
import socket
import sys
import textwrap
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import serve_and_check as sac  # noqa: E402

SERVER = textwrap.dedent("""
    import os, sys
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            code = 200 if self.path in ("/", "/order") else 404
            self.send_response(code)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *a):
            pass

    HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
""")


def write_server(tmp):
    path = Path(tmp) / "fake_dev.py"
    path.write_text(SERVER, encoding="utf-8")
    return path


class TestPortSelection(unittest.TestCase):
    def test_free_port_is_used_as_is(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            free = probe.getsockname()[1]
        self.assertEqual(sac.pick_port(free), free)

    def test_busy_port_moves_up(self):
        """Next.js 는 포트가 막히면 조용히 옮겨 간다 — 우리가 먼저 정한다."""
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen(1)
            busy = taken.getsockname()[1]
            chosen = sac.pick_port(busy)
            self.assertNotEqual(chosen, busy)
            self.assertGreater(chosen, busy)

    def test_no_free_port_raises(self):
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen(1)
            busy = taken.getsockname()[1]
            with self.assertRaises(RuntimeError):
                sac.pick_port(busy, span=1)


class TestWaitForReady(unittest.TestCase):
    def test_dead_process_stops_waiting_immediately(self):
        """죽은 프로세스에 타임아웃 전체를 쓰지 않는다."""
        slept = []
        status, error = sac.wait_for_ready(
            "http://127.0.0.1:1/", deadline=sac.time.monotonic() + 60,
            is_alive=lambda: False, sleep=slept.append)
        self.assertIsNone(status)
        self.assertIn("먼저 종료", error)
        self.assertEqual(slept, [], "죽은 프로세스를 기다리며 잠들었다")

    def test_timeout_reports_last_error(self):
        status, error = sac.wait_for_ready(
            "http://127.0.0.1:1/", deadline=sac.time.monotonic() - 1,
            sleep=lambda _: None)
        self.assertIsNone(status)
        self.assertTrue(error)


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server = write_server(self.tmp.name)

    def cmd(self):
        return f"{sys.executable} {self.server} {{port}}"

    def test_healthy_server_passes_and_is_stopped(self):
        code = sac.main(["--cmd", self.cmd(), "--dir", self.tmp.name,
                         "--port", "38210", "--route", "/order", "--timeout", "20"])
        self.assertEqual(code, 0)
        self.assertTrue(sac.port_is_free(38210), "확인 후 서버를 정리하지 않았다")

    def test_missing_route_fails(self):
        """존재하지 않는 라우트는 404 다 — 프로세스 생존만 보면 통과했을 것이다."""
        code = sac.main(["--cmd", self.cmd(), "--dir", self.tmp.name,
                         "--port", "38220", "--route", "/nope", "--timeout", "20"])
        self.assertEqual(code, 1)

    def test_server_that_never_listens_fails(self):
        code = sac.main([
            "--cmd", f"{sys.executable} -c \"import sys;sys.exit(1)\"",
            "--dir", self.tmp.name, "--port", "38230", "--timeout", "20"])
        self.assertEqual(code, 1)

    def test_port_placeholder_is_substituted(self):
        resolved, process = sac.launch(f"{sys.executable} -c \"import sys\" {{port}}",
                                       4321, Path(self.tmp.name))
        self.addCleanup(sac.stop, process)
        self.assertIn("4321", resolved)
        self.assertNotIn("{port}", resolved)


if __name__ == "__main__":
    unittest.main()
