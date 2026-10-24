// 시연 영상 비교 화면. /api/videos 의 영상을 나란히 놓고 재생·정지·이동을 함께 건다.
// 장면 버튼은 고른 대본(/api/script)의 줄 시각에서 만든다.

export {}; // 모듈로 둔다(다른 화면 스크립트와 전역 이름이 겹치지 않게)

type Video = { key: string; size: number; mtime: number; desc: string; check: boolean };
type Row = { n: string; time: string; scene: string };

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

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

const getJson = async <T>(url: string): Promise<T> => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json() as Promise<T>;
};

const sec = (t: string) => {
  const [m, s] = t.split(":");
  return Number(m) * 60 + Number(s);
};
const day = (ms: number) => new Date(ms).toLocaleString("sv-SE", { timeZone: "Asia/Seoul" }).slice(5, 16);
const mb = (n: number) => `${(n / 1024 / 1024).toFixed(0)}MB`;
const isTake = (key: string) => /-r\d+$/.test(key); // 같은 판의 중간 시안(-r1, -r2 …)

let all: Video[] = [];
let picked: string[] = [];
let sound = 0;
let players: HTMLVideoElement[] = [];

const live = () => players.filter((v) => !v.closest(".miss"));

function saveUrl() {
  const q = new URLSearchParams(location.search);
  q.set("v", picked.join(","));
  const s = $<HTMLSelectElement>("script").value;
  if (s) q.set("s", s);
  history.replaceState(null, "", `?${q}`);
}

function applyMute() {
  players.forEach((v, i) => (v.muted = i !== sound));
  $("sounds").querySelectorAll("button").forEach((b, i) => b.classList.toggle("on", i === sound));
}

function renderPicks() {
  const box = $("picks");
  box.replaceChildren(
    ...all.map((v) => {
      const on = picked.includes(v.key);
      const input = el("input", { type: "checkbox", checked: on, onchange: () => toggle(v.key) });
      return el("label", { class: on ? "pick on" : "pick", title: `${v.desc || v.key} · ${day(v.mtime)} · ${mb(v.size)}` }, input, v.key, el("small", {}, day(v.mtime)));
    }),
  );
}

function toggle(key: string) {
  picked = picked.includes(key) ? picked.filter((k) => k !== key) : [...picked, key];
  if (sound >= picked.length) sound = 0;
  renderPicks();
  renderGrid();
  saveUrl();
}

function renderGrid() {
  const grid = $("grid");
  players.forEach((v) => v.pause());
  const vids = picked.map((k) => all.find((v) => v.key === k)).filter((v): v is Video => !!v);
  if (!vids.length) {
    players = [];
    grid.replaceChildren(el("p", { class: "empty" }, "비교할 영상을 위에서 골라 주세요."));
    $("sounds").replaceChildren();
    return;
  }
  players = [];
  grid.replaceChildren(
    ...vids.map((v) => {
      const video = el("video", { preload: "auto", src: `videos/${encodeURIComponent(v.key)}.mp4?m=${Math.round(v.mtime)}` });
      players.push(video);
      const card = el(
        "article",
        { class: "card" },
        el("header", {}, el("b", {}, v.key), el("span", {}, v.desc)),
        video,
        el(
          "div",
          { class: "meta" },
          v.check ? el("a", { href: `videos/${encodeURIComponent(v.key)}/check.png`, target: "_blank", rel: "noopener" }, "점검 이미지") : el("span", {}, ""),
          el("span", {}, `${day(v.mtime)} · ${mb(v.size)}`),
        ),
      );
      video.addEventListener("error", () => card.classList.add("miss"));
      // 맨 앞 영상을 옮기면 나머지를 따라 맞춘다(0.3초 넘게 어긋날 때만)
      video.addEventListener("seeked", () => {
        const l = live();
        if (video !== l[0]) return;
        l.slice(1).forEach((o) => {
          if (Math.abs(o.currentTime - video.currentTime) > 0.3) o.currentTime = video.currentTime;
        });
      });
      return card;
    }),
  );
  $("sounds").replaceChildren(
    ...vids.map((v, i) =>
      el("button", { type: "button", onclick: () => ((sound = i), applyMute()) }, `소리: ${v.key}`),
    ),
  );
  applyMute();
}

function togglePlay() {
  const l = live();
  if (!l.length) return;
  const t = l[0].currentTime;
  if (l.some((v) => v.paused)) {
    l.forEach((v) => {
      v.currentTime = t;
      void v.play();
    });
  } else l.forEach((v) => v.pause());
}

async function loadScenes(file: string) {
  const box = $("scenes");
  box.replaceChildren();
  if (!file) return;
  const r = await getJson<{ doc: { rows: Row[] } }>(`api/script?file=${encodeURIComponent(file)}`).catch(() => null);
  if (!r) return;
  box.append(
    ...r.doc.rows.map((row) =>
      el(
        "button",
        {
          type: "button",
          title: `${row.time} ${row.scene}`,
          onclick: () =>
            live().forEach((v) => {
              v.currentTime = sec(row.time);
              void v.play();
            }),
        },
        row.n,
        el("small", {}, row.scene.length > 14 ? `${row.scene.slice(0, 14)}…` : row.scene),
      ),
    ),
  );
}

async function main() {
  const q = new URLSearchParams(location.search);
  const [{ dir, videos }, { files }] = await Promise.all([
    getJson<{ dir: string; videos: Video[] }>("api/videos"),
    getJson<{ files: string[] }>("api/files"),
  ]);
  all = videos;
  $("dir").textContent = `${dir} · ${videos.length}개`;

  const fromUrl = (q.get("v") ?? "").split(",").filter((k) => videos.some((v) => v.key === k));
  picked = fromUrl.length ? fromUrl : videos.filter((v) => !isTake(v.key)).slice(0, 3).map((v) => v.key);

  // 장면 대본: 주소의 s → 첫 영상의 판(v11 …)이 이름에 든 대본 → 마지막 대본
  const ver = picked[0]?.split("-")[0] ?? "";
  const pick = q.get("s") && files.includes(q.get("s")!) ? q.get("s")! : (files.find((f) => ver && f.includes(`-${ver}.`)) ?? files.at(-1) ?? "");
  const sel = $<HTMLSelectElement>("script");
  sel.replaceChildren(...files.map((f) => el("option", { value: f, selected: f === pick }, f.replace(/\.md$/, ""))));
  sel.addEventListener("change", () => {
    void loadScenes(sel.value);
    saveUrl();
  });

  renderPicks();
  renderGrid();
  await loadScenes(pick);
  saveUrl();

  $("play").addEventListener("click", togglePlay);
  document.addEventListener("keydown", (e) => {
    if (e.code !== "Space" || (e.target as HTMLElement).closest("input, select, textarea, button")) return;
    e.preventDefault();
    togglePlay();
  });
}

main().catch((err) => {
  $("grid").replaceChildren(el("p", { class: "empty" }, `불러오지 못했어요: ${String(err)}`));
});
