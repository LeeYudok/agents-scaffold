// 시연 영상 목록: <영상 폴더>/<접두><key><접미>(설정 videos.pattern, 예 demo-*.mp4). 영상 비교 화면(/compare)이 쓴다.
// 설명은 선택 파일 <영상 폴더>/videos.json({ "<key>": "설명" }), 점검 이미지는 <key>/<판>-check.png 또는 <판>/<판>-check.png.
import { readdir, readFile, stat } from "node:fs/promises";
import { join } from "node:path";

export const KEY_RE = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

export type Video = { key: string; size: number; mtime: number; desc: string; check: boolean };

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function createVideoStore(dir: string, prefix = "", suffix = ".mp4") {
  const VIDEO_RE = new RegExp(`^${esc(prefix)}([A-Za-z0-9][A-Za-z0-9._-]*)${esc(suffix)}$`);
  const file = (key: string) => (KEY_RE.test(key) ? join(dir, `${prefix}${key}${suffix}`) : null);

  // 판 이름은 key 의 첫 토막(v11-claude → v11). 점검 이미지는 영상별 폴더를 먼저 본다.
  const checkPath = async (key: string) => {
    if (!KEY_RE.test(key)) return null;
    const ver = key.split("-")[0];
    for (const sub of [key, ver]) {
      const p = join(dir, sub, `${ver}-check.png`);
      if ((await stat(p).catch(() => null))?.isFile()) return p;
    }
    return null;
  };

  return {
    file,
    checkPath,
    async list(): Promise<Video[]> {
      const names = await readdir(dir).catch(() => [] as string[]);
      const descs: Record<string, unknown> = await readFile(join(dir, "videos.json"), "utf8").then(JSON.parse).catch(() => ({}));
      const out: Video[] = [];
      for (const name of names) {
        const key = VIDEO_RE.exec(name)?.[1];
        if (!key) continue;
        const st = await stat(join(dir, name)).catch(() => null);
        if (!st?.isFile()) continue;
        const desc = typeof descs[key] === "string" ? (descs[key] as string) : "";
        out.push({ key, size: st.size, mtime: st.mtimeMs, desc, check: (await checkPath(key)) !== null });
      }
      return out.sort((a, b) => b.mtime - a.mtime);
    },
  };
}
