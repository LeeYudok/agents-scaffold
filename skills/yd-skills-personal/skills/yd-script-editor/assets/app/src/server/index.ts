// 내레이션 대본 수정 에디터 서버. node·bun 어느 쪽으로도 실행된다(node: 표준 모듈만 사용).
//   SCRIPT_EDITOR_CONFIG=<레포>/script-editor.json node src/server/index.ts   (보통은 스킬 scripts/setup.sh 가 서비스로 띄운다)
// 대본·음성(콘텐츠)은 설정 content 폴더에서 읽고 쓴다. 127.0.0.1 에만 바인딩한다.
import { createServer } from "node:http";
import { join, normalize } from "node:path";
import { createAudioStore, labelOf } from "./audio.ts";
import { loadConfig } from "./config.ts";
import { guard, readJson, sendFile, sendJson, type Req, type Res } from "./http.ts";
import { createScriptStore } from "./scripts.ts";
import { createSynthQueue } from "./synth-queue.ts";
import { createVideoStore } from "./videos.ts";

const cfg = loadConfig();
const scripts = createScriptStore(cfg.contentDir);
const audio = createAudioStore(cfg.contentDir);
const label = (name: string) => labelOf(name, cfg.prefix);
const synth = createSynthQueue(cfg.contentDir, cfg.python, cfg.synthScript, label);
const videos = createVideoStore(cfg.videoDir, cfg.videoPrefix, cfg.videoSuffix);

// 화면(vite build 결과): / · /<번호> → 에디터, /player → 대본 음성, /compare → 영상 비교, /assets/* → 번들
// 모든 경로는 설정 base(예 /editor) 아래에서도 같다 — 공개 주소가 리버스 프록시·터널로 그대로 넘어온다.
const BASE = cfg.base;
const PAGES: Record<string, string> = { "/": "editor/index.html", "/player": "player/index.html", "/compare": "compare/index.html" };

async function servePage(req: Req, res: Res, path: string) {
  const page = PAGES[path];
  const file = page ? join(cfg.distDir, page) : path.startsWith("/assets/") ? join(cfg.distDir, normalize(path)) : null;
  if (!file || !file.startsWith(cfg.distDir)) return false;
  if (await sendFile(req, res, file, page ? "no-cache" : "public, max-age=31536000, immutable")) return true;
  if (page) sendJson(res, { error: "화면이 아직 빌드되지 않았어요 — 스킬 scripts/setup.sh 를 다시 돌리세요" }, 503);
  return !!page;
}

async function handle(req: Req, res: Res) {
  if (!guard(req, res, cfg.port)) return;
  const url = new URL(req.url ?? "/", `http://${req.headers.host}`);
  if (BASE && (url.pathname === "/" || url.pathname === BASE)) {
    res.writeHead(302, { location: `${BASE}/${url.search}` });
    return res.end();
  }
  let path = BASE && url.pathname.startsWith(`${BASE}/`) ? url.pathname.slice(BASE.length) : url.pathname;
  // /editor/<번호> → 그 대본을 연 에디터. 뒤 / 는 떼야 화면의 상대 주소(api/…)가 맞는다
  const id = /^\/(\d+)(\/?)$/.exec(path);
  if (id?.[2]) {
    res.writeHead(302, { location: `${BASE}/${id[1]}${url.search}` });
    return res.end();
  }
  if (id) path = "/";
  const name = url.searchParams.get("file") ?? "";

  if (path === "/api/files" && req.method === "GET") return sendJson(res, { ...(await scripts.list()), prefix: cfg.prefix, words: cfg.words });

  if (path === "/api/script" && req.method === "GET") {
    const r = await scripts.read(name);
    return r ? sendJson(res, r) : sendJson(res, { error: "없는 파일" }, 404);
  }

  if (path === "/api/script" && req.method === "PUT") {
    const r = await scripts.save(name, await readJson(req));
    if (!r.ok) return sendJson(res, { error: r.error }, r.status);
    const resynth = await synth.onSaved(name, r.rows);
    return sendJson(res, { doc: r.doc, etag: r.etag, synth: resynth });
  }

  if (path === "/api/audio" && req.method === "GET") return sendJson(res, { label: label(name), tracks: await audio.tracks(label(name)) });
  if (path === "/api/synth" && req.method === "GET") return sendJson(res, synth.status());
  if (path === "/api/videos" && req.method === "GET") return sendJson(res, { dir: cfg.videoDir, videos: await videos.list() });

  // 시연 영상(Range 로 위치 이동)과 영상별 점검 이미지
  const video = /^\/videos\/([^/]+?)(\.mp4|\/check\.png)$/.exec(decodeURIComponent(path));
  if (video && req.method === "GET") {
    const file = video[2] === ".mp4" ? videos.file(video[1]) : await videos.checkPath(video[1]);
    if (file && (await sendFile(req, res, file))) return;
    return sendJson(res, { error: "없는 파일" }, 404);
  }

  if (path.startsWith("/audio/") && req.method === "GET") {
    const [label = "", file = ""] = path.slice("/audio/".length).split("/").map(decodeURIComponent);
    const filePath = audio.path(label, file);
    if (filePath && (await sendFile(req, res, filePath))) return;
    return sendJson(res, { error: "없는 파일" }, 404);
  }

  // 장면 영상: <콘텐츠>/clips/<라벨>/NN.mp4 (렌더한 영상을 대본 줄 구간대로 자른 조각)
  const clip = /^\/clips\/([^/.][^/]*)\/(\d{2}\.mp4)$/.exec(decodeURIComponent(path));
  if (clip && req.method === "GET") {
    if (await sendFile(req, res, join(cfg.contentDir, "clips", clip[1], clip[2]))) return;
    return sendJson(res, { error: "없는 파일" }, 404);
  }

  // 장면 썸네일: <콘텐츠>/frames/NN.jpg(게시본 영상) 또는 frames/<라벨>/NN.jpg(대본별 새 시안)
  const frame = /^\/frames\/(?:([^/.][^/]*)\/)?(\d{2}\.jpg)$/.exec(decodeURIComponent(path));
  if (frame && req.method === "GET") {
    const file = frame[1] ? join(cfg.contentDir, "frames", frame[1], frame[2]) : join(cfg.contentDir, "frames", frame[2]);
    if (await sendFile(req, res, file)) return;
    return sendJson(res, { error: "없는 파일" }, 404);
  }

  if (req.method === "GET" && (await servePage(req, res, path))) return;
  sendJson(res, { error: "not found" }, 404);
}

createServer((req, res) => {
  handle(req, res).catch((err) => {
    console.error(err);
    if (!res.headersSent) sendJson(res, { error: "서버 오류" }, 500);
    else res.end();
  });
}).listen(cfg.port, cfg.host, () => {
  console.log(`대본 에디터 ${cfg.name}: http://${cfg.host}:${cfg.port}${BASE}/  (콘텐츠 ${cfg.contentDir})`);
});
