"""memory_audit.py 가 SKILL.md 의 단언대로 동작하는지 임시 디렉터리로 확인한다 (stdlib only, 이슈 #201)."""

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("memory_audit", SKILL / "scripts" / "memory_audit.py")
m = importlib.util.module_from_spec(spec)
sys.modules["memory_audit"] = m
spec.loader.exec_module(m)


def mem(name="a", desc="d", typ="project", nested=False, body="본문"):
    t = f"metadata:\n  type: {typ}" if nested else f"type: {typ}"
    return f"---\nname: {name}\ndescription: {desc}\n{t}\n---\n{body}\n"


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name) / "memory"
        self.root.mkdir()
        self.repo = Path(self._t.name) / "repo"
        self.repo.mkdir()

    def put(self, name, text):
        (self.root / name).write_text(text, encoding="utf-8")

    def index(self, *names):
        self.put("MEMORY.md", "# Index\n" + "".join(f"- [t]({n}) — x\n" for n in names))

    def kinds(self):
        return {(f["kind"], f["file"]) for f in m.structure_findings(self.root)[0]}

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = m.main([str(a) for a in args])
        return code, out.getvalue(), err.getvalue()


class Structure(Base):
    def test_clean_dir_has_no_findings(self):
        self.put("project_a.md", mem("a", typ="project", nested=True))
        self.index("project_a.md")
        self.assertEqual(m.structure_findings(self.root)[0], [])
        self.assertEqual(self.run_main(self.root)[0], 0)

    def test_index_entry_without_file(self):
        self.index("project_gone.md")
        self.assertIn(("index-dangling", "project_gone.md"), self.kinds())
        self.assertEqual(self.run_main(self.root)[0], 1)

    def test_file_missing_from_index(self):
        self.put("project_a.md", mem("a"))
        self.index()
        self.assertIn(("not-indexed", "project_a.md"), self.kinds())

    def test_bad_frontmatter(self):
        self.put("project_a.md", "그냥 본문\n")
        self.put("project_b.md", "---\nname: b\n---\n본문\n")
        self.put("project_c.md", mem("c", typ="weird"))
        self.index("project_a.md", "project_b.md", "project_c.md")
        k = self.kinds()
        self.assertIn(("bad-frontmatter", "project_a.md"), k)
        self.assertIn(("bad-frontmatter", "project_b.md"), k)  # description, type 없음
        self.assertIn(("bad-frontmatter", "project_c.md"), k)  # 알 수 없는 type

    def test_broken_wikilink_and_valid_one(self):
        self.put("project_a.md", mem("a", body="[[project_b]] 와 [[nothing]]"))
        self.put("project_b.md", mem("b"))
        self.index("project_a.md", "project_b.md")
        details = [f["detail"] for f in m.structure_findings(self.root)[0]
                   if f["kind"] == "broken-link"]
        self.assertEqual(details, ["[[nothing]] 대상 없음"])

    def test_wikilink_in_code_is_not_a_link(self):
        body = "예시 `[[x]]` 와\n```\n[[y]]\n```\n"
        self.put("project_a.md", mem("a", body=body))
        self.index("project_a.md")
        self.assertEqual(m.structure_findings(self.root)[0], [])

    def test_duplicate_name(self):
        self.put("project_a.md", mem("same"))
        self.put("project_b.md", mem("same"))
        self.index("project_a.md", "project_b.md")
        self.assertIn(("duplicate-name", "project_a.md, project_b.md"), self.kinds())

    def test_personal_files_are_out_of_scope(self):
        self.put("user_me.md", "깨진 개인 파일")
        self.put("project_a.md", mem("a"))
        self.index("project_a.md")
        self.assertEqual(m.structure_findings(self.root)[0], [])
        self.assertEqual(m.audit(self.root, None)["skipped_personal"], ["user_me.md"])

    def test_missing_index_is_reported(self):
        self.put("project_a.md", mem("a"))
        self.assertIn(("no-index", "MEMORY.md"), self.kinds())

    def test_missing_dir_is_usage_error(self):
        code, _, err = self.run_main(self.root / "nope")
        self.assertEqual(code, 2)
        self.assertIn("없다", err)

    def test_missing_repo_is_usage_error(self):
        self.assertEqual(self.run_main(self.root, "--repo", self.repo / "nope")[0], 2)


class Claims(Base):
    def classify(self, body, repo=True):
        self.put("project_a.md", mem("a", body=body))
        self.index("project_a.md")
        rep = m.audit(self.root, self.repo if repo else None)
        return rep["memories"][0]

    def test_existing_path_is_fresh(self):
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts" / "x.py").write_text("print(1)\n")
        self.assertEqual(self.classify("스크립트는 `scripts/x.py` 에 있다")["class"], "fresh")

    def test_bare_filename_found_anywhere_is_fresh(self):
        (self.repo / "deep").mkdir()
        (self.repo / "deep" / "tool.py").write_text("x\n")
        self.assertEqual(self.classify("`tool.py` 를 쓴다")["class"], "fresh")

    def test_moved_path_is_stale(self):
        self.assertEqual(self.classify("스크립트는 `scripts/old.py` 에 있다")["class"], "stale")

    def test_symbol_present_and_absent(self):
        (self.repo / "a.go").write_text("func Reconcile() {}\n")
        self.assertEqual(self.classify("`Reconcile()` 가 있다")["class"], "fresh")
        self.assertEqual(self.classify("`Missing()` 가 있다")["class"], "stale")

    def test_no_repo_is_unverified_not_fresh(self):
        c = self.classify("스크립트는 `scripts/x.py` 에 있다", repo=False)
        self.assertEqual(c["class"], "unverified")

    def test_issue_numbers_are_never_fresh(self):
        c = self.classify("이슈 #196 은 아직 열려 있다")
        self.assertEqual([(x["kind"], x["value"], x["state"]) for x in c["claims"]],
                         [("issue", "196", "unverified")])
        self.assertEqual(c["class"], "unverified")

    def test_memory_without_claims_is_not_fresh(self):
        self.assertEqual(self.classify("그냥 서술만 있다")["class"], "unverified")

    def test_one_stale_claim_wins_over_fresh(self):
        (self.repo / "ok.py").write_text("x\n")
        self.assertEqual(self.classify("`ok.py` 와 `gone/x.py`")["class"], "stale")

    def test_fresh_plus_unverified_stays_unverified(self):
        (self.repo / "ok.py").write_text("x\n")
        self.assertEqual(self.classify("`ok.py` 이고 #5 도 있다")["class"], "unverified")

    def test_host_path_outside_repo_is_unverified(self):
        c = self.classify("서버 설정은 `/etc/definitely-not-here/app.conf` 에 있다")
        self.assertEqual(c["claims"][0]["state"], "unverified")

    def test_glob_url_option_and_fenced_text_are_not_claims(self):
        body = ("`grep --include=\"*.java\"` 와 `*.md` 와 `https://x.example/a/b.html` 와 `--flag/x`\n"
                "```\n`fake/path.py` #999\n```\n")
        self.assertEqual(self.classify(body)["claims"], [])

    def test_hash_inside_entity_or_word_is_not_an_issue(self):
        self.assertEqual(self.classify("색상 abc#12 와 &#8942;")["claims"], [])


class ReadOnly(Base):
    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.root.iterdir()}

    def test_audit_never_modifies_memory(self):
        self.put("project_a.md", mem("a", body="`gone/x.py` #3"))
        self.put("project_dead.md", "깨짐")
        self.index("project_a.md", "ghost.md")
        before = self.snapshot()
        self.run_main(self.root, "--repo", self.repo)
        self.run_main(self.root, "--json")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / "archive").exists())

    def test_json_output_parses(self):
        import json
        self.put("project_a.md", mem("a"))
        self.index("project_a.md")
        code, out, _ = self.run_main(self.root, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["memories"][0]["file"], "project_a.md")


if __name__ == "__main__":
    unittest.main()
