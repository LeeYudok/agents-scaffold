// 대본 수정 에디터 화면. 서버(server.ts)의 /api/files, /api/script 와 통신한다.
// 단일 보기(파일 하나)와 비교 보기(두 파일을 같은 번호끼리 나란히, Beyond Compare 식)를 가진다.
import { diffChars, type Seg } from "../../shared/diff.ts";
import { InlinePlayer, SPEAKER_ICON } from "../common/inline-player.ts";
import { fitTimes, fmtTime, targetOf } from "../common/timing.ts";
import { patchSpeak, pronounce, setWords } from "../../shared/pronounce.ts";
import DOMPurify from "dompurify";
import { marked } from "marked";

type Row = { n: string; time: string; scene: string; screen: string; say: string; speak: string; same: boolean; prompt: string };
type Doc = { before: string; head: string; sep: string; rows: Row[]; after: string; hasScreen: boolean; hasPrompt: boolean };
type Entry = { orig: Doc; cur: Doc; etag: string };
type Reply = { doc?: Doc; etag?: string; files?: string[]; ids?: Record<string, number>; prefix?: string; words?: [string, string][]; error?: string; synth?: number[] };
type Mode = "compare" | "single";

// 기준 음성(ref-bright-8s) 실측 읽기 속도. scripts/manual/20261004_i128_report_video/README.md
const RATE = 5.86;
const TIME_RE = /^\d+:\d{2}(\.\d)?$/;

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const state = {
  files: [] as string[],
  ids: {} as Record<string, number>, // 대본 파일 → 주소 번호(/editor/<번호>)
  mode: "single" as Mode,
  active: "",
  left: "",
  right: "",
  onlyDiff: false,
  entries: new Map<string, Entry>(),
  length: 292.1,
};

const store = {
  get(k: string) {
    try { return localStorage.getItem(k); } catch { return null; }
  },
  set(k: string, v: string) {
    try { localStorage.setItem(k, v); } catch { /* 저장 못 해도 동작에는 영향 없다 */ }
  },
};

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

async function api(path: string, init: RequestInit = {}): Promise<{ status: number; data: Reply }> {
  const res = await fetch(path, { ...init, headers: { "content-type": "application/json", "x-editor": "1" } });
  return { status: res.status, data: (await res.json().catch(() => ({}))) as Reply };
}

const secs = (t: string) => {
  const m = /^(\d+):(\d{2})(?:\.(\d))?$/.exec(t);
  return m ? Number(m[1]) * 60 + Number(m[2]) + Number(m[3] ?? 0) / 10 : null;
};
// 읽는 말 안의 정확한 쉼 표기: [쉼 0.5] (초). 자막에는 나오지 않고, 합성 때 그 자리에 무음을 넣는다.
const PAUSE_RE = /\[쉼\s*(\d+(?:\.\d+)?)\]/g;
const PAUSE_SPLIT = /(\[쉼\s*\d+(?:\.\d+)?\])/;
const pauseSecs = (s: string) => [...s.matchAll(PAUSE_RE)].reduce((sum, m) => sum + Number(m[1]), 0);
const syllables = (s: string) => (s.replace(PAUSE_RE, "").match(/[가-힣A-Za-z0-9]/g) ?? []).length;
let PREFIX = ""; // 대본 파일 접두어(서버 설정 prefix, /api/files 가 준다)
const label = (f: string) => {
  const s = f.replace(/\.md$/, "");
  return PREFIX && s.startsWith(PREFIX) ? s.slice(PREFIX.length) : s;
};
const eff = (r: Row) => (r.same ? r.say : r.speak); // 실제로 읽는 문장

// 대본별 줄 음성(서버 /api/audio?file=). 음성이 있는 줄은 칸 머리에 듣기 버튼을 단다.
const labelOf = label;
const audioVer = new Map<string, Map<number, number>>(); // 대본 파일 → (줄 번호 → 파일 버전)
async function loadAudio(files: string[]) {
  await Promise.all(
    files.map(async (f) => {
      try {
        const d = (await (await fetch(`api/audio?file=${encodeURIComponent(f)}`)).json()) as { tracks?: { n: number; v?: number }[] };
        audioVer.set(f, new Map((d.tracks ?? []).map((x) => [x.n, x.v ?? 0])));
      } catch { /* 음성 목록을 못 받아도 편집에는 영향 없다 */ }
    }),
  );
}

// ---- 저장 뒤 자동 음성 합성 상태 ------------------------------------------
type Job = { label: string; n: number };
type SynthStatus = { running: Job[]; queued: Job[]; last: string; error: string };
let synthTimer: ReturnType<typeof setInterval> | undefined;
// 합성 중인 줄은 듣기 아이콘 자리에 경과 시간을 띄우고, 끝나면 아이콘으로 되돌린다
const synthStart = new Map<string, number>(); // "라벨:줄" → 시작 시각
let synthTick: ReturnType<typeof setInterval> | undefined;
function paintSynthButtons() {
  document.querySelectorAll<HTMLElement>(".listen").forEach((b) => {
    const t0 = synthStart.get(`${b.dataset.label}:${b.dataset.n}`);
    if (t0 !== undefined) {
      b.classList.add("synthing");
      b.textContent = `${Math.floor((Date.now() - t0) / 1000)}s`;
    } else if (b.classList.contains("synthing")) {
      b.classList.remove("synthing");
      b.innerHTML = SPEAKER_ICON;
    }
  });
}
function markSynth(busy: Job[]) {
  const keys = new Set(busy.map((j) => `${j.label}:${j.n}`));
  keys.forEach((k) => synthStart.has(k) || synthStart.set(k, Date.now()));
  [...synthStart.keys()].forEach((k) => keys.has(k) || synthStart.delete(k));
  paintSynthButtons();
  if (keys.size && !synthTick) synthTick = setInterval(paintSynthButtons, 1000);
  if (!keys.size && synthTick) { clearInterval(synthTick); synthTick = undefined; }
  const s = $("synth");
  s.hidden = !busy.length;
  s.textContent = busy.length ? `음성 합성 중: ${busy.map((j) => `${j.label} ${j.n}`).join(", ")}번` : "";
}
function watchSynth() {
  if (synthTimer) return;
  synthTimer = setInterval(async () => {
    const st = (await (await fetch("api/synth")).json()) as SynthStatus;
    const busy = [...st.running, ...st.queued];
    markSynth(busy);
    if (busy.length) return;
    clearInterval(synthTimer);
    synthTimer = undefined;
    await loadAudio(shown());
    refreshAudioUi(); // 화면을 다시 그리지 않는다 — 재생 중인 플레이어를 끊지 않기 위해
    if (st.error) flash(`음성 합성 실패: ${st.error.split("\n").pop()}`, "err");
    else flash(`음성 갱신: ${st.last.split("\n").map((l) => Number(l.slice(0, 2))).filter(Boolean).join("·")}번`, "ok");
  }, 1500);
}
const numCell = (n: string) => el("td", { class: "n" }, n);

// 듣기 버튼: 누르면 그 칸 맨 아래에 플레이어가 펼쳐지고 바로 재생한다(다시 누르면 접는다)
const players = new Map<InlinePlayer, { file: string; n: number }>();
const audioUrl = (file: string, n: number) =>
  `audio/${encodeURIComponent(labelOf(file))}/${String(n).padStart(2, "0")}.m4a?v=${audioVer.get(file)?.get(n) ?? 0}`;
function refreshAudioUi() {
  document.querySelectorAll<HTMLElement>(".listen").forEach((b) => {
    b.hidden = !audioVer.get(b.dataset.file ?? "")?.has(Number(b.dataset.n));
  });
  players.forEach(({ file, n }, p) => p.setUrl(audioUrl(file, n)));
}
// 줄마다 플레이어를 여는 손잡이(전체 재생이 쓴다): "파일:줄" → 열고 플레이어를 돌려준다
const listenHandles = new Map<string, { box: HTMLElement; open: () => InlinePlayer }>();
function listenButton(c: Ctl, box: HTMLElement): HTMLElement {
  const n = c.i + 1;
  const label = labelOf(c.file);
  const b = el("button", { type: "button", class: "listen", title: `${n}번 음성 듣기`, "aria-label": `${label} ${n}번 음성 듣기`, "aria-expanded": "false", "data-label": label, "data-file": c.file, "data-n": n });
  b.hidden = !audioVer.get(c.file)?.has(n);
  b.innerHTML = SPEAKER_ICON;
  let p: InlinePlayer | null = null;
  listenHandles.set(`${c.file}:${n}`, {
    box,
    open: () => {
      if (!p) {
        p = new InlinePlayer(n, audioUrl(c.file, n));
        players.set(p, { file: c.file, n });
        box.append(p.el);
        b.setAttribute("aria-expanded", "true");
      }
      return p;
    },
  });
  b.addEventListener("click", () => {
    if (p) {
      p.dispose();
      players.delete(p);
      p = null;
      b.setAttribute("aria-expanded", "false");
      return;
    }
    p = new InlinePlayer(n, audioUrl(c.file, n));
    players.set(p, { file: c.file, n });
    box.append(p.el);
    b.setAttribute("aria-expanded", "true");
    p.toggle();
  });
  return b;
}
// ---- 비교 보기 전체 재생: 1번 줄부터 차례로, 끝나면 다음 줄 ----------------
let auto: { items: { file: string; n: number }[]; i: number } | null = null;
const AUTO_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';
const STOP_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6h12v12H6z"/></svg>';
function paintAutoButton() {
  const b = $("autoplay");
  b.innerHTML = auto ? `${STOP_ICON}<span>정지 ${auto.i + 1}/${auto.items.length}</span>` : `${AUTO_ICON}<span>전체 재생</span>`;
  b.classList.toggle("on", !!auto);
}
function stopAuto() {
  if (!auto) return;
  auto = null;
  players.forEach((_, p) => { p.onEnded = undefined; });
  paintAutoButton();
}
function startAuto() {
  const mode = $<HTMLSelectElement>("automode").value;
  const total = Math.max(entry(state.left)?.cur.rows.length ?? 0, entry(state.right)?.cur.rows.length ?? 0);
  const items: { file: string; n: number }[] = [];
  for (let n = 1; n <= total; n++) {
    const sides = mode === "left" ? [state.left] : mode === "alt" ? [state.left, state.right] : [state.right];
    for (const file of sides) if (audioVer.get(file)?.has(n) && listenHandles.has(`${file}:${n}`)) items.push({ file, n });
  }
  if (!items.length) return flash("재생할 음성이 없어요", "err");
  auto = { items, i: 0 };
  playAuto();
}
function playAuto() {
  if (!auto) return;
  const it = auto.items[auto.i];
  if (!it) { stopAuto(); flash("전체 재생을 마쳤어요"); return; }
  const h = listenHandles.get(`${it.file}:${it.n}`);
  if (!h) { auto.i++; playAuto(); return; }
  const p = h.open();
  p.onEnded = () => {
    p.onEnded = undefined;
    if (!auto) return;
    auto.i++;
    playAuto();
  };
  h.box.scrollIntoView({ block: "center", behavior: "smooth" });
  p.playFromStart();
  paintAutoButton();
}

function closePlayers() {
  stopAuto();
  listenHandles.clear();
  players.forEach((_, p) => p.dispose());
  players.clear();
}

const entry = (f: string) => state.entries.get(f);
const rowKey = (r: Row) => JSON.stringify([r.time, r.scene, r.screen, r.say, r.same ? "" : r.speak, r.same, r.prompt ?? ""]);
const modRows = (e: Entry) => e.cur.rows.flatMap((r, i) => (rowKey(r) !== rowKey(e.orig.rows[i]) ? [i] : []));
const dirtyCount = (e: Entry) => modRows(e).length + (e.cur.before !== e.orig.before ? 1 : 0);
const anyDirty = () => [...state.entries.values()].some((e) => dirtyCount(e) > 0);
const shown = () => (state.mode === "compare" ? [state.left, state.right] : [state.active]);

// ---- 읽기 시간 ----------------------------------------------------------

// 영상 길이: 머리말에 `목표 길이: 60초` 가 있으면 그 값, 없으면 상단 "영상 길이" 칸
const lengthOf = (doc: Doc) => targetOf(doc.before) ?? state.length;
const estOf = (r: Row) => syllables(eff(r)) / RATE + pauseSecs(eff(r));

function timing(doc: Doc, i: number) {
  const r = doc.rows[i];
  const start = secs(r.time);
  const next = i + 1 < doc.rows.length ? secs(doc.rows[i + 1].time) : lengthOf(doc);
  if (start == null || next == null) return null;
  const slot = next - start;
  const text = eff(r);
  const pause = pauseSecs(text);
  const est = estOf(r);
  const level = est > slot ? "over" : est > slot - 1 ? "warn" : "ok";
  const commas = (text.replace(PAUSE_RE, "").match(/,/g) ?? []).length;
  return { slot, est, level, pause, commas } as const;
}

// ---- 줄 편집 컨트롤 (단일·비교 화면이 같이 쓴다) ---------------------------

type Field = { wrap: HTMLElement; ta: HTMLTextAreaElement; hl: HTMLElement };
type Ctl = {
  file: string;
  i: number;
  time: HTMLInputElement;
  scene: HTMLInputElement;
  screen: Field; // 화면 자막(영상에 박히는 글)
  prompt: Field; // AI 프롬프트(장면 연출 지시, 표 맨 끝 칸)
  say: Field;
  speak: Field;
  est: HTMLElement;
  box: HTMLElement; // 수정 표시를 칠하는 바깥 요소(tr 또는 pane)
};
const reg = new Map<string, Ctl[]>();
const ctlAt = (file: string, i: number) => reg.get(file)?.[i];
const rowOf = (c: Ctl) => state.entries.get(c.file)!.cur.rows[c.i];

function field(name: string): Field {
  const ta = el("textarea", { rows: 2, spellcheck: "false", "aria-label": name });
  const hl = el("div", { class: "hl", "aria-hidden": "true" });
  return { wrap: el("div", { class: "hlw" }, hl, ta), ta, hl };
}

// 입력 칸 뒤에 같은 글자를 깔고 다른 글자만 칠한다(글자는 투명, 배경만 보인다).
function paintField(f: Field, segs: Seg[] | null) {
  const nodes: Node[] = [];
  for (const s of segs ?? [{ t: f.ta.value, d: false }]) {
    for (const part of s.t.split(PAUSE_SPLIT)) {
      if (!part) continue;
      const pause = /^\[쉼/.test(part);
      if (s.d || pause) nodes.push(el("mark", { class: [s.d ? "" : "", pause ? "pause" : ""].join(" ").trim() || null }, part));
      else nodes.push(document.createTextNode(part));
    }
  }
  if (f.ta.value.endsWith("\n")) nodes.push(document.createTextNode("​"));
  f.hl.replaceChildren(...nodes);
}

// 커서 위치에 [쉼 초] 를 끼워 넣는다
function insertPause(ta: HTMLTextAreaElement, sec: string) {
  const token = `[쉼 ${sec}]`;
  const a = ta.selectionStart ?? ta.value.length;
  const b = ta.selectionEnd ?? a;
  const before = ta.value.slice(0, a).replace(/\s+$/, "");
  const after = ta.value.slice(b).replace(/^\s+/, "");
  ta.value = `${before} ${token} ${after}`.trim();
  const at = before.length + token.length + 2;
  ta.focus();
  ta.setSelectionRange(at, at);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
}

function grow(ta: HTMLTextAreaElement) {
  ta.style.height = "auto";
  ta.style.height = `${ta.scrollHeight + 2}px`;
}

function syncCtl(c: Ctl) {
  const r = rowOf(c);
  c.time.value = r.time;
  c.scene.value = r.scene;
  c.screen.ta.value = r.screen;
  c.prompt.ta.value = r.prompt ?? "";
  c.say.ta.value = r.say;
  c.speak.ta.value = eff(r);
  paintField(c.speak, null);
  c.time.setAttribute("aria-invalid", String(!TIME_RE.test(r.time)));
}

function paintEst(file: string, i: number) {
  const e = entry(file);
  const c = ctlAt(file, i);
  if (!e || !c) return;
  const t = timing(e.cur, i);
  c.est.className = `est ${t?.level ?? "over"}`;
  c.est.replaceChildren(
    ...(t
      ? [
          el("b", {}, `${t.est.toFixed(1)}초 ${t.level === "over" ? "초과" : t.level === "warn" ? "주의" : "여유"}`),
          el("small", {}, `구간 ${t.slot.toFixed(1)}초 중`),
          ...(t.pause || t.commas
            ? [el("small", {}, [t.pause ? `쉼 ${t.pause.toFixed(1)}초` : "", t.commas ? `쉼표 ${t.commas}` : ""].filter(Boolean).join(" · "))]
            : []),
        ]
      : [el("b", {}, "시각 오류")]),
  );
  c.box.classList.toggle("mod", rowKey(e.cur.rows[i]) !== rowKey(e.orig.rows[i]));
}

function makeCtl(file: string, i: number, onEdit: (c: Ctl) => void): Ctl {
  const n = entry(file)!.cur.rows[i].n;
  const c: Ctl = {
    file,
    i,
    time: el("input", { class: "time", spellcheck: "false", "aria-label": `${label(file)} ${n}번 시각` }),
    scene: el("input", { "aria-label": `${label(file)} ${n}번 장면` }),
    screen: field(`${label(file)} ${n}번 화면 자막`),
    prompt: field(`${label(file)} ${n}번 AI 프롬프트`),
    say: field(`${label(file)} ${n}번 자막·대본`),
    speak: field(`${label(file)} ${n}번 읽는 말`),
    est: el("span", { class: "est" }),
    box: el("div"),
  };
  (reg.get(file) ?? reg.set(file, []).get(file)!)[i] = c;
  syncCtl(c);

  const edited = () => {
    paintEst(file, i);
    paintEst(file, i - 1); // 시각이 바뀌면 앞 줄의 구간이 달라진다
    onEdit(c);
  };
  c.time.addEventListener("input", () => {
    rowOf(c).time = c.time.value.trim();
    c.time.setAttribute("aria-invalid", String(!TIME_RE.test(rowOf(c).time)));
    edited();
  });
  c.scene.addEventListener("input", () => { rowOf(c).scene = c.scene.value; edited(); });
  // 기본은 자막만 고친다: 타자를 멈추면 읽는 말의 같은 자리를 발음 규칙으로 따라 고친다(직접 넣은 쉼표·[쉼]은 남긴다)
  let lastSay = rowOf(c).say;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const followSay = () => {
    const r = rowOf(c);
    if (r.say === lastSay) return;
    const patched = patchSpeak(lastSay, r.say, eff(r));
    const next = patched ?? pronounce(r.say);
    if (patched === null) flash(`${r.n}번 읽는 말을 자막 기준으로 새로 만들었어요 — 쉼표·쉼을 다시 확인해 주세요`);
    lastSay = r.say;
    r.same = next === r.say;
    r.speak = r.same ? "" : next;
    c.speak.ta.value = next;
    paintField(c.speak, null);
    grow(c.speak.ta);
    edited();
  };
  c.screen.ta.addEventListener("input", () => { rowOf(c).screen = c.screen.ta.value; grow(c.screen.ta); edited(); });
  c.prompt.ta.placeholder = "이 장면을 만들 AI 에게 주는 지시 — 화면·줌·강조·효과·전환 (예: 입력칸으로 줌인, 버튼에 클릭 효과)";
  c.prompt.ta.addEventListener("input", () => { rowOf(c).prompt = c.prompt.ta.value; grow(c.prompt.ta); edited(); });
  c.say.ta.addEventListener("input", () => {
    rowOf(c).say = c.say.ta.value;
    grow(c.say.ta);
    clearTimeout(timer);
    timer = setTimeout(followSay, 400);
    edited();
  });
  c.say.ta.addEventListener("blur", () => { clearTimeout(timer); followSay(); });
  // 읽는 말이 자막과 똑같으면 md 에는 (자막과 같음)으로 저장된다
  c.speak.ta.addEventListener("input", () => {
    const r = rowOf(c);
    const v = c.speak.ta.value;
    r.same = v === r.say;
    r.speak = r.same ? "" : v;
    paintField(c.speak, null);
    grow(c.speak.ta);
    edited();
  });
  return c;
}

function afterRender(...files: string[]) {
  for (const f of files) {
    reg.get(f)?.forEach((c) => {
      grow(c.screen.ta);
      grow(c.prompt.ta);
      grow(c.say.ta);
      grow(c.speak.ta);
      paintEst(c.file, c.i);
    });
  }
}

// ---- 상단 상태 ----------------------------------------------------------

let statusTimer: ReturnType<typeof setTimeout> | undefined;
function flash(text: string, kind: "ok" | "err" = "ok") {
  const s = $("status");
  s.textContent = text;
  s.className = `status ${kind}`;
  clearTimeout(statusTimer);
  statusTimer = setTimeout(updateTop, 3500);
}

function updateTop() {
  const loaded = shown().map(entry).filter((e): e is Entry => !!e);
  const n = loaded.reduce((sum, e) => sum + dirtyCount(e), 0);
  const s = $("status");
  s.className = "status";
  s.textContent = n ? `수정 ${n}곳 · 저장 전` : loaded.length ? "저장됨" : "";
  $<HTMLButtonElement>("save").disabled = !n;
  if (state.mode !== "compare") renderTabs();
  paintLength();
}

// 단일 보기: 읽기 합계와 목표 길이, 목표에 맞춘 시각 배분
function paintLength() {
  const e = state.mode === "single" ? entry(state.active) : undefined;
  const target = e ? targetOf(e.cur.before) : null;
  const lenInput = $<HTMLInputElement>("len");
  lenInput.disabled = target != null;
  lenInput.value = String(target ?? state.length);
  lenInput.title = target != null ? "대본 머리말의 목표 길이를 씁니다" : "";
  const total = $("total");
  const fit = $<HTMLButtonElement>("fit");
  total.hidden = !e;
  fit.hidden = !e;
  if (!e) return;
  const start = secs(e.cur.rows[0]?.time ?? "") ?? 0;
  const read = e.cur.rows.reduce((sum, r) => sum + estOf(r), 0);
  const spare = lengthOf(e.cur) - start - read;
  total.className = `total est ${spare < 0 ? "over" : spare < e.cur.rows.length ? "warn" : "ok"}`;
  total.replaceChildren(
    el("b", {}, `읽기 ${read.toFixed(1)}초`),
    el("small", {}, ` / ${target != null ? "목표" : "영상"} ${lengthOf(e.cur).toFixed(0)}초 · ${spare < 0 ? `${(-spare).toFixed(1)}초 초과` : `여유 ${spare.toFixed(1)}초`}`),
  );
  fit.disabled = target == null || !e.cur.rows.length;
  fit.title = target == null ? "머리말에 `목표 길이: 60초` 를 적으면 쓸 수 있어요" : "줄마다 읽기 시간에 같은 여유를 붙여 시각을 다시 나눕니다";
}

function fitToTarget() {
  const e = entry(state.active);
  const target = e ? targetOf(e.cur.before) : null;
  if (!e || target == null) return;
  const start = secs(e.cur.rows[0]?.time ?? "") ?? 0;
  const { times, spare, gap } = fitTimes(start, e.cur.rows.map(estOf), target);
  if (spare < 0) return flash(`읽는 말이 목표 ${target}초보다 ${(-spare).toFixed(1)}초 길어요 — 문장을 줄여 주세요`, "err");
  e.cur.rows.forEach((r, i) => { r.time = fmtTime(times[i]); });
  renderSingle();
  updateTop();
  flash(`시각을 목표 ${target}초에 맞췄어요 — 줄마다 여유 ${gap.toFixed(1)}초`);
}

function renderTabs() {
  $("tabs").replaceChildren(
    ...state.files.map((f) => {
      const e = entry(f);
      const b = el(
        "button",
        {
          type: "button",
          role: "tab",
          "aria-selected": String(f === state.active),
          title: state.ids[f] ? `주소 ${new URL(`./${state.ids[f]}`, location.href).pathname}` : undefined,
          onclick: () => { state.active = f; store.set("editor.file", f); render(); },
        },
        state.ids[f] ? `${state.ids[f]}. ${label(f)}` : label(f),
      );
      if (e && dirtyCount(e) > 0) b.append(el("span", { class: "dot", title: "저장 전 수정 있음" }, "●"));
      return b;
    }),
  );
}

function banner(text?: string, actions: HTMLElement[] = []) {
  const b = $("banner");
  b.hidden = !text;
  b.replaceChildren(...(text ? [el("span", {}, text), ...actions] : []));
}

// ---- 단일 보기 ----------------------------------------------------------

function renderSingle() {
  const e = entry(state.active);
  const body = $("rows");
  closePlayers();
  reg.clear();
  if (!e) return body.replaceChildren();
  body.replaceChildren(
    ...e.cur.rows.map((r, i) => {
      const c = makeCtl(state.active, i, () => updateTop());
      return el("tr", {}, numCell(r.n), el("td", { class: "thumbcell" }, thumb(i + 1)), el("td", {}, pane(c)));
    }),
  );
  afterRender(state.active);
  const before = $<HTMLTextAreaElement>("before");
  before.value = e.cur.before;
  // 렌더마다 덮어써 리스너가 쌓이지 않는다. 목표 길이가 바뀌면 마지막 줄 구간도 달라진다
  before.oninput = () => { e.cur.before = before.value; paintEst(state.active, e.cur.rows.length - 1); updateTop(); };
  paintPrompt();
}

// ---- 비교 보기 ----------------------------------------------------------

type CmpRow = {
  tr: HTMLTableRowElement;
  mark: HTMLElement;
  note: HTMLElement;
  lc?: Ctl;
  rc?: Ctl;
};
let cmpRows: CmpRow[] = [];

function pane(c?: Ctl): HTMLElement {
  if (!c) return el("div", { class: "empty" }, "(이 줄 없음)");
  const head = el("div", { class: "phead" }, c.time, c.scene, c.est);
  const box = el(
    "div",
    { class: "pane" },
    head,
    ...(entry(c.file)?.cur.hasScreen
      ? [el("div", { class: "lbl" }, "화면 자막 · 영상에 박히는 글, 한 줄에 한 문구"), c.screen.wrap]
      : []),
    el("div", { class: "lbl" }, "자막·대본"),
    c.say.wrap,
    el(
      "div",
      { class: "lblrow" },
      el("span", { class: "lbl" }, "읽는 말 · 자막을 따라 자동, 필요하면 직접 수정"),
      ...["0.3", "0.5", "0.8"].map((s) =>
        el("button", { type: "button", class: "pausebtn", title: `커서 위치에 ${s}초 쉼 넣기`, onclick: () => insertPause(c.speak.ta, s) }, `쉼 ${s}`),
      ),
    ),
    c.speak.wrap,
    // 장면마다 영상 제작 AI 가 읽는 연출 지시. md 표 맨 끝 'AI 프롬프트' 칸에 저장된다
    el("div", { class: "lbl" }, "AI 프롬프트 · 이 장면을 만들 AI 에게 주는 지시"),
    c.prompt.wrap,
  );
  head.append(listenButton(c, box));
  c.box = box;
  return box;
}

function paintDiff(i: number) {
  const r = cmpRows[i];
  if (!r) return;
  const diffs: string[] = [];
  if (r.lc && r.rc) {
    const a = rowOf(r.lc);
    const b = rowOf(r.rc);
    if (entry(r.lc.file)?.cur.hasScreen && entry(r.rc.file)?.cur.hasScreen) {
      const sc = diffChars(a.screen, b.screen);
      paintField(r.lc.screen, sc.a);
      paintField(r.rc.screen, sc.b);
      if (a.screen !== b.screen) diffs.push("화면 자막");
    }
    const sd = diffChars(a.say, b.say);
    const pd = diffChars(eff(a), eff(b));
    paintField(r.lc.say, sd.a);
    paintField(r.rc.say, sd.b);
    paintField(r.lc.speak, pd.a);
    paintField(r.rc.speak, pd.b);
    const tchg = a.time !== b.time;
    const schg = a.scene !== b.scene;
    for (const c of [r.lc, r.rc]) {
      c.time.classList.toggle("chg", tchg);
      c.scene.classList.toggle("chg", schg);
    }
    if (a.say !== b.say) diffs.push("자막");
    if (eff(a) !== eff(b)) diffs.push("읽는 말");
    if (tchg) diffs.push("시각");
    if (schg) diffs.push("장면");
  } else {
    diffs.push("한쪽만");
  }
  r.tr.classList.toggle("diff", diffs.length > 0);
  r.tr.classList.toggle("same-row", diffs.length === 0);
  r.mark.textContent = diffs.length ? "≠" : "=";
  r.note.textContent = diffs.join("·");
}

function updateCount() {
  const d = cmpRows.filter((r) => r.tr.classList.contains("diff")).length;
  $("diffcount").textContent = d ? `다른 줄 ${d} / ${cmpRows.length}` : "차이 없음";
  $<HTMLButtonElement>("prev").disabled = $<HTMLButtonElement>("next").disabled = d === 0;
}

function applyFilter() {
  for (const r of cmpRows) r.tr.hidden = state.onlyDiff && !r.tr.classList.contains("diff");
}

function onCmpEdit(c: Ctl) {
  paintDiff(c.i);
  updateCount();
  updateTop();
}

// 자막·읽는 말만 복사한다. 시각·장면은 영상마다 다를 수 있어 건드리지 않는다.
function copyRow(from?: Ctl, to?: Ctl) {
  if (!from || !to) return;
  const a = rowOf(from);
  const b = rowOf(to);
  b.say = a.say;
  b.same = a.same;
  if (!a.same) b.speak = a.speak;
  syncCtl(to);
  grow(to.say.ta);
  grow(to.speak.ta);
  paintEst(to.file, to.i);
  onCmpEdit(to);
}

// 장면 화면. 대본별 장면 영상(clips/<라벨>/NN.mp4)이 있으면 그 줄 구간만 재생하는 영상을, 없으면 썸네일 이미지를 보여 준다.
// 장면 칸: 기본은 구간 영상(clips/<라벨>/NN.mp4), 버튼으로 대표 이미지(frames/<라벨>/NN.jpg)와 바꿔 본다.
// 영상이 없으면 대표 이미지만 보여 주고 영상 버튼은 끈다.
function thumb(n: number, file = state.mode === "compare" ? state.right : state.active) {
  const nn = String(n).padStart(2, "0");
  const lab = encodeURIComponent(labelOf(file));
  const video = el("video", {
    class: "thumb",
    src: `clips/${lab}/${nn}.mp4`,
    poster: `frames/${lab}/${nn}.jpg`,
    controls: true,
    preload: "metadata",
    playsinline: true,
    "aria-label": `${n}번 장면 영상`,
  });
  const image = thumbImage(n, file);
  const holder = el("div", {}, video);
  const vBtn = el("button", { type: "button", "aria-pressed": "true" }, "영상");
  const iBtn = el("button", { type: "button", "aria-pressed": "false" }, "대표 이미지");
  const show = (mode: "video" | "image") => {
    if (mode === "image") video.pause();
    holder.replaceChildren(mode === "video" ? video : image);
    vBtn.setAttribute("aria-pressed", String(mode === "video"));
    iBtn.setAttribute("aria-pressed", String(mode === "image"));
  };
  vBtn.addEventListener("click", () => show("video"));
  iBtn.addEventListener("click", () => show("image"));
  video.addEventListener("error", () => { vBtn.disabled = true; show("image"); }, { once: true });
  const bar = el("div", { class: "seg mediatoggle", role: "group", "aria-label": `${n}번 장면 보기` }, vBtn, iBtn);
  return el("div", { class: "media" }, bar, holder);
}

// 장면 영상 하나를 재생하면 다른 장면 영상은 멈춘다
document.addEventListener(
  "play",
  (ev) => {
    if (!(ev.target instanceof HTMLVideoElement)) return;
    for (const v of document.querySelectorAll<HTMLVideoElement>("video.thumb")) if (v !== ev.target) v.pause();
  },
  true,
);

// 장면 썸네일. 누르면 크게 연다. 대본별 새 시안(frames/<라벨>/NN.jpg)이 있으면 그것을, 없으면 게시본 프레임(frames/NN.jpg)을 보여 준다.
function thumbImage(n: number, file: string) {
  const nn = String(n).padStart(2, "0");
  const base = `frames/${nn}.jpg`;
  const own = `frames/${encodeURIComponent(labelOf(file))}/${nn}.jpg`;
  const img = el("img", { class: "thumb", src: own, alt: `${n}번 장면 화면`, loading: "lazy" });
  img.addEventListener("error", () => {
    if (img.getAttribute("src") !== base) { img.setAttribute("src", base); (img.parentElement as HTMLAnchorElement).href = base; }
    else img.remove();
  });
  const src = own;
  return el("a", { href: src, target: "_blank", rel: "noreferrer", class: "thumblink", title: "크게 보기" }, img);
}

function renderCompare() {
  const L = entry(state.left);
  const R = entry(state.right);
  const body = $("cmprows");
  closePlayers();
  reg.clear();
  cmpRows = [];
  $("lname").textContent = label(state.left);
  $("rname").textContent = label(state.right);
  if (!L || !R) return body.replaceChildren();

  const total = Math.max(L.cur.rows.length, R.cur.rows.length);
  const trs: HTMLTableRowElement[] = [];
  for (let i = 0; i < total; i++) {
    const lc = i < L.cur.rows.length ? makeCtl(state.left, i, onCmpEdit) : undefined;
    const rc = i < R.cur.rows.length ? makeCtl(state.right, i, onCmpEdit) : undefined;
    const mark = el("span", { class: "state" });
    const note = el("small");
    const toR = el("button", { type: "button", title: "왼쪽 자막·읽는 말을 오른쪽으로 복사", "aria-label": `${i + 1}번 줄 오른쪽으로 복사` }, "→");
    const toL = el("button", { type: "button", title: "오른쪽 자막·읽는 말을 왼쪽으로 복사", "aria-label": `${i + 1}번 줄 왼쪽으로 복사` }, "←");
    toR.disabled = toL.disabled = !(lc && rc);
    toR.addEventListener("click", () => copyRow(lc, rc));
    toL.addEventListener("click", () => copyRow(rc, lc));
    const tr = el(
      "tr",
      {},
      numCell((L.cur.rows[i] ?? R.cur.rows[i]).n),
      el("td", {}, pane(lc)),
      el(
        "td",
        { class: "gut" },
        thumb(i + 1),
        mark,
        note,
        el("div", { class: "copy" }, toL, toR),
      ),
      el("td", {}, pane(rc)),
    );
    cmpRows.push({ tr, mark, note, lc, rc });
    trs.push(tr);
  }
  body.replaceChildren(...trs);
  afterRender(state.left, state.right);
  cmpRows.forEach((_, i) => paintDiff(i));
  applyFilter();
  updateCount();
}

function jump(dir: 1 | -1) {
  const off = $("top").offsetHeight + 40; // 상단 바와 표 머리줄 아래
  const rows = cmpRows.map((r) => r.tr).filter((tr) => tr.classList.contains("diff") && !tr.hidden);
  if (!rows.length) return;
  const tops = rows.map((tr) => tr.getBoundingClientRect().top);
  const target =
    dir === 1
      ? (rows.find((_, k) => tops[k] > off + 4) ?? rows[0])
      : (rows.filter((_, k) => tops[k] < off - 4).pop() ?? rows[rows.length - 1]);
  window.scrollTo({ top: window.scrollY + target.getBoundingClientRect().top - off, behavior: "smooth" });
}

// ---- 읽기·쓰기 ----------------------------------------------------------

function apply(file: string, doc: Doc, etag: string) {
  state.entries.set(file, { orig: structuredClone(doc), cur: doc, etag });
}

async function load(file: string) {
  const { status, data } = await api(`api/script?file=${encodeURIComponent(file)}`);
  if (status !== 200 || !data.doc || !data.etag) throw new Error(data.error ?? `${label(file)} 불러오기 실패(${status})`);
  apply(file, data.doc, data.etag);
}

function showMode() {
  const cmp = state.mode === "compare";
  $("compare").hidden = !cmp;
  $("single").hidden = cmp;
  $("tabs").hidden = cmp;
  $("pair").hidden = !cmp;
  document.querySelectorAll<HTMLButtonElement>("#mode button").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.mode === state.mode));
  });
  if (cmp) {
    for (const [id, v] of [["left", state.left], ["right", state.right]] as const) $<HTMLSelectElement>(id).value = v;
  }
  // 주소창: 단일 보기는 /editor/<번호>, 비교 보기는 /editor/
  const id = state.ids[state.active];
  history.replaceState(null, "", !cmp && id ? `./${id}${location.search}` : `./${location.search}`);
}

async function render() {
  showMode();
  try {
    await Promise.all([loadAudio(shown()), ...shown().filter((f) => !state.entries.has(f)).map(load)]);
  } catch (err) {
    flash((err as Error).message, "err");
  }
  if (state.mode === "compare") renderCompare();
  else renderSingle();
  updateTop();
}

// ---- AI 프롬프트 칸: 편집(마크다운 글) ↔ 보기(렌더링) ---------------------------
// Phosphor eye / pencil-simple (MIT)
const EYE_ICON = '<svg viewBox="0 0 256 256" aria-hidden="true"><path d="M247.31,124.76c-.35-.79-8.82-19.58-27.65-38.41C194.57,61.26,162.88,48,128,48S61.43,61.26,36.34,86.35C17.51,105.18,9,124,8.69,124.76a8,8,0,0,0,0,6.5c.35.79,8.82,19.57,27.65,38.4C61.43,194.74,93.12,208,128,208s66.57-13.26,91.66-38.34c18.83-18.83,27.3-37.61,27.65-38.4A8,8,0,0,0,247.31,124.76ZM128,192c-30.78,0-57.67-11.19-79.93-33.25A133.47,133.47,0,0,1,25,128,133.33,133.33,0,0,1,48.07,97.25C70.33,75.19,97.22,64,128,64s57.67,11.19,79.93,33.25A133.46,133.46,0,0,1,231.05,128C223.84,141.46,192.43,192,128,192Zm0-112a48,48,0,1,0,48,48A48.05,48.05,0,0,0,128,80Zm0,80a32,32,0,1,1,32-32A32,32,0,0,1,128,160Z"/></svg>';
const PENCIL_ICON = '<svg viewBox="0 0 256 256" aria-hidden="true"><path d="M227.31,73.37,182.63,28.68a16,16,0,0,0-22.63,0L36.69,152A15.86,15.86,0,0,0,32,163.31V208a16,16,0,0,0,16,16H92.69A15.86,15.86,0,0,0,104,219.31L227.31,96a16,16,0,0,0,0-22.63ZM92.69,208H48V163.31l88-88L180.69,120ZM192,108.68,147.31,64l24-24L216,84.68Z"/></svg>';
let promptView = store.get("editor.promptview") !== "0"; // 기본은 보기
function paintPrompt() {
  const ta = $<HTMLTextAreaElement>("before");
  const view = $("beforeview");
  const btn = $("viewprompt");
  ta.hidden = promptView;
  view.hidden = !promptView;
  btn.innerHTML = promptView ? PENCIL_ICON : EYE_ICON;
  btn.title = promptView ? "편집으로" : "마크다운으로 보기";
  btn.setAttribute("aria-label", btn.title);
  btn.setAttribute("aria-pressed", String(promptView));
  if (promptView) view.innerHTML = DOMPurify.sanitize(marked.parse(ta.value, { async: false }) as string);
}

async function save() {
  const files = shown().filter((f) => {
    const e = entry(f);
    return e && dirtyCount(e) > 0;
  });
  if (!files.length) return;
  for (const f of files) {
    const bad = entry(f)!.cur.rows.find((r) => !TIME_RE.test(r.time));
    if (bad) return flash(`${label(f)} ${bad.n}번 줄 시각 형식은 m:ss.s 예요`, "err");
  }
  let saved = 0;
  for (const f of files) {
    const e = entry(f)!;
    const { status, data } = await api(`api/script?file=${encodeURIComponent(f)}`, {
      method: "PUT",
      body: JSON.stringify({ etag: e.etag, before: e.cur.before, rows: e.cur.rows }),
    });
    if (status === 409) {
      banner(`${label(f)}: 디스크의 파일이 바뀌었어요. 다시 불러오면 이 파일의 수정은 사라져요.`, [
        el("button", { type: "button", class: "ghost", onclick: () => reload(true, f) }, "수정 버리고 다시 불러오기"),
        el("button", { type: "button", class: "ghost", onclick: () => banner() }, "닫기"),
      ]);
      continue;
    }
    if (status !== 200 || !data.doc || !data.etag) {
      flash(`${label(f)}: ${data.error ?? `저장 실패(${status})`}`, "err");
      continue;
    }
    apply(f, data.doc, data.etag);
    saved++;
    if (data.synth?.length) { markSynth(data.synth.map((n) => ({ label: labelOf(f), n }))); watchSynth(); }
  }
  if (saved) {
    if (saved === files.length) banner();
    await render();
    flash(`${saved}개 파일을 저장했어요`, "ok");
  }
}

let armed: ReturnType<typeof setTimeout> | undefined;
async function reload(force = false, only?: string) {
  const files = only ? [only] : shown();
  const btn = $<HTMLButtonElement>("reload");
  const dirty = files.some((f) => {
    const e = entry(f);
    return e && dirtyCount(e) > 0;
  });
  if (!force && dirty && !armed) {
    btn.textContent = "수정이 사라져요 — 한 번 더";
    armed = setTimeout(() => { armed = undefined; btn.textContent = "저장본 다시 불러오기"; }, 4000);
    return;
  }
  clearTimeout(armed);
  armed = undefined;
  btn.textContent = "저장본 다시 불러오기";
  try {
    await Promise.all(files.map(load));
    banner();
    await render();
    flash("저장본을 불러왔어요", "ok");
  } catch (err) {
    flash((err as Error).message, "err");
  }
}

// ---- 시작 ---------------------------------------------------------------

function fillSelects() {
  for (const id of ["left", "right"]) {
    $<HTMLSelectElement>(id).replaceChildren(...state.files.map((f) => el("option", { value: f }, label(f))));
  }
}

function pick(side: "left" | "right", file: string) {
  const other = side === "left" ? "right" : "left";
  state[side] = file;
  if (state[other] === file) state[other] = state.files.find((f) => f !== file) ?? file; // 같은 파일끼리 비교하지 않는다
  store.set("editor.left", state.left);
  store.set("editor.right", state.right);
  render();
}

async function main() {
  const len = Number(store.get("editor.len"));
  if (len > 0) state.length = len;
  const lenInput = $<HTMLInputElement>("len");
  lenInput.value = String(state.length);
  lenInput.addEventListener("change", () => {
    const v = Number(lenInput.value);
    if (!(v > 0)) { lenInput.value = String(state.length); return; }
    state.length = v;
    store.set("editor.len", String(v));
    render();
  });

  const { data } = await api("api/files");
  state.files = data.files ?? [];
  state.ids = data.ids ?? {};
  PREFIX = data.prefix ?? "";
  setWords(data.words ?? []);
  if (!state.files.length) return flash("대본 md 파일이 없어요", "err");
  fillSelects();

  const saved = (k: string) => { const v = store.get(k); return v && state.files.includes(v) ? v : null; };
  state.active = saved("editor.file") ?? state.files[0];
  state.left = saved("editor.left") ?? state.files[0];
  state.right = saved("editor.right") ?? state.files[1] ?? state.files[0];
  if (state.left === state.right) state.right = state.files.find((f) => f !== state.left) ?? state.right;
  const canCompare = state.files.length >= 2;
  state.mode = canCompare && store.get("editor.mode") !== "single" ? "compare" : "single";
  // /editor/<번호> 로 들어오면 그 대본을 단일 보기로 연다
  const urlId = /\/(\d+)$/.exec(location.pathname)?.[1];
  if (urlId) {
    const f = state.files.find((x) => String(state.ids[x]) === urlId);
    if (f) { state.active = f; state.mode = "single"; }
    else flash(`${urlId}번 대본이 없어요`, "err");
  }
  state.onlyDiff = store.get("editor.onlydiff") === "1";
  $<HTMLInputElement>("onlydiff").checked = state.onlyDiff;
  document.querySelector<HTMLButtonElement>('#mode button[data-mode="compare"]')!.disabled = !canCompare;

  document.querySelectorAll<HTMLButtonElement>("#mode button").forEach((b) =>
    b.addEventListener("click", () => {
      state.mode = b.dataset.mode as Mode;
      store.set("editor.mode", state.mode);
      render();
    }),
  );
  $<HTMLSelectElement>("left").addEventListener("change", (ev) => pick("left", (ev.target as HTMLSelectElement).value));
  $<HTMLSelectElement>("right").addEventListener("change", (ev) => pick("right", (ev.target as HTMLSelectElement).value));
  $("swap").addEventListener("click", () => {
    [state.left, state.right] = [state.right, state.left];
    store.set("editor.left", state.left);
    store.set("editor.right", state.right);
    render();
  });
  $("onlydiff").addEventListener("change", (ev) => {
    state.onlyDiff = (ev.target as HTMLInputElement).checked;
    store.set("editor.onlydiff", state.onlyDiff ? "1" : "0");
    applyFilter();
  });
  $("prev").addEventListener("click", () => jump(-1));
  $("autoplay").addEventListener("click", () => (auto ? stopAuto() : startAuto()));
  $("viewprompt").addEventListener("click", (ev) => {
    ev.preventDefault(); // 접기·펼치기로 번지지 않게
    promptView = !promptView;
    store.set("editor.promptview", promptView ? "1" : "0");
    paintPrompt();
  });
  $("copyprompt").addEventListener("click", async (ev) => {
    ev.preventDefault(); // 접기·펼치기로 번지지 않게
    try {
      await navigator.clipboard.writeText($<HTMLTextAreaElement>("before").value);
      flash("AI 프롬프트를 복사했어요");
    } catch {
      flash("복사하지 못했어요 — 칸을 선택해 직접 복사해 주세요", "err");
    }
  });
  paintAutoButton();
  $("next").addEventListener("click", () => jump(1));
  $("save").addEventListener("click", save);
  $("fit").addEventListener("click", fitToTarget);
  $("reload").addEventListener("click", () => reload());
  window.addEventListener("keydown", (ev) => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "s") { ev.preventDefault(); save(); }
  });
  window.addEventListener("beforeunload", (ev) => { if (anyDirty()) ev.preventDefault(); });
  window.addEventListener("resize", () => {
    document.querySelectorAll("#rows textarea, #cmprows textarea").forEach((t) => grow(t as HTMLTextAreaElement));
  });
  // 상단 바 높이가 줄바꿈으로 달라져도 표 머리줄이 바로 아래에 붙게 한다
  new ResizeObserver(() => document.documentElement.style.setProperty("--top", `${$("top").offsetHeight}px`)).observe($("top"));

  await render();
}

main().catch((err) => flash(String(err), "err"));
