#!/usr/bin/env python3
"""yd-script-editor CLI — 에이전트가 대본을 조회·수정하고 음성·렌더 엔진을 부른다. stdlib 만 쓴다.

대본 읽기·쓰기는 떠 있는 에디터 서버 API 를 거친다(저장 형식 검증·재합성 대기열이 그대로 적용된다).
엔진(음성·시각·렌더·믹스·클립)은 setup.sh 가 설치한 런타임(~/.local/share/yd-script-editor)에서 실행한다.

  se.py list                                  대본 목록(주소 번호·라벨·줄 수)
  se.py show <대본>                            줄 표(시각·장면·화면 자막·자막·읽는 말·AI 프롬프트)
  se.py set <대본> <줄> <칸> <값>              한 칸 고쳐 저장. 칸: time scene screen say speak prompt same
  se.py synth <대본> [줄…|all]                 음성 합성(OmniVoice)
  se.py fit <대본> [--apply] [--target 초]     실제 음성 길이로 시각 맞추기(기본은 미리보기)
  se.py render <대본> [--check|--only N|--thumbs]
  se.py intro <대본> <page.html> <초> [--name intro.webm]   HTML 장면을 녹화해 렌더 작업 폴더에 둔다
  se.py mix <대본>                             내레이션·배경음 믹싱 → 완성 영상, 장면 클립까지
  se.py clips <대본>                           완성 영상을 줄 구간대로 잘라 에디터 장면 영상으로
  se.py url [<대본>]                           로컬·공개 주소

<대본> 은 주소 번호(1), 라벨(데모-60초), 파일 이름 어느 것이나 된다.
설정: --config <script-editor.json> > SCRIPT_EDITOR_CONFIG > 현재 폴더에서 위로 찾기.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get('SCRIPT_EDITOR_HOME', Path.home() / '.local/share/yd-script-editor'))


def engine_dir():
    e = RUNTIME / 'engine'
    return e if (e / 'se_config.py').is_file() else SKILL / 'assets/engine'


sys.path.insert(0, str(engine_dir()))
from se_config import Config  # noqa: E402

FIELDS = ('time', 'scene', 'screen', 'say', 'speak', 'prompt', 'same')


class Api:
    def __init__(self, cfg):
        self.port = cfg.raw.get('port', 18750)
        base = '/' + cfg.raw.get('base', '/editor').strip('/')
        self.root = f'http://127.0.0.1:{self.port}{"" if base == "/" else base}/'

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.root + path, data=data, method=method,
                                     headers={'content-type': 'application/json', 'x-editor': '1'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = json.loads(e.read() or b'{}').get('error', e.reason)
            raise SystemExit(f'서버 {e.code}: {msg}')
        except urllib.error.URLError as e:
            raise SystemExit(f'에디터 서버에 연결하지 못했어요({self.root}) — setup.sh 로 띄웠는지 확인: {e.reason}')


def resolve_file(cfg, api, arg):
    files = api.call('GET', 'api/files')
    ids = files.get('ids', {})
    s = str(arg)
    for f in files['files']:
        if s == str(ids.get(f)) or s == f or s == cfg.label_of(f):
            return f, files
    raise SystemExit(f'없는 대본: {arg} (se.py list 로 확인)')


def q(name):
    return urllib.parse.quote(name)


def cmd_list(cfg, api, a):
    files = api.call('GET', 'api/files')
    for f in files['files']:
        doc = api.call('GET', f'api/script?file={q(f)}')['doc']
        print(f"{files['ids'].get(f, '-'):>3}  {cfg.label_of(f):30} {len(doc['rows']):3}줄  {api.root}{files['ids'].get(f, '')}")


def cmd_show(cfg, api, a):
    f, _ = resolve_file(cfg, api, a.script)
    doc = api.call('GET', f'api/script?file={q(f)}')['doc']
    print(f'# {f}')
    for r in doc['rows']:
        print(f"\n[{r['n']}] {r['time']}  {r['scene']}")
        if r.get('screen'):
            print('  화면 자막:', r['screen'].replace('\n', ' / '))
        print('  자막·대본:', r['say'])
        print('  읽는 말  :', '(자막과 같음)' if r['same'] else r['speak'])
        if r.get('prompt'):
            print('  AI 프롬프트:', r['prompt'].replace('\n', ' / '))


def cmd_set(cfg, api, a):
    if a.field not in FIELDS:
        raise SystemExit(f'칸은 {", ".join(FIELDS)} 중 하나')
    f, _ = resolve_file(cfg, api, a.script)
    got = api.call('GET', f'api/script?file={q(f)}')
    doc, etag = got['doc'], got['etag']
    row = next((r for r in doc['rows'] if r['n'] == str(a.row)), None)
    if row is None:
        raise SystemExit(f'{a.row}번 줄이 없어요')
    value = a.value.replace('\\n', '\n')
    if a.field == 'same':
        row['same'] = value.lower() in ('1', 'true', 'y', 'yes')
    else:
        row[a.field] = value
        if a.field == 'speak':
            row['same'] = False
    if row['same']:
        row['speak'] = ''
    out = api.call('PUT', f'api/script?file={q(f)}', {'etag': etag, 'before': doc['before'], 'rows': doc['rows']})
    synth = out.get('synth') or []
    print(f'저장: {f} {a.row}번 {a.field}' + (f' · 음성 재합성 대기 {synth}' if synth else ''))


def run(argv, **kw):
    print('$', ' '.join(str(x) for x in argv), flush=True)
    r = subprocess.run([str(x) for x in argv], **kw)
    if r.returncode:
        raise SystemExit(r.returncode)


def py_render():
    v = RUNTIME / 'venv/bin/python'
    return str(v) if v.exists() else sys.executable


def engine(cfg, script, *args, python=None):
    run([python or sys.executable, engine_dir() / script, *args, '--config', cfg.path])


def cmd_synth(cfg, api, a):
    label = cfg.resolve_label(a.script)
    run([cfg.python, engine_dir() / 'synth.py', *(a.lines or ['all']), '--script', label, '--config', cfg.path])


def cmd_fit(cfg, api, a):
    extra = (['--apply'] if a.apply else []) + (['--target', str(a.target)] if a.target else [])
    engine(cfg, 'fit_times.py', cfg.resolve_label(a.script), *extra)


def cmd_render(cfg, api, a):
    extra = (['--check'] if a.check else []) + (['--only', str(a.only)] if a.only else []) + (['--thumbs'] if a.thumbs else [])
    engine(cfg, 'render/render.py', cfg.resolve_label(a.script), *extra, python=py_render())


def cmd_intro(cfg, api, a):
    sys.path.insert(0, str(engine_dir()))
    from script import build_dir
    app = RUNTIME / 'app'
    if not (app / 'node_modules/playwright-core').is_dir():
        raise SystemExit('런타임이 없어요 — setup.sh 를 먼저 돌리세요')
    out = build_dir(cfg, cfg.resolve_label(a.script)) / a.name
    run(['node', app / 'tools/record_intro.mjs', cfg.resolve(a.page), a.sec, out], cwd=app)


def cmd_mix(cfg, api, a):
    engine(cfg, 'mix.py', cfg.resolve_label(a.script))


def cmd_clips(cfg, api, a):
    engine(cfg, 'cut_clips.py', cfg.resolve_label(a.script))


def cmd_url(cfg, api, a):
    pub = cfg.raw.get('public', {}).get('url', '')
    n = ''
    if a.script:
        f, files = resolve_file(cfg, api, a.script)
        n = str(files['ids'].get(f, ''))
    print('로컬:', api.root + n)
    if pub:
        print('공개:', pub.rstrip('/') + '/' + n)


def main():
    ap = argparse.ArgumentParser(description='yd-script-editor CLI')
    ap.add_argument('--config')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list')
    p = sub.add_parser('show'); p.add_argument('script')
    p = sub.add_parser('set'); p.add_argument('script'); p.add_argument('row', type=int); p.add_argument('field'); p.add_argument('value')
    p = sub.add_parser('synth'); p.add_argument('script'); p.add_argument('lines', nargs='*')
    p = sub.add_parser('fit'); p.add_argument('script'); p.add_argument('--apply', action='store_true'); p.add_argument('--target', type=float)
    p = sub.add_parser('render'); p.add_argument('script'); p.add_argument('--check', action='store_true')
    p.add_argument('--only', type=int); p.add_argument('--thumbs', action='store_true')
    p = sub.add_parser('intro'); p.add_argument('script'); p.add_argument('page'); p.add_argument('sec')
    p.add_argument('--name', default='intro.webm')
    p = sub.add_parser('mix'); p.add_argument('script')
    p = sub.add_parser('clips'); p.add_argument('script')
    p = sub.add_parser('url'); p.add_argument('script', nargs='?')
    a = ap.parse_args()
    cfg = Config(a.config)
    globals()[f'cmd_{a.cmd}'](cfg, Api(cfg), a)


if __name__ == '__main__':
    main()
