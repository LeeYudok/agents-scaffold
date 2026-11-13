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


def skill_block(label):
    """SKILL.md 에서 `<label>:` 다음 인용 블록 전체를 '> ' 를 떼어 돌려준다."""
    lines = (SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"{label}:")
    j = start + 1
    while not lines[j].startswith(">"):
        j += 1
    out = []
    while j < len(lines) and lines[j].startswith(">"):
        out.append(lines[j][1:].lstrip(" "))
        j += 1
    return "\n".join(out)


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


class SummaryExamples(unittest.TestCase):
    """SKILL.md 요약 예시: 나쁜 요약은 원문 대조에 걸리고, 고친 요약은 오류·경고 없이 통과한다 (#118)."""

    def setUp(self):
        self.source = skill_block("요약 원문")

    def test_bad_summary_is_caught_against_source(self):
        found = cw.check(skill_block("나쁜 요약 (세 줄)"), RULES, source=self.source, lines=3)
        errors_found = {f.match for f in found if f.level == "오류"}
        self.assertTrue({"2026-11-15", "#419", "완벽하게"} <= errors_found, found)
        warnings = {f.match for f in found if f.level == "경고"}
        self.assertTrue({"61", "5", "10"} <= warnings, found)

    def test_fixed_summary_passes_against_source(self):
        found = cw.check(skill_block("고친 요약 (세 줄)"), RULES, source=self.source, lines=3)
        self.assertEqual(found, [])


class SourceCheck(unittest.TestCase):
    """--source 원문 대조와 --lines 줄 수 상한 (#118)."""

    SOURCE = "2026-11-14 16:00 에 `closed_at` 인덱스를 추가한다(#418). 처리량은 하루 4,000건이다."

    def test_copied_values_pass(self):
        summary = "- 2026년 11월 14일 16:00 에 `closed_at` 인덱스를 추가한다(#418).\n- 하루 4000건이다."
        self.assertEqual(cw.check(summary, RULES, source=self.SOURCE, lines=2), [])

    def test_values_missing_from_source(self):
        summary = "- 2026-11-15 17:00 에 `created_at` 인덱스를 추가한다(#419).\n- 하루 5,000건이다."
        found = {(f.match, f.level) for f in cw.check(summary, RULES, source=self.SOURCE, lines=1)}
        self.assertEqual(found, {("2026-11-15", "오류"), ("17:00", "오류"), ("created_at", "오류"),
                                 ("#419", "오류"), ("5,000", "경고"), ("2줄", "오류")})

    def test_without_source_no_fact_check(self):
        self.assertEqual(cw.check("- #999 를 고쳤다.", RULES), [])

    def test_cli_source_and_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "원문.md"
            source.write_text(self.SOURCE, encoding="utf-8")
            summary = Path(tmp) / "요약.md"
            summary.write_text("- #419 를 고쳤다.\n- 둘째 줄이다.\n", encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                code = cw.main(["--source", str(source), "--lines", "1", str(summary)])
            self.assertEqual(code, 1)
            self.assertIn("'#419'", out.getvalue())
            self.assertIn("'2줄'", out.getvalue())


class NewBannedRules(unittest.TestCase):
    """#118 에서 더한 번역투·군더더기 규칙. 잡을 문장과 잡지 않을 문장을 함께 둔다."""

    CASES = [
        ("설정을 다시 확인할 필요가 있다.", "필요가 있다", "설정을 다시 확인할 필요는 없다."),
        ("이 작업은 관리자 권한을 필요로 한다.", "을 필요로 한", "이 작업에는 관리자 권한이 필요하다."),
        ("가장 많이 쓰는 명령 중 하나다.", "가장 많이 쓰는 명령 중 하나", "가장 많이 쓰는 명령은 `ls` 다."),
        ("경고에도 불구하고 배포했다.", "에도 불구하고", "경고가 있었는데도 배포했다."),
        ("사용자로 하여금 다시 로그인하게 한다.", "로 하여금", "사용자가 다시 로그인하게 한다."),
        ("키를 바꾸지 않으면 안 된다.", "지 않으면 안 된", "키를 바꿔야 한다."),
        ("내일까지 고치도록 하겠습니다.", "도록 하겠", "내일까지 고치겠습니다."),
        ("롤백하지 않을 수 없다.", "지 않을 수 없", "롤백해야 한다."),
        ("백필을 수행한다.", "을 수행한", "백필을 돌린다."),
        ("점검을 실시했다.", "을 실시했", "점검했다."),
    ]

    def test_new_rules_catch_and_spare(self):
        for bad, match, good in self.CASES:
            with self.subTest(bad=bad):
                self.assertIn(match, [f.match for f in errors(bad)])
                self.assertEqual(errors(good), [], good)


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

    def test_native_checker_failure_is_reported_without_network(self):
        with mock.patch.object(self.up.check_writing, "load_rules", side_effect=RuntimeError("native checker unavailable")):
            code, err = self.run_main("본문이다.", {"UPSTAGE_API_KEY": "x", "HOME": self.tmp})
        self.assertEqual(code, 2)
        self.assertIn("native checker unavailable", err)

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


class UpstageSummary(unittest.TestCase):
    """upstage_summarize.py — 네트워크 없이 call 을 바꿔 끼워 흐름만 본다 (#118)."""

    SOURCE = "2026-11-14 에 `closed_at` 인덱스를 추가한다(#418). 하루 4,000건씩 약 153일이 걸린다."

    def setUp(self):
        self.sm = load("upstage_summarize")
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))

    def run_main(self, text, fake, args=(), env=None):
        path = Path(self.tmp) / "src.md"
        path.write_text(text, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        # env 를 주면 환경을 비운다(실제 키가 새어 들지 않게). 기본은 검사기 실행에 PATH 가 필요해 유지한다.
        environ = mock.patch.dict(os.environ, env, clear=True) if env else mock.patch.dict(os.environ, {"UPSTAGE_API_KEY": "x"})
        with environ, mock.patch.object(self.sm, "call", side_effect=fake), redirect_stdout(out), redirect_stderr(err):
            code = self.sm.main([str(path), *args])
        return code, out.getvalue().strip(), err.getvalue()

    def test_summary_secret_is_not_sent(self):
        code, _, err = self.run_main("토큰 ghp_abcdef 이다.", AssertionError("네트워크 호출 금지"))
        self.assertEqual(code, 2)
        self.assertIn("보내지 않는다", err)

    def test_summary_missing_key(self):
        code, _, err = self.run_main("본문이다.", AssertionError("네트워크 호출 금지"), env={"HOME": self.tmp})
        self.assertEqual(code, 2)
        self.assertIn("UPSTAGE_API_KEY", err)

    def test_lines_must_be_positive(self):
        code, _, err = self.run_main("본문이다.", AssertionError("네트워크 호출 금지"), args=["--lines", "0"])
        self.assertEqual(code, 2)
        self.assertIn("--lines", err)

    def test_retry_on_source_errors_then_keep_first_lines(self):
        calls = []

        def fake(key, system, user, max_tokens):
            calls.append((system, user))
            if len(calls) == 1:
                return "- 2026-11-15 에 인덱스를 추가한다(#419).\n- 둘째다.\n- 셋째다.\n- 넷째다."
            return "- 2026-11-14 에 인덱스를 추가한다(#418).\n- 하루 4,000건씩 약 153일이 걸린다.\n- 셋째다.\n- 넷째다."

        code, out, err = self.run_main(self.SOURCE, fake)
        self.assertEqual(len(calls), 2, "오류가 남으면 한 번 더 고쳐야 한다")
        self.assertIn("결론", calls[0][0], "줄 역할을 시스템 프롬프트에 넣는다")
        self.assertIn("#419", calls[1][1])
        self.assertIn(self.SOURCE, calls[1][1], "재시도에는 원문을 붙인다")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.splitlines(), ["- 2026-11-14 에 인덱스를 추가한다(#418).",
                                            "- 하루 4,000건씩 약 153일이 걸린다.", "- 셋째다."])

    def test_empty_summary_retries_and_is_never_success(self):
        replies = iter(["", ""])
        code, out, err = self.run_main(self.SOURCE, lambda *args: next(replies))
        self.assertEqual(code, 1)
        self.assertIn("빈 요약", err)
        self.assertEqual(out, "")
        replies = iter(["", "- 인덱스를 추가한다."])
        code, out, err = self.run_main(self.SOURCE, lambda *args: next(replies))
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "- 인덱스를 추가한다.")

    def test_long_source_is_summarized_in_parts(self):
        paragraphs = ["첫째 단락이다. " * 4, "둘째 단락이다. " * 4, "셋째 단락이다. " * 4]
        calls = []

        def fake(key, system, user, max_tokens):
            calls.append(user)
            return "- 단락을 요약했다."

        with mock.patch.object(self.sm, "CHUNK_CHARS", 60):
            code, out, _ = self.run_main("\n\n".join(paragraphs), fake)
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 4, "부분 3번 + 합치기 1번")
        self.assertIn("1/3", calls[0])
        self.assertIn("부분별로 요약한", calls[3])

    def test_chunks_keep_text_within_limit(self):
        text = "\n\n".join(["가" * 30, "나" * 30, "다" * 150])
        parts = self.sm.chunks(text, limit=70)
        self.assertTrue(all(len(p) <= 70 for p in parts), [len(p) for p in parts])
        self.assertEqual("".join(parts).replace("\n", ""), text.replace("\n", ""))


if __name__ == "__main__":
    unittest.main()
