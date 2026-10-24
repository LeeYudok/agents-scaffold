#!/usr/bin/env python3
"""대본 줄별 음성을 합성해 <콘텐츠>/audio/<라벨>/NN.m4a 로 저장한다 (OmniVoice 음성 복제).

    <omnivoice 파이썬> synth.py 1 --script <대본 이름>        # 1번 줄만
    <omnivoice 파이썬> synth.py 1 2 3 --script <대본 이름>    # 여러 줄
    <omnivoice 파이썬> synth.py all --script <대본 이름>      # 전부
  보통은 에디터 서버가 저장할 때 바뀐 줄만 부르고, 손으로는 스킬 scripts/se.py synth 를 쓴다.

- 설정: 레포 script-editor.json (se_config). 콘텐츠 폴더·대본 접두어·캐시 폴더를 거기서 읽는다.
- 대본: 콘텐츠 폴더의 <대본 이름>.json (ref_audio·ref_text·lines[start·max·say/speak]). 읽는 말(speak)이 없으면 say.
- 참조 음성(ref_audio)을 복제하고, 합성 뒤 재전사 유사도가 0.85 미만이면 최대 3번 다시 만든다.
  max 를 넘으면 속도를 올려(최대 1.25) 다시 만든다.
- 읽는 말에 [쉼 0.5] 가 있으면 그 앞뒤를 따로 합성하고 사이에 그 길이의 무음을 넣는다. [쉼 0] 은 붙여 읽기.
- 줄마다 따로 듣기 위한 파일이라 -16 LUFS 로 맞춘다(영상 믹싱 때 mix.py 가 다시 맞춘다).
- 합성 wav 는 설정 synth.cache 에 캐시한다(문장·속도·참조 음성이 같으면 재사용).
"""
import argparse, difflib, hashlib, json, os, re, subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from se_config import Config  # noqa: E402

SR = 24000
# 읽는 말 안의 정확한 쉼: [쉼 0.5] (초). 그 자리에서 합성을 끊고 무음을 넣는다.
PAUSE_RE = re.compile(r"\[쉼\s*(\d+(?:\.\d+)?)\]")
JOIN_RE = re.compile(r"\s*\[쉼\s*0+(?:\.0+)?\]\s*")  # [쉼 0]: 붙여 읽기


def norm(s):
    return re.sub(r"[^0-9가-힣a-zA-Z]", "", s)


def pick_device():
    import torch
    if os.environ.get("SCRIPT_EDITOR_TTS_DEVICE"):
        return os.environ["SCRIPT_EDITOR_TTS_DEVICE"]
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lines", nargs="+", help="줄 번호 또는 all")
    ap.add_argument("--fresh", action="store_true", help="캐시를 쓰지 않고 새로 뽑는다(같은 문장 다시 뽑기)")
    ap.add_argument("--script", required=True, help="대본 이름(확장자 없이)·라벨·주소 번호. 입력 <이름>.json, 출력 audio/<라벨>/")
    ap.add_argument("--config", help="script-editor.json 경로(기본: SCRIPT_EDITOR_CONFIG 또는 위로 찾기)")
    a = ap.parse_args()

    cfg = Config(a.config)
    CACHE = cfg.synth_cache
    label = cfg.resolve_label(a.script)
    doc = json.loads(cfg.script_json(label).read_text())
    OUT = cfg.content / "audio" / label
    ref = str(Path(doc["ref_audio"]).expanduser())
    total = len(doc["lines"])
    nums = list(range(1, total + 1)) if a.lines == ["all"] else sorted({int(x) for x in a.lines})
    bad = [n for n in nums if not 1 <= n <= total]
    if bad:
        sys.exit(f"없는 줄 번호: {bad} (1~{total})")
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    model = prompt = None

    def load():
        nonlocal model, prompt
        if model is None:
            import torch
            from omnivoice import OmniVoice
            device = pick_device()
            print(f"[엔진] OmniVoice ({device})", flush=True)
            dtype = torch.float16 if device.startswith("cuda") else torch.float32
            model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device, dtype=dtype)
            prompt = model.create_voice_clone_prompt(ref_audio=ref, ref_text=doc.get("ref_text"))
            model.load_asr_model()  # ref_text 를 주면 내장 whisper 가 자동으로 올라오지 않는다

    def synth(text, speed):
        load()
        best, best_sim = None, -1.0
        kw = {"speed": speed} if speed != 1.0 else {}
        for _ in range(3):
            wav = np.asarray(model.generate(text=text, language="ko", voice_clone_prompt=prompt, **kw)[0], dtype=np.float32)
            sim = difflib.SequenceMatcher(None, norm(text), norm(model.transcribe((wav, SR)))).ratio()
            if sim > best_sim:
                best, best_sim = wav, sim
            if sim >= 0.85:
                break
        return best, best_sim

    def synth_line(text, speed):
        """[쉼 초] 가 없으면 그대로, 있으면 조각별로 합성해 무음과 이어 붙인다(유사도는 조각 중 최저).
        [쉼 0] 은 끊지 말고 붙여 읽으라는 표시라 표기와 앞뒤 공백만 지운다."""
        text = JOIN_RE.sub("", text)
        if not PAUSE_RE.search(text):
            return synth(text, speed)
        pieces, sims, pos = [], [], 0
        for m in PAUSE_RE.finditer(text):
            chunk = text[pos:m.start()].strip()
            if chunk:
                wav, sim = synth(chunk, speed)
                pieces.append(wav)
                sims.append(sim)
            pieces.append(np.zeros(int(float(m.group(1)) * SR), dtype=np.float32))
            pos = m.end()
        tail = text[pos:].strip()
        if tail:
            wav, sim = synth(tail, speed)
            pieces.append(wav)
            sims.append(sim)
        return np.concatenate(pieces), (min(sims) if sims else 1.0)

    for n in nums:
        line = doc["lines"][n - 1]
        text = line.get("speak") or line["say"]
        speed = 1.0
        while True:
            key = hashlib.sha1(f"{text}|{speed}|{ref}".encode()).hexdigest()[:16]
            wav_path = CACHE / f"line-{n:02d}-{key}.wav"  # 문장이 같으면 대본이 달라도 재사용
            meta_path = wav_path.with_suffix(".json")
            if a.fresh or not wav_path.exists():
                wav, sim = synth_line(text, speed)
                sf.write(wav_path, wav, SR)
                meta_path.write_text(json.dumps({"sim": sim, "speed": speed, "text": text}, ensure_ascii=False))
            dur = sf.info(wav_path).duration
            sim = json.loads(meta_path.read_text())["sim"]
            if dur <= line["max"] or speed >= 1.25:
                break
            speed = round(min(1.25, speed * dur / line["max"] * 1.03), 2)

        m4a = OUT / f"{n:02d}.m4a"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(wav_path),
                        "-af", "loudnorm=I=-16:TP=-1.5:LRA=9", "-ar", "48000", "-ac", "1",
                        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(m4a)], check=True)
        out_dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                 "-of", "csv=p=0", str(m4a)]).decode().strip())
        (OUT / f"{n:02d}.json").write_text(json.dumps({
            "n": n, "id": line["id"], "start": line["start"], "max": line["max"],
            "say": line["say"], "speak": text, "speed": speed, "sim": round(sim, 2),
            "dur": round(out_dur, 2), "engine": "OmniVoice (k2-fsa)", "ref": Path(ref).name,
        }, ensure_ascii=False, indent=2) + "\n")
        flag = "" if out_dur <= line["max"] + 0.2 else "  ← 길이 초과"
        print(f"{n:02d} {line['id']:18} {out_dur:5.1f}s / {line['max']:4.1f}s  속도 {speed}  유사도 {sim:.2f}{flag}", flush=True)


if __name__ == "__main__":
    main()
