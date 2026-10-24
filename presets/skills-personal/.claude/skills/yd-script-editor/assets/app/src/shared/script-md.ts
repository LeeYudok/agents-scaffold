// 내레이션 대본 md(머리말 + 대본 표)를 구조로 읽고 되돌린다.
// 표는 두 모양이다:
//   5칸 `| # | 시각 | 장면 | 자막·대본 | 읽는 말 |`
//   6칸 `| # | 시각 | 장면 | 화면 자막 | 자막·대본 | 읽는 말 |` — 화면 자막은 영상에 박히는 글, 줄은 ` <br> ` 로 구분
// 맨 끝에 `AI 프롬프트` 칸이 붙을 수 있다 — 장면마다 영상 제작 AI 에게 주는 연출 지시(줄은 ` <br> `).
//   이 칸이 없는 대본은 그대로 두고, 어느 줄이든 프롬프트를 쓰면 저장할 때 칸을 붙인다.
// 표 밖의 글은 그대로 보존한다 — parse → serialize 가 바이트 단위로 같아야 한다(script-md.test.ts).

export const SAME = "(자막과 같음)";

export type Row = {
  n: string;
  time: string;
  scene: string;
  screen: string; // 화면 자막(여러 줄은 \n). 5칸 표면 빈 문자열
  prompt: string; // AI 프롬프트(여러 줄은 \n). 칸이 없으면 빈 문자열
  say: string;
  speak: string;
  same: boolean;
};

export type Doc = {
  before: string;
  head: string;
  sep: string;
  rows: Row[];
  after: string;
  hasScreen: boolean;
  hasPrompt: boolean;
};

export const PROMPT_HEAD = "AI 프롬프트";

export const TIME_RE = /^\d+:\d{2}(\.\d)?$/;
const BR_RE = /\s*<br\s*\/?>\s*/gi;

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split(/(?<!\\)\|/)
    .map((c) => c.trim().replace(/\\\|/g, "|"));

const esc = (s: string) => s.replace(/\|/g, "\\|");

export const oneLine = (s: string) => s.replace(/\s*\r?\n\s*/g, " ").trim();
/** 화면 자막 칸 정리: 줄마다 다듬고 빈 줄은 뺀다 */
export const screenLines = (s: string) =>
  s
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean)
    .join("\n");

export function parse(text: string): Doc {
  const lines = text.split("\n");
  const h = lines.findIndex((l) => /^\|\s*#\s*\|/.test(l));
  if (h < 0 || !/^\|[-\s|:]+\|$/.test(lines[h + 1] ?? "")) {
    throw new Error("대본 표(| # | 시각 | … |)를 찾지 못했어요");
  }
  const headCells = cells(lines[h]);
  const hasPrompt = headCells[headCells.length - 1] === PROMPT_HEAD;
  const width = headCells.length;
  const hasScreen = width - (hasPrompt ? 1 : 0) === 6;
  const rows: Row[] = [];
  let i = h + 2;
  for (; i < lines.length && lines[i].startsWith("|"); i++) {
    const c = cells(lines[i]);
    if (c.length !== width) throw new Error(`${i + 1}번째 줄의 칸 수가 표 머리줄과 달라요`);
    const prompt = hasPrompt ? c.pop()! : "";
    const [n, time, scene, ...rest] = c;
    const [screen, say, speak] = hasScreen ? rest : ["", ...rest];
    const same = speak === SAME;
    rows.push({
      n, time, scene, screen: screen.split(BR_RE).join("\n"), say, speak: same ? "" : speak, same,
      prompt: prompt.split(BR_RE).join("\n"),
    });
  }
  return {
    before: lines.slice(0, h).join("\n").replace(/\n+$/, ""),
    head: lines[h],
    sep: lines[h + 1],
    rows,
    after: lines.slice(i).join("\n"),
    hasScreen,
    hasPrompt,
  };
}

const brJoin = (s: string) => esc(screenLines(s).split("\n").join(" <br> "));

export function serialize(d: Doc): string {
  // 프롬프트를 처음 쓴 대본이면 머리줄·구분줄에 칸을 붙인다
  const withPrompt = d.hasPrompt || d.rows.some((r) => screenLines(r.prompt ?? ""));
  const head = withPrompt && !d.hasPrompt ? `${d.head} ${PROMPT_HEAD} |` : d.head;
  const sep = withPrompt && !d.hasPrompt ? `${d.sep}---|` : d.sep;
  const body = d.rows.map((r) => {
    const screen = d.hasScreen ? ` ${brJoin(r.screen)} |` : "";
    const prompt = withPrompt ? ` ${brJoin(r.prompt ?? "")} |` : "";
    return `| ${r.n} | ${r.time} | ${esc(r.scene)} |${screen} ${esc(r.say)} | ${esc(r.same ? SAME : r.speak)} |${prompt}`;
  });
  return `${d.before.replace(/\n+$/, "")}\n\n${head}\n${sep}\n${body.join("\n")}\n${d.after}`;
}
