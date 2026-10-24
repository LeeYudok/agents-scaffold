#!/usr/bin/env python3
"""렌더한 영상을 대본 줄 구간대로 잘라 에디터 장면 영상으로 둔다.

- 입력: 완성 영상(<videos.dir>/<videos.pattern>, mix.py 결과), 대본 md 의 줄별 '시각'과 '목표 길이'
- 출력: <콘텐츠>/clips/<라벨>/NN.mp4 — 에디터가 썸네일 대신 이 조각을 보여 준다(/clips/<라벨>/NN.mp4)
- 구간: 줄 시각 ~ 다음 줄 시각(마지막 줄은 영상 끝), 첫 줄은 0초부터. 정확히 자르려고 다시 인코딩한다(960×540).

사용: python3 cut_clips.py <라벨|주소 번호> [--video <mp4>] [--config <script-editor.json>]
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from se_config import Config  # noqa: E402
from script import read_script, video_path  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('label')
    ap.add_argument('--video', type=Path)
    ap.add_argument('--config')
    a = ap.parse_args()
    cfg = Config(a.config)
    label = cfg.resolve_label(a.label)
    video = a.video or video_path(cfg, label)
    _, rows = read_script(cfg, label)
    out = cfg.content / 'clips' / label
    out.mkdir(parents=True, exist_ok=True)
    for row in rows:
        start, end = row['start'], row['end']
        path = out / f"{row['n']:02d}.mp4"
        subprocess.run([cfg.ffmpeg, '-y', '-v', 'error', '-ss', f'{start:.3f}', '-i', str(video), '-t', f'{end - start:.3f}',
                        '-vf', 'scale=960:540', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(path)], check=True)
        print(f"{row['n']:02d} {start:6.2f}~{end:6.2f}s → {path.name} {path.stat().st_size // 1024}KB")
    print('clips', out)


if __name__ == '__main__':
    main()
