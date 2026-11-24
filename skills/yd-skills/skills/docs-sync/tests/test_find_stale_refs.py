"""find_stale_refs.py 회귀 테스트 (stdlib only). 임시 git 레포에서 돌린다."""
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "find_stale_refs.py"


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def write(root, rel, body):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")


def commit(root, msg):
    sh(root, "git", "add", "-A")
    sh(root, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


def load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import find_stale_refs as mod
    finally:
        sys.path.pop(0)
    return mod


def run(root, *args):
    out = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--json", *args],
                         capture_output=True, text=True)
    return out.returncode, (json.loads(out.stdout) if out.stdout.strip().startswith("{") else out.stderr)


class FindStaleRefsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        sh(self.root, "git", "init", "-q")
        write(self.root, "backend/cmd/server/main.go", "package main\n")
        write(self.root, "backend/README.md", "# backend\n")
        write(self.root, "app/web/src/index.ts", "export {}\n")
        write(self.root, "pack/config/catalog.yaml", "a: 1\n")
        write(self.root, "docs/12_specs.md", "# specs\n")
        write(self.root, "old_name.md", "# old\n")
        self.base = commit(self.root, "base")

        sh(self.root, "git", "rm", "-q", "-r", "backend")
        sh(self.root, "git", "mv", "old_name.md", "new_name.md")
        write(self.root, "AGENTS.md", """\
            # 지침
            서버는 `backend/cmd/server` 로 띄운다.
            예전 샘플 `backend/` 는 #9 에서 제거했다.
            웹 소스는 `web/src` 아래에 있다.
            카탈로그는 `config/catalog.yaml` 이다(팩 기준).
            명세는 `docs/12` 를 본다.
            안내는 [old](old_name.md) 를 본다.
            형식은 `docs/pack-vX.Y.Z` 처럼 쓴다.
            URL `https://example.com/backend/x` 는 경로가 아니다.
            """)
        write(self.root, "CHANGELOG.md", "- `backend/cmd/server` 추가\n")
        commit(self.root, "remove backend")

    def tearDown(self):
        self.tmp.cleanup()

    def refs(self, data, kind):
        return {(f["file"], f["ref"]) for f in data[kind]}

    def test_removed_since_finds_current_and_history(self):
        code, data = run(self.root, "--removed-since", self.base)
        self.assertEqual(code, 1)
        self.assertIn(("AGENTS.md", "backend/cmd/server"), self.refs(data, "current"))

    def test_history_marker_line_is_history(self):
        _, data = run(self.root, "--removed-since", self.base)
        self.assertIn(("AGENTS.md", "backend"), self.refs(data, "history"))  # 「제거했다」 표지
        self.assertNotIn(("AGENTS.md", "backend"), self.refs(data, "current"))

    def test_default_history_files(self):
        write(self.root, "docs/archive/old.md", "`backend/cmd/server` 로 띄운다\n")
        commit(self.root, "archive")
        _, data = run(self.root, "--removed-since", self.base)
        history = self.refs(data, "history")
        self.assertIn(("CHANGELOG.md", "backend/cmd/server"), history)
        self.assertIn(("docs/archive/old.md", "backend/cmd/server"), history)

    def test_current_findings_exit_1(self):
        out = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root),
                              "--removed-since", self.base], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertEqual(out.stderr, "", "exit 1 은 오류가 아니라 고칠 줄이 있다는 뜻")
        self.assertIn("current", out.stdout)

    def test_rename_reports_new_path(self):
        code, data = run(self.root, "--removed-since", self.base)
        renamed = [f for f in data["current"] if f["ref"] == "old_name.md"]
        self.assertEqual(len(renamed), 1)
        self.assertEqual(renamed[0]["reason"], "renamed -> new_name.md")

    def test_subproject_tail_not_reported(self):
        _, data = run(self.root, "--removed-since", self.base)
        refs = {f["ref"] for f in data["current"] + data["history"]}
        self.assertNotIn("web/src", refs)              # app/web/src 꼬리
        self.assertNotIn("config/catalog.yaml", refs)  # pack/config 꼬리

    def test_number_abbreviation_not_reported(self):
        write(self.root, "README.md", "명세는 `docs/12` 를 본다.\n")
        commit(self.root, "add readme")
        for args in ((), ("--removed-since", self.base)):
            _, data = run(self.root, *args)
            refs = {f["ref"] for f in data["current"] + data["history"]}
            self.assertNotIn("docs/12", refs)
            self.assertNotIn("docs/pack-vX.Y.Z", refs)  # 자리표시자

    def test_existence_mode_checks_first_segment(self):
        write(self.root, "README.md", "자세한 건 `docs/13_missing.md` 를 본다. 옆 레포 `other-repo/x.md`.\n")
        commit(self.root, "add readme")
        code, data = run(self.root)
        self.assertEqual(code, 1)
        current = {f["ref"] for f in data["current"]}
        self.assertIn("docs/13_missing.md", current)  # 첫 조각 docs/ 는 있다
        self.assertNotIn("other-repo/x.md", current)  # 첫 조각이 레포에 없다

    def test_removed_top_folder_needs_removed_since(self):
        _, data = run(self.root)
        self.assertNotIn("backend/cmd/server", {f["ref"] for f in data["current"]})
        _, data = run(self.root, "--removed-since", self.base)
        self.assertIn("backend/cmd/server", {f["ref"] for f in data["current"]})

    def test_history_only_passes_unless_strict(self):
        (self.root / "AGENTS.md").write_text("이력: 예전 `backend/` 는 #9 에서 제거했다.\n", encoding="utf-8")
        commit(self.root, "fix docs")
        code, data = run(self.root, "--removed-since", self.base)
        self.assertEqual(data["current"], [])
        self.assertTrue(data["history"])
        self.assertEqual(code, 0, "history 만 남으면 기본은 통과")
        code, _ = run(self.root, "--removed-since", self.base, "--strict")
        self.assertEqual(code, 1, "--strict 는 history 도 실패")

    def test_ignore_regex(self):
        _, data = run(self.root, "--removed-since", self.base, "--ignore", "띄운다")
        self.assertNotIn(("AGENTS.md", "backend/cmd/server"), self.refs(data, "current"))

    def test_bad_rev_and_bad_regex_exit_2(self):
        code, _ = run(self.root, "--removed-since", "no-such-rev")
        self.assertEqual(code, 2)
        code, _ = run(self.root, "--removed-since", self.base, "--ignore", "(")
        self.assertEqual(code, 2)

    def test_code_files_are_not_scanned(self):
        write(self.root, "tools/run.py", "SERVER = 'backend/cmd/server'  # `backend/cmd/server`\n")
        write(self.root, "notes/untracked.md", "`backend/cmd/server`\n")
        sh(self.root, "git", "add", "tools/run.py")
        sh(self.root, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "code")
        _, data = run(self.root, "--removed-since", self.base)
        files = {f["file"] for f in data["current"] + data["history"]}
        self.assertNotIn("tools/run.py", files)        # 코드 파일
        self.assertNotIn("notes/untracked.md", files)  # 추적하지 않는 문서
        self.assertIn("AGENTS.md", files)

    def test_exclude_option(self):
        _, data = run(self.root, "--removed-since", self.base, "--exclude", "AGENTS.md")
        self.assertNotIn("AGENTS.md", {f["file"] for f in data["current"] + data["history"]})
        self.assertIn(("CHANGELOG.md", "backend/cmd/server"), self.refs(data, "history"))

    def test_repo_config_history_and_exclude(self):
        write(self.root, "AGENTS.yaml", """\
            x-doc-sync:
              history:
                - AGENTS.md   # 이 레포에선 지침도 이력 취급(테스트용)
              exclude: ['notes/{a,b}/**']
            """)
        write(self.root, "notes/a/x.md", "`backend/cmd/server`\n")
        commit(self.root, "config")
        _, data = run(self.root, "--removed-since", self.base)
        files = {f["file"] for f in data["current"]}
        self.assertNotIn("AGENTS.md", files)
        self.assertIn(("AGENTS.md", "backend/cmd/server"), self.refs(data, "history"))
        self.assertNotIn("notes/a/x.md", {f["file"] for f in data["current"] + data["history"]})

    def test_repo_config_without_pyyaml(self):
        mod = load_module()
        write(self.root, "AGENTS.yaml", "name: x\nx-doc-sync:\n  history:\n    - CHANGELOG.md\n    - 'plans/**'\n  exclude: [data/**, \"b/*\"]\nother: 1\n")
        saved = sys.modules.get("yaml")
        sys.modules["yaml"] = None  # import yaml -> ImportError
        try:
            cfg = mod.repo_config(self.root)
        finally:
            if saved is None:
                sys.modules.pop("yaml", None)
            else:
                sys.modules["yaml"] = saved
        self.assertEqual(cfg, {"history": ["CHANGELOG.md", "plans/**"], "exclude": ["data/**", "b/*"]})

    def test_glob_brace_and_double_star(self):
        mod = load_module()
        self.assertTrue(mod.glob_match("docs/x/plans/a.md", ["docs/x/{plans,specs}/**"]))
        self.assertTrue(mod.glob_match("docs/x/specs/deep/b.md", ["docs/x/{plans,specs}/**"]))
        self.assertTrue(mod.glob_match("a/b/c.md", ["a/*"]))  # * 도 / 를 넘는다
        self.assertFalse(mod.glob_match("docs/x/other.md", ["docs/x/{plans,specs}/**"]))

    def test_broken_agents_yaml_falls_back(self):
        write(self.root, "AGENTS.yaml", "x-doc-sync: [\n  history: {\n")
        commit(self.root, "broken yaml")
        out = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--json",
                              "--removed-since", self.base], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stderr)  # 2(오류)가 아니라 기본값으로 돈다
        data = json.loads(out.stdout)
        self.assertIn(("AGENTS.md", "backend/cmd/server"), self.refs(data, "current"))
        self.assertIn(("CHANGELOG.md", "backend/cmd/server"), self.refs(data, "history"))
        try:
            import yaml  # noqa: F401
        except ImportError:
            return  # PyYAML 이 없으면 정규식 경로가 섹션을 못 찾고 조용히 기본값으로 간다
        self.assertIn("경고", out.stderr)


if __name__ == "__main__":
    unittest.main()
