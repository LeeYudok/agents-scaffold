// 대본 md 파일 목록·읽기·검증된 쓰기.
import { createHash } from "node:crypto";
import { readdir, readFile, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { oneLine, parse, screenLines, serialize, TIME_RE, type Doc, type Row } from "../shared/script-md.ts";

export const hash = (t: string) => createHash("sha1").update(t).digest("hex");

export type SaveResult = { ok: true; doc: Doc; etag: string; rows: Row[] } | { ok: false; status: number; error: string };

// 주소 번호(/editor/<번호>)는 ids.json 에 고정한다. 새 대본은 다음 번호를 받고, 지운 대본의 번호는 다시 쓰지 않는다.
export function assignIds(files: string[], ids: Record<string, string>) {
  const next = { ...ids };
  const known = new Set(Object.values(next));
  let max = Math.max(0, ...Object.keys(next).map(Number).filter((n) => n > 0));
  for (const f of files) if (!known.has(f)) next[String(++max)] = f;
  const byFile = Object.fromEntries(Object.entries(next).map(([n, f]) => [f, Number(n)]));
  return { ids: next, changed: Object.keys(next).length !== Object.keys(ids).length, byFile };
}

export function createScriptStore(dir: string) {
  const mdFiles = async () => (await readdir(dir)).filter((f) => f.endsWith(".md") && f !== "README.md").sort();
  const idsPath = join(dir, "ids.json");
  /** 대본 파일(주소 번호 순)과 파일 → 번호 */
  const list = async () => {
    const files = await mdFiles();
    let saved: Record<string, string> = {};
    try { saved = JSON.parse(await readFile(idsPath, "utf8")); } catch { /* 처음이면 없다 */ }
    const { ids, changed, byFile } = assignIds(files, saved);
    if (changed) await writeFile(idsPath, `${JSON.stringify(ids, null, 2)}\n`);
    const ordered = files.sort((a, b) => byFile[a] - byFile[b]);
    return { files: ordered, ids: Object.fromEntries(ordered.map((f) => [f, byFile[f]])) };
  };
  const resolveName = async (name: string) => ((await mdFiles()).includes(name) ? join(dir, name) : null);

  return {
    list,
    async read(name: string) {
      const path = await resolveName(name);
      if (!path) return null;
      const text = await readFile(path, "utf8");
      return { doc: parse(text), etag: hash(text) };
    },
    async save(name: string, body: unknown): Promise<SaveResult> {
      const path = await resolveName(name);
      if (!path) return { ok: false, status: 404, error: "없는 파일" };
      const b = body as { etag?: unknown; before?: unknown; rows?: unknown } | null;
      if (!b || typeof b.before !== "string") return { ok: false, status: 400, error: "본문 형식 오류" };
      const text = await readFile(path, "utf8");
      if (b.etag !== hash(text)) return { ok: false, status: 409, error: "디스크의 파일이 바뀌었어요" };
      const current = parse(text);
      const rows = cleanRows(b.rows, current.rows);
      if (typeof rows === "string") return { ok: false, status: 400, error: rows };
      const before = b.before.replace(/\r\n/g, "\n");
      if (/^\|\s*#\s*\|/m.test(before)) return { ok: false, status: 400, error: "머리말에 표 머리줄을 넣을 수 없어요" };
      const out = serialize({ ...current, before, rows });
      const doc = parse(out); // 다시 읽히는지 확인
      await writeFile(`${path}.tmp`, out);
      await rename(`${path}.tmp`, path);
      return { ok: true, doc, etag: hash(out), rows };
    },
  };
}

function cleanRows(input: unknown, current: Row[]): Row[] | string {
  if (!Array.isArray(input) || input.length !== current.length) return "행 수가 달라요";
  const rows: Row[] = [];
  for (const [i, raw] of input.entries()) {
    const r = raw as Partial<Row>;
    if ([r.time, r.scene, r.say, r.speak].some((v) => typeof v !== "string")) return `${i + 1}번 줄 형식 오류`;
    const row: Row = {
      n: current[i].n,
      time: oneLine(r.time!),
      scene: oneLine(r.scene!),
      screen: typeof r.screen === "string" ? screenLines(r.screen) : current[i].screen,
      prompt: typeof r.prompt === "string" ? screenLines(r.prompt) : current[i].prompt,
      say: oneLine(r.say!),
      speak: oneLine(r.speak!),
      same: r.same === true,
    };
    if (!TIME_RE.test(row.time)) return `${row.n}번 줄 시각 형식은 m:ss.s 예요`;
    if (!row.say) return `${row.n}번 줄 자막·대본이 비었어요`;
    if (!row.same && !row.speak) return `${row.n}번 줄 읽는 말이 비었어요`;
    if (row.same) row.speak = "";
    rows.push(row);
  }
  return rows;
}
