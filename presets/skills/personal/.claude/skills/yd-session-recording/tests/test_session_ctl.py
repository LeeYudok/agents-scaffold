"""session_ctl.py 를 더미 프로세스로 검증한다 (stdlib only, 이슈 #201).

whisper-stream 이나 ffmpeg 는 필요 없다. 신호는 이 테스트가 직접 띄운 python 자식에게만 간다.
"""

import contextlib
import importlib.util
import io
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "session_ctl.py"
spec = importlib.util.spec_from_file_location("session_ctl", SCRIPT)
m = importlib.util.module_from_spec(spec)
sys.modules["session_ctl"] = m
spec.loader.exec_module(m)

SLEEP = "import time; time.sleep(60)"
# SIGINT 를 받으면 마무리 표시를 남기고 끝난다. SIGTERM 은 기본 동작(표시 없이 죽음)이다.
FINALIZER = ("import signal, sys, time\n"
             "def h(*a):\n"
             "    open('finalized', 'w').write('ok'); sys.exit(0)\n"
             "signal.signal(signal.SIGINT, h)\n"
             "time.sleep(60)\n")


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.tmp = Path(self._t.name)
        self.procs = []
        self.addCleanup(self._reap)

    def _reap(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()

    def spawn(self, code, tag, cwd=None):
        """cmdline 에 tag 가 들어 있는 더미 자식을 띄운다."""
        p = subprocess.Popen([sys.executable, "-c", code, tag], cwd=cwd)
        self.procs.append(p)
        return p

    def pidfile(self, proc, name="whisper.pid"):
        f = self.tmp / name
        f.write_text(f"{proc.pid}\n")
        return f


class SessionDir(Base):
    def test_name_has_date_and_time(self):
        d = m.new_session(self.tmp)
        self.assertTrue(d.is_dir())
        self.assertRegex(d.name, r"^session-\d{4}-\d{2}-\d{2}_\d{4}$")

    def test_same_minute_does_not_reuse_directory(self):
        t = time.strptime("2026-10-04 09:30", "%Y-%m-%d %H:%M")
        a, b, c = (m.new_session(self.tmp, t) for _ in range(3))
        self.assertEqual([a.name, b.name, c.name],
                         ["session-2026-10-04_0930", "session-2026-10-04_0930-2",
                          "session-2026-10-04_0930-3"])


class Glossary(Base):
    def run_glossary(self, home, project):
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            return m.glossary_terms(project)

    def test_merges_three_layers_and_skips_comments(self):
        home, proj = self.tmp / "home", self.tmp / "proj"
        gd = home / ".config" / "session-recording" / "glossary.d"
        gd.mkdir(parents=True)
        proj.mkdir()
        (gd / "me.txt").write_text("# 주석\n\n쿠버네티스 | 쿠베르네티스 | 비고\n")
        (proj / "glossary.txt").write_text("독삼 | 독상,도삼 |\n")
        terms = self.run_glossary(home, proj).split(",")
        self.assertIn("애자일", terms)          # 스킬 내장 공용 사전
        self.assertIn("쿠버네티스", terms)      # 개인 전역
        self.assertIn("독삼", terms)            # 프로젝트
        self.assertNotIn("# 주석", terms)
        self.assertNotIn("쿠베르네티스", terms)  # 오인식 열은 프롬프트에 넣지 않는다
        self.assertNotIn("", terms)

    def test_missing_local_dictionaries_are_skipped(self):
        home, proj = self.tmp / "nohome", self.tmp / "noproj"
        home.mkdir()
        proj.mkdir()
        self.assertIn("애자일", self.run_glossary(home, proj))

    def test_builtin_dictionary_has_no_project_names(self):
        for f in (SKILL / "resources" / "glossary.d").glob("*.txt"):
            body = f.read_text(encoding="utf-8")
            self.assertNotRegex(body, r"(?i)jb|금융")


class Delta(Base):
    def write(self, text):
        f = self.tmp / "transcript.txt"
        f.write_bytes(text.encode("utf-8"))
        return f

    def test_hallucination_lines_are_dropped_and_real_speech_kept(self):
        f = self.write("오늘 안건은 배포다\n양념장을 만들어서\n감사합니다.\n"
                       "감사합니다 오늘 회의를 시작합니다\n- 네.\n")
        text, _ = m.delta(f, 1)
        self.assertEqual(text, "오늘 안건은 배포다\n감사합니다 오늘 회의를 시작합니다\n")

    def test_offset_is_byte_based_and_incremental(self):
        first = "한글 첫줄\n"
        f = self.write(first)
        _, nxt = m.delta(f, 1)
        self.assertEqual(nxt, len(first.encode("utf-8")) + 1)
        f.write_bytes(f.read_bytes() + "둘째 줄\n".encode("utf-8"))
        text, nxt2 = m.delta(f, nxt)
        self.assertEqual(text, "둘째 줄\n")
        self.assertEqual(nxt2, f.stat().st_size + 1)

    def test_nothing_new_returns_empty(self):
        f = self.write("끝\n")
        _, nxt = m.delta(f, 1)
        self.assertEqual(m.delta(f, nxt)[0], "")

    def test_cli_missing_file_exits_2(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "delta", str(self.tmp / "no.txt"), "1"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class Stop(Base):
    def test_stops_only_the_recorded_pid(self):
        mine = self.spawn(SLEEP, "whisper-stream")
        bystander = self.spawn(SLEEP, "whisper-stream")  # 같은 도구 이름이지만 기록된 PID 가 아니다
        res = m.stop_pidfile(self.pidfile(mine), signal.SIGTERM, "whisper-stream", wait=5)
        self.assertEqual(res, "stopped")
        mine.wait(timeout=5)
        self.assertIsNone(bystander.poll())

    def test_reused_pid_of_unrelated_process_is_not_signalled(self):
        other = self.spawn(SLEEP, "unrelated-job")
        res = m.stop_pidfile(self.pidfile(other), signal.SIGTERM, "whisper-stream", wait=1)
        self.assertEqual(res, "not-ours")
        time.sleep(0.2)
        self.assertIsNone(other.poll())

    def test_pidfile_problems(self):
        self.assertEqual(m.stop_pidfile(self.tmp / "none.pid", signal.SIGTERM, "x"), "no-pidfile")
        bad = self.tmp / "bad.pid"
        bad.write_text("not-a-number")
        self.assertEqual(m.stop_pidfile(bad, signal.SIGTERM, "x"), "bad-pidfile")

    def test_finished_process_is_already_exited(self):
        p = self.spawn("pass", "whisper-stream")
        p.wait()
        self.assertEqual(m.stop_pidfile(self.pidfile(p), signal.SIGTERM, "whisper-stream"),
                         "already-exited")

    def test_pid_1_is_never_signalled(self):
        f = self.tmp / "init.pid"
        f.write_text("1\n")
        self.assertEqual(m.stop_pidfile(f, signal.SIGTERM, ""), "already-exited")

    def test_ffmpeg_gets_sigint_so_it_can_finalize(self):
        self.assertEqual(m.STOP_PLAN["ffmpeg"][0], signal.SIGINT)
        self.assertEqual(m.STOP_PLAN["whisper"][0], signal.SIGTERM)
        p = self.spawn(FINALIZER, "ffmpeg", cwd=self.tmp)
        time.sleep(0.5)  # 핸들러 설치 대기
        self.pidfile(p, "ffmpeg.pid")
        r = subprocess.run([sys.executable, str(SCRIPT), "stop", str(self.tmp)],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertIn("ffmpeg: stopped", r.stdout)
        self.assertIn("whisper: no-pidfile", r.stdout)
        self.assertTrue((self.tmp / "finalized").exists(), "SIGINT 마무리 경로를 타지 않았다")

    def test_stop_unknown_session_exits_2(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "stop", str(self.tmp / "none")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class Run(Base):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                              timeout=30)

    def test_records_pid_and_propagates_exit_code(self):
        r = self.cli("run", str(self.tmp), "whisper", "--", sys.executable, "-c", "raise SystemExit(7)")
        self.assertEqual(r.returncode, 7)
        self.assertRegex((self.tmp / "whisper.pid").read_text(), r"^\d+\n$")

    def test_runs_in_session_directory(self):
        self.cli("run", str(self.tmp), "whisper", "--", sys.executable, "-c",
                 "open('transcript.txt','w').write('x')")
        self.assertTrue((self.tmp / "transcript.txt").exists())

    def test_missing_command_exits_127_without_pidfile(self):
        r = self.cli("run", str(self.tmp), "whisper", "--", "definitely-not-installed-xyz")
        self.assertEqual(r.returncode, 127)
        self.assertFalse((self.tmp / "whisper.pid").exists())

    def test_missing_session_dir_exits_2(self):
        r = self.cli("run", str(self.tmp / "none"), "whisper", "--", "true")
        self.assertEqual(r.returncode, 2)

    def test_run_then_stop_end_to_end(self):
        w = subprocess.Popen([sys.executable, str(SCRIPT), "run", str(self.tmp), "whisper", "--",
                              sys.executable, "-c", SLEEP, "whisper-stream"])
        self.procs.append(w)
        for _ in range(50):
            if (self.tmp / "whisper.pid").exists():
                break
            time.sleep(0.1)
        r = self.cli("stop", str(self.tmp))
        self.assertIn("whisper: stopped", r.stdout)
        w.wait(timeout=10)


class Tools(Base):
    def run_check(self, path, model):
        out = io.StringIO()
        with mock.patch.object(m, "MODEL", model), contextlib.redirect_stdout(out):
            return m.check_tools(path), out.getvalue()

    def fake_bin(self, *names):
        d = self.tmp / "bin"
        d.mkdir(exist_ok=True)
        for n in names:
            f = d / n
            f.write_text("#!/bin/sh\n")
            f.chmod(0o755)
        return str(d)

    def test_missing_whisper_stops_before_recording(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        rc, out = self.run_check(str(empty), self.tmp / "no-model.bin")
        self.assertEqual(rc, 1)
        self.assertIn("whisper-stream: 없음", out)
        self.assertIn("임의로 내려받지 않는다", out)

    def test_ffmpeg_missing_falls_back_to_transcript_only(self):
        model = self.tmp / "model.bin"
        model.write_text("x")
        rc, out = self.run_check(self.fake_bin("whisper-stream"), model)
        self.assertEqual(rc, 0)
        self.assertIn("전사만으로 진행", out)

    def test_all_present(self):
        model = self.tmp / "model.bin"
        model.write_text("x")
        rc, out = self.run_check(self.fake_bin("whisper-stream", "ffmpeg"), model)
        self.assertEqual(rc, 0)
        self.assertNotIn("없음", out)


if __name__ == "__main__":
    unittest.main()
