"""yd-mobile-web-planner 고유의 Agent Adapter 문구와 번들 검증기 계약 테스트.

모든 스킬에 공통으로 적용되는 레이아웃·어댑터 형식 규약은 저장소 루트의
tests/test_skill_layout.py 가 스킬을 순회하며 검증한다. 이 파일은 이 스킬에서만
의미가 있는 계약만 다룬다.
"""
import contextlib
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
# agents-scaffold(#78): 에이전트 원본은 .claude/agents/<스킬명>.md 하나다. Codex·agy 에이전트는 설치기가
# 이 파일에서 생성한다(bin/agents-scaffold.sh emit_agents) — 런타임별 어댑터 파일을 따로 두지 않는다.
AGENT = SKILL_ROOT.parent.parent / "agents" / f"{SKILL_ROOT.name}.md"
TEMPLATE = SKILL_ROOT / "resources" / "template.html"


@contextlib.contextmanager
def minimal_storyboard():
    """검증기가 위반 0건으로 통과해야 하는 최소 산출물을 임시 파일로 만든다.

    저장소는 생성 산출물(HTML)을 커밋하지 않으므로, 검증기 계약은 커밋된
    예시 대신 이 픽스처로 확인한다. 화면 ID 를 정의하지 않으므로 짝을
    이루는 Business Rules 문서도 요구되지 않는다.
    """
    template = TEMPLATE.read_text(encoding="utf-8")
    match = re.search(r"<style>(.*?)</style>", template, re.DOTALL)
    if match is None:
        raise RuntimeError("template.html 에 <style> 블록이 없다")
    html = (
        "<!DOCTYPE html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
        f"<style>{match.group(1)}</style></head><body>"
        "<div class=\"docwrap\">"
        "<div class=\"ppt-slide\"><div class=\"ppt-top-no\">NO. 01</div></div>"
        "</div>"
        "<script src=\"https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js\">"
        "</script></body></html>"
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture_storyboard.html"
        path.write_text(html, encoding="utf-8")
        yield path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"모듈을 불러올 수 없다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestAdapterInstructions(unittest.TestCase):
    """에이전트 원본(Codex·agy 생성의 원천)이 '검증기를 돌린다'는 계약을 담고 있어야 한다."""

    def test_agent_requires_validation(self):
        text = AGENT.read_text(encoding="utf-8")
        self.assertIn("`yd-mobile-web-planner` Skill", text)
        self.assertIn("검증기", text)


class TestBundledValidator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_module(
            "validate_storyboard",
            SKILL_ROOT / "scripts" / "validate_storyboard.py",
        )

    def test_uses_only_skill_local_template(self):
        self.assertEqual(
            self.validator.TEMPLATE,
            SKILL_ROOT / "resources" / "template.html",
        )

    def test_accepts_minimal_conforming_storyboard(self):
        css = self.validator.extract_style(
            self.validator.TEMPLATE.read_text(encoding="utf-8"))
        with minimal_storyboard() as path:
            violations, _ = self.validator.check(path, css)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
