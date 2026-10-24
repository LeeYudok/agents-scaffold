// 대본별 줄 음성: <콘텐츠>/audio/<라벨>/NN.m4a + NN.json. 라벨은 대본 파일 이름에서 접두어(설정 prefix)·확장자를 뺀 것.
import { readdir, readFile, stat } from "node:fs/promises";
import { join } from "node:path";

export const AUDIO_FILE_RE = /^\d{2}\.m4a$/;
const LABEL_RE = /^[^/\\.][^/\\]*$/;

export const labelOf = (mdName: string, prefix: string) => {
  const s = mdName.replace(/\.md$/, "");
  return prefix && s.startsWith(prefix) ? s.slice(prefix.length) : s;
};

export function createAudioStore(contentDir: string) {
  const dirOf = (label: string) => (LABEL_RE.test(label) ? join(contentDir, "audio", label) : null);
  return {
    path(label: string, file: string) {
      const dir = dirOf(label);
      return dir && AUDIO_FILE_RE.test(file) ? join(dir, file) : null;
    },
    async tracks(label: string) {
      const dir = dirOf(label);
      if (!dir) return [];
      const names = (await readdir(dir).catch(() => [] as string[])).filter((f) => AUDIO_FILE_RE.test(f)).sort();
      return Promise.all(
        names.map(async (f) => {
          const nn = f.slice(0, 2);
          const meta = await readFile(join(dir, `${nn}.json`), "utf8").then(JSON.parse).catch(() => ({}));
          const v = (await stat(join(dir, f))).mtimeMs; // 다시 합성하면 바뀌어 브라우저 캐시를 피한다
          return { ...meta, n: Number(nn), v };
        }),
      );
    },
  };
}
