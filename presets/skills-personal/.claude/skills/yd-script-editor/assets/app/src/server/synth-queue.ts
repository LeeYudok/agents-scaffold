// 대본을 저장하면 바뀐 줄만 음성을 다시 합성하는 큐. 대본 옆에 <이름>.json(합성 입력)이 있을 때만 동작한다.
// 한 번에 synth.py 하나만 돌린다.
import { spawn } from "node:child_process";
import { access, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { Row } from "../shared/script-md.ts";

type Line = { id: string; start: number; max: number; say: string; speak?: string };
type Job = { label: string; n: number };

export type SynthStatus = { running: Job[]; queued: Job[]; last: string; error: string; doneAt: number };

export function createSynthQueue(contentDir: string, python: string, script: string, labelOf: (name: string) => string) {
  const queue = new Map<string, Set<number>>(); // 대본 이름(확장자 없이) → 줄 번호
  const status: SynthStatus = { running: [], queued: [], last: "", error: "", doneAt: 0 };
  let busy = false;

  const jobs = (m: Map<string, Set<number>>) =>
    [...m].flatMap(([name, nums]) => [...nums].sort((a, b) => a - b).map((n) => ({ label: labelOf(name), n })));

  /** md 표를 합성 입력 JSON 에 반영하고, 읽는 문장이 바뀐 줄 번호를 돌려준다 */
  async function syncJson(name: string, rows: Row[]): Promise<number[]> {
    const path = join(contentDir, `${name}.json`);
    if (!(await access(path).then(() => true, () => false))) return [];
    const doc = JSON.parse(await readFile(path, "utf8")) as { lines: Line[] };
    const changed: number[] = [];
    rows.forEach((r, i) => {
      const line = doc.lines[i];
      if (!line) return;
      const speak = r.same ? undefined : r.speak;
      if (line.say === r.say && line.speak === speak) return;
      const before = line.speak ?? line.say;
      line.say = r.say;
      if (speak === undefined) delete line.speak;
      else line.speak = speak;
      if ((line.speak ?? line.say) !== before) changed.push(i + 1);
    });
    await writeFile(path, `${JSON.stringify(doc, null, 2)}\n`);
    return changed;
  }

  function run(name: string, nums: number[]): Promise<{ code: number; out: string; err: string }> {
    return new Promise((resolve) => {
      const p = spawn(python, [script, ...nums.map(String), "--script", name], { env: { ...process.env, EDITOR_CONTENT: contentDir } });
      let out = "";
      let err = "";
      p.stdout.on("data", (d) => (out += d));
      p.stderr.on("data", (d) => (err += d));
      p.on("error", (e) => resolve({ code: 1, out, err: `${err}\n${e.message}` }));
      p.on("close", (code) => resolve({ code: code ?? 1, out, err }));
    });
  }

  async function pump() {
    if (busy || !queue.size) return;
    busy = true;
    const [name, set] = [...queue][0];
    queue.delete(name);
    const nums = [...set].sort((a, b) => a - b);
    status.running = nums.map((n) => ({ label: labelOf(name), n }));
    const { code, out, err } = await run(name, nums);
    status.last = out.split("\n").filter((l) => /^\d{2} /.test(l)).join("\n");
    status.error = code ? err.split("\n").filter(Boolean).slice(-3).join("\n") : "";
    status.running = [];
    status.doneAt = Date.now();
    busy = false;
    void pump();
  }

  return {
    status: (): SynthStatus => ({ ...status, queued: jobs(queue) }),
    /** 대본 저장 뒤 호출: JSON 을 맞추고 바뀐 줄을 큐에 넣는다 */
    async onSaved(mdName: string, rows: Row[]) {
      const name = mdName.replace(/\.md$/, "");
      const changed = await syncJson(name, rows);
      if (changed.length) {
        const set = queue.get(name) ?? new Set<number>();
        changed.forEach((n) => set.add(n));
        queue.set(name, set);
        void pump();
      }
      return changed;
    },
  };
}
