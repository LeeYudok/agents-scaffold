"""원격 태그 설치·체크섬·임시 다운로드 정리 검사 (#106). 실제 네트워크를 사용하지 않는다."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RemoteInstall(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='scaffold-remote-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        standalone = self.base / 'standalone'
        standalone.mkdir()
        self.script = standalone / 'agents-scaffold.sh'
        shutil.copy(ROOT / 'bin/agents-scaffold.sh', self.script)
        self.archive = self.base / 'payload.tar.gz'
        with tarfile.open(self.archive, 'w:gz') as out:
            for name in ('bin', '.claude', 'presets', 'AGENTS.md'):
                out.add(ROOT / name, arcname='agents-scaffold/' + name,
                        filter=lambda info: None if '__pycache__' in info.name or info.name.endswith('.pyc') else info)
        self.tools = self.base / 'tools'
        self.tools.mkdir()
        curl = self.tools / 'curl'
        curl.write_text('''#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$2" > "$REMOTE_URL_LOG"
while [ "$#" -gt 0 ]; do
  if [ "$1" = -o ]; then
    printf '%s\\n' "$2" > "$REMOTE_PATH_LOG"
    cp "$REMOTE_PAYLOAD" "$2"
    exit 0
  fi
  shift
done
exit 1
''')
        curl.chmod(0o755)

    def install(self, checksum):
        target = self.base / 'target'
        target.mkdir()
        env = dict(os.environ, PATH=str(self.tools) + os.pathsep + os.environ['PATH'],
                   REMOTE_PAYLOAD=str(self.archive), REMOTE_URL_LOG=str(self.base / 'url'),
                   REMOTE_PATH_LOG=str(self.base / 'download'), AGENTS_SCAFFOLD_REPO='https://example.invalid/project',
                   AGENTS_SCAFFOLD_REF='v1.0.0', AGENTS_SCAFFOLD_SHA256=checksum)
        result = subprocess.run(['bash', str(self.script), str(target), '--lang', 'en', '--stack', 'python', '--yes'],
                                env=env, capture_output=True, text=True)
        downloaded = Path((self.base / 'download').read_text().strip())
        self.assertFalse(downloaded.parent.exists(), '원격 소스 임시 폴더가 남았다')
        return result, target

    def test_tag_ref_and_checksum_install_without_network(self):
        result, target = self.install(hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base / 'url').read_text().strip(), 'https://example.invalid/project/archive/v1.0.0.tar.gz')
        self.assertIn('checksum verified', result.stderr)
        self.assertTrue((target / 'AGENTS.md').is_file())
        self.assertTrue((target / '.claude/rules/python.md').is_file())

    def test_bad_checksum_stops_before_writing_payload(self):
        result, target = self.install('0' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('checksum mismatch', result.stderr)
        self.assertFalse((target / '.claude').exists())
        self.assertFalse((target / 'AGENTS.md').exists())
