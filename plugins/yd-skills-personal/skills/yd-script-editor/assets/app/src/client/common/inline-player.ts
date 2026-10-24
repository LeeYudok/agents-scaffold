// 줄 아래에 펼쳐지는 사운드클라우드 식 플레이어(재생 버튼 + 파형 + 시간). 페이지 전체에서 오디오는 하나만 재생한다.

const pad = (n: number) => String(n).padStart(2, "0");
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const cssVar = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export const PLAY_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';
export const PAUSE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';
// 스피커 아이콘(Phosphor speaker-high 단순화)
export const SPEAKER_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

const audio = new Audio();
audio.preload = "auto";
let active: InlinePlayer | null = null;

async function peaksOf(url: string, bins = 200): Promise<number[]> {
  const buf = await (await fetch(url)).arrayBuffer();
  const ctx = new AudioContext();
  try {
    const ch = (await ctx.decodeAudioData(buf)).getChannelData(0);
    const step = Math.max(1, Math.floor(ch.length / bins));
    const out: number[] = [];
    for (let b = 0; b < bins; b++) {
      let m = 0;
      for (let k = b * step; k < Math.min(ch.length, (b + 1) * step); k++) m = Math.max(m, Math.abs(ch[k]));
      out.push(m);
    }
    const top = Math.max(...out) || 1;
    return out.map((v) => v / top);
  } finally {
    ctx.close();
  }
}

export class InlinePlayer {
  readonly el: HTMLDivElement;
  private btn: HTMLButtonElement;
  private wave: HTMLDivElement;
  private canvas: HTMLCanvasElement;
  private time: HTMLSpanElement;
  private peaks: number[] | null = null;
  private pos = 0;
  private ro: ResizeObserver;
  private pending: string | null = null;
  /** 끝까지 재생했을 때(전체 재생에서 다음 줄로 넘어갈 때 쓴다) */
  onEnded?: () => void;

  constructor(readonly n: number, public url = `audio/${pad(n)}.m4a`) {
    this.el = document.createElement("div");
    this.el.className = "ip";
    this.btn = document.createElement("button");
    this.btn.type = "button";
    this.btn.className = "ip-play";
    this.btn.setAttribute("aria-label", `${n}번 재생·일시정지`);
    this.btn.innerHTML = PLAY_ICON;
    this.wave = document.createElement("div");
    this.wave.className = "ip-wave";
    this.canvas = document.createElement("canvas");
    this.wave.append(this.canvas);
    this.time = document.createElement("span");
    this.time.className = "ip-time";
    this.time.textContent = "0:00 / -:--";
    this.el.append(this.btn, this.wave, this.time);

    this.btn.addEventListener("click", () => this.toggle());
    this.wave.addEventListener("click", (ev) => {
      const r = this.wave.getBoundingClientRect();
      this.seek((ev.clientX - r.left) / r.width);
    });
    this.ro = new ResizeObserver(() => this.draw());
    this.ro.observe(this.wave);
    this.loadPeaks();
  }

  private loadPeaks() {
    const url = this.url;
    peaksOf(url)
      .then((p) => { if (url === this.url) { this.peaks = p; this.draw(); } })
      .catch((err) => console.warn(`${this.n}번 파형을 만들지 못했어요`, err));
  }

  /** 새로 합성된 음성으로 바꾼다. 재생 중이면 끊지 않고 끝난 뒤에 바꾼다. */
  setUrl(url: string) {
    if (url === this.url) return;
    if (active === this && !audio.paused) { this.pending = url; return; }
    this.applyUrl(url);
  }

  applyPending() {
    if (this.pending) this.applyUrl(this.pending);
  }

  private applyUrl(url: string) {
    this.url = url;
    this.pending = null;
    if (active === this) audio.src = url;
    this.peaks = null;
    this.pos = 0;
    this.time.textContent = "0:00 / -:--";
    this.draw();
    this.loadPeaks();
  }

  private take() {
    if (active === this) return;
    active?.reset();
    active = this;
    audio.src = this.url;
  }

  toggle() {
    if (active !== this) { this.take(); audio.play().catch(() => {}); return; }
    if (audio.paused) audio.play().catch(() => {});
    else audio.pause();
  }

  playFromStart() {
    this.take();
    const go = () => { audio.currentTime = 0; audio.play().catch(() => {}); };
    if (audio.readyState >= 1) go();
    else audio.addEventListener("loadedmetadata", go, { once: true });
  }

  seek(ratio: number) {
    this.take();
    const go = () => {
      audio.currentTime = Math.min(1, Math.max(0, ratio)) * audio.duration;
      audio.play().catch(() => {});
    };
    if (audio.readyState >= 1) go();
    else audio.addEventListener("loadedmetadata", go, { once: true });
  }

  /** 다른 플레이어가 재생을 가져가거나 닫힐 때 */
  reset() {
    this.btn.innerHTML = PLAY_ICON;
    this.el.classList.remove("on");
  }

  dispose() {
    if (active === this) { audio.pause(); active = null; }
    this.ro.disconnect();
    this.el.remove();
  }

  sync() {
    const playing = !audio.paused;
    this.btn.innerHTML = playing ? PAUSE_ICON : PLAY_ICON;
    this.el.classList.toggle("on", playing);
    if (audio.duration) {
      this.pos = audio.currentTime / audio.duration;
      this.time.textContent = `${fmt(audio.currentTime)} / ${fmt(audio.duration)}`;
    }
    this.draw();
  }

  draw() {
    const dpr = window.devicePixelRatio || 1;
    const w = this.wave.clientWidth;
    const h = this.wave.clientHeight;
    if (!w || !h) return;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    const g = this.canvas.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const bar = 3, gap = 2, n = Math.floor(w / (bar + gap)), mid = h * 0.68, played = this.pos * n;
    const on = cssVar("--accent"), off = cssVar("--muted");
    for (let k = 0; k < n; k++) {
      const p = this.peaks ? this.peaks[Math.min(this.peaks.length - 1, Math.floor((k / n) * this.peaks.length))] : 0.1;
      const done = k < played;
      g.fillStyle = done ? on : off;
      g.globalAlpha = done ? 1 : 0.55;
      g.fillRect(k * (bar + gap), mid - Math.max(3, p * mid * 0.95), bar, Math.max(3, p * mid * 0.95));
      g.globalAlpha = done ? 0.4 : 0.22;
      g.fillRect(k * (bar + gap), mid + 1, bar, Math.max(2, p * (h - mid) * 0.9));
    }
    g.globalAlpha = 1;
  }
}

for (const ev of ["play", "pause", "timeupdate", "ended"]) audio.addEventListener(ev, () => active?.sync());
audio.addEventListener("ended", () => {
  if (!active) return;
  audio.currentTime = 0;
  const p = active;
  p.sync();
  p.applyPending();
  p.onEnded?.();
});
