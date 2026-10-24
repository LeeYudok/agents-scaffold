"""레포 설정(<레포>/script-editor.json) 읽기 — 엔진 스크립트 공용. stdlib 만 쓴다.

설정 파일 위치: --config 인자 > SCRIPT_EDITOR_CONFIG > 현재 폴더에서 위로 올라가며 찾은 script-editor.json.
상대 경로는 레포(설정 파일이 있는 폴더) 기준, ~ 는 홈.
"""
import json
import os
import re
import shutil
from pathlib import Path

NAME = 'script-editor.json'


def find(start=None):
    env = os.environ.get('SCRIPT_EDITOR_CONFIG')
    if env:
        return Path(env).expanduser().resolve()
    p = Path(start or os.getcwd()).resolve()
    for d in (p, *p.parents):
        if (d / NAME).is_file():
            return d / NAME
    raise SystemExit(f'{NAME} 를 찾지 못했어요 — 레포 루트에 두거나 SCRIPT_EDITOR_CONFIG 로 경로를 주세요')


class Config:
    def __init__(self, path=None):
        self.path = Path(path).expanduser().resolve() if path else find()
        self.repo = self.path.parent
        self.raw = json.loads(self.path.read_text(encoding='utf-8'))
        c = self.raw
        self.name = c['name']
        self.prefix = c.get('prefix', '')
        self.content = self.resolve(os.environ.get('EDITOR_CONTENT') or c.get('content', 'docs/editor'))
        synth = c.get('synth', {})
        self.python = self.resolve(synth.get('python', '~/.cache/omnivoice-venv/bin/python'))
        self.synth_cache = self.resolve(synth.get('cache', f'~/.cache/yd-script-editor/{self.name}'))
        videos = c.get('videos', {})
        self.video_dir = self.resolve(videos.get('dir', 'videos'))
        render = c.get('render', {})
        self.scenes = self.resolve(render['scenes']) if render.get('scenes') else None
        self.assets = self.resolve(render.get('assets', '.'))
        self.render_out = self.resolve(render.get('out', f'~/.cache/yd-script-editor/{self.name}/render'))
        self.music = self.resolve(render['music']) if render.get('music') else None
        self.ffmpeg = shutil.which('ffmpeg') or 'ffmpeg'

    def resolve(self, p):
        p = str(p)
        if p.startswith('~/'):
            return Path.home() / p[2:]
        q = Path(p)
        return q if q.is_absolute() else (self.repo / q).resolve()

    # ---- 대본 이름 ↔ 라벨
    def label_of(self, name):
        """대본 파일 이름(확장자 있거나 없거나) 또는 라벨 → 라벨(파일 이름 - 접두어 - .md)."""
        s = re.sub(r'\.(md|json)$', '', Path(str(name)).name)
        return s[len(self.prefix):] if self.prefix and s.startswith(self.prefix) else s

    def script_md(self, label):
        return self.content / f'{self.prefix}{self.resolve_label(label)}.md'

    def script_json(self, label):
        return self.content / f'{self.prefix}{self.resolve_label(label)}.json'

    def ids(self):
        """주소 번호 → 대본 파일 이름(서버가 content/ids.json 에 고정한다)."""
        try:
            return json.loads((self.content / 'ids.json').read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {}

    def resolve_label(self, arg):
        """'3' 같은 주소 번호, 라벨, 파일 이름 무엇이든 라벨로."""
        s = str(arg)
        if s.isdigit() and s in self.ids():
            return self.label_of(self.ids()[s])
        return self.label_of(s)
