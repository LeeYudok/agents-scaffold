// 대본 음성 재생 페이지(사운드클라우드 식). /api/script, /api/audio, /audio/NN.m4a 를 쓴다.

type Row = { n: string; time: string; scene: string; say: string; speak: string; same: boolean };
type Meta = { n: number; dur?: number; sim?: number; speed?: number; engine?: string; ref?: string };
type Track = {
  i: number; // 줄 번호(1부터)
  row: Row;
  meta?: Meta;
  card: HTMLElement;
  wave: HTMLElement;
  canvas: HTMLCanvasElement;
  cur: HTMLElement;
  tot: HTMLElement;
  peaks?: number[];
  pos: number; // 0~1, 마지막 재생 위치
};

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const pad = (n: number) => String(n).padStart(2, "0");
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const cssVar = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Record<string, unknown> = {},
  ...kids: (Node | string)[]
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = String(v);
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v as EventListener);
    else e.setAttribute(k, v === true ? "" : String(v));
  }
  e.append(...kids);
  return e;
}

const audio = new Audio();
audio.preload = "metadata";
let tracks: Track[] = [];
let current: Track | null = null;

// ---- 파형 ---------------------------------------------------------------

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

function draw(t: Track) {
  const dpr = window.devicePixelRatio || 1;
  const w = t.wave.clientWidth;
  const h = t.wave.clientHeight;
  if (!w || !h) return;
  if (t.canvas.width !== Math.round(w * dpr) || t.canvas.height !== Math.round(h * dpr)) {
    t.canvas.width = Math.round(w * dpr);
    t.canvas.height = Math.round(h * dpr);
  }
  const g = t.canvas.getContext("2d")!;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  const bar = 3;
  const gap = 2;
  const n = Math.floor(w / (bar + gap));
  const mid = h * 0.68; // 위쪽이 본체, 아래쪽은 옅은 반사
  const played = t.pos * n;
  const on = cssVar("--accent");
  const off = cssVar("--muted");
  for (let k = 0; k < n; k++) {
    const p = t.peaks ? t.peaks[Math.min(t.peaks.length - 1, Math.floor((k / n) * t.peaks.length))] : 0.1;
    const up = Math.max(3, p * mid * 0.95);
    const down = Math.max(2, p * (h - mid) * 0.9);
    g.fillStyle = k < played ? on : off;
    g.globalAlpha = k < played ? 1 : 0.55;
    g.fillRect(k * (bar + gap), mid - up, bar, up);
    g.globalAlpha = k < played ? 0.4 : 0.22;
    g.fillRect(k * (bar + gap), mid + 1, bar, down);
  }
  g.globalAlpha = 1;
}

let raf = 0;
const redraw = (t: Track) => {
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(() => draw(t));
};

// ---- 재생 ---------------------------------------------------------------

// 어떤 대본의 음성인지: /player?file=<대본.md> (없으면 목록 첫 대본). 라벨은 서버(/api/audio)가 정한다.
let FILE = new URLSearchParams(location.search).get("file") ?? "";
let LABEL = "";
const src = (t: Track) => `audio/${encodeURIComponent(LABEL)}/${pad(t.i)}.m4a`;

function mark() {
  for (const t of tracks) t.card.classList.toggle("playing", t === current && !audio.paused);
}

function switchTo(t: Track) {
  if (current && current !== t) {
    current.pos = audio.duration ? audio.currentTime / audio.duration : current.pos;
    draw(current);
  }
  current = t;
  audio.src = src(t);
}

function toggle(t: Track | undefined) {
  if (!t?.meta) return;
  if (current === t) {
    if (audio.paused) audio.play().catch(() => {});
    else audio.pause();
    return;
  }
  switchTo(t);
  audio.play().catch(() => {});
}

function seekTo(t: Track, ratio: number) {
  if (!t.meta) return;
  if (current !== t) switchTo(t);
  const go = () => {
    audio.currentTime = Math.min(1, Math.max(0, ratio)) * (audio.duration || t.meta?.dur || 0);
    audio.play().catch(() => {});
  };
  if (audio.readyState >= 1) go();
  else audio.addEventListener("loadedmetadata", go, { once: true });
}

audio.addEventListener("play", mark);
audio.addEventListener("pause", mark);
audio.addEventListener("timeupdate", () => {
  const t = current;
  if (!t || !audio.duration) return;
  t.pos = audio.currentTime / audio.duration;
  t.cur.textContent = fmt(audio.currentTime);
  t.tot.textContent = fmt(audio.duration);
  redraw(t);
});
audio.addEventListener("ended", () => {
  const t = current;
  if (!t) return;
  const next = tracks.find((x) => x.i > t.i && x.meta);
  t.pos = 0;
  t.cur.textContent = "0:00";
  draw(t);
  mark();
  if (next) {
    switchTo(next);
    audio.play().catch(() => {});
  }
});

// ---- 화면 ---------------------------------------------------------------

function buildTrack(row: Row, i: number, meta?: Meta): Track {
  const canvas = el("canvas");
  const wave = el("div", { class: "wave", role: "slider", "aria-label": `${pad(i)}번 재생 위치` }, canvas);
  const cur = el("span", {}, "0:00");
  const tot = el("span", {}, meta?.dur ? fmt(meta.dur) : "-:--");
  const btn = el("button", { type: "button", class: "play", "aria-label": `${pad(i)}번 재생·일시정지`, disabled: !meta });
  btn.innerHTML =
    '<svg viewBox="0 0 24 24" class="i-play" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>' +
    '<svg viewBox="0 0 24 24" class="i-pause" aria-hidden="true"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';

  const pill = meta
    ? `${meta.engine?.split(" ")[0] ?? "합성"}${meta.sim != null ? ` · 유사도 ${meta.sim.toFixed(2)}` : ""}${meta.speed ? ` · ${meta.speed}배속` : ""}`
    : "음성 대기";
  const card = el(
    "li",
    { class: `track${meta ? "" : " pending"}`, id: `t${i}` },
    btn,
    el("div", { class: "head" }, el("span", { class: "num" }, pad(i)), el("span", { class: "scene" }, row.scene), el("span", { class: "pill" }, pill)),
    el("p", { class: "say" }, row.say),
    ...(row.same ? [] : [el("p", { class: "speak" }, `읽는 말: ${row.speak}`)]),
    wave,
    el("div", { class: "times" }, cur, tot),
  );
  const t: Track = { i, row, meta, card, wave, canvas, cur, tot, pos: 0 };
  btn.addEventListener("click", () => toggle(t));
  wave.addEventListener("click", (ev) => {
    const r = wave.getBoundingClientRect();
    seekTo(t, (ev.clientX - r.left) / r.width);
  });
  return t;
}

function focusHash() {
  const i = Number(location.hash.replace("#", ""));
  const t = tracks.find((x) => x.i === i);
  if (!t) return;
  t.card.scrollIntoView({ block: "center", behavior: "smooth" });
  t.card.classList.add("target");
  setTimeout(() => t.card.classList.remove("target"), 2500);
}

async function main() {
  const files = ((await (await fetch("api/files")).json()) as { files: string[] }).files;
  FILE = FILE || files[0] || "";
  const name = files.find((f) => f === FILE);
  if (!name) {
    $("tracks").replaceChildren(el("li", { class: "muted" }, "대본 파일이 없어요"));
    return;
  }
  const [script, list] = await Promise.all([
    fetch(`api/script?file=${encodeURIComponent(name)}`).then((r) => r.json()) as Promise<{ doc: { rows: Row[] } }>,
    fetch(`api/audio?file=${encodeURIComponent(FILE)}`).then((r) => r.json()) as Promise<{ label: string; tracks: Meta[] }>,
  ]);
  LABEL = list.label;
  const have = new Map(list.tracks.map((m) => [m.n, m]));
  tracks = script.doc.rows.map((row, k) => buildTrack(row, k + 1, have.get(k + 1)));
  $("tracks").replaceChildren(...tracks.map((t) => t.card));

  const first = list.tracks[0];
  $("sub").textContent = `${LABEL} 대본 · ${first?.engine ?? "OmniVoice"} 음성 복제${first?.ref ? ` (참조: ${first.ref})` : ""}`;
  $("count").textContent = `음성 ${list.tracks.length} / ${tracks.length}줄`;

  new ResizeObserver(() => tracks.forEach(draw)).observe($("tracks"));
  tracks.forEach(draw);
  await Promise.all(
    tracks
      .filter((t) => t.meta)
      .map(async (t) => {
        try {
          t.peaks = await peaksOf(src(t));
          draw(t);
        } catch (err) {
          console.warn(`${pad(t.i)}번 파형을 만들지 못했어요`, err);
        }
      }),
  );

  window.addEventListener("hashchange", focusHash);
  window.addEventListener("keydown", (ev) => {
    if ((ev.target as HTMLElement).closest("input, textarea, select, button")) return;
    if (ev.code === "Space") {
      ev.preventDefault();
      toggle(current ?? tracks.find((t) => t.meta));
    } else if ((ev.code === "ArrowRight" || ev.code === "ArrowLeft") && current) {
      audio.currentTime = Math.max(0, audio.currentTime + (ev.code === "ArrowRight" ? 5 : -5));
    }
  });
  focusHash();
}

main().catch((err) => $("tracks").replaceChildren(el("li", { class: "muted" }, String(err))));
