"""yd-blueprint 뼈대 생성기와 검사기(check.ts)의 동작을 고정한다.

생성기 테스트는 bash 와 git 만 있으면 돌고, 검사기 테스트는 bun 이 있어야 돈다
(없으면 skip). 검사기는 node_modules 없이 돌도록 만들어져 있어 bun install 은 하지 않는다.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
NEW = SKILL / "scripts" / "new-blueprint.sh"
HAS_RUNTIME = shutil.which("bun") is not None or shutil.which("node") is not None


def sh(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)


def line(**kw):
    return json.dumps(kw, ensure_ascii=False)


META = line(kind="meta", title="t", asOf="2026-10-05")
LANE = line(kind="lane", id="front", title="프론트")
LANE2 = line(kind="lane", id="back", title="백엔드")


def node(id="a", lane="front", row=0, **extra):
    base = dict(kind="node", id=id, lane=lane, row=row, title="상자", state="done", summary="요약")
    base.update(extra)
    return line(**base)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="yd-blueprint-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        sh(["git", "init", "-q"], self.tmp)
        (self.tmp / "README.md").write_text("x\n", encoding="utf-8")

    def scaffold(self, *extra, cwd=None, env=None):
        return sh([str(NEW), "--no-install", *extra], cwd or self.tmp, env)

    @property
    def app(self):
        return self.tmp / "frontend"

    def write_data(self, *lines):
        (self.app / "data" / "blueprint.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def check(self, *args):
        return sh(["sh", "scripts/check.sh", *args], self.app)


class ScaffoldTests(Base):
    def test_scaffold_vite_base_blueprint(self):
        r = self.scaffold()
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = (self.app / "vite.config.ts").read_text(encoding="utf-8")
        self.assertIn('base: "/blueprint/"', cfg)
        self.assertNotIn("port:", cfg)  # 기본 포트를 그대로 쓴다
        pkg = json.loads((self.app / "package.json").read_text(encoding="utf-8"))
        self.assertTrue(pkg["name"].endswith("-blueprint"))
        self.assertNotIn("__NAME__", json.dumps(pkg))
        self.assertTrue((self.app / "data" / "blueprint.jsonl").is_file())

    def test_package_scripts_are_manager_neutral(self):
        self.assertEqual(self.scaffold().returncode, 0)
        pkg = json.loads((self.app / "package.json").read_text(encoding="utf-8"))
        for name, command in pkg["scripts"].items():
            for word in ("bun", "bunx", "pnpm", "npm ", "node "):
                self.assertNotIn(word, command, f"scripts.{name} 가 {word!r} 를 직접 부른다")
        self.assertEqual(pkg["scripts"]["check"], "sh scripts/check.sh")

    def test_pm_option_is_validated_and_printed(self):
        r = self.scaffold("--pm", "yarn")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("bun·pnpm·npm", r.stderr)
        r = self.scaffold("--pm", "pnpm")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pnpm run dev", r.stdout)

    def test_scaffold_pins_loopback_host(self):
        self.assertEqual(self.scaffold().returncode, 0)
        cfg = (self.app / "vite.config.ts").read_text(encoding="utf-8")
        self.assertIn('host: "127.0.0.1"', cfg)

    def test_scaffold_refuses_existing(self):
        self.assertEqual(self.scaffold().returncode, 0)
        before = (self.app / "data" / "blueprint.jsonl").read_text(encoding="utf-8")
        r = self.scaffold()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("덮어쓰지 않는다", r.stderr)
        self.assertEqual(before, (self.app / "data" / "blueprint.jsonl").read_text(encoding="utf-8"))

    def test_scaffold_dir_cannot_escape_root(self):
        r = self.scaffold("--dir", "../outside")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.tmp.parent / "outside").exists())

    def test_not_git_repo_needs_root(self):
        plain = Path(tempfile.mkdtemp(prefix="yd-blueprint-plain-"))
        self.addCleanup(shutil.rmtree, plain, ignore_errors=True)
        r = self.scaffold(cwd=plain)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--root", r.stderr)
        r = self.scaffold("--root", str(plain), cwd=plain)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_bun_message(self):
        bare = {"PATH": "/usr/bin:/bin"}
        if shutil.which("bun", path=bare["PATH"]):
            self.skipTest("/usr/bin 에 bun 이 있다")
        r = sh([str(NEW)], self.tmp, env={**os.environ, **bare})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("패키지 매니저가 없다", r.stderr)
        self.assertIn("oven-sh/bun", r.stderr)
        self.assertFalse(self.app.exists())


FAKE_PM = """#!/bin/sh
# 가짜 패키지 매니저: 인자를 기록하고 받은 패키지 자리만 만든다(네트워크 없이 돈다).
echo "$PWD $*" >> "$FAKE_PM_LOG"
for a in "$@"; do
  case "$a" in add|install|-*) continue ;; esac
  name="${a%@*}"
  mkdir -p "node_modules/$name" && echo '{}' > "node_modules/$name/package.json"
done
"""


class SharedDepsTests(Base):
    def setUp(self):
        super().setUp()
        self.bin = self.tmp / "fakebin"
        self.bin.mkdir()
        for pm in ("bun", "npm"):
            (self.bin / pm).write_text(FAKE_PM, encoding="utf-8")
            (self.bin / pm).chmod(0o755)
        self.log = self.tmp / "pm.log"
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "FAKE_PM_LOG": str(self.log)}
        self.shared = Path(tempfile.mkdtemp(prefix="yd-blueprint-deps-"))
        self.addCleanup(shutil.rmtree, self.shared, ignore_errors=True)

    def make(self, *extra, root=None):
        args = [str(NEW), "--pm", "bun", "--deps-dir", str(self.shared), *extra]
        return sh(args, root or self.tmp, self.env)

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def test_deps_dir_installs_missing_once_and_links(self):
        r = self.make()
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls()
        self.assertEqual(len(calls), 2, calls)  # dependencies 한 번, devDependencies 한 번
        self.assertIn("add react@", calls[0])
        self.assertIn("add --dev", calls[1])
        self.assertIn("@types/react@", calls[1])
        self.assertTrue(all(c.startswith(str(self.shared.resolve())) for c in calls), "공유 폴더에서 설치")
        link = self.app / "node_modules"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (self.shared / "node_modules").resolve())
        self.assertTrue((self.shared / "package.json").is_file())
        r = self.make("--dir", "second")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.calls()), 2, "이미 있는 패키지는 다시 설치하지 않는다")
        self.assertTrue((self.tmp / "second" / "node_modules").is_symlink())

    def test_deps_dir_parent_needs_no_link(self):
        proj = self.shared / "scratch"
        proj.mkdir()
        sh(["git", "init", "-q"], proj)
        r = self.make(root=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((proj / "frontend" / "node_modules").exists(), "상위 폴더의 node_modules 를 찾는다")
        self.assertTrue((self.shared / "node_modules" / "vite" / "package.json").is_file())

    def test_deps_dir_npm_uses_install_save_dev(self):
        r = sh([str(NEW), "--pm", "npm", "--deps-dir", str(self.shared)], self.tmp, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("install --save-dev", self.calls()[1])

    def test_template_cache_dir_stays_in_project(self):
        self.assertEqual(self.scaffold().returncode, 0)
        cfg = (self.app / "vite.config.ts").read_text(encoding="utf-8")
        self.assertIn('cacheDir: ".vite"', cfg)
        self.assertIn(".vite", (self.app / ".gitignore").read_text(encoding="utf-8").split())


@unittest.skipUnless(HAS_RUNTIME, "bun 또는 node 가 필요하다")
class CheckTests(Base):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.scaffold().returncode, 0)

    @unittest.skipUnless(shutil.which("node"), "node 가 필요하다")
    def test_check_runs_on_node_without_bun(self):
        only_node = self.tmp / "only-node"
        only_node.mkdir()
        os.symlink(shutil.which("node"), only_node / "node")
        env = {**os.environ, "PATH": f"{only_node}:/usr/bin:/bin"}
        if shutil.which("bun", path=env["PATH"]):
            self.skipTest("/usr/bin 에 bun 이 있다")
        r = sh(["sh", "scripts/check.sh", "--stale-days", "100000"], self.app, env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[OK]", r.stdout)

    def test_check_passes_sample(self):
        r = self.check("--stale-days", "100000")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[OK]", r.stdout)

    def test_check_catches_missing_path(self):
        self.write_data(META, LANE, node(paths=["README.md", "src/nope.py"]))
        r = self.check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("없는 경로 'src/nope.py'", r.stderr)
        self.assertNotIn("README.md'", r.stderr)

    def test_no_paths_flag_skips_existence(self):
        self.write_data(META, LANE, node(paths=["src/nope.py"]))
        self.assertEqual(self.check("--no-paths").returncode, 0)

    def test_check_rejects_unknown_field(self):
        self.write_data(META, LANE, node(colour="red"))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("알 수 없는 필드 'colour'", r.stderr)

    def test_check_rejects_cell_collision(self):
        self.write_data(META, LANE, node("a"), node("b"))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("이미 노드가 있습니다", r.stderr)

    def test_check_rejects_edge_to_unknown_node(self):
        self.write_data(META, LANE, node("a"), line(kind="edge", **{"from": "a", "to": "ghost"}))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("없는 to 'ghost'", r.stderr)

    def test_check_rejects_bad_json_and_names_the_line(self):
        self.write_data(META, "{not json}", LANE)
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("blueprint.jsonl:2", r.stderr)

    def test_check_rejects_impossible_date(self):
        self.write_data(line(kind="meta", title="t", asOf="2026-13-45"), LANE, node())
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("asOf", r.stderr)

    def test_stale_warns_but_passes(self):
        self.write_data(line(kind="meta", title="t", asOf="2020-01-01"), LANE, node())
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 0)
        self.assertIn("[WARN] 기준일", r.stderr)

    def test_wide_title_warns_but_passes(self):
        self.write_data(META, LANE, node(title="아주아주아주 긴 상자 제목이 폭을 넘는다 정말로"))
        r = self.check("--no-paths", "--stale-days", "100000")
        self.assertEqual(r.returncode, 0)
        self.assertIn("상자 폭을 넘을 수 있습니다", r.stderr)

    def test_short_latin_title_does_not_warn(self):
        self.write_data(META, LANE, node(title="nginx 게이트 · LAN", lines=["127.0.0.1:18555 · POST 두 개"]))
        r = self.check("--no-paths", "--stale-days", "100000")
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("[WARN]", r.stderr)

    def test_links_accept_paths_and_reject_script_urls(self):
        ok = line(kind="meta", title="t", asOf="2026-10-05", links=[{"label": "감지 화면", "href": "/detect/201/"}])
        self.write_data(ok, LANE, node())
        self.assertEqual(self.check("--no-paths", "--stale-days", "100000").returncode, 0)
        bad = line(kind="meta", title="t", asOf="2026-10-05", links=[{"label": "x", "href": "javascript:alert(1)"}])
        self.write_data(bad, LANE, node())
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("links", r.stderr)

    def test_group_and_boundary_edge_are_accepted(self):
        self.write_data(META, LANE, LANE2, node("a"), node("b", lane="back"),
                        line(kind="edge", **{"from": "a"}, to="b", type="boundary"),
                        line(kind="group", id="host", title="한 호스트", nodes=["b"]))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_group_rejects_unknown_node(self):
        self.write_data(META, LANE, node("a"), line(kind="group", id="host", title="한 호스트", nodes=["a", "ghost"]))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("group host: 없는 node 'ghost'", r.stderr)

    def test_long_sentence_and_field_warn_but_pass(self):
        long_sentence = "가" * 61 + "."
        self.write_data(line(kind="meta", title="t", asOf="2026-10-05", basis="짧은 기준입니다."),
                        LANE, node("a", summary=long_sentence),
                        node("b", row=1, summary=" ".join(["열 글자 문장입니다."] * 13)))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("node a.summary: 문장 61자", r.stderr)
        self.assertIn("node b.summary:", r.stderr)
        self.assertIn("자 안으로 줄이세요", r.stderr)
        self.assertNotIn("meta.basis", r.stderr)

    def test_sample_has_no_length_warnings(self):
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = r.stderr + r.stdout
        self.assertNotIn("안으로 나누세요", out)  # 샘플은 기준일 경고만 날 수 있다
        self.assertNotIn("안으로 줄이세요", out)

    def test_tiers_layout_with_to_next_and_tags(self):
        self.write_data(line(kind="meta", title="t", asOf="2026-10-05", layout="tiers"),
                        line(kind="lane", id="ui", title="화면", toNext="HTTPS / REST"), LANE2,
                        node("a", lane="ui", tags=["React", "Vite"]), node("b", lane="back", tags=["Go"]))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_tiers_rejects_edges(self):
        self.write_data(line(kind="meta", title="t", asOf="2026-10-05", layout="tiers"), LANE, LANE2, node("a"), node("b", lane="back"),
                        line(kind="edge", **{"from": "a"}, to="b"))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("tiers 에서는 edge 를 쓸 수 없습니다", r.stderr)

    def test_to_next_rules(self):
        self.write_data(META, line(kind="lane", id="front", title="프론트", toNext="REST"), node("a"))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("toNext 는 meta.layout 이 tiers 일 때만", r.stderr)
        self.write_data(line(kind="meta", title="t", asOf="2026-10-05", layout="tiers"), line(kind="lane", id="front", title="프론트", toNext="REST"), node("a"))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("마지막 띠에는 toNext 를 쓰지 않습니다", r.stderr)

    def test_tiers_group_must_be_one_lane_and_adjacent(self):
        self.write_data(line(kind="meta", title="t", asOf="2026-10-05", layout="tiers"), LANE, LANE2, node("a"), node("b", row=1), node("c", row=2), node("d", lane="back"),
                        line(kind="group", id="gap", title="떨어진 묶음", nodes=["a", "c"]),
                        line(kind="group", id="cross", title="띠 건너기", nodes=["a", "d"]))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("group gap: tiers 에서는 이웃한 노드만", r.stderr)
        self.assertIn("group cross: tiers 에서는 한 띠 안의 노드만", r.stderr)

    def test_tags_limits(self):
        self.write_data(META, LANE, node("a", tags=["a", "b", "c", "d"]))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 1)
        self.assertIn("tags 는 3개까지", r.stderr)
        self.write_data(META, LANE, node("a", lines=["한 줄", "두 줄", "세 줄"], tags=["PostgreSQL 17 shared cluster"]))
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("18자를 넘습니다", r.stderr)
        self.assertIn("lines 와 tags 를 합쳐 4줄", r.stderr)

    def test_tiers_warns_on_crowded_band(self):
        nodes = [node(f"n{i}", row=i) for i in range(7)]
        self.write_data(line(kind="meta", title="t", asOf="2026-10-05", layout="tiers"), LANE, *nodes)
        r = self.check("--no-paths")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("노드 7개", r.stderr)

    def test_blank_lines_are_ignored(self):
        self.write_data(META, "", LANE, "   ", node(), "")
        r = self.check("--no-paths", "--stale-days", "100000")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_check_without_repo_needs_flag(self):
        plain = Path(tempfile.mkdtemp(prefix="yd-blueprint-plain-"))
        self.addCleanup(shutil.rmtree, plain, ignore_errors=True)
        self.assertEqual(self.scaffold("--root", str(plain), cwd=plain).returncode, 0)
        r = sh(["sh", "scripts/check.sh"], plain / "frontend")
        self.assertEqual(r.returncode, 1)
        self.assertIn("--repo-root", r.stderr)


if __name__ == "__main__":
    unittest.main()
