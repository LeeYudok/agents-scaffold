"""repo_state.py 의 출력 해석과 판정 (stdlib only)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import repo_state as rs  # noqa: E402

SAME = {"head": "abc", "upstream": "abc", "listhash": "h1", "tracked": "10", "dirty": "0"}


class ParseTest(unittest.TestCase):
    def test_ignores_unknown_lines(self):
        s = rs.parse("noise\nhead=abc\nbranch=main\nfoo=bar\n")
        self.assertEqual(s, {"head": "abc", "branch": "main"})


class VerdictTest(unittest.TestCase):
    def test_all_same(self):
        self.assertEqual(rs.verdict({"local": dict(SAME), "pig": dict(SAME)}), [])

    def test_head_difference(self):
        other = dict(SAME, head="def", upstream="def")
        problems = rs.verdict({"local": dict(SAME), "pig": other})
        self.assertTrue(any(p.startswith("head") for p in problems))

    def test_dirty_clone_is_reported(self):
        problems = rs.verdict({"local": dict(SAME, dirty="3")})
        self.assertEqual(problems, ["local: 고친 파일 3개"])

    def test_behind_origin_is_reported(self):
        problems = rs.verdict({"local": dict(SAME, upstream="zzz")})
        self.assertEqual(problems, ["local: origin 과 HEAD 가 다르다"])


if __name__ == "__main__":
    unittest.main()
