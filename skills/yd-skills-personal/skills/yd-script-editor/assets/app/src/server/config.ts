// 서버 설정. 레포마다 <레포>/script-editor.json 하나로 정한다(SCRIPT_EDITOR_CONFIG 가 그 경로).
// node·bun 어느 런타임에서도 같게 동작하도록 node: 표준 모듈만 쓴다.
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
export const APP_ROOT = resolve(here, "../..");

/** <레포>/script-editor.json 의 모양. 상대 경로는 레포(설정 파일이 있는 폴더) 기준, ~ 는 홈. */
export type RepoConfig = {
  name: string; // 서비스 이름(launchd·systemd 라벨, 캐시 폴더)
  content?: string; // 대본 md·음성·장면 영상 폴더 (기본 docs/editor)
  prefix?: string; // 대본 파일 접두어 — 라벨 = 파일 이름 - 접두어 - .md (기본 "")
  base?: string; // 공개 경로 (기본 /editor)
  port?: number; // 127.0.0.1 포트 (기본 18750)
  pronounce?: string; // 읽는 말 단어 표(TSV: 자막 낱말 \t 읽는 말)
  synth?: { python?: string; cache?: string };
  videos?: { dir?: string; pattern?: string }; // 영상 비교 페이지: <dir>/<접두>*<접미> (pattern 의 * 자리가 키)
  render?: { scenes?: string; assets?: string; out?: string; music?: string };
  public?: { ssh?: string; url?: string };
};

export type Config = {
  name: string;
  repo: string;
  host: string;
  port: number;
  base: string; // 끝 / 없음, 예: /editor
  prefix: string;
  contentDir: string;
  distDir: string; // 화면 빌드 결과(vite build) — setup 이 인스턴스마다 base 를 넣어 빌드한다
  python: string; // 음성 합성용 파이썬
  synthScript: string;
  words: [string, string][]; // 읽는 말 단어 표
  videoDir: string;
  videoPrefix: string;
  videoSuffix: string;
};

export const expand = (p: string, repo: string) =>
  p.startsWith("~/") ? join(homedir(), p.slice(2)) : isAbsolute(p) ? p : resolve(repo, p);

/** TSV 단어 표: 빈 줄·# 줄은 건너뛴다 */
export function parseWords(text: string): [string, string][] {
  return text
    .split("\n")
    .map((l) => l.replace(/\r$/, ""))
    .filter((l) => l.trim() && !l.startsWith("#"))
    .map((l) => l.split("\t"))
    .filter((c) => c.length >= 2 && c[0])
    .map((c) => [c[0], c[1]] as [string, string]);
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const file = env.SCRIPT_EDITOR_CONFIG;
  if (!file) throw new Error("SCRIPT_EDITOR_CONFIG(<레포>/script-editor.json 경로)가 필요해요");
  const repo = dirname(resolve(file));
  const c = JSON.parse(readFileSync(file, "utf8")) as RepoConfig;
  if (!c.name || !/^[a-z0-9][a-z0-9-]*$/.test(c.name)) throw new Error("script-editor.json name 은 영소문자·숫자·- 만");
  const base = `/${(c.base ?? "/editor").replace(/^\/+|\/+$/g, "")}`;
  const [vPre, vSuf] = (c.videos?.pattern ?? "*.mp4").split("*");
  const engine = env.SCRIPT_EDITOR_ENGINE ?? resolve(APP_ROOT, "../engine");
  return {
    name: c.name,
    repo,
    host: "127.0.0.1",
    port: Number(env.EDITOR_PORT ?? c.port ?? 18750),
    base: base === "/" ? "" : base,
    prefix: c.prefix ?? "",
    contentDir: expand(env.EDITOR_CONTENT ?? c.content ?? "docs/editor", repo),
    distDir: resolve(env.SCRIPT_EDITOR_DIST ?? join(APP_ROOT, "dist")),
    python: expand(env.EDITOR_PYTHON ?? c.synth?.python ?? "~/.cache/omnivoice-venv/bin/python", repo),
    synthScript: join(engine, "synth.py"),
    words: c.pronounce ? parseWords(readFileSync(expand(c.pronounce, repo), "utf8")) : [],
    videoDir: expand(env.EDITOR_VIDEOS ?? c.videos?.dir ?? "videos", repo),
    videoPrefix: vPre ?? "",
    videoSuffix: vSuf ?? ".mp4",
  };
}
