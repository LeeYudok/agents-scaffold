"""yd-script-editor: 설정 읽기·대본 표 읽기·CLI 저장 경로·설치기 인자 검사 (stdlib 만)."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ENGINE = SKILL / 'assets/engine'
sys.path.insert(0, str(ENGINE))
from se_config import Config  # noqa: E402
from script import build_dir, read_script, video_path  # noqa: E402

MD = """# 예시 대본

- 목표 길이: 20초

| # | 시각 | 장면 | 화면 자막 | 자막·대본 | 읽는 말 | AI 프롬프트 |
|---|---|---|---|---|---|---|
| 1 | 0:00.5 | 인트로 | 데모 <br> 부제 | 시작합니다. | (자막과 같음) | 검은 바탕 |
| 2 | 0:06.0 | 화면 | 목록 <br> 추가 버튼 | 추가 버튼을 붙였습니다. | (자막과 같음) |  |
| 3 | 0:15.0 | 아웃트로 | 끝 | 끝입니다. | (자막과 같음) |  |
"""


def make_repo(tmp, **over):
    repo = Path(tmp)
    (repo / 'docs/editor').mkdir(parents=True)
    (repo / 'docs/editor/대본-데모.md').write_text(MD, encoding='utf-8')
    (repo / 'docs/editor/ids.json').write_text(json.dumps({'1': '대본-데모.md'}), encoding='utf-8')
    conf = {'name': 'demo', 'prefix': '대본-', 'port': 18799, 'videos': {'dir': 'out', 'pattern': 'demo-*.mp4'},
            'render': {'out': 'build'}}
    conf.update(over)
    (repo / 'script-editor.json').write_text(json.dumps(conf, ensure_ascii=False), encoding='utf-8')
    return repo


class ConfigTest(unittest.TestCase):
    def test_paths_relative_to_repo_and_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            cfg = Config(repo / 'script-editor.json')
            self.assertEqual(cfg.content, (repo / 'docs/editor').resolve())
            self.assertEqual(cfg.label_of('대본-데모.md'), '데모')
            self.assertEqual(cfg.resolve_label('1'), '데모')        # 주소 번호
            self.assertEqual(cfg.resolve_label('데모'), '데모')     # 라벨
            self.assertEqual(cfg.script_md('1').name, '대본-데모.md')
            self.assertEqual(video_path(cfg, '데모'), (repo / 'out/demo-데모.mp4').resolve())
            self.assertEqual(build_dir(cfg, '데모'), (repo / 'build/데모').resolve())

    def test_find_walks_up_from_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            sub = repo / 'a/b'
            sub.mkdir(parents=True)
            env = {k: v for k, v in os.environ.items() if k != 'SCRIPT_EDITOR_CONFIG'}
            out = subprocess.run([sys.executable, '-c', 'import se_config; print(se_config.Config().repo)'],
                                 cwd=sub, env={**env, 'PYTHONPATH': str(ENGINE)}, capture_output=True, text=True, check=True)
            self.assertEqual(Path(out.stdout.strip()), repo.resolve())

    def test_tilde_expands_to_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(make_repo(tmp, synth={'cache': '~/.cache/x'}) / 'script-editor.json')
            self.assertEqual(cfg.synth_cache, Path.home() / '.cache/x')


class ScriptTest(unittest.TestCase):
    def test_read_script_rows_and_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(make_repo(tmp) / 'script-editor.json')
            target, rows = read_script(cfg, '데모')
            self.assertEqual(target, 20.0)
            self.assertEqual([r['n'] for r in rows], [1, 2, 3])
            self.assertEqual(rows[0]['start'], 0.0)              # 인트로는 0초부터
            self.assertEqual(rows[1]['end'], 15.0)
            self.assertEqual(rows[-1]['end'], 20.0)              # 마지막 줄은 목표 길이까지
            self.assertEqual(rows[1]['lines'], ['목록', '추가 버튼'])
            self.assertEqual(rows[0]['prompt'], ['검은 바탕'])

    def test_missing_target_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            p = repo / 'docs/editor/대본-데모.md'
            p.write_text(MD.replace('- 목표 길이: 20초\n', ''), encoding='utf-8')
            with self.assertRaises(SystemExit):
                read_script(Config(repo / 'script-editor.json'), '데모')


class FakeEditor(BaseHTTPRequestHandler):
    """에디터 서버 API 흉내: 파일 목록·대본 읽기·저장(PUT 본문을 기록)."""
    doc = None
    puts = []

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('content-type', 'application/json')
        self.send_header('content-length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith('/editor/api/files'):
            return self._send({'files': ['대본-데모.md'], 'ids': {'대본-데모.md': 1}, 'prefix': '대본-'})
        if self.path.startswith('/editor/api/script'):
            return self._send({'doc': FakeEditor.doc, 'etag': 'e1'})
        self._send({'error': 'x'}, 404)

    def do_PUT(self):
        if self.headers.get('x-editor') != '1':
            return self._send({'error': 'x-editor 헤더'}, 403)
        n = int(self.headers['content-length'])
        FakeEditor.puts.append(json.loads(self.rfile.read(n)))
        self._send({'doc': FakeEditor.doc, 'etag': 'e2', 'synth': [2]})


class CliTest(unittest.TestCase):
    def setUp(self):
        FakeEditor.doc = {'before': '# 예시\n', 'rows': [
            {'n': '1', 'time': '0:00.5', 'scene': '인트로', 'screen': '데모', 'prompt': '', 'say': '시작', 'speak': '', 'same': True},
            {'n': '2', 'time': '0:06.0', 'scene': '화면', 'screen': '목록', 'prompt': '', 'say': '추가', 'speak': '', 'same': True}]}
        FakeEditor.puts = []
        self.srv = HTTPServer(('127.0.0.1', 0), FakeEditor)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name, port=self.srv.server_address[1])

    def tearDown(self):
        self.srv.shutdown()
        self.tmp.cleanup()

    def se(self, *args):
        return subprocess.run([sys.executable, str(SKILL / 'scripts/se.py'), '--config', str(self.repo / 'script-editor.json'), *args],
                              capture_output=True, text=True, env={**os.environ, 'SCRIPT_EDITOR_HOME': self.tmp.name})

    def test_set_prompt_sends_whole_doc_with_etag(self):
        r = self.se('set', '1', '2', 'prompt', '첫 줄\\n둘째 줄')
        self.assertEqual(r.returncode, 0, r.stderr)
        put = FakeEditor.puts[-1]
        self.assertEqual(put['etag'], 'e1')
        self.assertEqual(put['before'], '# 예시\n')
        self.assertEqual(put['rows'][1]['prompt'], '첫 줄\n둘째 줄')
        self.assertEqual(put['rows'][0], FakeEditor.doc['rows'][0])   # 다른 줄은 그대로
        self.assertIn('재합성 대기 [2]', r.stdout)

    def test_set_speak_turns_off_same(self):
        self.se('set', '데모', '1', 'speak', '시작합니다')
        row = FakeEditor.puts[-1]['rows'][0]
        self.assertEqual((row['same'], row['speak']), (False, '시작합니다'))

    def test_unknown_field_and_row_fail(self):
        self.assertNotEqual(self.se('set', '1', '1', 'color', 'x').returncode, 0)
        self.assertNotEqual(self.se('set', '1', '9', 'say', 'x').returncode, 0)
        self.assertEqual(FakeEditor.puts, [])

    def test_unknown_script_fails(self):
        r = self.se('show', '없는대본')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('없는 대본', r.stderr)


class SetupArgsTest(unittest.TestCase):
    def test_missing_config_fails_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(['sh', str(SKILL / 'scripts/setup.sh'), tmp], capture_output=True, text=True,
                               env={**os.environ, 'SCRIPT_EDITOR_HOME': tmp + '/rt'})
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('설정이 없음', r.stderr)
            self.assertFalse(Path(tmp, 'rt').exists())   # 아무것도 설치하지 않았다

    def test_bad_name_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'script-editor.json').write_text(json.dumps({'name': 'Bad Name'}))
            r = subprocess.run(['sh', str(SKILL / 'scripts/setup.sh'), tmp, 'status'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('name 은', r.stderr)

    def status(self, public):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'script-editor.json').write_text(json.dumps({'name': 'demo', 'port': 18799, 'public': public}))
            return subprocess.run(['sh', str(SKILL / 'scripts/setup.sh'), tmp, 'status'], capture_output=True, text=True, timeout=60)

    def test_public_list_gets_one_tunnel_per_host(self):
        r = self.status([{'ssh': 'relay-a.invalid', 'url': 'https://a.example/editor/'}, {'ssh': 'relay-b.invalid'}])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('script-editor.demo.tunnel.relay-a.invalid:', r.stdout)
        self.assertIn('script-editor.demo.tunnel.relay-b.invalid:', r.stdout)
        self.assertIn('터널: relay-b.invalid 쪽', r.stdout)

    def test_public_object_still_works(self):
        r = self.status({'ssh': 'relay-a.invalid'})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('script-editor.demo.tunnel.relay-a.invalid:', r.stdout)

    def test_bad_ssh_host_rejected(self):
        r = self.status([{'ssh': 'relay;rm -rf ~'}])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('public.ssh 는', r.stderr)


if __name__ == '__main__':
    unittest.main()
