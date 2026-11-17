"""check_writing.py · upstage_proofread.py 회귀 테스트 (stdlib only, 네트워크 없음)."""

import importlib.util
import io
import json
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
        # 2026-11-15 번역 소설 검사에서 놓친 꼴 (#126). 예문은 직접 썼다.
        ("문이 저절로 닫혀졌다.", "닫혀졌", "문이 저절로 닫혔다."),
        ("배포를 실수로 해 버렸다.", "해 버렸", "배포를 실수로 했다."),
        ("공동생활에 있어서는 인내가 필요하다.", "에 있어서", "공동생활에는 인내가 필요하다."),
        # 근거 없는 평가어 (#132)
        ("혁신적인 구조로 바꿨다.", "혁신적", "구조를 모듈 3개로 나눴다."),
        ("획기적으로 빨라졌다.", "획기적", "응답 시간이 2초에서 0.4초로 줄었다."),
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

    def test_eitsseo_existential_clause_passes(self):
        # "있다 + -어서" 는 번역투가 아니다 (#126)
        for text in ("깃대가 마당 한가운데에 있어서 잘 보인다.", "설정이 서버에 있어서 권한이 필요하다.",
                     "비밀번호가 코드에 있어서는 안 된다.", "전화기가 복도에 있어서, 모두 그곳을 쓴다."):
            with self.subTest(text=text):
                self.assertEqual(errors(text), [])

    def test_prose_mode_keeps_translationese_only(self):
        narration = "그 말에 그는 웃지 않을 수 없었다. " + "가" * 70 + "다."
        self.assertTrue(cw.check(narration, RULES))
        self.assertEqual(cw.check(narration, RULES, prose=True), [])
        found = cw.check("그 일에 대해 오래 생각했다.", RULES, prose=True)
        self.assertEqual([(f.kind, f.match) for f in found], [("영어 번역투", "에 대해")])
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(narration)
        self.addCleanup(os.unlink, f.name)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cw.main(["--prose", "--strict", f.name]), 0)
            self.assertEqual(cw.main([f.name]), 1)


class StructureRules(unittest.TestCase):
    """문단·목록 단위 검사와 심각도 3단계 (#132). 예문은 직접 썼다."""

    def levels(self, text, **kw):
        return {f.kind: f.level for f in cw.check(text, RULES, max_len=200, **kw)}

    def test_repeated_ending_warns_in_a_paragraph_only(self):
        text = "설정을 바꿀 수 있다. 값을 읽을 수 있다. 결과를 볼 수 있다."
        self.assertEqual(self.levels(text).get("종결 반복"), "경고")
        self.assertNotIn("종결 반복", self.levels("설정을 바꿀 수 있다. 값을 읽을 수 있다.\n\n결과를 볼 수 있다."))
        self.assertNotIn("종결 반복", self.levels("- 설정을 바꿀 수 있다.\n- 값을 읽을 수 있다.\n- 결과를 볼 수 있다."))
        self.assertNotIn("종결 반복", self.levels("바꿀 수 있어요. 읽을 수 있어요. 볼 수 있어요.", chat=True))

    def test_sentence_initial_conjunctions_warn_at_three(self):
        self.assertEqual(self.levels("또한 캐시를 지운다. 그리고 서버를 띄운다. 따라서 로그를 본다.").get("문두 접속사"), "경고")
        self.assertNotIn("문두 접속사", self.levels("또한 캐시를 지운다. 그리고 서버를 띄운다. 로그를 본다."))

    def test_colon_before_a_list_warns_only_after_a_predicate(self):
        self.assertEqual(self.levels("다음 순서로 진행합니다:\n\n- 이슈를 등록한다").get("콜론 뒤 목록"), "경고")
        self.assertNotIn("콜론 뒤 목록", self.levels("진행 순서:\n\n- 이슈를 등록한다"))
        self.assertNotIn("콜론 뒤 목록", self.levels("```\n다음 순서로 진행합니다:\n- 이슈를 등록한다\n```"))

    def test_bound_nouns_are_a_note(self):
        self.assertEqual(self.levels("확인할 수 있는 것은 값이 다르다는 점이다.").get("의존명사"), "참고")
        self.assertNotIn("의존명사", self.levels("점수를 수정한 것이다."))

    def test_notes_never_change_the_exit_code(self):
        text = "- **속도**: 빠르다\n- **안정성**: 높다\n- **비용**: 낮다\n"
        self.assertEqual(self.levels(text), {"굵은 머리말 목록": "참고"})
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(text)
        self.addCleanup(os.unlink, f.name)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cw.main(["--strict", f.name]), 0)
        self.assertIn("참고 1건", out.getvalue())

    def test_prose_mode_skips_structure_rules(self):
        text = "그는 웃고 있었다. 나도 웃고 있었다. 모두 웃고 있었다."
        self.assertEqual(cw.check(text, RULES, prose=True), [])


class MorphOption(unittest.TestCase):
    """--morph 는 kiwipiepy 가 있을 때만 돈다 (#132). CI 는 kiwipiepy 를 깔지 않는다."""

    TEXT = "확인할 건 값이 다르다는 게 문제라는 걸 아는지다.\n"

    def run_morph(self, modules):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(self.TEXT)
        self.addCleanup(os.unlink, f.name)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(sys.modules, modules), redirect_stdout(out), redirect_stderr(err):
            code = cw.main(["--morph", "--strict", f.name])
        return code, out.getvalue(), err.getvalue()

    def test_morph_is_skipped_without_kiwipiepy(self):
        code, out, err = self.run_morph({"kiwipiepy": None})
        self.assertEqual(code, 0)
        self.assertIn("kiwipiepy 가 없어 형태소 검사를 건너뛴다", err)
        self.assertNotIn("형태소 참고", out)

    def test_morph_counts_contracted_bound_nouns(self):
        from types import ModuleType, SimpleNamespace

        class FakeKiwi:
            def split_into_sents(self, text, return_tokens=False):
                forms = ["건", "것", "거"] if "건" in text else []  # kiwipiepy 가 준말을 푼 꼴
                tokens = [SimpleNamespace(form=form, tag="NNB") for form in forms]
                return [SimpleNamespace(text=text, tokens=tokens)]

        fake = ModuleType("kiwipiepy")
        fake.Kiwi = FakeKiwi
        code, out, _err = self.run_morph({"kiwipiepy": fake})
        self.assertEqual(code, 0, "참고는 --strict 에서도 종료 코드를 바꾸지 않는다")
        self.assertIn("[의존명사(형태소)] '3회'", out)
        self.assertIn("형태소 참고 1건", out)


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


class Expansion(unittest.TestCase):
    """#137 — 참고 문헌 확장 규칙, 경고·횟수 옵션, 표기 프로필."""

    CASES = json.loads((SKILL / "tests" / "fixtures" / "expansion-cases.json").read_text(encoding="utf-8"))

    @staticmethod
    def by_banned(text, banned, **kw):
        return [f for f in cw.check(text, RULES, **kw) if f.hint.startswith(banned + " → ")]

    def section(self, name):
        """name 절의 규칙마다 잡을 예문과 오탐 예문이 있고, 그대로 판정되는지 본다."""
        banned = {r.banned for r in RULES if r.section == name}
        cases = [c for c in self.CASES if c["banned"] in banned]
        self.assertTrue(banned, f"금지 표현 표에 {name} 절이 없다")
        self.assertEqual({c["banned"] for c in cases}, banned, "규칙마다 예문이 있어야 한다")
        for case in cases:
            self.assertTrue(case["flagged"] and case["passed"], case["banned"])
            for text in case["flagged"]:
                with self.subTest(banned=case["banned"], flagged=text):
                    self.assertEqual([(f.match, f.level) for f in self.by_banned(text, case["banned"])],
                                     [(case["want"], case["level"])])
                    self.assertEqual(self.by_banned(text, case["banned"], prose=True), [], "산문 모드는 보지 않는다")
            for text in case["passed"]:
                with self.subTest(banned=case["banned"], passed=text):
                    self.assertEqual(self.by_banned(text, case["banned"]), [])

    def test_redundant_pairs_catch_and_spare(self):
        self.section("겹말")

    def test_stacked_particles_catch_and_spare(self):
        self.section("조사 겹침·일본어 투 보강")

    def test_stretched_predicates_catch_and_spare(self):
        self.section("늘어지는 서술어")

    def test_filler_words_catch_and_spare(self):
        self.section("군더더기 낱말")

    def test_overuse_counts_catch_and_spare(self):
        self.section("남용 (한 문장 안의 횟수)")

    def test_every_case_belongs_to_an_expansion_rule(self):
        banned = {r.banned for r in RULES}
        self.assertEqual([c["banned"] for c in self.CASES if c["banned"] not in banned], [])

    def test_count_rule_fires_once_per_sentence_as_warning(self):
        rule = next(r for r in RULES if r.banned == "한 문장에 ~의 3개 이상")
        self.assertEqual((rule.level, rule.min_count), ("경고", 3))
        found = cw.check("서버의 설정의 기본값의 출처의 기록을 찾는다. 서버의 설정을 찾는다.", RULES)
        self.assertEqual([(f.match, f.level) for f in found], [("4회", "경고")])
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as f:
            f.write("여러 파일들을 지웠다.\n")
            f.flush()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cw.main([f.name]), 0, "경고만 있으면 종료 코드는 0 이다")
                self.assertEqual(cw.main(["--strict", f.name]), 1)

    def test_default_profile_is_doksam(self):
        text = "배포 시각은 2026-11-17T09:00:00+09:00 이다."
        default = cw.check(text, RULES)
        self.assertEqual([f.kind for f in default], ["시각 표기"])
        self.assertEqual(cw.check(text, RULES, profile="doksam"), default)

    def test_profile_switches_checks_and_adds_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "acme.md"
            path.write_text("## 표기 검사\n| 검사 | 수준 | 안내 |\n|---|---|---|\n| 시각 표기 | 끔 | - |\n\n"
                            "## acme 표현\n| 금지 | 대체 | 검사 |\n|---|---|---|\n| 금일 | 오늘 | `금일` |\n", encoding="utf-8")
            found = cw.check("금일 2026-11-17T09:00:00+09:00 에 배포한다.", RULES, profile=str(path))
            self.assertEqual([(f.kind, f.match) for f in found], [("acme 표현", "금일")])
            with self.assertRaises(RuntimeError):
                cw.check("본문이다.", RULES, profile=str(Path(tmp) / "missing.md"))


class CustomEndpoint(unittest.TestCase):
    """WRITER_LLM_BASE_URL — 폐쇄망의 OpenAI 호환 엔드포인트 (#137). 실제 네트워크는 쓰지 않는다."""

    BASE = "http://llm.internal:8000/v1"

    def setUp(self):
        self.up = load("upstage_proofread")
        self.sm = load("upstage_summarize")
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        self.requests = []

    def urlopen(self, req, timeout=None):
        self.requests.append(req)
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": "백필 작업이 늦다."}}]}).encode())

    def run_main(self, module, text, extra, args=()):
        path = Path(self.tmp) / "in.md"
        path.write_text(text, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("WRITER_LLM") and k != "UPSTAGE_API_KEY"}
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env | {"HOME": self.tmp} | extra, clear=True), \
                mock.patch.object(self.up.urllib.request, "urlopen", side_effect=self.urlopen), \
                redirect_stdout(out), redirect_stderr(err):
            code = module.main([str(path), *args])
        return code, out.getvalue().strip(), err.getvalue()

    def test_base_url_replaces_upstage(self):
        code, out, err = self.run_main(self.up, "백필 작업이 늦어지고 있는 중이다.",
                                       {"WRITER_LLM_BASE_URL": self.BASE + "/", "WRITER_LLM_MODEL": "qwen", "UPSTAGE_API_KEY": "upstage-key"})
        self.assertEqual((code, out), (0, "백필 작업이 늦다."), err)
        self.assertTrue(self.requests)
        for req in self.requests:
            self.assertEqual(req.full_url, self.BASE + "/chat/completions")
            self.assertNotIn("upstage", req.full_url)
            self.assertIsNone(req.get_header("Authorization"), "Upstage 키를 다른 호스트로 보내지 않는다")
            self.assertEqual(json.loads(req.data)["model"], "qwen")

    def test_base_url_sends_its_own_key(self):
        code, _, err = self.run_main(self.up, "백필 작업이 늦다.",
                                     {"WRITER_LLM_BASE_URL": self.BASE, "WRITER_LLM_MODEL": "qwen", "WRITER_LLM_API_KEY": "internal"})
        self.assertEqual(code, 0, err)
        self.assertEqual(self.requests[0].get_header("Authorization"), "Bearer internal")

    def test_base_url_requires_model(self):
        code, _, err = self.run_main(self.up, "본문이다.", {"WRITER_LLM_BASE_URL": self.BASE})
        self.assertEqual(code, 2)
        self.assertIn("WRITER_LLM_MODEL", err)
        self.assertEqual(self.requests, [])

    def test_secret_is_blocked_on_custom_endpoint(self):
        for module in (self.up, self.sm):
            code, _, err = self.run_main(module, "토큰은 glpat-abcdefghijklmnop 이다.",
                                         {"WRITER_LLM_BASE_URL": self.BASE, "WRITER_LLM_MODEL": "qwen"})
            self.assertEqual(code, 2)
            self.assertIn("보내지 않는다", err)
        self.assertEqual(self.requests, [])

    def test_default_endpoint_is_upstage(self):
        code, _, err = self.run_main(self.up, "백필 작업이 늦다.", {"UPSTAGE_API_KEY": "upstage-key"})
        self.assertEqual(code, 0, err)
        self.assertEqual(self.requests[0].full_url, self.up.API)
        self.assertEqual(self.requests[0].get_header("Authorization"), "Bearer upstage-key")
        self.assertEqual(json.loads(self.requests[0].data)["model"], self.up.MODEL)

    def test_summary_uses_custom_endpoint_without_key(self):
        code, out, err = self.run_main(self.sm, "백필 작업이 늦다. 원인은 쿼리다.",
                                       {"WRITER_LLM_BASE_URL": self.BASE, "WRITER_LLM_MODEL": "qwen"}, args=["--lines", "1"])
        self.assertEqual((code, out), (0, "백필 작업이 늦다."), err)
        self.assertEqual({req.full_url for req in self.requests}, {self.BASE + "/chat/completions"})


if __name__ == "__main__":
    unittest.main()
