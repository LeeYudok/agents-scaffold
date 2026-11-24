"""Go CLI/호환 계층의 종료 코드·배포 동작 (#115, #117). 외부 API는 호출하지 않는다."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
LAUNCHER = SKILL / 'scripts' / 'check-writing'


def native(*args, text=None, env=None):
    binary = os.environ.get('CHECK_WRITING_BIN')
    command = [binary, '--rules', str(SKILL / 'references' / 'banned-expressions.md')] if binary else ['bash', str(LAUNCHER)]
    return subprocess.run([*command, *args], input=text, text=True, capture_output=True, env=env)


class NativeCli(unittest.TestCase):
    def test_baseline_matches_through_json_protocol(self):
        cases = json.loads((SKILL / 'tests' / 'fixtures' / 'python-baseline.json').read_text())
        for case in cases:
            with self.subTest(text=case['text'], chat=case['chat']):
                result = native('--bridge', text=json.dumps(dict(action='check', text=case['text'], chat=case['chat'])))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), case['findings'])

    def test_stdin_and_strict_warning_exit_codes(self):
        self.assertEqual(native('-', text='본문이다.').returncode, 0)
        self.assertEqual(native('-', text='배포를 완료함.').returncode, 1)
        chat = native('--chat', '-', text='배포를 완료함.')
        self.assertEqual(chat.returncode, 0, chat.stderr)
        text = '가' * 61
        self.assertEqual(native('-', text=text).returncode, 0)
        strict = native('--strict', '-', text=text)
        self.assertEqual(strict.returncode, 1)
        self.assertIn('61자', strict.stdout)
        self.assertIn('(--strict)', strict.stdout)

    def test_tool_errors_return_two_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            for args in [[], ['--unknown'], ['--max-len'], ['--max-len', '-1', '-'], [str(Path(tmp) / 'missing.md')], [tmp]]:
                with self.subTest(args=args):
                    result = native(*args)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn('panicked', result.stderr)
        result = native('--bridge', text='{invalid json')
        self.assertEqual(result.returncode, 2)
        self.assertIn('JSON', result.stderr)

    def test_rule_file_is_read_at_runtime_and_invalid_regex_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rules.md'
            path.write_text('## 시험\n| 금지 | 대체 | 검사 |\n|---|---|---|\n| foo | bar | `foo` |\n')
            checked = native('--rules', str(path), '-', text='foo')
            self.assertEqual(checked.returncode, 1, checked.stderr)
            self.assertIn('foo → bar', checked.stdout)
            path.write_text('## 시험\n| foo | bar | `(?` |\n')
            bad = native('--rules', str(path), '-', text='foo')
            self.assertEqual(bad.returncode, 2)
            self.assertIn('정규식', bad.stderr)
            path.write_text('# no rules\n')
            self.assertEqual(native('--rules', str(path), '-', text='foo').returncode, 2)
            path.write_text('## 시험\n| foo | bar | `fo(?!x)o` |\n')
            middle = native('--rules', str(path), '-', text='foo')
            self.assertEqual(middle.returncode, 2)
            self.assertIn('맨 앞', middle.stderr, '전후방 탐색 위치 제약을 안내해야 한다')

    def test_multifile_json_and_unicode_line_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / '문서 하나.md'
            second = Path(tmp) / '문서 둘.md'
            first.write_text('본문이다.\n배포를 완료함.\n')
            second.write_text('가' * 61)
            result = native('--json', str(first), str(second))
            self.assertEqual(result.returncode, 1, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual((data['errors'], data['warnings']), (1, 1))
            self.assertEqual(data['files'][0]['findings'][0]['line'], 2)
            self.assertEqual(data['files'][1]['findings'][0]['match'], '61자')

    def test_python_cli_matches_native_and_preserves_exit_code(self):
        import sys
        result = subprocess.run([sys.executable, str(SKILL / 'scripts' / 'check_writing.py'), '-'], input='배포를 완료함.', text=True, capture_output=True)
        direct = native('-', text='배포를 완료함.')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (direct.returncode, direct.stdout, direct.stderr))

    def test_launcher_can_use_native_binary_without_go(self):
        binary = os.environ.get('CHECK_WRITING_BIN')
        if not binary:
            self.skipTest('CI 또는 CHECK_WRITING_BIN 을 지정한 검증에서 실행한다')
        result = subprocess.run(['bash', str(LAUNCHER), '-'], input='본문이다.', text=True, capture_output=True, env=dict(os.environ, CHECK_WRITING_BIN=binary, PATH='/usr/bin:/bin'))
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
