"""흐름 지도와 그 검증기 (#143). 지도에서 하나를 빼면 검증이 실패하는지 본다."""

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("flow_map", SKILL / "scripts" / "flow_map.py")
fm = importlib.util.module_from_spec(spec)
sys.modules["flow_map"] = fm
spec.loader.exec_module(fm)


class RealSkill(unittest.TestCase):
    def test_map_covers_the_whole_skill(self):
        self.assertEqual(fm.problems(SKILL), [])

    def test_three_flows_start_and_end(self):
        data = fm.load(SKILL)
        self.assertEqual([f["start"] for f in data["flows"].values()], ["intake", "m-what", "e-prompts"])
        ends = [n for n, node in data["nodes"].items() if node["kind"] == "end"]
        self.assertEqual(ends, ["deliver", "m-done", "e-done"])

    def test_every_work_path_passes_the_checker_and_a_checklist(self):
        """쓰기·고치기·요약 어느 길로 가도 검사기와 점검표를 거쳐야 끝난다."""
        nodes = fm.load(SKILL)["nodes"]
        for start, must in (("w-reader", {"check", "checklist"}), ("r-check", {"check", "checklist"}),
                            ("s-kind", {"s-source", "s-numbers", "s-checklist"})):
            for gate in must:
                without = fm.reach([start], lambda n, gate=gate: [] if n == gate else [e["to"] for e in fm.edges(nodes[n])])
                with self.subTest(start=start, gate=gate):
                    self.assertNotIn("deliver", without, f"{gate} 를 거치지 않고 끝나는 길이 있다")

    def test_parser_reads_the_same_as_a_yaml_library(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML 이 없다")
        text = (SKILL / "references" / "flow.yaml").read_text(encoding="utf-8")
        self.assertEqual(fm.parse_yaml(text), yaml.safe_load(text))


class Parser(unittest.TestCase):
    def test_maps_lists_and_quotes(self):
        text = 'a:\n  b: [x, "y, z"]\n  "0": 영\nc:\n  - to: d\n    when: 조건\n  - "e: f"\n'
        self.assertEqual(fm.parse_yaml(text), {"a": {"b": ["x", "y, z"], "0": "영"}, "c": [{"to": "d", "when": "조건"}, "e: f"]})

    def test_values_that_yaml_reads_differently_are_errors(self):
        for text in ("a: b #주석", "a: true", "a: `x`", "a: x\na: y", "a:\n\tb: c", "a:\n    b: c\n  d: e"):
            with self.subTest(text=text), self.assertRaises(fm.FlowError):
                fm.parse_yaml(text)


class Omissions(unittest.TestCase):
    """스킬 사본에서 한 군데를 바꾸고 검증이 그 누락을 짚는지 본다."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()) / "skill"
        self.addCleanup(shutil.rmtree, self.root.parent)
        shutil.copytree(SKILL, self.root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "bin"))

    def edit(self, rel, old, new):
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def found(self):
        return "\n".join(fm.problems(self.root))

    def test_copy_is_clean(self):
        self.assertEqual(self.found(), "")

    def test_new_script_option_must_be_on_the_map(self):
        self.edit("scripts/upstage_summarize.py", 'ap.add_argument("--chat"',
                  'ap.add_argument("--tone", help="말투")\n    ap.add_argument("--chat"')
        self.assertIn("tools.upstage-summarize: 지도에 없는 옵션: --tone", self.found())

    def test_new_checker_option_must_be_on_the_map(self):
        self.edit("go/main.go", 'case arg == "--chat":', 'case arg == "--quiet":\n\t\tcase arg == "--chat":')
        self.assertIn("tools.check-writing: 지도에 없는 옵션: --quiet", self.found())

    def test_new_environment_variable_must_be_on_the_map(self):
        self.edit("scripts/upstage_proofread.py", 'os.environ.get("UPSTAGE_API_KEY")', 'os.environ.get("WRITER_LLM_TIMEOUT") or os.environ.get("UPSTAGE_API_KEY")')
        self.assertIn("tools.upstage-proofread: 지도에 없는 환경변수: WRITER_LLM_TIMEOUT", self.found())

    def test_removed_option_must_leave_the_map(self):
        self.edit("references/flow.yaml", "      --seed: --blind 의 섞는 순서\n", "      --seed: --blind 의 섞는 순서\n      --rounds: 반복 횟수\n")
        self.assertIn("tools.score-writing-tasks: 스크립트에 없는 옵션: --rounds", self.found())

    def test_new_skill_section_must_belong_to_a_step(self):
        self.edit("SKILL.md", "## 예외\n", "## 번역할 때\n\n- 원문의 문단을 지킨다.\n\n## 예외\n")
        self.assertIn("SKILL.md 의 절이 어느 단계에도 없다: 번역할 때", self.found())

    def test_headings_inside_code_blocks_are_not_sections(self):
        self.assertNotIn("배경", fm.headings((SKILL / "SKILL.md").read_text(encoding="utf-8")))

    def test_new_file_must_be_on_the_map(self):
        (self.root / "scripts" / "translate.py").write_text("print()\n", encoding="utf-8")
        self.assertIn("files: 지도에 없는 파일: scripts/translate.py", self.found())

    def test_mapped_file_must_exist_and_be_used(self):
        (self.root / "references" / "profiles" / "README.md").unlink()
        self.assertIn("files: 없는 파일이다: references/profiles/README.md", self.found())

    def test_step_without_a_way_out_or_in(self):
        self.edit("references/flow.yaml", "      - to: w-evidence\n", "      - to: w-format\n")
        self.assertIn("w-evidence: 어느 시작에서도 닿지 않는다", self.found())
        self.edit("references/flow.yaml", "      - to: w-format\n", "      - to: nowhere\n")
        self.assertIn("w-reader: 없는 단계로 간다: nowhere", self.found())

    def test_branch_needs_a_condition_and_gate_needs_a_pass_rule(self):
        self.edit("references/flow.yaml", "      - to: w-reader\n        when: 새로 쓴다\n", "      - to: w-reader\n")
        self.edit("references/flow.yaml", "    pass: 점검표의 모든 항목이 예다\n", "")
        found = self.found()
        self.assertIn("route: 갈림인데 w-reader 로 가는 조건(when)이 없다", found)
        self.assertIn("checklist: 관문에 통과 조건(pass)이 없다", found)

    def test_renamed_rule_section_must_be_fixed_on_the_map(self):
        self.edit("references/banned-expressions.md", "## 겹말\n", "## 겹친 말\n")
        self.assertIn("modes.sections 가 금지 표현 파일의 절 제목과 다르다", self.found())

    def test_prose_sections_follow_the_engine(self):
        self.edit("go/engine.go", '"피동형", "중복 수식"', '"피동형", "겹말", "중복 수식"')
        self.assertIn("modes.prose_only 가 Go 엔진의 proseSections 와 다르다", self.found())

    def test_flow_md_must_be_regenerated(self):
        self.edit("references/flow.yaml", "title: 근거를 모은다", "title: 근거를 확인한다")
        self.assertIn("references/flow.md 가 지도와 다르다", self.found())
        (self.root / "references" / "flow.md").write_text(fm.render(fm.load(self.root), self.root), encoding="utf-8")
        self.assertEqual(self.found(), "")

    def test_added_checklist_item_shows_in_flow_md(self):
        self.edit("SKILL.md", "- [ ] 소리 내어 읽어도 막히지 않는다.\n", "- [ ] 소리 내어 읽어도 막히지 않는다.\n- [ ] 제목이 결론이다.\n")
        self.assertIn("references/flow.md 가 지도와 다르다", self.found())
        self.assertIn("검수 점검표 (11항목)", fm.render(fm.load(self.root), self.root))


class Cli(unittest.TestCase):
    def test_check_passes_and_unreadable_map_is_a_tool_error(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(fm.main(["--check"]), 0)
        self.assertIn("흐름 지도: 문제 0건", out.getvalue())
        root, err = fm.ROOT, io.StringIO()
        self.addCleanup(setattr, fm, "ROOT", root)
        fm.ROOT = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, fm.ROOT)
        with contextlib.redirect_stderr(err):
            self.assertEqual(fm.main(["--check"]), 2)
        self.assertIn("파일이 없다", err.getvalue())


if __name__ == "__main__":
    unittest.main()
