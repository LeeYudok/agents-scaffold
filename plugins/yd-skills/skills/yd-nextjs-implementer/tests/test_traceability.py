import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "validate_traceability", ROOT / "scripts" / "validate_traceability.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


RULES = """# T Business Rules

## DTC-MAIN-001 홈

### 출력 규칙
| 상태 | 표시 |
|---|---|
| DTC-MAIN-001.OUT-01 · 로딩 | 스켈레톤 |
"""


class TestTraceability(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "home.tsx").write_text("export {}", encoding="utf-8")
        (self.root / "src" / "home.test.tsx").write_text("export {}", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self):
        return {"screens": [{
            "screenId": "DTC-MAIN-001",
            "route": "/",
            "implementation": ["src/home.tsx"],
            "rules": [{
                "ruleId": "DTC-MAIN-001.OUT-01",
                "tests": ["src/home.test.tsx"],
            }],
        }]}

    def test_valid_manifest_passes(self):
        self.assertEqual(validator.validate(self.manifest(), RULES, self.root), [])

    def test_missing_rule_and_file_are_reported(self):
        manifest = self.manifest()
        manifest["screens"][0]["implementation"] = ["src/missing.tsx"]
        manifest["screens"][0]["rules"] = []
        joined = "\n".join(validator.validate(manifest, RULES, self.root))
        self.assertIn("구현 파일 없음", joined)
        self.assertIn("규칙 ID 누락", joined)

    def test_wrong_screen_and_duplicate_rule_are_reported(self):
        manifest = self.manifest()
        rule = manifest["screens"][0]["rules"][0]
        rule["ruleId"] = "DTC-OTHER-001.OUT-01"
        manifest["screens"][0]["rules"].append(dict(rule))
        joined = "\n".join(validator.validate(manifest, RULES, self.root))
        self.assertIn("다른 화면", joined)
        self.assertIn("중복 규칙 ID", joined)


class TestRouteRegistration(unittest.TestCase):
    """SPA 모드에서 매핑표와 라우터가 어긋나는 경우 (이슈 #139).

    빌드도 타입 검사도 통과하고, 그 URL 로 들어갔을 때만 빈 화면이 된다 —
    그래서 기계 대조가 필요하다.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        for name in ("home.tsx", "home.test.tsx", "board.tsx", "board.test.tsx"):
            (self.root / "src" / name).write_text("export {}", encoding="utf-8")

    def manifest(self, *screens):
        return {"screens": list(screens)}

    def screen(self, screen_id, route, stem):
        return {
            "screenId": screen_id,
            "route": route,
            "implementation": [f"src/{stem}.tsx"],
            "rules": [{"ruleId": f"{screen_id}.OUT-01",
                       "tests": [f"src/{stem}.test.tsx"]}],
        }

    def rules_for(self, *screen_ids):
        return "\n".join(
            f"## {sid} 화면\n\n### 출력 규칙\n| {sid}.OUT-01 · 로딩 | 스켈레톤 |\n"
            for sid in screen_ids)

    def test_route_object_syntax_is_read(self):
        router = 'createBrowserRouter([{ path: "/", element: <Home/> }])'
        result = validator.validate(
            self.manifest(self.screen("DTC-MAIN-001", "/", "home")),
            self.rules_for("DTC-MAIN-001"), self.root, [router])
        self.assertEqual(result, [])

    def test_jsx_route_syntax_is_read(self):
        router = '<Route path="/board" element={<Board/>} />'
        result = validator.validate(
            self.manifest(self.screen("DTC-BOARD-001", "/board", "board")),
            self.rules_for("DTC-BOARD-001"), self.root, [router])
        self.assertEqual(result, [])

    def test_unregistered_route_is_reported(self):
        router = 'createBrowserRouter([{ path: "/", element: <Home/> }])'
        joined = "\n".join(validator.validate(
            self.manifest(self.screen("DTC-BOARD-001", "/board", "board")),
            self.rules_for("DTC-BOARD-001"), self.root, [router]))
        self.assertIn("라우터에 등록되지 않았다", joined)

    def test_orphan_route_in_router_is_reported(self):
        router = ('createBrowserRouter([{ path: "/", element: <Home/> },'
                  '{ path: "/secret", element: <Secret/> }])')
        joined = "\n".join(validator.validate(
            self.manifest(self.screen("DTC-MAIN-001", "/", "home")),
            self.rules_for("DTC-MAIN-001"), self.root, [router]))
        self.assertIn("문서에 없는 라우트", joined)

    def test_catch_all_is_not_an_orphan(self):
        router = ('createBrowserRouter([{ path: "/", element: <Home/> },'
                  '{ path: "*", element: <NotFound/> }])')
        self.assertEqual(validator.validate(
            self.manifest(self.screen("DTC-MAIN-001", "/", "home")),
            self.rules_for("DTC-MAIN-001"), self.root, [router]), [])

    def test_param_names_and_trailing_slash_do_not_split_routes(self):
        router = 'createBrowserRouter([{ path: "/board/:boardId" }])'
        self.assertEqual(validator.validate(
            self.manifest(self.screen("DTC-BOARD-001", "/board/:id/", "board")),
            self.rules_for("DTC-BOARD-001"), self.root, [router]), [])

    def test_duplicate_route_is_reported_without_router(self):
        """라우터 소스를 안 줘도 두 화면이 같은 라우트인 것은 잡는다."""
        joined = "\n".join(validator.validate(
            self.manifest(self.screen("DTC-MAIN-001", "/", "home"),
                          self.screen("DTC-BOARD-001", "/", "board")),
            self.rules_for("DTC-MAIN-001", "DTC-BOARD-001"), self.root))
        self.assertIn("라우트 중복", joined)

    def test_overlay_screens_without_route_are_untouched(self):
        """팝업·바텀시트는 라우트가 없다 — 없다고 위반이 되면 안 된다."""
        overlay = self.screen("DTC-POPUP-001", None, "board")
        overlay.pop("route")
        self.assertEqual(validator.validate(
            self.manifest(self.screen("DTC-MAIN-001", "/", "home"), overlay),
            self.rules_for("DTC-MAIN-001", "DTC-POPUP-001"), self.root,
            ['createBrowserRouter([{ path: "/" }])']), [])


if __name__ == "__main__":
    unittest.main()
