"""check_bundle.py 회귀 테스트. stdlib 만 쓴다."""

import gzip
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_bundle.py"

spec = importlib.util.spec_from_file_location("check_bundle", SCRIPT)
assert spec and spec.loader
check_bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_bundle)


class DistFixture(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def kinds(self, allowed=()):
        found, _ = check_bundle.collect(self.dir, set(allowed))
        return [f.kind for f in found]


class TestExternalURL(DistFixture):
    def test_external_url_is_reported_with_line(self):
        self.write("index.html", "<html>\n<link href='https://fonts.example.com/x.css'>\n</html>")
        found, _ = check_bundle.collect(self.dir, set())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].kind, "external-url")
        self.assertEqual(found[0].line, 2, "줄 번호가 맞아야 한다")

    def test_localhost_and_private_ranges_are_not_external(self):
        self.write("assets/app.js", "\n".join([
            "fetch('http://localhost:9992/api')",
            "fetch('http://127.0.0.1/x')",
            "fetch('http://10.0.0.5/y')",
        ]))
        self.assertEqual(self.kinds(), [])

    def test_xml_namespace_is_not_a_request(self):
        self.write("assets/icon.js", "const NS='http://www.w3.org/2000/svg'")
        self.assertEqual(self.kinds(), [])

    def test_allow_host_exempts(self):
        self.write("assets/app.js", "fetch('https://ui.doksam.com/r/x.json')")
        self.assertEqual(self.kinds(), ["external-url"])
        self.assertEqual(self.kinds(allowed=["ui.doksam.com"]), [])

    def test_doc_link_in_error_message_is_not_flagged(self):
        # React·Tailwind 등은 에러 메시지에 문서 URL 을 심어 둔다. 요청이 아니다.
        self.write("assets/app.js", 
                   'throw Error("자세히: https://react.dev/errors/418")')
        self.write("assets/app.css", "/* https://tailwindcss.com/docs */\n.a{color:red}")
        self.assertEqual(self.kinds(), [])

    def test_strict_mode_reports_doc_links(self):
        self.write("assets/app.js", 'throw Error("https://react.dev/errors/418")')
        found, _ = check_bundle.collect(self.dir, set(), strict=True)
        self.assertEqual([f.kind for f in found], ["external-url"])

    def test_requesting_contexts_are_flagged(self):
        cases = {
            "a.html": '<script src="https://cdn.example.com/x.js"></script>',
            "b.css": "@import 'https://fonts.example.com/x.css';",
            "c.css": ".a{background:url(https://img.example.com/x.png)}",
            "d.js": 'fetch("https://api.example.com/x")',
            "e.js": 'el.src = "https://cdn.example.com/y.js"',
        }
        for name, body in cases.items():
            with self.subTest(name=name):
                shutil.rmtree(self.dir, ignore_errors=True)
                self.dir.mkdir(parents=True, exist_ok=True)
                self.write(name, body)
                self.assertEqual(self.kinds(), ["external-url"], f"{name} 이 안 잡혔다")

    def test_binary_assets_are_not_scanned(self):
        # woff2 안의 바이트열이 URL 처럼 보여도 검사 대상이 아니다
        (self.dir / "assets").mkdir()
        (self.dir / "assets" / "font.woff2").write_bytes(b"\x00https://evil.example.com\x00")
        self.assertEqual(self.kinds(), [])


class TestSourcemap(DistFixture):
    def test_map_file_is_reported(self):
        self.write("assets/app.js.map", "{}")
        self.assertEqual(self.kinds(), ["sourcemap"])

    def test_source_mapping_comment_is_reported(self):
        self.write("assets/app.js", "console.log(1)\n//# sourceMappingURL=app.js.map")
        self.assertEqual(self.kinds(), ["sourcemap"])


class TestBudget(DistFixture):
    def _incompressible(self, n: int) -> str:
        # gzip 이 줄이지 못하게 엔트로피가 높은 문자열을 만든다.
        # 재현 가능해야 하므로 난수 대신 고정 시드 LCG 를 쓴다.
        state = 0x2545F491
        out = []
        for _ in range(n):
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            out.append(chr(0x20 + (state >> 13) % 95))
        return "".join(out)

    def test_fixture_is_actually_incompressible(self):
        # 이 픽스처가 압축돼 버리면 아래 예산 테스트가 의미를 잃는다
        body = self._incompressible(200_000).encode()
        self.assertGreater(len(gzip.compress(body, 6)), len(body) * 0.5)

    def test_small_bundle_passes(self):
        self.write("assets/app.js", "const a=1")
        self.write("assets/app.css", ".a{color:red}")
        self.assertEqual(self.kinds(), [])

    def test_oversized_js_is_reported(self):
        body = self._incompressible(check_bundle.BUDGET_JS * 3)
        self.write("assets/app.js", body)
        found, totals = check_bundle.collect(self.dir, set())
        self.assertIn("budget", [f.kind for f in found])
        self.assertGreater(totals["js"], check_bundle.BUDGET_JS)

    def test_gzip_size_is_measured_not_raw(self):
        # 같은 문자 반복은 원본이 커도 gzip 후에는 작다 → 예산을 넘지 않아야 한다
        self.write("assets/app.js", "a" * (check_bundle.BUDGET_JS * 4))
        found, totals = check_bundle.collect(self.dir, set())
        self.assertEqual([f.kind for f in found], [])
        self.assertLess(totals["js"], check_bundle.BUDGET_JS)


class TestGzipHelper(DistFixture):
    def test_gzip_size_matches_gzip_module(self):
        path = self.write("assets/app.js", "const answer = 42")
        self.assertEqual(
            check_bundle.gzip_size(path),
            len(gzip.compress(path.read_bytes(), 6)),
        )


if __name__ == "__main__":
    unittest.main()
