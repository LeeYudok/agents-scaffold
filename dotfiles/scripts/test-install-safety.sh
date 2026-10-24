#!/usr/bin/env bash
# 설치·제거 안전성 회귀 시험. 임시 HOME과 격리된 PATH만 사용하며 네트워크·실제 패키지 작업은 하지 않는다.
# 원본 복원 후 반복 제거, 미설치 파일 보존, Claude 설정 사전 거부, apt/dnf 설치 기록·purge,
# sudo 불가·패키지 설치 실패 시 플러그인 tarball 폴백을 확인한다.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path.cwd()
PLUGINS = {'zsh-autosuggestions', 'zsh-syntax-highlighting'}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def snapshot(home):
    return {str(p.relative_to(home)): (p.read_bytes(), p.stat().st_mode)
            for p in home.rglob('*') if p.is_file()}


class Machine:
    def __init__(self, base, manager='apt-get', installed=(), fail='', sudo=True, jq=True):
        self.base = base
        self.home = base / 'home'
        self.bin = base / 'bin'
        self.home.mkdir(parents=True)
        self.bin.mkdir()
        self.state = base / 'packages.json'
        self.state.write_text(json.dumps(sorted(installed)))
        self.log = base / 'calls.jsonl'
        write(base / 'fail-package', fail)
        if not sudo:
            write(base / 'no-sudo', '')
        write(base / 'proc-version', 'Linux microsoft test\n')
        # PATH를 실제 시스템에 연결하지 않는다. 허용한 파일 작업 도구만 링크한다.
        for name in ('bash', 'dirname', 'grep', 'mkdir', 'cp', 'cmp', 'touch',
                     'basename', 'chmod', 'rm', 'rmdir', 'tr', 'sed', 'python3',
                     'mktemp', 'tar', 'gzip', 'find', 'head', 'mv', 'true'):
            path = shutil.which(name)
            assert path, name
            (self.bin / name).symlink_to(path)
        dispatcher = base / 'mock.py'
        write(dispatcher, '#!' + sys.executable + '\n' + '''
import json, os, pathlib, sys
base = pathlib.Path(__file__).resolve().parent
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
state = base / 'packages.json'
packages = set(json.loads(state.read_text()))
if name == 'uname':
    print('Linux' if args == ['-s'] else 'x86_64')
elif name == 'sudo':
    if args[0] == '-n':
        if (base / 'no-sudo').exists():
            sys.exit(1)
        args = args[1:]
    elif args[:2] in (['apt-get', 'install'], ['dnf', 'install']):
        # 설치 중 비밀번호 프롬프트가 뜰 수 있는 호출을 기록한다
        (base / 'sudo-without-n').touch()
    os.execvp(args[0], args)
elif name in ('rpm', 'dpkg-query'):
    present = args[-1] in packages
    if present and name == 'dpkg-query':
        assert args[:2] == ['-W', '-f=${db:Status-Status}']
        print('installed', end='')
    sys.exit(0 if present else 1)
elif name in ('apt-get', 'dnf'):
    with (base / 'calls.jsonl').open('a') as f:
        f.write(json.dumps([name] + args) + '\\n')
    action, flag, *targets = args
    assert action in ('install', 'remove') and flag == '-y'
    if (base / 'fail-package').read_text() in targets:
        sys.exit(1)
    if action == 'install':
        packages.update(targets)
    else:
        packages.difference_update(targets)
    state.write_text(json.dumps(sorted(packages)))
elif name == 'curl' and args[-1].startswith('https://github.com/zsh-users/') and '-o' in args:
    # 플러그인 태그 tarball: <이름>-<버전>/<이름>.zsh 구조를 흉내 낸다
    import io, tarfile
    repo, tag = args[-1].split('/')[4], args[-1].rsplit('/', 1)[1][:-len('.tar.gz')]
    with (base / 'calls.jsonl').open('a') as f:
        f.write(json.dumps(['curl', repo, tag]) + '\\n')
    data = ('# ' + repo + ' ' + tag + '\\n').encode()
    info = tarfile.TarInfo(repo + '-' + tag.lstrip('v') + '/' + repo + '.zsh')
    info.size = len(data)
    with tarfile.open(args[args.index('-o') + 1], 'w:gz') as t:
        t.addfile(info, io.BytesIO(data))
elif name in ('curl', 'unzip'):
    raise SystemExit('예상하지 않은 다운로드 또는 압축 해제')
''')
        dispatcher.chmod(0o755)
        for name in ('uname', 'sudo', manager, 'rpm' if manager == 'dnf' else 'dpkg-query',
                     'curl', 'unzip', 'zsh', 'starship', 'jq', 'zoxide', 'fzf', 'eza', 'fc-cache'):
            if name == 'jq' and not jq:
                continue
            (self.bin / name).symlink_to(dispatcher)
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin),
                        DOTFILES_PROC_VERSION=str(base / 'proc-version'))

    def run(self, script, *args, ok=True):
        p = subprocess.run([str(self.bin / 'bash'), str(ROOT / script), *args],
                           env=self.env, capture_output=True, text=True)
        assert (p.returncode == 0) == ok, p.stdout + p.stderr
        return p

    def packages(self):
        return set(json.loads(self.state.read_text()))

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def plugins(self):
        manifest = self.home / '.config/dotfiles/backup/plugin-installed.txt'
        return {Path(p).name for p in manifest.read_text().splitlines()} if manifest.exists() else set()


with tempfile.TemporaryDirectory(prefix='dotfiles-safety-') as tmp:
    base = Path(tmp)
    m = Machine(base / 'unmanaged')
    for name in ('.zshrc', '.zshrc.bak', '.config/starship.toml', '.config/eza/theme.yml',
                 '.claude/statusline-command.sh', '.codex/cost-hook.py',
                 '.gemini/antigravity-cli/statusline-command.sh'):
        write(m.home / name, '사용자 원본\n')
    for name in ('.claude/settings.json', '.codex/hooks.json', '.codex/config.toml',
                 '.gemini/antigravity-cli/settings.json'):
        write(m.home / name, '파싱하지 않고 보존할 사용자 파일\n')
    before = snapshot(m.home)
    m.run('uninstall.sh')
    m.run('uninstall.sh', '--purge')
    assert snapshot(m.home) == before
    print('ok 설치 기록 없는 파일·설정·백업 보존')

    for i, invalid in enumerate(('[]', 'null', 'true', '42', '"text"', '{')):
        m = Machine(base / ('invalid-' + str(i)))
        write(m.home / '.claude/settings.json', invalid)
        before = snapshot(m.home)
        m.run('install.sh', ok=False)
        assert snapshot(m.home) == before and not m.log.exists()
        assert not (m.home / '.config').exists()
    print('ok Claude 비객체·깨진 JSON을 홈 변경 전에 거부')

    m = Machine(base / 'default-roundtrip', installed=PLUGINS)
    write(m.home / '.zshrc', '# 기존 셸 설정\n')
    m.run('install.sh')
    m.run('uninstall.sh')
    assert (m.home / '.zshrc').read_text() == '# 기존 셸 설정\n'
    before = snapshot(m.home)
    m.run('uninstall.sh')
    assert snapshot(m.home) == before
    print('ok 기본 제거 2회 후 원본 유지')

    for manager in ('apt-get', 'dnf'):
        cases = [set(), {'zsh-autosuggestions'}, {'zsh-syntax-highlighting'}, PLUGINS]
        if manager == 'dnf':
            cases.append({'epel-release', 'zsh-autosuggestions'})
        for i, existing in enumerate(cases):
            for failed in ('', 'zsh-syntax-highlighting'):
                m = Machine(base / (manager + str(i) + failed), manager, existing, failed)
                write(m.home / '.zshrc', '# 사용자 원본\n')
                write(m.home / '.claude/settings.json', '{"statusLine":{"command":"original"},"other":true}')
                m.run('install.sh')
                assert not (m.base / 'sudo-without-n').exists()
                expected = PLUGINS - existing - {failed}
                if manager == 'dnf' and not PLUGINS <= existing and 'epel-release' not in existing:
                    expected |= {'epel-release'}
                manifest = m.home / '.config/dotfiles/backup/pkg-installed.txt'
                recorded = set(manifest.read_text().splitlines()) if manifest.exists() else set()
                assert recorded == expected, (manager, existing, recorded, expected)
                m.run('install.sh')
                if manifest.exists():
                    assert sorted(manifest.read_text().splitlines()) == sorted(expected)
                assert m.plugins() == {failed} - {''} - existing, (manager, existing, m.plugins())
                assert not any(existing.intersection(call[3:]) for call in m.calls())
                m.run('uninstall.sh', '--purge')
                assert m.packages() == existing
                assert not (m.home / '.local/share/zsh').exists()
                assert (m.home / '.zshrc').read_text() == '# 사용자 원본\n'
                assert json.loads((m.home / '.claude/settings.json').read_text()) == {
                    'statusLine': {'command': 'original'}, 'other': True}
                before = snapshot(m.home)
                m.run('uninstall.sh', '--purge')
                assert snapshot(m.home) == before
        print('ok ' + manager + ' 기존 패키지 조합·설치 실패·반복 설치·purge·반복 제거')

    for manager in ('apt-get', 'dnf'):
        m = Machine(base / ('no-sudo-' + manager), manager, sudo=False)
        write(m.home / '.zshrc', '# 사용자 원본\n')
        # 사용자가 직접 둔 플러그인은 기록하지도 지우지도 않는다
        own = m.home / '.local/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh'
        write(own, '# 사용자 설치\n')
        # 구조가 다른 같은 이름 디렉터리도 설치 대상으로 삼거나 기록하지 않는다
        other = m.home / '.local/share/zsh/plugins/zsh-syntax-highlighting/src/other.zsh'
        write(other, '# 다른 구조\n')
        before = snapshot(m.home)
        m.run('install.sh')
        assert m.plugins() == set()
        assert list(other.parent.parent.rglob('*.zsh')) == [other]
        m.run('uninstall.sh', '--purge')
        assert snapshot(m.home) == before
        other.unlink()
        other.parent.rmdir()
        other.parent.parent.rmdir()
        before = snapshot(m.home)
        m.run('install.sh')
        assert not any(call[0] in ('apt-get', 'dnf') for call in m.calls()), m.calls()
        assert m.plugins() == {'zsh-syntax-highlighting'}
        plugin = m.home / '.local/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh'
        assert plugin.read_text() == '# zsh-syntax-highlighting 0.8.0\n'
        installed = snapshot(m.home)
        m.run('install.sh')
        assert snapshot(m.home) == installed and len(m.calls()) == 1
        m.run('uninstall.sh', '--purge')
        assert snapshot(m.home) == before and m.packages() == set()
        m.run('uninstall.sh', '--purge')
        assert snapshot(m.home) == before
    print('ok sudo 불가 시 패키지 관리자 없이 tarball 설치·반복 설치·purge·사용자 플러그인·같은 이름 경로 보존')

    for manager in ('apt-get', 'dnf'):
        m = Machine(base / ('jq-fail-' + manager), manager, PLUGINS, fail='jq', jq=False)
        p = m.run('install.sh')
        assert 'jq 설치 실패' in p.stdout, p.stdout
        assert not (m.home / '.config/dotfiles/backup/pkg-installed.txt').exists()
    print('ok jq 패키지 설치 실패 시 경고하고 기록하지 않음')

    for manager, query in (('apt-get', 'dpkg-query'), ('dnf', 'rpm')):
        m = Machine(base / ('missing-' + query), manager)
        (m.bin / query).unlink()
        m.run('install.sh', ok=False)
        assert not list(m.home.iterdir()) and not m.log.exists()
    print('ok 패키지 조회 도구 누락을 홈 변경 전에 거부')
print('전체 통과')
PY
