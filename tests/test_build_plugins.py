"""플러그인 마켓플레이스 계약(#82). 플러그인 사본은 원본과 같고, 매니페스트끼리 이름이 맞고, 심링크가 없다."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "dev" / "build-plugins.py"
MARKET = ROOT / ".claude-plugin" / "marketplace.json"


class PluginContractTests(unittest.TestCase):
    def test_plugin_copies_match_their_sources(self):
        proc = subprocess.run(
            [sys.executable, str(BUILD), "--check"], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_marketplace_entries_match_plugin_manifests(self):
        market = json.loads(MARKET.read_text(encoding="utf-8"))
        names = [p["name"] for p in market["plugins"]]
        self.assertEqual(names, ["yd-skills", "yd-skills-personal"])
        for entry in market["plugins"]:
            root = (ROOT / entry["source"]).resolve()
            claude = json.loads(
                (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
            )
            agy = json.loads(
                (root / ".antigravity-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(claude["name"], entry["name"])
            self.assertEqual(agy["name"], entry["name"])
            self.assertEqual(agy["skills"], "./skills/")
            # version 을 두지 않는다 — Claude 는 커밋 SHA 를 버전으로 써서 커밋마다 갱신을 받는다
            self.assertNotIn("version", claude)

    def test_no_symlinks_inside_plugins(self):
        # codex-cli 0.164.0 의 plugin add 는 심링크를 버린다(2026-10-24 실측)
        links = [p for p in (ROOT / "plugins").rglob("*") if p.is_symlink()]
        self.assertEqual(links, [])

    def test_plugins_carry_skills_only(self):
        for plugin in (ROOT / "plugins").iterdir():
            tops = {p.name for p in plugin.iterdir()}
            self.assertLessEqual(
                tops,
                {".claude-plugin", ".antigravity-plugin", "skills", "README.md"},
                plugin,
            )
            self.assertFalse(
                (plugin / "bin").exists()
            )  # claude.ai 는 bin/ 이 있는 플러그인을 거부한다


if __name__ == "__main__":
    unittest.main()
