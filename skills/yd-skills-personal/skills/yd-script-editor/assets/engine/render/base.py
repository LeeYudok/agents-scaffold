"""렌더 공용 바탕: 화면 크기·색, 글꼴, 이징, 강조 박스, 결과 화면(두 폰) 녹화 소스.

글꼴 폴더와 ffmpeg 는 setup() 으로 정한다(render.py 가 장면 데이터의 FONT_DIR 로 부른다).
글꼴은 <FONT_DIR>/NotoSansCJK-Regular.ttc · NotoSansCJK-Bold.ttc (Noto Sans CJK, SIL OFL) 를 쓴다.
"""
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = None
FFMPEG = shutil.which('ffmpeg') or 'ffmpeg'


W, H, FPS = 1920, 1080, 25
VW, VH, VX, VY = 1600, 900, 160, 76
BG = '#111e32'; FG = '#f5f2e9'; MUTED = '#b0bacb'; ACCENT = '#7dd9cd'
BLUE = (59, 130, 246)
BOX_W, BOX_R = 5, 10
FONTS = {}


def setup(font_dir, ffmpeg=None):
    global FONT_DIR, FFMPEG
    FONT_DIR = Path(font_dir)
    if ffmpeg:
        FFMPEG = ffmpeg


def font(size, bold=False):
    key = (size, bold)
    if key not in FONTS:
        if FONT_DIR is None:
            raise SystemExit('글꼴 폴더가 없어요 — 장면 데이터에 FONT_DIR 를 두세요')
        FONTS[key] = ImageFont.truetype(str(FONT_DIR / ('NotoSansCJK-' + ('Bold' if bold else 'Regular') + '.ttc')), size, index=1)
    return FONTS[key]


def smooth(p):
    p = min(1, max(0, p))
    return p * p * (3 - 2 * p)



_BOX_CACHE = {}


def box_patch(w, h):
    """파랑 5px · 반지름 10 둥근 테두리(썸네일 step_labels.compose 와 같은 모양), 3배 그려 줄인다."""
    key = (w, h)
    if key not in _BOX_CACHE:
        s = 3
        im = Image.new('RGBA', ((w + 1) * s, (h + 1) * s), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((0, 0, w * s, h * s), radius=BOX_R * s, outline=BLUE + (255,), width=BOX_W * s)
        _BOX_CACHE[key] = im.resize((w + 1, h + 1), Image.LANCZOS)
        if len(_BOX_CACHE) > 400:
            _BOX_CACHE.clear()
    return _BOX_CACHE[key]


def with_alpha(img, a):
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel('A').point(lambda v: round(v * a)))
    return out



class ResultSource:
    """재녹화 webm 에서 두 폰 영역을 잘라 872×900 으로 줄인 프레임을 장면 시각에 맞춰 준다.
    pieces: [(장면 시각, 녹화 시작, 녹화 끝)] — 조작은 녹화 그대로, 사이 정지 구간은 마지막 화면 유지."""

    def __init__(self, video, crop, pieces, duration):
        x0, y0, x1, y1 = crop
        cw, ch = x1 - x0, y1 - y0
        s = min(VW / cw, VH / ch)
        self.size = (round(cw * s), round(ch * s))
        self.scale = s
        self.margin = (VW - self.size[0]) // 2
        n = duration * FPS
        self.index = []
        for i in range(n):
            t = i / FPS
            piece = pieces[0]
            for p in pieces:
                if t >= p[0]:
                    piece = p
            st, v0, v1 = piece
            v = min(v1, v0 + max(0.0, t - st))
            self.index.append(round(v * FPS))
        need = sorted(set(self.index))
        lo, hi = need[0], need[-1]
        fw, fh = self.size
        cmd = [FFMPEG, '-v', 'error', '-i', str(video), '-vf',
               f'select=between(n\\,{lo}\\,{hi}),crop={cw}:{ch}:{x0}:{y0},scale={fw}:{fh}:flags=lanczos',
               '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']
        dec = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        keep = set(need)
        self.frames = {}
        k = lo
        while True:
            data = dec.stdout.read(fw * fh * 3)
            if len(data) < fw * fh * 3:
                break
            if k in keep:
                self.frames[k] = Image.frombytes('RGB', (fw, fh), data)
            k += 1
        dec.wait()
        missing = [k for k in need if k not in self.frames]
        if missing:
            last = max(self.frames)
            for k in missing:
                self.frames[k] = self.frames[last]
            print(f'  주의: 녹화 끝 넘음 {len(missing)}프레임 → 마지막 화면', flush=True)

    def view(self, n):
        panel = Image.new('RGB', (VW, VH), BG)
        panel.paste(self.frames[self.index[n]], (self.margin, (VH - self.size[1]) // 2))
        return panel
