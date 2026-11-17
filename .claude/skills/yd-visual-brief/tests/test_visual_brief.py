"""yd-visual-brief — 검사기·조립기·그림 생성기 테스트 (stdlib only)."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_brief  # noqa: E402
import check_brief  # noqa: E402
import figures  # noqa: E402

EXAMPLE = json.loads((ROOT / "assets" / "example" / "brief.json").read_text(encoding="utf-8"))
PALETTES = json.loads((ROOT / "assets" / "palettes.json").read_text(encoding="utf-8"))["palettes"]


def kinds(problems):
    return [(level, kind) for level, kind, _ in problems]


class Palettes(unittest.TestCase):
    def test_every_shipped_palette_passes(self):
        self.assertGreaterEqual(len(PALETTES), 3)
        for name, p in PALETTES.items():
            self.assertEqual(check_brief.palette_problems(p, name), [], name)

    def test_low_contrast_text_is_an_error(self):
        p = dict(PALETTES["ink-cobalt"], muted="#b0b0b0")
        self.assertIn(("오류", "색 대비"), kinds(check_brief.palette_problems(p)))

    def test_accent_and_signal_must_differ_in_hue(self):
        p = dict(PALETTES["ink-cobalt"], signal="#3a5ae0")
        self.assertIn(("오류", "색 구별"), kinds(check_brief.palette_problems(p)))

    def test_missing_role_is_reported(self):
        p = {k: v for k, v in PALETTES["ink-cobalt"].items() if k != "signal"}
        self.assertEqual(kinds(check_brief.palette_problems(p)), [("오류", "팔레트")])


class Brief(unittest.TestCase):
    def setUp(self):
        self.html = build_brief.build(EXAMPLE)

    def test_example_builds_clean(self):
        self.assertEqual(check_brief.brief_problems(self.html), [])

    def test_example_has_every_figure_kind(self):
        found = set(re.findall(r'data-figure="([a-z-]+)"', self.html))
        self.assertEqual(found, {"architecture", "flow", "compare", "schedule"})

    def test_every_palette_builds_clean(self):
        for name in PALETTES:
            html = build_brief.build(dict(EXAMPLE, palette=name))
            self.assertEqual(check_brief.brief_problems(html), [], name)

    def test_third_hue_is_an_error(self):
        html = self.html.replace("</div>\n</html>", '<i style="color:#2e9d4f"></i></div>\n</html>')
        self.assertIn(("오류", "색 가짓수"), kinds(check_brief.brief_problems(html)))

    def test_small_svg_text_is_an_error(self):
        html = self.html.replace('font-size="11"', 'font-size="9"', 1)
        self.assertIn(("오류", "글자 크기"), kinds(check_brief.brief_problems(html)))

    def test_emoji_is_an_error(self):
        html = self.html.replace("<h2>", "<h2>\U0001F680 ", 1)
        self.assertIn(("오류", "이모지"), kinds(check_brief.brief_problems(html)))

    def test_screenshot_image_is_an_error(self):
        html = self.html.replace("<section>", '<section><img src="capture.png">', 1)
        self.assertIn(("오류", "캡처 이미지"), kinds(check_brief.brief_problems(html)))

    def test_missing_architecture_is_an_error(self):
        html = self.html.replace('data-figure="architecture"', 'data-figure="flow"')
        self.assertIn(("오류", "구성도"), kinds(check_brief.brief_problems(html)))

    def test_two_h1_is_an_error(self):
        html = self.html.replace("<section>", "<section><h1>또 하나</h1>", 1)
        self.assertIn(("오류", "결론"), kinds(check_brief.brief_problems(html)))

    def test_external_resource_is_a_warning(self):
        html = self.html.replace("<style>", '<link rel="stylesheet" href="https://cdn.example.com/a.css"><style>', 1)
        self.assertIn(("경고", "외부 자원"), kinds(check_brief.brief_problems(html)))

    def test_template_loads_nothing_external(self):
        self.assertNotIn(("경고", "외부 자원"), kinds(check_brief.brief_problems(self.html)))

    def test_text_is_escaped(self):
        brief = dict(EXAMPLE, lead="<script>alert(1)</script>")
        self.assertNotIn("<script>alert(1)</script>", build_brief.build(brief))

    def test_title_marks_become_emphasis(self):
        self.assertIn("<em>12주</em>", self.html)


class Figures(unittest.TestCase):
    def setUp(self):
        self.p = figures.palette("ink-cobalt")

    def spec(self, kind):
        for section in EXAMPLE["sections"]:
            for block in section["blocks"]:
                if block["type"] == "figure" and block["kind"] == kind:
                    return block["spec"]
        raise KeyError(kind)

    def test_architecture_puts_outside_system_beyond_the_boundary(self):
        svg = figures.architecture(self.p, self.spec("architecture"))
        boundary = re.search(r'<path d="(M20 74[^"]+)"', svg).group(1)
        self.assertEqual(boundary.count("H832"), 1)
        without = dict(self.spec("architecture"))
        without.pop("outside")
        self.assertNotIn("H832", figures.architecture(self.p, without))

    def test_architecture_numbers_flags_in_signal_colour(self):
        svg = figures.architecture(self.p, self.spec("architecture"))
        self.assertEqual(svg.count(f'r="10" fill="{self.p["signal"]}"'), 4)

    def test_metro_draws_a_cut_line_dashed_in_signal_colour(self):
        svg = figures.metro(self.p, self.spec("metro"))
        self.assertRegex(svg, rf'stroke="{self.p["signal"]}" stroke-width="8"[^>]*stroke-dasharray')

    def test_gantt_places_bars_in_date_order(self):
        svg = figures.gantt(self.p, self.spec("gantt"))
        xs = [float(x) for x in re.findall(r'<rect x="(\d+)" y="\d+" width="\d+" height="28"', svg)]
        self.assertEqual(xs, sorted(xs))
        self.assertEqual(len(xs), 4)

    def test_figures_use_only_palette_colours(self):
        allowed = {v.lower() for v in self.p.values()} | {"#ffffff"}
        for kind, builder in (("architecture", figures.architecture), ("metro", figures.metro),
                              ("compare_rows", figures.compare_rows), ("gantt", figures.gantt), ("dumbbell", figures.dumbbell)):
            used = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}", builder(self.p, self.spec(kind)))}
            self.assertLessEqual(used, allowed, kind)


class Cli(unittest.TestCase):
    def run_script(self, name, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *args], capture_output=True, text=True)

    def test_build_then_check_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "brief.html")
            built = self.run_script("build_brief.py", str(ROOT / "assets" / "example" / "brief.json"), "-o", out)
            self.assertEqual(built.returncode, 0, built.stderr)
            checked = self.run_script("check_brief.py", out)
            self.assertEqual(checked.returncode, 0, checked.stdout)
            self.assertIn("오류 0건", checked.stdout)

    def test_check_exits_one_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.html"
            path.write_text("<html><h1>a</h1></html>", encoding="utf-8")
            self.assertEqual(self.run_script("check_brief.py", str(path)).returncode, 1)

    def test_missing_file_exits_two(self):
        self.assertEqual(self.run_script("check_brief.py", "/nonexistent/brief.html").returncode, 2)

    def test_unknown_block_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brief.json"
            brief = dict(EXAMPLE, sections=[{"label": "a", "title": "b", "blocks": [{"type": "nope"}]}])
            path.write_text(json.dumps(brief), encoding="utf-8")
            self.assertEqual(self.run_script("build_brief.py", str(path), "-o", str(Path(tmp) / "o.html")).returncode, 2)

    def test_palettes_mode_exits_zero(self):
        self.assertEqual(self.run_script("check_brief.py", "--palettes").returncode, 0)


if __name__ == "__main__":
    unittest.main()
