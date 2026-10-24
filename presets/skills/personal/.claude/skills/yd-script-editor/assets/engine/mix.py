#!/usr/bin/env python3
"""렌더한 영상에 내레이션·배경음을 믹싱한다(덕킹·2회 loudnorm).

- 내레이션: <콘텐츠>/audio/<라벨>/NN.m4a 를 합성 입력 json 의 줄 start 에 놓는다(자르기·속도 변경 없음).
- 배경음: 설정 render.music -12dB, 내레이션 sidechain 덕킹, 끝 2초 페이드아웃.
- 1·2장: 작업 폴더에 intro.webm·scene2.webm(브라우저 녹화, record_intro.mjs)이 있으면 바꿔 끼운다.
- 최종 -16 LUFS, True Peak -1.5dB. 영상은 다시 인코딩하지 않는다(copy). 끝나면 cut_clips 로 장면 영상을 다시 자른다.
사용: python3 mix.py <라벨|주소 번호> [--video <video-only.mp4>] [--out <결과.mp4>] [--config <script-editor.json>]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from se_config import Config  # noqa: E402
from script import build_dir, probe, read_script, video_path  # noqa: E402

FFMPEG = 'ffmpeg'


def splice_html_scenes(video, build, rows):
    """video-only 에서 1장을 intro.webm 으로, 2장 앞 4초를 scene2.webm 으로 바꾼 video-only-html.mp4 를 만든다."""
    intro, s2 = build / 'intro.webm', build / 'scene2.webm'
    if not intro.exists():
        return video
    r1, r2 = rows[0], rows[1]
    out = build / 'video-only-html.mp4'
    parts, filt = ['-i', str(video), '-ss', '0.6', '-i', str(intro)], []
    d1 = r1['end']
    filt.append(f'[1:v]trim=0:{d1:.3f},setpts=PTS-STARTPTS,scale=1920:1080,fps=25,settb=AVTB,fade=t=out:st={d1 - 0.3:.2f}:d=0.3[s1]')
    if s2.exists():
        parts += ['-ss', '0.4', '-i', str(s2)]
        filt.append('[2:v]trim=0:4,setpts=PTS-STARTPTS,scale=1920:1080,fps=25,settb=AVTB,fade=t=in:st=0:d=0.3[s2a]')
        filt.append(f'[0:v]trim={r2["start"] + 4:.3f}:{r2["end"]:.3f},setpts=PTS-STARTPTS,fps=25,settb=AVTB[s2b]')
        filt.append('[s2a][s2b]xfade=transition=fade:duration=0.4:offset=3.6[s2]')
        filt.append(f'[0:v]trim={r2["end"]:.3f},setpts=PTS-STARTPTS,fps=25,settb=AVTB[rest]')
        filt.append('[s1][s2][rest]concat=n=3:v=1:a=0[v]')
    else:
        filt.append(f'[0:v]trim={r1["end"]:.3f},setpts=PTS-STARTPTS,fps=25,settb=AVTB[rest]')
        filt.append('[s1][rest]concat=n=2:v=1:a=0[v]')
    subprocess.run([FFMPEG, '-y', '-v', 'error', *parts, '-filter_complex', ';'.join(filt), '-map', '[v]', '-an',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', str(out)], check=True)
    print('html 장면 합성', out.name, f'{probe(out):.2f}s')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('label', help='대본 라벨 또는 주소 번호')
    ap.add_argument('--video', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--config')
    a = ap.parse_args()
    global FFMPEG
    cfg = Config(a.config)
    FFMPEG = cfg.ffmpeg
    if cfg.music is None or not cfg.music.is_file():
        sys.exit(f'배경음이 없어요: script-editor.json render.music ({cfg.music})')
    MUSIC = cfg.music
    label = cfg.resolve_label(a.label)
    target, rows = read_script(cfg, label)
    build = build_dir(cfg, label)
    video = a.video or build / 'video-only.mp4'
    out = a.out or video_path(cfg, label)
    audio = cfg.content / 'audio' / label
    meta = json.loads(cfg.script_json(label).read_text())
    placed = []
    for i, row in enumerate(rows):
        start = meta['lines'][i]['start']   # 첫 줄은 카드가 0초부터라도 음성은 표 시각에 놓는다
        path = audio / f"{row['n']:02d}.m4a"
        dur = probe(path)
        end = row['end']
        placed.append((start, path, dur))
        flag = '  ← 다음 줄과 겹침' if start + dur > end else ''
        print(f"{row['n']:02d} {start:6.2f}s ~ {start + dur:6.2f}s ({dur:.2f}s, 구간 끝 {end:.1f}s){flag}")
    # 1·2장은 브라우저 녹화본(intro/*.html → intro.webm·scene2.webm)으로 바꿔 끼운다(있을 때만)
    video = splice_html_scenes(video, build, rows)
    vlen = probe(video)
    inputs = ['-i', str(video), '-i', str(MUSIC)]
    for _, path, _ in placed:
        inputs += ['-i', str(path)]
    parts = []
    for i, (start, *_r) in enumerate(placed, 2):
        ms = int(round(start * 1000))
        parts.append(f'[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[n{i}]')
    mix = ''.join(f'[n{i}]' for i in range(2, len(placed) + 2))
    graph = ';'.join(parts) + (
        f';{mix}amix=inputs={len(placed)}:normalize=0,apad,loudnorm=I=-16:TP=-2:LRA=7[voice]'
        ';[voice]asplit=2[v1][v2]'
        f';[1:a]aresample=48000,atrim=0:{vlen:.2f},afade=t=out:st={vlen - 2:.2f}:d=2,volume=-12dB[bgm]'
        ';[bgm][v1]sidechaincompress=threshold=0.01:ratio=12:attack=40:release=500:makeup=1[duck]'
        ';[duck][v2]amix=inputs=2:normalize=0:duration=first[a]'
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    pre = build / 'premix.wav'
    subprocess.run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'error', *inputs, '-filter_complex', graph,
                    '-map', '[a]', '-t', f'{vlen:.2f}', '-c:a', 'pcm_f32le', '-ar', '48000', str(pre)], check=True)
    scan = subprocess.run([FFMPEG, '-hide_banner', '-nostats', '-i', str(pre), '-af',
                           'loudnorm=I=-16:TP=-1.5:LRA=20:print_format=json', '-f', 'null', '-'],
                          capture_output=True, text=True).stderr
    m = json.loads(scan[scan.rfind('{'):scan.rfind('}') + 1])
    norm = (f"loudnorm=I=-16:TP=-1.5:LRA=20:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
            "linear=true:print_format=json,aresample=48000")
    r = subprocess.run([FFMPEG, '-y', '-hide_banner', '-nostats', '-i', str(video), '-i', str(pre), '-map', '0:v', '-map', '1:a',
                        '-af', norm, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest',
                        '-movflags', '+faststart', str(out)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-2000:])
    m2 = json.loads(r.stderr[r.stderr.rfind('{'):r.stderr.rfind('}') + 1])
    print('음량', {k: m2[k] for k in ('output_i', 'output_tp', 'normalization_type')})
    print('complete', out, f'{probe(out):.2f}s')
    # 에디터 장면 영상(<콘텐츠>/clips/<라벨>/NN.mp4)도 새 영상으로 다시 자른다
    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / 'cut_clips.py'), label, '--video', str(out),
                    '--config', str(cfg.path)], check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
