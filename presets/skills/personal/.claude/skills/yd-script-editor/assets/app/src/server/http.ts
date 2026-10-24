// HTTP 공통: JSON 응답·본문 읽기·접근 검사·파일 전송(Range 지원).
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import type { IncomingMessage, ServerResponse } from "node:http";
import { extname } from "node:path";

export type Req = IncomingMessage;
export type Res = ServerResponse;

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".map": "application/json",
  ".m4a": "audio/mp4",
  ".jpg": "image/jpeg",
  ".png": "image/png",
  ".mp4": "video/mp4",
  ".woff2": "font/woff2",
};

export function sendJson(res: Res, data: unknown, status = 200) {
  const body = JSON.stringify(data);
  res.writeHead(status, { "content-type": MIME[".json"], "content-length": Buffer.byteLength(body) });
  res.end(body);
}

export async function readJson(req: Req, limit = 2_000_000): Promise<unknown> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    size += (chunk as Buffer).length;
    if (size > limit) return null;
    chunks.push(chunk as Buffer);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    return null;
  }
}

// DNS rebinding·다른 사이트의 요청을 막는다: Host 확인, 쓰기는 사용자 지정 헤더(CORS 사전요청이 필요해 막힌다).
export function guard(req: Req, res: Res, port: number): boolean {
  const host = req.headers.host ?? "";
  if (host !== `127.0.0.1:${port}` && host !== `localhost:${port}`) {
    sendJson(res, { error: "허용하지 않는 Host" }, 403);
    return false;
  }
  if (req.method !== "GET" && req.method !== "HEAD" && req.headers["x-editor"] !== "1") {
    sendJson(res, { error: "x-editor 헤더가 필요해요" }, 403);
    return false;
  }
  return true;
}

/** 파일을 보낸다. 없으면 false. Range 요청이면 206 으로 일부만 보낸다(오디오·영상 재생 위치 이동). */
export async function sendFile(req: Req, res: Res, path: string, cache = "no-cache"): Promise<boolean> {
  const st = await stat(path).catch(() => null);
  if (!st?.isFile()) return false;
  const size = st.size;
  const headers = { "content-type": MIME[extname(path)] ?? "application/octet-stream", "accept-ranges": "bytes", "cache-control": cache };
  const m = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? "");
  if (!m || (m[1] === "" && m[2] === "")) {
    res.writeHead(200, { ...headers, "content-length": size });
    createReadStream(path).pipe(res);
    return true;
  }
  const start = m[1] === "" ? Math.max(0, size - Number(m[2])) : Number(m[1]);
  const end = m[1] === "" || m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1);
  if (start > end || start >= size) {
    res.writeHead(416, { "content-range": `bytes */${size}` });
    res.end();
    return true;
  }
  res.writeHead(206, { ...headers, "content-range": `bytes ${start}-${end}/${size}`, "content-length": end - start + 1 });
  createReadStream(path, { start, end }).pipe(res);
  return true;
}
