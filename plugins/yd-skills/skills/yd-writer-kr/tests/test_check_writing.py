"""check_writing.py · upstage_proofread.py 회귀 테스트 (stdlib only, 네트워크 없음)."""

import importlib.util
import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SKILL / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod   # dataclass 가 모듈을 sys.modules 에서 찾는다
    spec.loader.exec_module(mod)
    return mod


cw = load("check_writing")
RULES = cw.load_rules()


def errors(text, chat=False):
    return [f for f in cw.check(text, RULES, chat=chat) if f.level == "오류"]


def skill_examples(label):
    """SKILL.md 예시 절에서 `<label>:` 다음 인용문을 모은다."""
    lines = (SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()
    out = []
    for i, line in enumerate(lines):
        if line.strip().startswith(label) and line.strip().endswith(":"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith(">"):
                j += 1
            out.append(lines[j].lstrip("> ").strip())
    return out


class BannedTable(unittest.TestCase):
    def test_rules_load_and_compile(self):
        self.assertGreaterEqual(len(RULES), 40)
        for r in RULES:
            self.assertIsInstance(r.pattern, re.Pattern)

    def test_every_row_has_check_column(self):
        text = (SKILL / "references" / "banned-expressions.md").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("|") and not set(line.replace("|", "").strip()) <= {"-"}:
                with self.subTest(row=line):
                    self.assertEqual(len(cw.split_row(line)), 3, "금지 | 대체 | 검사 세 칸이어야 한다")

    def test_escaped_pipe_is_alternation(self):
        self.assertEqual(cw.split_row(r"| a | b | `x\|y` |"), ["a", "b", "`x|y`"])


class SkillExamples(unittest.TestCase):
    """SKILL.md 의 나쁜 예는 잡히고, 고친 예는 통과해야 한다."""

    def test_bad_document_examples_fail(self):
        bad = skill_examples("나쁜 이슈 문장") + skill_examples("나쁜 공지 문장")
        self.assertEqual(len(bad), 2)
        for s in bad:
            with self.subTest(s=s):
                self.assertTrue(errors(s), "나쁜 예문이 통과했다")

    def test_fixed_examples_pass(self):
        fixed = skill_examples("고친 문장")
        self.assertEqual(len(fixed), 2)
        for s in fixed:
            with self.subTest(s=s):
                self.assertEqual(errors(s), [])

    def test_chat_examples(self):
        self.assertTrue(errors(skill_examples("나쁜 채팅")[0], chat=True))
        self.assertEqual(errors(skill_examples("고친 채팅")[0], chat=True), [])


class Checks(unittest.TestCase):
    def test_noun_ending_doc_only(self):
        self.assertTrue(errors("배포를 완료함."))
        self.assertEqual(errors("배포를 완료함.", chat=True), [])
        self.assertEqual(errors("설정 파일도 포함."), [], "포함 은 명사형 종결이 아니다")

    def test_iso_time_and_emoji(self):
        self.assertEqual(errors("2026-10-04T16:00:00+09:00 에 끝났다.")[0].kind, "시각 표기")
        self.assertEqual(errors("배포가 끝났다 \U0001F680")[0].kind, "이모지")
        self.assertEqual(errors("2026-10-04 16:00:00.000 에 끝났다."), [])

    def test_skipped_zones(self):
        text = "\n".join([
            "```", "에 있어서 되어지다", "```",
            "`에 있어서` 는 코드다.",
            "| 에 있어서 | 표 |",
            "> 에 있어서 인용이다",
            "에 있어서 면제한다 <!-- writer:allow -->",
            "<!--", "에 있어서", "-->",
            "[에 있어서](https://example.com/에-있어서) 링크 글자는 본다",
        ])
        found = errors(text)
        self.assertEqual([f.line for f in found], [11])

    def test_hash_number_is_not_heading(self):
        found = errors("#418 이슈 관련하여 고쳤다.")
        self.assertTrue(found, "#418 은 제목이 아니므로 검사해야 한다")

    def test_heading_skips_noun_ending_and_length(self):
        self.assertEqual(cw.check("## 설치 방법 정리함", RULES), [])

    def test_long_sentence_warning_and_strict(self):
        long = "가" * 70 + "다."
        found = cw.check(long, RULES)
        self.assertEqual([f.level for f in found], ["경고"])
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(long)
        self.addCleanup(os.unlink, f.name)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cw.main([f.name]), 0)
            self.assertEqual(cw.main(["--strict", f.name]), 1)

    def test_frontmatter_skipped(self):
        self.assertEqual(errors("---\ndescription: 에 있어서\n---\n본문이다."), [])


class SelfCheck(unittest.TestCase):
    """스킬 자신의 문서가 자기 규칙을 지킨다."""

    def test_skill_docs_pass(self):
        for p in (SKILL / "SKILL.md", SKILL / "references" / "banned-expressions.md"):
            with self.subTest(path=p.name):
                self.assertEqual(errors(p.read_text(encoding="utf-8")), [])


class UpstageGuards(unittest.TestCase):
    """네트워크 없이 확인할 수 있는 안전장치만 본다."""

    def setUp(self):
        self.up = load("upstage_proofread")
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))

    def run_main(self, text, env):
        path = Path(self.tmp) / "in.md"
        path.write_text(text, encoding="utf-8")
        err = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), redirect_stderr(err), redirect_stdout(io.StringIO()):
            with mock.patch.object(self.up, "call", side_effect=AssertionError("네트워크 호출 금지")):
                code = self.up.main([str(path)])
        return code, err.getvalue()

    def test_secret_is_not_sent(self):
        code, err = self.run_main("토큰은 glpat-abcdefghijklmnop 이다.", {"UPSTAGE_API_KEY": "x", "HOME": self.tmp})
        self.assertEqual(code, 2)
        self.assertIn("보내지 않는다", err)

    def test_missing_key(self):
        code, err = self.run_main("본문이다.", {"HOME": self.tmp})
        self.assertEqual(code, 2)
        self.assertIn("UPSTAGE_API_KEY", err)

    def test_doc_style_follows_majority_ending(self):
        polite = "설치는 두 가지입니다. 심링크를 만듭니다. 결과는 백필이 늦다."
        plain = "백필이 늦다. 쿼리가 느리다. 설치합니다."
        self.assertEqual(self.up.doc_style(polite), self.up.STYLE_POLITE)
        self.assertEqual(self.up.doc_style(plain), self.up.STYLE_PLAIN)
        self.assertEqual(self.up.doc_style("```\n코드\n```"), self.up.STYLE_DOC)

    def test_retry_when_errors_remain(self):
        calls = []

        def fake(key, system, user, max_tokens):
            calls.append(user)
            return "백필 작업에 있어서 늦다." if len(calls) == 1 else "백필 작업이 늦다."

        path = Path(self.tmp) / "in.md"
        path.write_text("백필 작업에 있어서 늦어지고 있는 중이다.", encoding="utf-8")
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"UPSTAGE_API_KEY": "x"}), \
                mock.patch.object(self.up, "call", side_effect=fake), \
                redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = self.up.main([str(path)])
        self.assertEqual(len(calls), 2, "오류가 남으면 한 번 더 고쳐야 한다")
        self.assertIn("에 있어서", calls[1])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "백필 작업이 늦다.")


if __name__ == "__main__":
    unittest.main()
