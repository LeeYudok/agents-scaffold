#!/usr/bin/env python3
"""대본 표로 시연 영상을 합성한다. 그리기·합성은 이 파일, 내용(녹화 경로·컷 계획·문구)은 레포의 장면 데이터(render.scenes).

- 장면 원본: 화면 녹화(<SRC>/recording.json 구간 + raw/)와 결과 화면 재녹화(두 폰, result_rec(name) → events.json + *.webm).
- 줄마다 화면 칸(1600×900)에 SHOTS 의 컷을 이어 붙이고, 아래 띠에 화면 자막 첫 줄(제목)·둘째 줄(요점)을 쓴다.
  강조 박스가 있는 컷은 박스 밖을 어둡게 눌러 바뀐 곳에 시선을 모은다. 결과 화면 컷은 BEFORE/AFTER 꼬리표를 단다.
- 첫 줄·마지막 줄은 카드(인트로·아웃트로)다.

장면 데이터 모듈이 두는 이름:
  FONT_DIR, SRC, SRC_BY_LABEL, STEPS, SIGNPOST, PRESENTER, STEP_NOTES, LEFT_PHONE, RIGHT_PHONE, SHOTS, AD_INTRO,
  OUTRO_CREDIT, TEXT, result_rec(name), result_pieces(name, events), [build_name(label), video_key(label)]
  선택: THEME(프레임 색 — bg·fg·muted·accent·step_todo·step_todo_bar·panel_line·outro_accent·highlight,
        단계 표지 sign_dim·sign_num·sign_name·sign_sub. 빠진 키는 기본값),
        decorate_frame(im, draw, ctx)·decorate_card(im, draw, ctx)(프레임·카드를 그린 뒤 덧그린다. ctx 는 frame_ctx() 참고)

사용: python3 render.py <라벨|주소 번호> [--config <script-editor.json>] [--check] [--only N] [--thumbs]
     → <render.out>/<build_name>/video-only.mp4 (--check: 줄마다 확인 프레임 check.jpg 만)
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from se_config import Config  # noqa: E402
from script import build_dir, build_name, load_scenes, read_script  # noqa: E402
import base as rv  # noqa: E402


def _config_arg():
    """장면 데이터가 모듈 상수(기본 인자 등)에 쓰이므로 import 때 설정을 읽는다."""
    argv = sys.argv
    for i, x in enumerate(argv):
        if x == '--config' and i + 1 < len(argv):
            return argv[i + 1]
        if x.startswith('--config='):
            return x.split('=', 1)[1]
    return None


CFG = Config(_config_arg())
SC = load_scenes(CFG)
rv.setup(SC.FONT_DIR, CFG.ffmpeg)

W, H, FPS = rv.W, rv.H, rv.FPS
VW, VH, VX, VY = rv.VW, rv.VH, rv.VX, rv.VY
# 프레임 색. 장면 데이터의 THEME 가 덮어쓴다(없으면 아래 기본값 — 프레임 바탕은 1장(HTML 인트로)과 같은 블랙 계열).
THEME = {'bg': '#04070d', 'fg': rv.FG, 'muted': rv.MUTED, 'accent': rv.ACCENT, 'step_todo': '#667b90',
         'step_todo_bar': '#2a3b4d', 'panel_line': '#1f2b3a', 'outro_accent': '#f3b995'}
THEME.update(getattr(SC, 'THEME', {}))
BG, FG, MUTED, ACCENT = THEME['bg'], THEME['fg'], THEME['muted'], THEME['accent']
# 단계 표지(signpost): 화면 칸을 누르는 색과 글자 색. 밝은 프레임은 fg 가 짙어 표지 위에서 안 읽히므로 따로 받는다.
for _k, _v in (('sign_dim', '#020408'), ('sign_num', ACCENT), ('sign_name', FG), ('sign_sub', MUTED)):
    THEME.setdefault(_k, _v)
if 'highlight' in THEME:   # 강조 박스(스포트라이트 테두리) 색. 없으면 base.BLUE
    rv.BLUE = tuple(int(THEME['highlight'][i:i + 2], 16) for i in (1, 3, 5))
DECORATE_FRAME = getattr(SC, 'decorate_frame', None)
DECORATE_CARD = getattr(SC, 'decorate_card', None)
BLUE = rv.BLUE
FFMPEG = rv.FFMPEG
ORDINAL = ['첫째', '둘째', '셋째', '넷째', '다섯째', '여섯째', '일곱째', '여덟째']
SIGNPOST_SEC = 1.8   # 단계 표지가 떠 있는 시간(초)
presenter = ''   # main 에서 대본 라벨로 정한다
FADE = 0.25
RAW_SCALE = VW / 1920   # 원본 녹화 1920×1080 → 화면 칸
CAM_EASE = 0.7

TEXT = {'brand': '', 'brand_sub': '', 'card_brand': '', 'intro_title': '', 'intro_sub': '',
        'before': ('BEFORE', ''), 'after': ('AFTER', ''), 'after_zoom': 'AFTER', 'boost': ('', '', '')}
TEXT.update(getattr(SC, 'TEXT', {}))
STEPS = SC.STEPS
SIGNPOST = getattr(SC, 'SIGNPOST', set())
PRESENTER = getattr(SC, 'PRESENTER', {})
STEP_NOTES = getattr(SC, 'STEP_NOTES', {})
LEFT_PHONE, RIGHT_PHONE = getattr(SC, 'LEFT_PHONE', (364, 0, 800, 900)), getattr(SC, 'RIGHT_PHONE', (800, 0, 1236, 900))
SHOTS = SC.SHOTS
AD_INTRO = getattr(SC, 'AD_INTRO', {})
OUTRO_CREDIT = getattr(SC, 'OUTRO_CREDIT', [])
SRC_BY_LABEL = getattr(SC, 'SRC_BY_LABEL', {})
SRC = SC.SRC   # main 에서 라벨에 따라 바꾼다


# ---------------------------------------------------------------- 그림
def font(size, bold=False):
    return rv.font(size, bold)


def tw(d, s, size, bold=False):
    return d.textlength(s, font=font(size, bold))


def rgb(c):
    """'#rrggbb' → (r, g, b). 튜플은 그대로."""
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) if isinstance(c, str) else tuple(c)


def frame_ctx(row, step, steps, kind=None):
    """꾸미기 훅에 넘기는 값: 줄(row: n·start·end·scene·lines), 단계 순번·이름 목록, 카드 종류, 좌표, 글꼴·글자 폭 함수, 테마."""
    return {'row': row, 'step': step, 'steps': steps, 'kind': kind, 'W': W, 'H': H, 'VX': VX, 'VY': VY, 'VW': VW, 'VH': VH,
            'font': font, 'tw': tw, 'theme': THEME}


def frame_base(row, step, steps=STEPS):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((42, 24), TEXT['brand'], font=font(24, True), fill=ACCENT, anchor='lt')
    x_sub = 42 + tw(d, TEXT['brand'], 24, True) + 16
    d.text((x_sub, 26), TEXT['brand_sub'], font=font(22), fill=MUTED, anchor='lt')
    if steps is not STEPS:
        # 사인포스팅: 지금 단계를 머리에 꼬리표로 늘 보여 준다
        label = f'{step:02d}  {steps[step - 1]}'
        x0 = x_sub + tw(d, TEXT['brand_sub'], 22) + 28
        d.rounded_rectangle((x0, 16, x0 + tw(d, label, 24, True) + 32, 58), radius=4, fill=ACCENT)
        d.text((x0 + 16, 23), label, font=font(24, True), fill=BG, anchor='lt')
    gap, fsz = {5: (190, 21), 6: (136, 21)}.get(len(steps), (150, 18))
    for i, s in enumerate(steps):
        x = W - 42 - len(steps) * gap + 24 + i * gap
        on = i + 1 == step
        color = ACCENT if on else (MUTED if i + 1 < step else THEME['step_todo'])
        d.text((x, 22 + (21 - fsz)), s, font=font(fsz, on), fill=color, anchor='lt')
        d.rounded_rectangle((x, 56, x + gap - 24, 59), radius=1, fill=color if i + 1 <= step else THEME['step_todo_bar'])
    d.rectangle((VX - 1, VY - 1, VX + VW, VY + VH), outline=THEME['panel_line'], width=1)
    head, sub = row['lines'][0], row['lines'][1] if len(row['lines']) > 2 else ''
    d.text(((W - tw(d, head, 38, True)) / 2, 988), head, font=font(38, True), fill=FG, anchor='lt')
    if sub:
        d.text(((W - tw(d, sub, 24)) / 2, 1040), sub, font=font(24), fill=ACCENT, anchor='lt')
    if DECORATE_FRAME:
        DECORATE_FRAME(im, d, frame_ctx(row, step, steps))
    return im


def spotlight(panel, box, p):
    """박스 밖을 어둡게(최대 55%) 누르고 파란 테두리를 그린다. p: 0~1 나타남 정도."""
    if p <= 0:
        return panel
    x0, y0, x1, y1 = [round(v) for v in box]
    dark = Image.blend(panel, Image.new('RGB', panel.size, (2, 4, 8)), 0.55 * p)
    dark.paste(panel.crop((x0, y0, x1, y1)), (x0, y0))
    w, h = x1 - x0, y1 - y0
    patch = rv.box_patch(w, h)
    if p < 1:
        patch = rv.with_alpha(patch, p)
    dark.paste(patch, (x0, y0), patch)
    return dark


def tags(panel):
    d = ImageDraw.Draw(panel)
    for (x0, _, x1, _), (tag, desc), color in ((LEFT_PHONE, TEXT['before'], '#94a3b8'),
                                                (RIGHT_PHONE, TEXT['after'], '#3B82F6')):
        side_x = 30 if x0 < 400 else 1236 + 30
        d.rounded_rectangle((side_x, 380, side_x + 300, 520), radius=4, fill='#0f1a2c', outline=color, width=2)
        d.text((side_x + 24, 400), tag, font=font(44, True), fill=color, anchor='lt')
        d.text((side_x + 24, 466), desc, font=font(26), fill=FG, anchor='lt')
    return panel


def big_text(panel, title, sub, p):
    if p <= 0:
        return panel
    out = Image.blend(panel, Image.new('RGB', panel.size, (2, 4, 8)), 0.78 * p)
    d = ImageDraw.Draw(out)
    a = round(255 * p)
    layer = Image.new('RGBA', panel.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    size = 150
    while tw(d, title, size, True) > VW - 160:   # 긴 제목은 화면 칸 폭에 맞춰 줄인다
        size -= 6
    ld.text(((VW - tw(d, title, size, True)) / 2, 300 + (150 - size) // 2), title, font=font(size, True), fill=(245, 242, 233, a), anchor='lt')
    ld.text(((VW - tw(d, sub, 40)) / 2, 520), sub, font=font(40), fill=(125, 217, 205, a), anchor='lt')
    out.paste(layer, (0, 0), layer)
    return out


def pledge(panel, spec, t):
    """긴 요건을 공약표처럼 번호 매긴 핵심 몇 줄로 줄여 보여 준다. 항목은 하나씩 차례로 올라온다."""
    t0 = spec['at']
    if t < t0:
        return panel
    p = rv.smooth(min(1.0, (t - t0) / 0.4))
    out = Image.blend(panel, Image.new('RGB', panel.size, (2, 4, 8)), 0.55 * p)
    layer = Image.new('RGBA', panel.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    items = spec['items']
    x0, x1, y0, row = 300, 1300, 70, 128
    a = round(255 * p)
    d.rectangle((x0, y0, x1, y0 + 96), fill=(17, 30, 50, a))
    d.text((x0 + 36, y0 + 24), spec['title'], font=font(44, True), fill=(245, 242, 233, a), anchor='lt')
    d.text((x1 - 36, y0 + 34), spec.get('tag', ''), font=font(26), fill=(125, 217, 205, a), anchor='rt')
    for i, item in enumerate(items):
        q = rv.smooth(min(1.0, max(0.0, (t - t0 - 0.5 - i * 0.7) / 0.6)))   # 한 줄씩 0.7초 간격으로 천천히
        if q <= 0:
            continue
        aa = round(255 * q)
        y = y0 + 96 + i * row + round(24 * (1 - q))
        d.rectangle((x0, y, x1, y + row - 2), fill=(245, 242, 233, aa) if i % 2 == 0 else (229, 233, 240, aa))
        d.text((x0 + 40, y + 14), str(i + 1), font=font(84, True), fill=(37, 99, 235, aa), anchor='lt')
        d.text((x0 + 150, y + 38), item, font=font(44, True), fill=(17, 24, 39, aa), anchor='lt')
    if spec.get('foot'):
        yf = y0 + 96 + len(items) * row
        d.rectangle((x0, yf, x1, yf + 52), fill=(17, 30, 50, a))
        d.text((x0 + 36, yf + 14), spec['foot'], font=font(24), fill=(176, 186, 203, a), anchor='lt')
    out = out.convert('RGBA')
    out.alpha_composite(layer)
    return out.convert('RGB')


def zoom_after(panel, spec, t):
    """결과 화면: 두 폰을 먼저 보여 준 뒤 AI가 만든 화면의 바뀐 부분(화면 칸 좌표 box)으로 부드럽게 줌인한다.
    줌인 뒤에는 왼쪽 위에 AFTER 꼬리표를 단다."""
    t0, ease = spec['at'], spec.get('ease', 0.9)
    if t < t0:
        return panel
    q = rv.smooth(min(1.0, (t - t0) / ease))
    x0, y0, x1, y1 = spec['box']
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w = min(VW, max(x1 - x0, (y1 - y0) * VW / VH) * spec.get('pad', 1.6))
    h = w * VH / VW
    tx = min(max(cx - w / 2, 0), VW - w)
    ty = min(max(cy - h / 2, 0), VH - h)
    rect = (tx * q, ty * q, VW + (tx + w - VW) * q, VH + (ty + h - VH) * q)
    out = panel.crop(tuple(round(v) for v in rect)).resize((VW, VH), Image.LANCZOS)
    if q > 0.6:
        a = round(255 * min(1.0, (q - 0.6) / 0.4))
        layer = Image.new('RGBA', out.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        label = TEXT['after_zoom']
        d.rounded_rectangle((24, 24, 24 + tw(d, label, 30, True) + 40, 82), radius=4, fill=(59, 130, 246, a))
        d.text((44, 36), label, font=font(30, True), fill=(255, 255, 255, a), anchor='lt')
        out = out.convert('RGBA')
        out.alpha_composite(layer)
        out = out.convert('RGB')
    return out


def filelist(panel, spec, t):
    """파일 목록 카드: spec['cols'] = [(칸 제목, [(역할, 파일 이름)…])…] 를 두 칸 표로 정리해 보여 준다."""
    t0 = spec['at']
    if t < t0:
        return panel
    p = rv.smooth(min(1.0, (t - t0) / 0.4))
    out = Image.blend(panel, Image.new('RGB', panel.size, (2, 4, 8)), 0.6 * p)
    layer = Image.new('RGBA', panel.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = round(255 * p)
    x0, x1, y0 = 90, 1510, 70
    d.rectangle((x0, y0, x1, y0 + 92), fill=(17, 30, 50, a))
    d.text((x0 + 36, y0 + 22), spec['title'], font=font(44, True), fill=(245, 242, 233, a), anchor='lt')
    d.text((x1 - 36, y0 + 32), spec.get('tag', ''), font=font(26), fill=(125, 217, 205, a), anchor='rt')
    colw, row = (x1 - x0) // 2, 118
    for c, (head, files) in enumerate(spec['cols']):
        cx = x0 + c * colw
        d.rectangle((cx, y0 + 92, cx + colw - 2, y0 + 92 + 56), fill=(42, 59, 77, a))
        d.text((cx + 28, y0 + 104), head, font=font(28, True), fill=(245, 242, 233, a), anchor='lt')
        for i, (role, fname) in enumerate(files):
            k = c * len(files) + i
            q = rv.smooth(min(1.0, max(0.0, (t - t0 - 0.3 - k * 0.12) / 0.3)))
            if q <= 0:
                continue
            aa = round(255 * q)
            y = y0 + 148 + i * row
            d.rectangle((cx, y, cx + colw - 2, y + row - 2), fill=(245, 242, 233, aa) if i % 2 == 0 else (229, 233, 240, aa))
            d.text((cx + 24, y + 16), f'{k + 1:02d}', font=font(34, True), fill=(37, 99, 235, aa), anchor='lt')
            d.text((cx + 92, y + 16), role, font=font(30, True), fill=(17, 24, 39, aa), anchor='lt')
            d.text((cx + 92, y + 62), fname, font=font(22), fill=(71, 85, 105, aa), anchor='lt')
    out = out.convert('RGBA')
    out.alpha_composite(layer)
    return out.convert('RGB')


def boost(panel, spec, t):
    """향상 이펙트: 기본 막대가 차고, 더해지는 몫이 이어 붙어 끝까지 올라간다(문구는 TEXT['boost']).
    측정한 수치가 없으므로 숫자는 쓰지 않는다(막대 길이는 연출)."""
    t0 = spec['at']
    if t < t0:
        return panel
    layer = Image.new('RGBA', panel.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, x1, y0, y1 = 300, 1300, 640, 700
    a = round(255 * rv.smooth(min(1.0, (t - t0) / 0.3)))
    d.text((x0, y0 - 46), TEXT['boost'][0], font=font(30, True), fill=(245, 242, 233, a), anchor='lt')
    d.rounded_rectangle((x0, y0, x1, y1), radius=4, fill=(42, 59, 77, a))
    base = 0.55 * rv.smooth(min(1.0, max(0.0, (t - t0 - 0.2) / 0.8)))
    extra = 0.40 * rv.smooth(min(1.0, max(0.0, (t - t0 - 1.3) / 1.2)))
    xb = x0 + (x1 - x0) * base
    if base > 0:
        d.rounded_rectangle((x0, y0, xb, y1), radius=4, fill=(148, 163, 184, a))
        d.text((x0 + 16, y1 + 14), TEXT['boost'][1], font=font(24), fill=(176, 186, 203, a), anchor='lt')
    if extra > 0:
        xe = xb + (x1 - x0) * extra
        d.rectangle((xb, y0, xe, y1), fill=(59, 130, 246, a))
        d.text((xb + 16, y1 + 14), TEXT['boost'][2], font=font(24, True), fill=(125, 217, 205, a), anchor='lt')
        # 위로 오르는 화살표: 막대 끝을 따라가며 솟는다
        ax, rise = xe, 22 * (1 - abs(((t - t0 - 1.3) % 0.9) / 0.45 - 1))
        d.polygon([(ax - 16, y0 - 14 - rise), (ax + 16, y0 - 14 - rise), (ax, y0 - 42 - rise)], fill=(125, 217, 205, a))
        if extra >= 0.399:   # 다 찬 뒤 테두리가 한 번 빛난다
            g = max(0.0, 1 - (t - t0 - 2.5) / 0.8)
            if g > 0:
                d.rounded_rectangle((x0 - 6, y0 - 6, x1 + 6, y1 + 6), radius=8, outline=(125, 217, 205, round(255 * g)), width=4)
    out = panel.convert('RGBA')
    out.alpha_composite(layer)
    return out.convert('RGB')


# ---------------------------------------------------------------- 원본 컷
def raw_frames(name, offset, n, full=False, speed=1.0):
    """원본 녹화 구간을 화면 칸 크기(full=True 면 원본 1920×1080)로 n 프레임 읽는다. speed>1 이면 빨리 감기."""
    meta = json.loads((SRC / 'recording.json').read_text())
    seg = {s['name']: s for s in meta['segments']}[name]   # 같은 이름이면 마지막(최신) 녹화
    raw = SRC / 'raw' / Path(seg.get('rawVideo', meta['rawVideo'])).name
    start = meta.get('codingCandidates', {}).get(name, seg['start']) + offset
    w, h = (W, H) if full else (VW, VH)
    dec = subprocess.Popen([FFMPEG, '-v', 'error', '-ss', f'{start:.3f}', '-i', str(raw), '-vf',
                            f'setpts=PTS/{speed},fps={FPS},scale={w}:{h}:flags=lanczos,tpad=stop_mode=clone:stop_duration=10',
                            '-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'], stdout=subprocess.PIPE)
    for _ in range(n):
        data = dec.stdout.read(w * h * 3)
        yield Image.frombytes('RGB', (w, h), data)
    dec.stdout.close()
    dec.wait()


# ---------------------------------------------------------------- 편집 효과(초안용: 줌인·타이핑·클릭·멈춤)
# 원본 컷의 덧붙임(extra)에 넣는다. 시각은 컷 안 초, 음수면 컷 끝에서 거꾸로 센 초.
#   'freeze': (원본 시각, 멈출 초)      — 그 프레임에서 화면을 멈춘다(설명하는 동안 버튼 누르기 전 화면 유지)
#   'cam': [(시각, 원본 영역 | None[, 전환 초[, 여백 배율]])] — 그 시각부터 전환 초(기본 0.7) 동안 영역으로 줌인(None = 전체 화면)
#   'type': {'box': 원본 입력칸, 'text': 글, 'at': 시작, 'dur': 길이, 'size': 글자 크기}  — 입력칸에 글자가 하나씩 찍힌다
#   'click': (시각, 원본 버튼 영역)      — 포인터가 다가와 누르고 물결·테두리가 퍼진다
#   'spot': (시각, 원본 박스)            — 줌인한 화면에서 그 박스 밖을 어둡게 누르고 파란 테두리(카메라를 따라간다)
#   'slot': {'box': 원본 숫자 칸, 'value': '10', 'at': 시작, 'dur': 굴리는 초} — 슬롯머신처럼 굴러가다 값에서 멈춤
#   'speed': 배속                        — 빨리 감기(코딩 콘솔 글자가 줄줄 흐르게)
#   'console': 원본 콘솔 영역            — 콘솔만 잘라 화면 칸 폭에 꽉 채우고(움직임 없음) 위에 붙인다. 남는 아래는 콘솔 바탕색


def at_sec(v, total):
    return v if v >= 0 else total + v


def cam_rect(region, pad=1.12):
    """원본 영역을 16:9 로 넓히고(여백 pad) 원본 화면 안에 들인다."""
    if region is None:
        return (0.0, 0.0, float(W), float(H))
    x0, y0, x1, y1 = region
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w = max(x1 - x0, (y1 - y0) * W / H) * pad
    w = min(w, W)
    h = w * H / W
    x = min(max(cx - w / 2, 0), W - w)
    y = min(max(cy - h / 2, 0), H - h)
    return (x, y, x + w, y + h)


def cam_at(keys, t, total):
    cur = cam_rect(None)
    for key in keys:
        k_t, region = key[:2]
        ease = key[2] if len(key) > 2 else CAM_EASE
        t0 = at_sec(k_t, total)
        if t < t0:
            break
        nxt = cam_rect(region, key[3] if len(key) > 3 else 1.12)
        p = rv.smooth((t - t0) / max(ease, 0.01))
        cur = tuple(a + (b - a) * p for a, b in zip(cur, nxt)) if p < 1 else nxt
    return cur


def to_view(box, rect):
    """원본 좌표 박스 → 카메라 rect 를 화면 칸에 펼친 좌표."""
    x, y, x1, y1 = rect
    sx, sy = VW / (x1 - x), VH / (y1 - y)
    return ((box[0] - x) * sx, (box[1] - y) * sy, (box[2] - x) * sx, (box[3] - y) * sy)


def wrap(d, text, size, width):
    lines, cur = [], ''
    for ch in text:
        if d.textlength(cur + ch, font=font(size)) > width:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    return lines + [cur]


def type_schedule(text, dur):
    """사람이 치는 리듬: 글자마다 간격을 조금씩 다르게(고정 시드), 띄어쓰기·쉼표·마침표 뒤에는 잠깐 멈춘다.
    합이 dur 이 되도록 맞춘 글자별 등장 시각을 돌려준다."""
    import random
    rnd = random.Random(len(text))
    gaps = []
    for ch in text:
        g = rnd.uniform(0.75, 1.3)
        if ch == ' ':
            g *= 1.7
        elif ch in ',.:”':
            g *= 3.2
        gaps.append(g)
    scale = dur / sum(gaps)
    out, acc = [], 0.0
    for g in gaps:
        acc += g * scale
        out.append(acc)
    return out


_SCHEDULES = {}


def draw_typing(img, spec, t, total):
    """원본 프레임의 입력칸을 비우고 굵은 글씨로 한 글자씩 친다. 줄바꿈은 전체 문장 기준으로 미리 정해 글자가 줄을 건너뛰지 않고,
    새 글자는 0.08초에 걸쳐 진해진다. 치는 동안 커서는 켜져 있고, 다 친 뒤에만 깜빡인다."""
    t0 = at_sec(spec['at'], total)
    if t < t0:
        return img
    x0, y0, x1, y1 = spec['box']
    size = spec.get('size', 18)
    width = spec.get('wrap', x1 - x0 - 36)
    line_h, top = size + spec.get('gap', 10), spec.get('pad', 14)
    text = spec['text']
    key = (text, spec['dur'])
    if key not in _SCHEDULES:
        _SCHEDULES[key] = type_schedule(text, spec['dur'])
    sched = _SCHEDULES[key]
    el = t - t0
    n = sum(1 for ts in sched if ts <= el)
    fresh = 0.0 if n >= len(text) else min(1.0, max(0.0, (el - (sched[n - 1] if n else 0.0)) / 0.08))
    d = ImageDraw.Draw(img)
    d.rectangle((x0 + 3, y0 + 3, x1 - 3, y1 - 3), fill='white')
    f = font(size, True)
    lines = wrap(d, text, size + 1, width)   # 굵은 글씨 폭 여유
    ink = (17, 24, 39)
    if spec.get('marker', True):
        # 형광펜: 다 친 뒤 줄마다 왼쪽에서 오른쪽으로 쫘악 긋는다(글자 아래쪽 2/3 를 덮는 노란 띠)
        per = 0.3
        hp = (el - spec['dur'] - 0.15) / per
        for i, line in enumerate(lines):
            q = rv.smooth(min(1.0, max(0.0, hp - i)))
            if q <= 0:
                break
            ly = y0 + top + i * line_h
            lw = d.textlength(line, font=f)
            d.rounded_rectangle((x0 + 14, ly + size * 0.28, x0 + 14 + (lw + 8) * q, ly + size + 4), radius=3, fill=(253, 224, 71))
    left, y, cx, cy = n, y0 + top, x0 + 18, y0 + top
    for line in lines:
        part = line[:max(0, left)]
        if part:
            d.text((x0 + 18, y), part, font=f, fill=ink, anchor='lt')
            cx, cy = x0 + 18 + d.textlength(part, font=f), y
        if left <= len(line):
            if left < len(line) and fresh > 0:   # 다음 글자가 막 찍히는 중: 흰색에서 진한 색으로
                c = tuple(round(255 + (v - 255) * fresh) for v in ink)
                d.text((cx, y), line[left], font=f, fill=c, anchor='lt')
            break
        left -= len(line)
        y += line_h
        cx, cy = x0 + 18, y
    typing = n < len(text)
    if typing or int(el * 2.2) % 2 == 0:
        d.line((cx + 2, cy - 2, cx + 2, cy + size + 2), fill='#2563eb', width=3)
    return img


def draw_slot(img, spec, t, total):
    """슬롯머신 숫자: 원본 숫자 칸을 비우고 두 자리 숫자가 위로 굴러가다 느려지며 최종 값에서 멈춘 뒤 살짝 커졌다 돌아온다."""
    import random
    x0, y0, x1, y1 = spec['box']
    t0, dur, final = at_sec(spec['at'], total), spec.get('dur', 1.8), spec['value']
    if t < t0:
        return img
    rnd = random.Random(7)
    steps = 28
    seq = [f'{rnd.randint(11, 99):02d}' for _ in range(steps)] + [final]
    p = min(1.0, (t - t0) / dur)
    r = steps * (1 - (1 - p) ** 3)   # 처음엔 빠르게, 끝에서 천천히
    k, frac = int(r), r - int(r)
    if p >= 1:
        k, frac = steps, 0.0
    size, color = spec.get('size', 24), spec.get('color', (0, 103, 235))
    w, h = x1 - x0, y1 - y0
    pop = 1.0
    if p >= 1:
        pop = 1 + 0.35 * max(0.0, 1 - (t - t0 - dur) / 0.3)
    cell = Image.new('RGB', (w, h), spec.get('bg', (253, 255, 255)))
    cd = ImageDraw.Draw(cell)
    f = font(round(size * pop), True)
    def put(txt, dy):
        tw_ = cd.textlength(txt, font=f)
        cd.text(((w - tw_) / 2, (h - size * pop) / 2 - 2 + dy), txt, font=f, fill=color, anchor='lt')
    put(seq[k], -frac * h)
    if k + 1 < len(seq):
        put(seq[k + 1], (1 - frac) * h)
    img.paste(cell, (x0, y0))
    return img


CURSOR = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]


def draw_click(panel, spec, t, total, rect):
    t_click, box = at_sec(spec[0], total), spec[1]
    if t < t_click - 0.9 or t > t_click + 1.4:
        return panel
    bx0, by0, bx1, by1 = to_view(box, rect)
    tx, ty = (bx0 + bx1) / 2, (by0 + by1) / 2
    layer = Image.new('RGBA', panel.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    dt = t - t_click
    if dt >= 0:   # 누른 뒤: 버튼 테두리 강조 + 물결
        a = max(0.0, 1 - dt / 1.4)
        d.rounded_rectangle((bx0 - 6, by0 - 6, bx1 + 6, by1 + 6), radius=8, outline=(250, 204, 21, round(255 * a)), width=4)
        if dt < 0.6:
            r = 18 + 70 * rv.smooth(dt / 0.6)
            d.ellipse((tx - r, ty - r, tx + r, ty + r), outline=(250, 204, 21, round(230 * (1 - dt / 0.6))), width=5)
    # 포인터: 0.9초 전부터 오른쪽 아래에서 다가와 누를 때 살짝 작아진다
    mv = rv.smooth(min(1.0, (dt + 0.9) / 0.7))
    px, py = tx + 140 * (1 - mv), ty + 110 * (1 - mv)
    sc = 1.6 * (0.85 if 0 <= dt < 0.18 else 1.0)
    alpha = round(255 * min(1.0, (dt + 0.9) / 0.25, max(0.0, (1.4 - dt) / 0.4)))
    pts = [(px + x * sc, py + y * sc) for x, y in CURSOR]
    d.polygon(pts, fill=(255, 255, 255, alpha), outline=(17, 24, 39, alpha))
    d.line(pts + [pts[0]], fill=(17, 24, 39, alpha), width=2)
    out = panel.convert('RGBA')
    out.alpha_composite(layer)
    return out.convert('RGB')


def edited_raw_frames(name, offset, n, extra):
    """줌인·타이핑·멈춤이 있는 원본 컷: 원본 해상도로 읽어 효과를 입히고 카메라 영역을 화면 칸으로 키운다."""
    total = n / FPS
    f_at, f_n = n, 0
    if extra.get('freeze'):
        at, length = extra['freeze']
        f_at = round(at * FPS)
        f_n = max(0, round((at_sec(length, total) - at if length < 0 else length) * FPS))
    src = raw_frames(name, offset, n - f_n + 1, full=True, speed=extra.get('speed', 1.0))
    last = None
    bg = None
    for k in range(n):
        if last is None or not (f_at <= k < f_at + f_n):
            last = next(src)
        img = last.copy()
        t = k / FPS
        if 'type' in extra:
            img = draw_typing(img, extra['type'], t, total)
        if 'slot' in extra:
            img = draw_slot(img, extra['slot'], t, total)
        if 'console' in extra:
            x0, y0, x1, y1 = extra['console']
            con = img.crop((x0, y0, x1, y1))
            h = round((y1 - y0) * VW / (x1 - x0))
            if bg is None:   # 콘솔 바탕색 = 가장 많은 색(글자 색이 섞이지 않게)
                bg = max(con.resize((120, 40)).getcolors(4800))[1]
            panel = Image.new('RGB', (VW, VH), bg)
            panel.paste(con.resize((VW, h), Image.LANCZOS), (0, 0))   # 위에 붙여 아래는 빈 터미널처럼 이어지게
            yield panel
            continue
        rect = cam_at(extra.get('cam', []), t, total)
        panel = img.crop(tuple(round(v) for v in rect)).resize((VW, VH), Image.LANCZOS)
        if 'spot' in extra:
            s_at, s_box = extra['spot']
            panel = spotlight(panel, to_view(s_box, rect), ramp(t, at_sec(s_at, total), total + 1))
        if 'click' in extra:
            panel = draw_click(panel, extra['click'], t, total, rect)
        yield panel


def result_frames(name, offset, n):
    rec = SC.result_rec(name)
    ev = json.loads((rec / 'events.json').read_text())
    take, pieces = SC.result_pieces(name, ev['events'])
    _, v0, v1 = pieces[0]
    src = rv.ResultSource(next(rec.glob('*.webm')), ev['takes'][take]['crop'],
                          [(0, min(v0 + offset, v1), v1)], int(n / FPS) + 2)
    for k in range(n):
        yield src.view(k)


def shot_frames(kind, name, offset, n, extra=None):
    if kind == 'raw' and extra and any(k in extra for k in ('cam', 'type', 'click', 'freeze', 'console', 'slot')):
        return edited_raw_frames(name, offset, n, extra)
    return raw_frames(name, offset, n) if kind == 'raw' else result_frames(name, offset, n)


# ---------------------------------------------------------------- 줄 렌더
def ramp(t, a, b, fade=0.35):
    """a~b 구간에서 1, 앞뒤 fade 초 동안 0↔1."""
    if t < a or t > b:
        return 0.0
    return rv.smooth(min(1.0, (t - a) / fade, (b - t) / fade))


def signpost(panel, step, steps, p):
    """단계가 바뀌는 줄 첫머리: 화면 칸을 누르고 '둘째 · 분석' 표지를 크게 띄운다."""
    if p <= 0:
        return panel
    out = Image.blend(panel, Image.new('RGB', panel.size, rgb(THEME['sign_dim'])), 0.8 * p)
    a = round(255 * p)
    layer = Image.new('RGBA', panel.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    num, name = f'{step:02d}', steps[step - 1]
    ld.text(((VW - tw(ld, num, 96, True)) / 2, 250), num, font=font(96, True), fill=rgb(THEME['sign_num']) + (a,), anchor='lt')
    ld.text(((VW - tw(ld, name, 120, True)) / 2, 380), name, font=font(120, True), fill=rgb(THEME['sign_name']) + (a,), anchor='lt')
    sub = f'{ORDINAL[step - 1]} 단계 / 전체 {len(steps)}단계'
    ld.text(((VW - tw(ld, sub, 34)) / 2, 560), sub, font=font(34), fill=rgb(THEME['sign_sub']) + (a,), anchor='lt')
    out.paste(layer, (0, 0), layer)
    return out


def render_row(row, step, shots, emit, check=None, steps=STEPS, new_step=False, thumb=None):
    n_row = round((row['end'] - row['start']) * FPS)
    base = frame_base(row, step, steps)
    plan = list(shots)
    used = sum(round(s[3] * FPS) for s in plan[:-1])
    lengths = [round(s[3] * FPS) for s in plan[:-1]] + [n_row - used]
    k_row = 0
    for (kind, name, offset, _dur, box, extra), n in zip(plan, lengths):
        if kind == 'raw' and box:
            box = tuple(v * RAW_SCALE for v in box)
        for k, panel in enumerate(shot_frames(kind, name, offset, n, extra)):
            t = k / FPS
            if box:
                panel = spotlight(panel, box, ramp(t, 0.4, n / FPS + 1))
            if kind == 'result':
                # 어둡게 누른 뒤에 그려 꼬리표는 늘 또렷하게. 줌인이 시작되면 옆 꼬리표는 빼고 줌 화면에 AFTER 꼬리표만 단다
                if 'zoom' in extra and t >= extra['zoom']['at']:
                    panel = zoom_after(panel, extra['zoom'], t)
                else:
                    panel = tags(panel)
                for c in extra.get('clicks', ()):   # 결과 화면 클릭 효과(화면 칸 좌표)
                    panel = draw_click(panel, c, t, n / FPS, (0, 0, VW, VH))
            if 'pledge' in extra:
                panel = pledge(panel, extra['pledge'], t)
            if 'filelist' in extra:
                panel = filelist(panel, extra['filelist'], t)
            if 'big' in extra:
                panel = big_text(panel, *extra['big'], ramp(t, extra['big_at'], n / FPS + 1, 0.5))
            if 'boost' in extra:
                panel = boost(panel, extra['boost'], t)
            tt = k_row / FPS
            if new_step:
                panel = signpost(panel, step, steps, ramp(tt, 0, SIGNPOST_SEC, 0.3))
            frame = base.copy()
            frame.paste(panel, (VX, VY))
            fade = min(1.0, tt / FADE, (n_row / FPS - tt) / FADE)
            if fade < 1:
                frame = Image.blend(Image.new('RGB', (W, H), BG), frame, max(0.0, fade))
            if check is not None and k == min(n - 1, round(n * 0.6)):
                check.append(frame.copy())
            if thumb is not None and not thumb and (tt >= (SIGNPOST_SEC + 0.6 if new_step else n_row / FPS * 0.5) or k_row == n_row - 1):
                thumb.append(frame.copy())   # 에디터 장면 썸네일: 줄마다 1장(단계 표지가 걷힌 뒤)
            emit(frame)
            k_row += 1


def card(row, kind, steps=None):
    """인트로·아웃트로 카드. 화면 자막 셋째 줄이 'A → B → …' 이면 그 단계를 아래 단계 줄로 쓰고(STEP_NOTES 설명 포함),
    아니면 STEPS 를 쓰고 셋째 줄을 맨 아래 한 줄로 쓴다."""
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    accent = ACCENT if kind == 'intro' else THEME['outro_accent']
    title, sub, foot = row['lines'][:3]
    steps = [s.strip() for s in foot.split('→')] if '→' in foot else (steps or STEPS)
    d.rectangle((128, 171, 184, 176), fill=accent)
    d.text((208, 159), TEXT['card_brand'], font=font(26), fill=accent, anchor='lt')
    parts = [p.strip() for p in re.split(r'(?<=[.,])\s+', title) if p.strip()]
    for i, s in enumerate(parts[:2]):
        d.text((128, 300 + i * 120), s, font=font(84, True), fill=FG, anchor='lt')
    d.text((132, 300 + len(parts[:2]) * 120 + 40), sub, font=font(34), fill=accent, anchor='lt')
    gap = (W - 264) // len(steps)
    big, small = (32, 22) if len(steps) <= 6 else (27, 19)
    for i, s in enumerate(steps):
        x = 132 + i * gap
        d.line((x, 760, x + gap - (40 if len(steps) <= 6 else 24), 760), fill=accent, width=2)
        d.text((x, 780), f'0{i + 1}', font=font(22), fill=accent, anchor='lt')
        d.text((x, 818), s, font=font(big, True), fill=FG, anchor='lt')
        for j, note in enumerate(STEP_NOTES.get(s, ())):
            d.text((x, 866 + j * (small + 8)), note, font=font(small), fill=MUTED, anchor='lt')
    if '→' not in foot:
        d.text((132, 936 if steps is STEPS else 950), foot, font=font(24), fill=MUTED, anchor='lt')
    if kind == 'intro' and presenter:
        d.text((132, 1000), presenter, font=font(28, True), fill=FG, anchor='lt')
    if kind == 'outro':
        for y, line in zip((1004, 1036), OUTRO_CREDIT):
            d.text((132, y), line, font=font(16), fill=MUTED, anchor='lt')
    if DECORATE_CARD:
        DECORATE_CARD(im, d, frame_ctx(row, 0, steps, kind))
    return im


def render_card(row, kind, emit, check=None, steps=None):
    pic = card(row, kind, steps)
    if check is not None:
        check.append(pic)
    n = round((row['end'] - row['start']) * FPS)
    bgimg = Image.new('RGB', (W, H), BG)
    for j in range(n):
        t = j / FPS
        a = rv.smooth(min(1.0, t / 0.8)) if kind == 'intro' else rv.smooth(min(1.0, t / 0.5, (n / FPS - t) / 1.2))
        emit(Image.blend(bgimg, pic, a) if a < 1 else pic)


# 광고 같은 인트로(키네틱 타이포그래피): 검은 화면에 큰 글자가 내레이션 박자대로 한 덩어리씩 나온다.
# 장면 데이터 AD_INTRO[라벨] = [(시작 초, 끝 초, 글, 크기, 색)], 비면 제목 + 단계 블럭 플립만
PRESENTER_COLOR = (243, 185, 149)   # 발표자 표기는 본문과 다른 따뜻한 색


def flip_block(i, name, w, h, active=False, passed=False):
    """단계 블럭 한 장(앞면): 짙은 단색 바탕 + 1px 테두리 + 4px 모서리. active 는 지금 단계(청록 테두리·밝게), passed 는 지난 단계."""
    card = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    fill = (30, 44, 48, 255) if active else (22, 24, 30, 255)
    line = (125, 217, 205, 255) if active else ((110, 114, 124, 255) if passed else (70, 74, 84, 255))
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=4, fill=fill, outline=line, width=3 if active else 1)
    d.text((22, 20), f'0{i + 1}', font=font(30, True), fill=(125, 217, 205, 255), anchor='lt')
    size = 28
    while d.textlength(name, font=font(size, True)) > w - 40:
        size -= 1
    d.text((22, h - 30 - size), name, font=font(size, True), fill=(245, 245, 247, 255), anchor='lt')
    return card


def intro_ad_frame(row, t, total, steps, beats):
    im = Image.new('RGB', (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    for t0, t1, text, size, color in beats:
        if not (t0 <= t < t1 + 0.25):
            continue
        a = rv.smooth(min(1.0, (t - t0) / 0.35, max(0.0, (t1 + 0.25 - t) / 0.25)))
        sc = 1.06 - 0.06 * rv.smooth(min(1.0, (t - t0) / 0.6))   # 살짝 다가오며 자리 잡는다
        f = font(round(size * sc), True)
        w_ = d.textlength(text, font=f)
        col = tuple(round(c * a) for c in color)
        d.text((W / 2, H / 2 - 30 + 18 * (1 - a)), text, font=f, fill=col, anchor='mm')
    end = beats[-1][1] + 0.25 if beats else 0.3
    if t >= end:   # 마무리: 제목이 나오고 1~7단계 블럭이 차례로 뒤집히며 자리 잡는다
        a = rv.smooth(min(1.0, (t - end) / 0.6))
        title = TEXT['intro_title']
        f = font(120, True)
        d.text(((W - d.textlength(title, font=f)) / 2, 250 + 20 * (1 - a)), title, font=f,
               fill=tuple(round(v * a) for v in (245, 245, 247)), anchor='lt')
        sub = TEXT['intro_sub']
        f2 = font(40)
        d.text(((W - d.textlength(sub, font=f2)) / 2, 410), sub, font=f2, fill=tuple(round(v * a) for v in (125, 217, 205)), anchor='lt')
        n, gapx = len(steps), 20
        bw = (W - 240 - gapx * (n - 1)) // n
        bh, by = 170, 560
        done = end + 0.6 + (len(steps) - 1) * 0.5 + 0.55
        cur = int((t - done) / 0.55) if t >= done else -1   # 다 펴진 뒤 0.55초마다 다음 단계로 이동
        for i, st in enumerate(steps):
            q = min(1.0, max(0.0, (t - end - 0.6 - i * 0.5) / 0.55))
            if q <= 0:
                continue
            ang = (1 - rv.smooth(q)) * 90   # 옆으로 선 카드가 정면으로 돌아온다
            import math
            sx = max(0.02, math.cos(math.radians(ang)))
            card = flip_block(i, st, bw, bh, active=(i == cur), passed=(0 <= cur and i < cur))
            if q < 1:   # 돌아가는 동안 살짝 어둡게(빛을 받는 각도)
                shade = Image.new('RGBA', card.size, (0, 0, 0, round(150 * (1 - sx))))
                card = Image.alpha_composite(card, shade)
            cw = max(1, round(bw * sx))
            card = card.resize((cw, bh), Image.LANCZOS)
            x = 120 + i * (bw + gapx) + (bw - cw) // 2
            im.paste(card, (x, by + round(14 * (1 - rv.smooth(q)))), card)
    if presenter:   # 발표자: 오른쪽 아래, 본문과 다른 따뜻한 색
        pa = rv.smooth(min(1.0, t / 0.8))
        fp = font(30, True)
        d.text((W - 120 - d.textlength(presenter, font=fp), H - 92), presenter, font=fp,
               fill=tuple(round(v * pa) for v in PRESENTER_COLOR), anchor='lt')
    return im


def render_intro_ad(row, emit, steps, beats, thumb=None):
    n = round((row['end'] - row['start']) * FPS)
    for j in range(n):
        t = j / FPS
        fr = intro_ad_frame(row, t, n / FPS, steps, beats)
        fade = min(1.0, (n / FPS - t) / FADE)
        if fade < 1:
            fr = Image.blend(Image.new('RGB', (W, H), BG), fr, max(0.0, fade))
        if thumb is not None and not thumb and t >= n / FPS - 1.0:
            thumb.append(fr.copy())
        emit(fr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('label', help='대본 라벨 또는 주소 번호')
    ap.add_argument('--config', help='script-editor.json 경로')
    ap.add_argument('--out', type=Path, help='작업 폴더의 부모(기본 설정 render.out)')
    ap.add_argument('--check', action='store_true', help='확인 프레임(줄마다 1장) 모음만 만든다')
    ap.add_argument('--only', type=int, help='이 줄만 렌더해 <폴더>/row-NN.mp4 로 쓴다(에디터 장면 영상 미리보기용)')
    ap.add_argument('--thumbs', action='store_true', help='에디터 장면 썸네일 <콘텐츠>/frames/<라벨>/NN.jpg 도 쓴다')
    a = ap.parse_args()
    global presenter
    label = CFG.resolve_label(a.label)
    presenter = PRESENTER.get(label, '')
    global SRC
    SRC = SRC_BY_LABEL.get(label, SC.SRC)
    if label not in SHOTS:
        sys.exit(f'컷 계획이 없는 대본: {label} (가능: {", ".join(SHOTS)})')
    target, rows = read_script(CFG, label)
    plan = SHOTS[label]
    out = (a.out / build_name(CFG, label)) if a.out else build_dir(CFG, label)
    out.mkdir(parents=True, exist_ok=True)
    checks = []
    if a.check:
        emit = lambda f: None  # noqa: E731
    else:
        enc = subprocess.Popen([FFMPEG, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                                '-r', str(FPS), '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                                '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                                str(out / (f'row-{a.only:02d}.mp4' if a.only else 'video-only.mp4'))],
                               stdin=subprocess.PIPE)
        emit = lambda f: enc.stdin.write(f.tobytes())  # noqa: E731
    intro_foot = rows[0]['lines'][2] if len(rows[0]['lines']) > 2 else ''
    steps = [x.strip() for x in intro_foot.split('→')] if label in SIGNPOST and '→' in intro_foot else STEPS
    thumbs_dir = CFG.content / 'frames' / label
    prev_step = 0
    for row in rows:
        thumb = []
        if a.only and row['n'] != a.only:
            if row['n'] in plan:
                prev_step = plan[row['n']][0]
            continue
        if row['n'] == 1:
            if label in AD_INTRO:
                render_intro_ad(row, emit, steps, AD_INTRO[label], thumb)
            else:
                render_card(row, 'intro', emit, thumb)
        elif row['n'] == rows[-1]['n']:
            render_card(row, 'outro', emit, thumb, None if steps is STEPS else steps)
        else:
            step, shots = plan[row['n']]
            render_row(row, step, shots, emit, checks, steps, steps is not STEPS and step != prev_step, thumb)
            prev_step = step
        if row['n'] in (1, rows[-1]['n']):
            checks.extend(thumb)
        if a.thumbs and thumb:
            thumbs_dir.mkdir(parents=True, exist_ok=True)
            thumb[0].resize((960, 540)).save(thumbs_dir / f"{row['n']:02d}.jpg", quality=85)
        print(f"{row['n']:02d} {row['start']:5.1f}~{row['end']:5.1f}s {row['scene']}", flush=True)
    if not a.check:
        enc.stdin.close()
        assert enc.wait() == 0
        print('COMPLETE', out / (f'row-{a.only:02d}.mp4' if a.only else 'video-only.mp4'), f'{target}s')
    cols = 2
    sheet = Image.new('RGB', (cols * 960, ((len(checks) + cols - 1) // cols) * 540), BG)
    for i, im in enumerate(checks):
        sheet.paste(im.resize((960, 540)), ((i % cols) * 960, (i // cols) * 540))
    sheet.save(out / 'check.jpg', quality=85)
    print('check', out / 'check.jpg')


if __name__ == '__main__':
    main()
