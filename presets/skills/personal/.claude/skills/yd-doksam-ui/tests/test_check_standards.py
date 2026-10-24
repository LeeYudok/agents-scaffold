"""check_standards.py 가 맨손 grep 의 오탐을 실제로 제거하는지 검증 (stdlib only).

이 스캐너의 존재 이유가 "grep -r ' any' 는 company 를 잡는다" 이므로,
탐지(true positive)만큼 **비탐지(false positive 부재)** 를 같은 무게로 단언한다.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_ROOT / "scripts" / "check_standards.py"

spec = importlib.util.spec_from_file_location("check_standards", SCRIPT)
check_standards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_standards)


class ScanCase(unittest.TestCase):
    def scan(self, name, body, only=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text(body, encoding="utf-8")
            return check_standards.scan([tmp], only)

    def assertHit(self, name, body, key):
        findings = self.scan(name, body, [key])
        self.assertTrue(findings[key], f"{key} 를 잡았어야 한다: {body!r}")

    def assertClean(self, name, body, key):
        findings = self.scan(name, body, [key])
        self.assertFalse(findings[key], f"{key} 오탐: {findings[key]}")


class TestColor(ScanCase):
    def test_hex_literal_is_flagged(self):
        self.assertHit("a.tsx", 'const c = "#ff0000"', "color")

    def test_color_function_literal_is_flagged(self):
        self.assertHit("a.tsx", "const c = rgb(255, 0, 0)", "color")

    def test_tailwind_palette_class_is_flagged(self):
        self.assertHit("a.tsx", '<p className="text-red-600" />', "color")

    def test_semantic_token_class_is_clean(self):
        self.assertClean(
            "a.tsx",
            '<p className="bg-background text-destructive text-chart-1" />',
            "color")

    def test_gain_loss_token_is_clean(self):
        self.assertClean("a.tsx", '<span className="text-[--gain]" />', "color")

    def test_token_source_css_may_define_hex(self):
        self.assertClean("globals.css", "  --background: #ffffff;", "color")

    def test_issue_reference_is_clean(self):
        self.assertClean("a.tsx", "// 한국 시/도 분포 지도 (bizinfo #233 이식, #56).", "color")
        self.assertClean("a.tsx", '<span>배치 #241</span>', "color")

    def test_anchor_fragment_is_clean(self):
        self.assertClean("a.tsx", '{ href: "#feed", label: "피드" },', "color")

    def test_short_hex_literal_is_flagged(self):
        self.assertHit("a.tsx", 'const c = "#f00"', "color")

    def test_shadcn_primitive_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "components" / "ui"
            target.mkdir(parents=True)
            (target / "bubble.tsx").write_text(
                'className="bg-[oklch(from_var(--primary)_0.93_c_h)]"',
                encoding="utf-8")
            self.assertFalse(check_standards.scan([tmp], ["color"])["color"])

    def test_component_test_file_is_skipped(self):
        self.assertClean("relation-network.test.tsx",
                         '{ key: "a", color: "#22d3ee" },', "color")

    def test_css_var_reference_is_clean(self):
        self.assertClean("a.tsx", "const c = 'var(--primary)'", "color")


class TestEmoji(ScanCase):
    def test_emoji_is_flagged(self):
        self.assertHit("a.tsx", "<span>\U0001F4CB</span>", "emoji")

    def test_korean_text_is_clean(self):
        self.assertClean("a.tsx", '<p>주문 내역을 확인하세요</p>', "emoji")

    def test_korean_comment_is_clean(self):
        self.assertClean("a.tsx", "// 등락색은 --gain / --loss 를 쓴다", "emoji")

    def test_cjk_and_japanese_are_clean(self):
        self.assertClean("a.tsx", '<p>注文履歴 · 訂單 · 주문</p>', "emoji")

    def test_phosphor_import_is_clean(self):
        self.assertClean(
            "a.tsx",
            'import { CaretRight } from "@phosphor-icons/react/dist/ssr"',
            "emoji")


class TestUrl(ScanCase):
    """폐쇄망 규칙이 막는 것은 '리소스를 실제로 가져오는 것'이다."""

    def test_fetch_is_flagged(self):
        self.assertHit("a.tsx", 'fetch("https://cdn.example.com/x.json")', "url")

    def test_script_src_is_flagged(self):
        self.assertHit(
            "a.tsx",
            '<Script src="https://www.googletagmanager.com/gtag/js?id=X" />',
            "url")

    def test_img_src_is_flagged(self):
        self.assertHit("a.tsx", '<img src="https://cdn.example.com/a.png" />', "url")

    def test_link_stylesheet_is_flagged(self):
        self.assertHit(
            "a.tsx",
            '<link rel="stylesheet" href="https://fonts.example.com/x.css" />',
            "url")

    def test_css_url_is_flagged(self):
        self.assertHit("a.css", "background: url(https://cdn.example.com/a.png);",
                       "url")

    def test_anchor_href_is_clean(self):
        """바깥으로 나가는 링크는 네트워크 요청이 아니다."""
        self.assertClean(
            "a.tsx",
            '<a href="https://www.doksam.com" target="_blank">doksam</a>',
            "url")

    def test_displayed_url_string_is_clean(self):
        self.assertClean(
            "a.tsx",
            '<Input readOnly defaultValue="https://ui.doksam.com/components" />',
            "url")

    def test_mock_data_base_url_is_clean(self):
        self.assertClean("a.ts", 'webhookUrl: "https://hooks.example.com/events",',
                         "url")

    def test_comment_link_is_clean(self):
        self.assertClean("a.tsx", "// 참고: https://ui.doksam.com/rules", "url")

    def test_local_path_is_clean(self):
        self.assertClean("a.tsx", 'src="/placeholder/avatar.png"', "url")

    def test_localhost_is_clean(self):
        self.assertClean("a.tsx", 'fetch("http://localhost:3000/api")', "url")


class TestAny(ScanCase):
    def test_annotation_any_is_flagged(self):
        self.assertHit("a.ts", "function f(x: any) {}", "any")

    def test_as_any_is_flagged(self):
        self.assertHit("a.ts", "const v = raw as any", "any")

    def test_generic_any_is_flagged(self):
        self.assertHit("a.ts", "const v: Array<any> = []", "any")

    def test_any_array_is_flagged(self):
        self.assertHit("a.ts", "const v: any[] = []", "any")

    def test_word_containing_any_is_clean(self):
        self.assertClean(
            "a.ts",
            "const company = many.filter((x) => x.germany)",
            "any")

    def test_prose_any_in_string_is_clean(self):
        self.assertClean("a.ts", 'const msg = "any time"', "any")

    def test_tsx_only_scope(self):
        self.assertClean("a.css", ".x { color: var(--primary); }", "any")

    def test_test_file_global_stub_is_clean(self):
        """테스트의 전역 스텁은 프로덕션 타입 안전성과 무관하다."""
        self.assertClean(
            "page.test.tsx",
            ";(globalThis as any).ResizeObserver ??= class {}",
            "any")


class TestSuppression(ScanCase):
    """정당한 예외는 이유와 함께 면제할 수 있어야 한다."""

    def test_allow_color_suppresses_color_only(self):
        line = '  "#ef4444",  // doksam-ui:allow-color 색 선택기 팔레트 원본\n'
        self.assertClean("a.tsx", line, "color")

    def test_bare_allow_suppresses_every_check(self):
        line = 'const c = "#ef4444" // doksam-ui:allow 레거시 마이그레이션 중\n'
        self.assertClean("a.tsx", line, "color")

    def test_wrong_check_name_does_not_suppress(self):
        line = 'const c = "#ef4444" // doksam-ui:allow-url 엉뚱한 면제\n'
        self.assertHit("a.tsx", line, "color")


class TestExitContract(unittest.TestCase):
    def test_clean_tree_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.tsx").write_text(
                '<p className="bg-background">주문</p>\n', encoding="utf-8")
            self.assertEqual(check_standards.main([tmp]), 0)

    def test_violation_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.tsx").write_text(
                '<p className="text-red-600">x</p>\n', encoding="utf-8")
            self.assertEqual(check_standards.main([tmp]), 1)

    def test_skips_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "node_modules" / "pkg"
            nested.mkdir(parents=True)
            (nested / "a.tsx").write_text('c = "#ff0000"', encoding="utf-8")
            self.assertEqual(check_standards.main([tmp]), 0)


if __name__ == "__main__":
    unittest.main()
