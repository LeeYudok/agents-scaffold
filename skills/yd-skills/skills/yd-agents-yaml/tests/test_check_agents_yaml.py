"""check-agents-yaml.sh 회귀 테스트.

검증기는 PyYAML 이 필요하다. 저장소 테스트는 stdlib 전용이므로 PyYAML 이 없으면
조용히 통과하지 않고 skip 사유를 출력한다. CI 의 agents-yaml job 은 PyYAML 을
설치하고 이 테스트를 돌린다.
"""

import importlib.util
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "check-agents-yaml.sh"
HAS_YAML = importlib.util.find_spec("yaml") is not None

VALID = """\
schema_version: '1.0'
meta:
  name: fixture
  updated: '2026-10-04'
nodes:
- {id: app, type: script, label: 'App', path: scripts/app.sh}
- {id: db, type: postgres, label: 'DB'}
edges:
- {from: app, to: db, rel: uses_db, env: [DB_HOST]}
ports:
- {port: 8080, service: app, scope: local}
commands:
  local:
    run: ./scripts/app.sh
policies:
- {id: sync, rule: 'keep in sync', source: AGENTS.md}
"""


@unittest.skipUnless(HAS_YAML, "PyYAML 없음 — 검증기 테스트를 건너뛴다 (CI agents-yaml job 에서 돈다)")
class CheckAgentsYaml(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        (self.repo / "scripts").mkdir()
        shutil.copy(SCRIPT, self.repo / "scripts" / "check-agents-yaml.sh")
        (self.repo / "scripts" / "app.sh").write_text("#!/bin/sh\n")
        (self.repo / "AGENTS.md").write_text("# fixture\n")

    def run_check(self, text):
        (self.repo / "AGENTS.yaml").write_text(textwrap.dedent(text))
        return subprocess.run(["sh", str(self.repo / "scripts" / "check-agents-yaml.sh")],
                              capture_output=True, text=True)

    def assert_fails_with(self, text, needle):
        r = self.run_check(text)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(needle, r.stdout)

    def test_valid_passes(self):
        r = self.run_check(VALID)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("[OK]", r.stdout)

    def test_unquoted_date(self):
        self.assert_fails_with(VALID.replace("'2026-10-04'", "2026-10-04"), "parsed as date")

    def test_unquoted_version(self):
        self.assert_fails_with(VALID.replace("schema_version: '1.0'", "schema_version: 1.10"),
                               "expected string")

    def test_edge_to_unknown_node(self):
        self.assert_fails_with(VALID.replace("to: db", "to: cache"), "unknown node 'cache'")

    def test_duplicate_node_id(self):
        self.assert_fails_with(VALID.replace("{id: db,", "{id: app,"), "duplicate node id")

    def test_missing_path(self):
        self.assert_fails_with(VALID.replace("path: scripts/app.sh", "path: scripts/gone.sh"),
                               "path not found 'scripts/gone.sh'")

    def test_missing_command_file(self):
        self.assert_fails_with(VALID.replace("run: ./scripts/app.sh", "run: ./scripts/gone.sh"),
                               "path not found 'scripts/gone.sh'")

    def test_port_must_be_int(self):
        self.assert_fails_with(VALID.replace("port: 8080", "port: '8080'"), "port must be int")

    def test_unknown_top_level_key(self):
        self.assert_fails_with(VALID + "deliverables: []\n", "unknown top-level key 'deliverables'")

    def test_x_prefixed_key_allowed(self):
        r = self.run_check(VALID + "x-deliverables: []\n")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_missing_required_key(self):
        self.assert_fails_with(VALID.replace("edges:\n- {from: app, to: db, rel: uses_db, env: [DB_HOST]}\n", ""),
                               "missing top-level key 'edges'")


class CopiedValidatorIsUnchanged(unittest.TestCase):
    """저장소 루트 사본은 스킬 원본과 바이트 단위로 같아야 한다 (수정 없이 복사 규칙)."""

    def test_root_copy_matches(self):
        root_copy = SKILL.parents[1] / "scripts" / "check-agents-yaml.sh"
        if not root_copy.exists():
            self.skipTest("저장소 루트에 사본이 없다")
        self.assertEqual(root_copy.read_bytes(), SCRIPT.read_bytes(),
                         "scripts/check-agents-yaml.sh 가 스킬 원본과 다르다 — 원본을 다시 복사한다")


if __name__ == "__main__":
    unittest.main()
