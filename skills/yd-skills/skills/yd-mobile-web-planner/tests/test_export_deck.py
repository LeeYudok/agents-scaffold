"""export_deck.py 의 PPTX 조립 계약을 검증한다 (stdlib only).

Chrome 을 띄우는 부분은 이 테스트의 대상이 아니다 — 캡처는 환경에 의존하고
느리다. 대신 순수 함수인 슬라이드 분해와 OOXML 조립을 검증한다.
"""
import re
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import export_deck  # noqa: E402


PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100" "05fe02fe" "dccc59e7"
    "0000000049454e44ae426082"
)


def storyboard(slide_count):
    slides = "".join(
        f'<div class="ppt-slide"><div class="ppt-top-bar">'
        f'<div class="ppt-top-no">NO. {i:02d}</div></div>'
        f'<div class="ppt-content"><div class="ppt-body-full">본문 {i}</div></div>'
        f'</div>'
        for i in range(1, slide_count + 1)
    )
    return (f'<html><head><style>.x{{}}</style></head><body>'
            f'<div class="docwrap">{slides}</div></body></html>')


class TestSlideSplit(unittest.TestCase):
    def test_splits_every_slide_in_document_order(self):
        slides = export_deck.split_slides(storyboard(4))
        self.assertEqual([no for no, _ in slides], ["01", "02", "03", "04"])

    def test_keeps_nested_divs_intact(self):
        _, block = export_deck.split_slides(storyboard(1))[0]
        self.assertIn("ppt-body-full", block)
        self.assertTrue(block.endswith("</div>"))
        # 여는 div 와 닫는 div 수가 같아야 블록이 온전하다
        self.assertEqual(len(re.findall(r"<div\b", block)),
                         len(re.findall(r"</div>", block)))

    def test_isolated_page_preserves_original_page_number(self):
        """Page No. 는 CSS counter 라 떼어내면 1부터 다시 센다."""
        page = export_deck.isolated_page("<html><head></head>", "<div/>", 14)
        self.assertIn("counter-reset:slide 14", page)


class TestPptxPackage(unittest.TestCase):
    def _build(self, count):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shots = []
        for i in range(1, count + 1):
            shot = root / f"image{i}.png"
            shot.write_bytes(PNG_1PX)
            shots.append(shot)
        dest = root / "deck.pptx"
        export_deck.build_pptx(shots, dest)
        return zipfile.ZipFile(dest)

    def test_relationship_types_use_the_officedocument_namespace(self):
        """관계 타입 URL 은 패키지 네임스페이스에서 파생시킬 수 없다.

        둘을 문자열 조작으로 합치면 package/2006/officeDocument/2006/... 같은
        무효 URL 이 나오는데 XML 은 여전히 well-formed 라 파싱 검사로는 잡히지
        않는다. 실제로 그 버그가 있었고, 파일은 열리지 않는다.
        """
        pkg = self._build(2)
        for name in pkg.namelist():
            if not name.endswith(".rels"):
                continue
            for url in re.findall(r'Type="([^"]+)"', pkg.read(name).decode()):
                with self.subTest(part=name, url=url):
                    self.assertTrue(
                        url.startswith(
                            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"),
                        f"관계 타입 URL 이 잘못됐다: {url}")

    def test_every_part_is_wellformed_xml(self):
        pkg = self._build(3)
        for name in pkg.namelist():
            if name.endswith((".xml", ".rels")):
                with self.subTest(part=name):
                    ET.fromstring(pkg.read(name))

    def test_content_types_declares_every_slide(self):
        pkg = self._build(5)
        declared = pkg.read("[Content_Types].xml").decode()
        for i in range(1, 6):
            with self.subTest(slide=i):
                self.assertIn(f'PartName="/ppt/slides/slide{i}.xml"', declared)

    def test_each_slide_references_an_image_that_exists(self):
        pkg = self._build(4)
        names = set(pkg.namelist())
        for i in range(1, 5):
            rels = pkg.read(f"ppt/slides/_rels/slide{i}.xml.rels").decode()
            targets = re.findall(r'Target="\.\./media/([^"]+)"', rels)
            with self.subTest(slide=i):
                self.assertEqual(len(targets), 1)
                self.assertIn(f"ppt/media/{targets[0]}", names)

    def test_presentation_lists_every_slide_with_matching_rels(self):
        pkg = self._build(6)
        pres = pkg.read("ppt/presentation.xml").decode()
        rels = pkg.read("ppt/_rels/presentation.xml.rels").decode()
        rids = re.findall(r'<p:sldId id="\d+" r:id="(rId\d+)"/>', pres)
        self.assertEqual(len(rids), 6)
        for rid in rids:
            with self.subTest(rid=rid):
                self.assertRegex(rels, f'Id="{rid}"[^>]*Target="slides/slide\\d+\\.xml"')

    def test_slide_size_is_16_by_9_widescreen(self):
        pres = self._build(1).read("ppt/presentation.xml").decode()
        self.assertIn(f'<p:sldSz cx="{export_deck.EMU_W}" cy="{export_deck.EMU_H}"/>', pres)
        self.assertAlmostEqual(export_deck.EMU_W / export_deck.EMU_H, 16 / 9, places=3)

    def test_image_fills_the_whole_slide(self):
        slide = self._build(1).read("ppt/slides/slide1.xml").decode()
        self.assertIn('<a:off x="0" y="0"/>', slide)
        self.assertIn(f'<a:ext cx="{export_deck.EMU_W}" cy="{export_deck.EMU_H}"/>', slide)


class TestPrintCssFallback(unittest.TestCase):
    """인쇄 CSS 가 없는 예전 산출물도 A4 로 떨어져야 한다.

    #114 이전에 만든 문서에는 @page 가 없다. 그대로 인쇄하면 기본 용지(US
    Letter 세로)로 떨어지고 슬라이드가 페이지 경계에서 잘린다 — 46슬라이드
    문서가 20페이지로 나온 실측 사례가 있다.
    """

    def test_template_still_exposes_the_print_block(self):
        css = export_deck.template_print_css()
        self.assertIsNotNone(css, "템플릿에서 인쇄 CSS 를 찾지 못했다 — 표식이 바뀌었나")
        self.assertIn("@page", css)
        self.assertIn("size: A4 landscape", css)
        self.assertIn("@media print", css)

    def test_injected_css_lands_inside_the_style_block(self):
        css = export_deck.template_print_css()
        legacy = storyboard(2)
        self.assertNotIn("@media print", legacy)
        patched = legacy.replace("</style>", css + "</style>", 1)
        self.assertIn("@media print", patched)
        # 스타일 블록 안에 들어가야 유효하다
        self.assertLess(patched.index("@page"), patched.index("</style>"))

    def test_print_css_is_not_duplicated_in_the_script(self):
        """인쇄 CSS 의 원본은 템플릿 한 곳이다."""
        source = (SKILL_ROOT / "scripts" / "export_deck.py").read_text(encoding="utf-8")
        self.assertNotIn("size: A4 landscape", source)


class TestParallelCapture(unittest.TestCase):
    """캡처는 병렬로 돈다 — 슬라이드끼리 파일을 공유하면 안 된다."""

    def setUp(self):
        self.seen_pages = []
        self.original = export_deck.run_chrome

        def fake_run_chrome(chrome, *args):
            # --screenshot=<경로> 와 file://<경로> 를 뜯어 기록하고 결과를 만든다
            shot = next(a.split("=", 1)[1] for a in args if a.startswith("--screenshot="))
            page = next(a[len("file://"):] for a in args if a.startswith("file://"))
            self.seen_pages.append((Path(page).name,
                                    Path(page).read_text(encoding="utf-8")))
            Path(shot).write_bytes(PNG_1PX)

        export_deck.run_chrome = fake_run_chrome
        self.addCleanup(lambda: setattr(export_deck, "run_chrome", self.original))

    def test_each_slide_writes_its_own_temp_page(self):
        """임시 HTML 을 한 파일에 덮어쓰면 병렬 실행에서 서로를 덮어쓴다."""
        with TemporaryDirectory() as tmp:
            slides = export_deck.split_slides(storyboard(6))
            head = "<html><head></head>"
            export_deck.shoot_slides("chrome", head, slides, Path(tmp), 2.0, jobs=4)
        names = [name for name, _ in self.seen_pages]
        self.assertEqual(len(names), 6)
        self.assertEqual(len(set(names)), 6, f"임시 파일 이름이 겹친다: {names}")

    def test_shots_come_back_in_slide_order(self):
        """as_completed 는 완료 순서라 결과를 순번으로 되돌려야 한다."""
        with TemporaryDirectory() as tmp:
            slides = export_deck.split_slides(storyboard(8))
            shots = export_deck.shoot_slides("chrome", "<html><head></head>",
                                             slides, Path(tmp), 2.0, jobs=4)
        self.assertEqual([s.name for s in shots],
                         [f"image{i}.png" for i in range(1, 9)])

    def test_each_page_carries_its_own_slide_content(self):
        with TemporaryDirectory() as tmp:
            slides = export_deck.split_slides(storyboard(5))
            export_deck.shoot_slides("chrome", "<html><head></head>",
                                     slides, Path(tmp), 2.0, jobs=5)
        for name, body in self.seen_pages:
            index = int(re.search(r"_slide(\d+)\.html", name).group(1))
            with self.subTest(page=name):
                self.assertIn(f"본문 {index}<", body)

    def test_default_jobs_leaves_headroom_and_is_bounded(self):
        jobs = export_deck.default_jobs()
        self.assertGreaterEqual(jobs, 1)
        self.assertLessEqual(jobs, 8)


class TestDesignConstants(unittest.TestCase):
    def test_capture_width_matches_the_template_design_width(self):
        """목업 크기와 배지 top 이 이 폭에서 나온 절대 픽셀값이다."""
        template = (SKILL_ROOT / "resources" / "template.html").read_text(encoding="utf-8")
        self.assertIn(f"max-width: {export_deck.DESIGN_W}px", template)

    def test_render_wait_is_long_enough_for_mermaid(self):
        """대기가 없으면 IA·흐름도·시퀀스가 빈 칸으로 나온다."""
        self.assertGreaterEqual(export_deck.RENDER_WAIT_MS, 5000)


DESC_SAMPLE = {
    "hasPanel": True,
    "slide": {"w": 1400, "h": 787.5},
    "items": [
        {"label": "1-1", "badge": {"x": 1216, "y": 142, "w": 29, "h": 21},
         "text": {"x": 1254, "y": 142, "w": 130, "h": 49},
         "lines": ["알림 아이콘", "미읽음 존재 시 적색 점", "탭: 알림 목록 (BIZ-ALERT-001)"],
         "boldFirst": True},
        {"label": "2-1", "badge": {"x": 1216, "y": 300, "w": 29, "h": 21},
         "text": {"x": 1254, "y": 300, "w": 130, "h": 33},
         "lines": ["따옴표 & <꺾쇠> 검사"], "boldFirst": False},
    ],
}


class TestEditableDesc(unittest.TestCase):
    """설명 패널을 PPT 도형으로 얹는 경로."""

    def test_emu_scale_comes_from_the_slide_not_a_fixed_dpi(self):
        """고정 96dpi(9525 EMU/px)로 환산하면 도형이 슬라이드 밖으로 나간다.

        슬라이드는 13.333in(96dpi 기준 1280px)인데 설계 폭은 1400px 이다.
        9.4% 어긋나 오른쪽으로 밀리며, 실제로 그 버그가 있었다 (이슈 #125).
        """
        self.assertEqual(export_deck._emu(export_deck.DESIGN_W), export_deck.EMU_W)
        self.assertEqual(export_deck._emu(export_deck.DESIGN_H), export_deck.EMU_H)
        self.assertNotAlmostEqual(export_deck.EMU_PER_PX, 914400 / 96, places=1)

    def test_each_item_yields_a_badge_and_a_text_shape(self):
        xml = export_deck.desc_shapes(DESC_SAMPLE, "0F4C81")
        self.assertEqual(xml.count("<p:sp>"), 4)
        self.assertIn('name="badge 1-1"', xml)
        self.assertIn('name="desc 1-1"', xml)
        self.assertIn("<a:srgbClr val=\"0F4C81\"/>", xml)

    def test_shapes_stay_inside_the_slide(self):
        xml = export_deck.desc_shapes(DESC_SAMPLE, "0F4C81")
        for off, ext in zip(re.findall(r'<a:off x="(\d+)" y="(\d+)"/>', xml),
                            re.findall(r'<a:ext cx="(\d+)" cy="(\d+)"/>', xml)):
            with self.subTest(off=off):
                self.assertLessEqual(int(off[0]) + int(ext[0]), export_deck.EMU_W)
                self.assertLessEqual(int(off[1]) + int(ext[1]), export_deck.EMU_H)

    def test_first_line_is_bold_only_when_the_source_says_so(self):
        xml = export_deck.desc_shapes(DESC_SAMPLE, "0F4C81")
        first = xml[xml.index('name="desc 1-1"'):xml.index('name="badge 2-1"')]
        second = xml[xml.index('name="desc 2-1"'):]
        self.assertIn(f'sz="{export_deck.DESC_PT}" b="1"', first)
        self.assertNotIn(f'sz="{export_deck.DESC_PT}" b="1"', second)

    def test_markup_characters_are_escaped(self):
        xml = export_deck.desc_shapes(DESC_SAMPLE, "0F4C81")
        self.assertIn("&amp;", xml)
        self.assertIn("&lt;꺾쇠&gt;", xml)
        ET.fromstring(f'<root xmlns:a="{export_deck.NS_A}" '
                      f'xmlns:p="{export_deck.NS_P}" xmlns:r="{export_deck.NS_R}">{xml}</root>')

    def test_no_panel_means_no_shapes(self):
        self.assertEqual(export_deck.desc_shapes(None, "0F4C81"), "")

    def test_blanking_css_hides_only_the_panel_body(self):
        """헤더까지 지우면 기준 산출물과 달라지고, display:none 이면 레이아웃이 밀린다."""
        self.assertIn("ppt-desc-body", export_deck.DESC_BLANK_CSS)
        self.assertIn("visibility:hidden", export_deck.DESC_BLANK_CSS)
        self.assertNotIn("display:none", export_deck.DESC_BLANK_CSS)

    def test_accent_is_read_from_the_storyboard(self):
        self.assertEqual(export_deck.slide_accent(":root{--accent: #0f4c81;}"), "0F4C81")
        self.assertEqual(export_deck.slide_accent("accent 없음"), "1B64DA")

    def test_overlay_lands_on_its_own_slide(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            shots = []
            for i in range(1, 4):
                shot = root / f"image{i}.png"
                shot.write_bytes(PNG_1PX)
                shots.append(shot)
            dest = root / "deck.pptx"
            export_deck.build_pptx(shots, dest, {1: '<p:sp id="probe"/>'})
            pkg = zipfile.ZipFile(dest)
            self.assertNotIn("probe", pkg.read("ppt/slides/slide1.xml").decode())
            self.assertIn("probe", pkg.read("ppt/slides/slide2.xml").decode())
            self.assertNotIn("probe", pkg.read("ppt/slides/slide3.xml").decode())


if __name__ == "__main__":
    unittest.main()
