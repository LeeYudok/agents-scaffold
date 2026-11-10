#!/usr/bin/env python3
"""cc-check.py 유닛테스트 (#37) — stdlib unittest 전용.

CC(인지 복잡도) 추정 훅의 계산 로직을 직접 검증한다. 정확한 CC 산출이 아니라
"임계값 초과 함수를 놓치지 않는가"(false negative 방지)가 관심사다.

실행: python3 -m unittest discover -s tests -p 'test_*.py'
"""
import importlib.util
import os
import sys

# .claude 트리에 __pycache__(.pyc 바이너리)를 남기면 스캐폴드 sed 가 전멸한다(#37)
sys.dont_write_bytecode = True
import shutil
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPT = os.path.join(REPO_ROOT, ".claude", "hooks", "cc-check.py")

spec = importlib.util.spec_from_file_location("cc_check_under_test", SCRIPT)
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)


def py_func_with_branches(name, n):
    """분기 n 개짜리 파이썬 함수 소스 생성."""
    body = "\n".join(f"    if x > {i}:\n        x += 1" for i in range(n))
    return f"def {name}(x):\n{body}\n    return x\n"


class TestCalcCc(unittest.TestCase):
    def check_source(self, source, suffix=".py"):
        with tempfile.TemporaryDirectory() as d:
            path = f"target{suffix}"
            with open(os.path.join(d, path), "w", encoding="utf-8") as f:
                f.write(source)
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": d}):
                return cc.check_file(path)

    def test_at_threshold_no_warning(self):
        self.assertEqual(self.check_source(py_func_with_branches("ok", cc.THRESHOLD)), [])

    def test_over_threshold_warns_with_name_and_cc(self):
        w = self.check_source(py_func_with_branches("busy", cc.THRESHOLD + 1))
        self.assertEqual(len(w), 1)
        self.assertIn("busy()", w[0])
        self.assertIn(f"CC~{cc.THRESHOLD + 1}", w[0])

    def test_branches_inside_strings_are_not_counted(self):
        lines = ['    s = "if while for && || case"' for _ in range(30)]
        src = "def quiet():\n" + "\n".join(lines) + "\n    return s\n"
        self.assertEqual(self.check_source(src), [])

    def test_function_boundaries_scope_the_count(self):
        # 두 함수에 임계값 절반씩 — 합치면 초과지만 각각은 미만이어야 경고 없음
        half = cc.THRESHOLD // 2 + 1
        src = py_func_with_branches("first", half) + py_func_with_branches("second", half)
        self.assertEqual(self.check_source(src), [])

    def test_unsupported_extension_returns_empty(self):
        self.assertEqual(self.check_source("if if if", suffix=".md"), [])

    def test_missing_file_returns_empty(self):
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": tempfile.gettempdir()}):
            self.assertEqual(cc.check_file("no-such-file.py"), [])


class TestLanguageDetection(unittest.TestCase):
    def check_source(self, source, suffix):
        with tempfile.TemporaryDirectory() as d:
            path = f"target{suffix}"
            with open(os.path.join(d, path), "w", encoding="utf-8") as f:
                f.write(source)
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": d}):
                return cc.check_file(path)

    def test_ts_function_over_threshold_warns(self):
        cond = " && x".join(str(i) for i in range(cc.THRESHOLD + 2))
        src = f"function tsBusy(x) {{\n  if ({cond}) {{ return 1; }}\n}}\n"
        w = self.check_source(src, ".ts")
        self.assertEqual(len(w), 1)
        self.assertIn("tsBusy()", w[0])

    def test_go_function_over_threshold_warns(self):
        body = "\n".join(f"\tif x > {i} {{ x++ }}" for i in range(cc.THRESHOLD + 1))
        src = f"func goBusy(x int) int {{\n{body}\n\treturn x\n}}\n"
        w = self.check_source(src, ".go")
        self.assertEqual(len(w), 1)
        self.assertIn("goBusy()", w[0])


class TestSelfCheck(unittest.TestCase):
    def test_cc_check_passes_its_own_threshold(self):
        # 자기 자신의 함수가 전부 임계값 이하 — 아니라면 이 훅부터 리팩토링 대상
        with tempfile.TemporaryDirectory() as d:
            dst = os.path.join(d, "cc-check.py")
            shutil.copy(SCRIPT, dst)
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": d}):
                self.assertEqual(cc.check_file("cc-check.py"), [])


if __name__ == "__main__":
    unittest.main()
