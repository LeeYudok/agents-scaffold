"""대본 md 표 읽기와 렌더 산출물 이름 — 엔진 공용. stdlib 만 쓴다.

장면 데이터 모듈(설정 render.scenes, 레포 소유)이 아래 함수를 두면 이름을 바꾼다(없으면 라벨 그대로).
  build_name(label) → 렌더 작업 폴더 이름(<render.out>/<이름>/: video-only.mp4·intro.webm·check.jpg)
  video_key(label)  → 완성 영상 키(<videos.dir>/<videos.pattern 의 * 자리>)
"""
import importlib.util
import re
import subprocess
from pathlib import Path

TARGET_RE = re.compile(r'목표\s*길이\s*[:：]\s*(\d+(?:\.\d+)?)\s*초')
ROW_RE = re.compile(r'^\| \d+ \|')


def secs(t):
    m, s = t.split(':')
    return int(m) * 60 + float(s)


def fmt(sec):
    t = round(sec * 10) / 10
    m = int(t // 60)
    return f'{m}:{t - m * 60:04.1f}'


def probe(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                          '-of', 'csv=p=0', str(path)]))


def target_of(md):
    m = TARGET_RE.search(md)
    return float(m.group(1)) if m else None


def read_script(cfg, label):
    """(목표 길이, 줄 목록). 줄: n·start·end·scene·lines(화면 자막 줄)·prompt(AI 프롬프트 줄).
    6칸 표(화면 자막 있음) 기준이다. 첫 줄(인트로 카드)은 0초부터, 마지막 줄은 목표 길이까지."""
    md = cfg.script_md(label).read_text(encoding='utf-8')
    target = target_of(md)
    if target is None:
        raise SystemExit(f'{cfg.script_md(label).name}: 머리말에 "목표 길이: N초" 가 없어요')
    rows = []
    for line in md.splitlines():
        if not ROW_RE.match(line):
            continue
        cols = [c.strip() for c in re.split(r'(?<!\\)\|', line.strip().strip('|'))]
        n, t, scene, cap = cols[:4]
        prompt = [s.strip() for s in cols[6].split('<br>') if s.strip()] if len(cols) > 6 else []
        rows.append({'n': int(n), 'start': secs(t), 'scene': scene, 'lines': [s.strip() for s in cap.split('<br>')], 'prompt': prompt})
    for a, b in zip(rows, rows[1:]):
        a['end'] = b['start']
    rows[-1]['end'] = target
    rows[0]['start'] = 0.0
    return target, rows


_SCENES = {}


def load_scenes(cfg):
    """설정 render.scenes 의 장면 데이터 모듈(레포 소유 .py)."""
    if cfg.scenes is None:
        raise SystemExit('script-editor.json 에 render.scenes(장면 데이터 .py)가 없어요')
    key = str(cfg.scenes)
    if key not in _SCENES:
        spec = importlib.util.spec_from_file_location('scenes', cfg.scenes)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _SCENES[key] = mod
    return _SCENES[key]


def build_name(cfg, label):
    if cfg.scenes is not None:
        f = getattr(load_scenes(cfg), 'build_name', None)
        if f:
            return f(label)
    return label


def build_dir(cfg, label):
    return cfg.render_out / build_name(cfg, label)


def video_path(cfg, label):
    """완성 영상: <videos.dir>/<pattern 의 * 를 키로>."""
    key = label
    if cfg.scenes is not None:
        f = getattr(load_scenes(cfg), 'video_key', None)
        if f:
            key = f(label)
    pattern = cfg.raw.get('videos', {}).get('pattern', '*.mp4')
    return cfg.video_dir / pattern.replace('*', key)
