// 청사진 데이터(JSONL) 스키마와 파서. 화면(Vite)과 검사기(sh scripts/check.sh)가 같은 코드를 쓴다.
// 파일 순서 = 표시 순서. 줄마다 JSON 한 개, kind 로 종류를 구분한다.

export type State = "done" | "partial" | "missing";
export type Priority = "P0" | "P1" | "P2";
// flow = 동작하는 흐름(실선), write = 쓰기 경로, boundary = 경계·미연결(점선).
export type EdgeType = "flow" | "write" | "boundary";
// grid = 열(lane)·행(row) 격자와 화살표, tiers = lane 을 위아래 가로 띠로 쌓고 띠 사이를 한 줄 문구로 잇는다.
export type Layout = "grid" | "tiers";

export interface Meta {
  kind: "meta";
  title: string;
  eyebrow?: string;
  summary?: string;
  badges?: string[];
  links?: { label: string; href: string }[];
  basis?: string;
  layout?: Layout;
  asOf: string;
}
export interface Lane {
  kind: "lane";
  id: string;
  title: string;
  toNext?: string; // tiers 에서 이 띠와 다음 띠 사이의 연결(예: HTTPS / REST)
}
export interface Node {
  kind: "node";
  id: string;
  lane: string;
  row: number;
  title: string;
  lines?: string[];
  tags?: string[]; // 기술명·런타임만(예: Go, PostgreSQL). 역할은 lines 에 쓴다
  state: State;
  summary: string;
  paths?: string[];
  next?: string;
  gap?: string;
}
export interface Edge {
  kind: "edge";
  from: string;
  to: string;
  label?: string;
  type?: EdgeType;
}
// 노드 몇 개를 점선 경계 상자로 묶는다(한 호스트, 한 pod 같은 배포 경계).
export interface Group {
  kind: "group";
  id: string;
  title: string;
  nodes: string[];
}
export interface Step {
  kind: "flow";
  title: string;
  body: string;
}
export interface Feature {
  kind: "feature";
  name: string;
  state: State;
  now: string;
  remaining: string;
}
export interface Gap {
  kind: "gap";
  id: string;
  priority: Priority;
  title: string;
  state: State;
  now: string;
  todo: string;
  done: string;
  paths?: string[];
}
export interface Doc {
  kind: "doc";
  id: string;
  title: string;
  paragraphs: string[];
}
export interface Blueprint {
  meta: Meta;
  lanes: Lane[];
  nodes: Node[];
  edges: Edge[];
  groups: Group[];
  flow: Step[];
  features: Feature[];
  gaps: Gap[];
  docs: Doc[];
}
export interface Parsed {
  blueprint: Blueprint | null;
  errors: string[];
}
export interface Source {
  name: string;
  text: string;
}

type Field = { t: "s" | "i" | "a" | "e" | "l"; opt: boolean; values?: readonly string[] };
const s = (opt = false): Field => ({ t: "s", opt });
const i = (): Field => ({ t: "i", opt: false });
const a = (opt = false): Field => ({ t: "a", opt });
const l = (opt = false): Field => ({ t: "l", opt });
const e = (values: readonly string[], opt = false): Field => ({
  t: "e",
  opt,
  values,
});
const STATES = ["done", "partial", "missing"] as const;

const SPECS: Record<string, Record<string, Field>> = {
  meta: { title: s(), eyebrow: s(true), summary: s(true), badges: a(true), links: l(true), basis: s(true), layout: e(["grid", "tiers"], true), asOf: s() },
  lane: { id: s(), title: s(), toNext: s(true) },
  node: {
    id: s(),
    lane: s(),
    row: i(),
    title: s(),
    lines: a(true),
    tags: a(true),
    state: e(STATES),
    summary: s(),
    paths: a(true),
    next: s(true),
    gap: s(true),
  },
  edge: { from: s(), to: s(), label: s(true), type: e(["flow", "write", "boundary"], true) },
  group: { id: s(), title: s(), nodes: a() },
  flow: { title: s(), body: s() },
  feature: { name: s(), state: e(STATES), now: s(), remaining: s() },
  gap: {
    id: s(),
    priority: e(["P0", "P1", "P2"]),
    title: s(),
    state: e(STATES),
    now: s(),
    todo: s(),
    done: s(),
    paths: a(true),
  },
  doc: { id: s(), title: s(), paragraphs: a() },
};

function checkField(key: string, value: unknown, field: Field): string | null {
  if (value === undefined) return field.opt ? null : `'${key}' 가 없습니다`;
  if (field.t === "s")
    return typeof value === "string" && value.trim()
      ? null
      : `'${key}' 는 비어 있지 않은 문자열이어야 합니다`;
  if (field.t === "i")
    return Number.isInteger(value) && (value as number) >= 0
      ? null
      : `'${key}' 는 0 이상의 정수여야 합니다`;
  if (field.t === "a")
    return Array.isArray(value) &&
      value.length > 0 &&
      value.every((item) => typeof item === "string" && item.trim())
      ? null
      : `'${key}' 는 비어 있지 않은 문자열 배열이어야 합니다`;
  if (field.t === "l")
    return Array.isArray(value) &&
      value.length > 0 &&
      value.every(
        (item) =>
          typeof item === "object" &&
          item !== null &&
          typeof item.label === "string" &&
          item.label.trim() &&
          typeof item.href === "string" &&
          /^(\/|#|https?:\/\/)/.test(item.href),
      )
      ? null
      : `'${key}' 는 {label, href} 배열이어야 하고 href 는 / # http(s):// 로 시작해야 합니다`;
  return typeof value === "string" && field.values?.includes(value)
    ? null
    : `'${key}' 는 ${field.values?.join("·")} 중 하나여야 합니다`;
}

function validate(kind: string, obj: Record<string, unknown>): string[] {
  const spec = SPECS[kind];
  const problems: string[] = [];
  for (const key of Object.keys(obj))
    if (key !== "kind" && !(key in spec))
      problems.push(`알 수 없는 필드 '${key}' (${kind})`);
  for (const [key, field] of Object.entries(spec)) {
    const problem = checkField(key, obj[key], field);
    if (problem) problems.push(`${problem} (${kind})`);
  }
  return problems;
}

function duplicates(values: string[]): string[] {
  return values.filter((value, index) => values.indexOf(value) !== index);
}

export function parseBlueprint(sources: Source[]): Parsed {
  const errors: string[] = [];
  const records: { at: string; value: Record<string, unknown> & { kind: string } }[] = [];
  for (const source of [...sources].sort((x, y) => x.name.localeCompare(y.name))) {
    source.text.split("\n").forEach((line, index) => {
      if (!line.trim()) return;
      const at = `${source.name}:${index + 1}`;
      let value: unknown;
      try {
        value = JSON.parse(line);
      } catch (error) {
        errors.push(`${at}: JSON 문법 오류 — ${(error as Error).message}`);
        return;
      }
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        errors.push(`${at}: 한 줄은 JSON 객체 하나여야 합니다`);
        return;
      }
      const record = value as Record<string, unknown>;
      const kind = typeof record.kind === "string" ? record.kind : "";
      if (!(kind in SPECS)) {
        errors.push(`${at}: kind 는 ${Object.keys(SPECS).join("·")} 중 하나여야 합니다`);
        return;
      }
      const problems = validate(kind, record);
      for (const problem of problems) errors.push(`${at}: ${problem}`);
      if (!problems.length) records.push({ at, value: record as never });
    });
  }
  const of = <T,>(kind: string) =>
    records.filter((r) => r.value.kind === kind).map((r) => r.value as unknown as T);
  const metas = of<Meta>("meta");
  const lanes = of<Lane>("lane");
  const nodes = of<Node>("node");
  const edges = of<Edge>("edge");
  const groups = of<Group>("group");
  const gaps = of<Gap>("gap");
  const docs = of<Doc>("doc");
  if (metas.length !== 1) errors.push(`meta 줄은 정확히 하나여야 합니다 (현재 ${metas.length}개)`);
  else if (
    !/^\d{4}-\d{2}-\d{2}$/.test(metas[0].asOf) ||
    Number.isNaN(Date.parse(metas[0].asOf))
  )
    errors.push(`meta.asOf 는 실제 날짜 YYYY-MM-DD 여야 합니다 — ${metas[0].asOf}`);
  for (const [label, ids] of [
    ["lane", lanes.map((x) => x.id)],
    ["node", nodes.map((x) => x.id)],
    ["group", groups.map((x) => x.id)],
    ["gap", gaps.map((x) => x.id)],
    ["doc", docs.map((x) => x.id)],
  ] as const)
    for (const id of duplicates([...ids])) errors.push(`${label} id 가 겹칩니다 — ${id}`);
  const laneIds = new Set(lanes.map((x) => x.id));
  const nodeIds = new Set(nodes.map((x) => x.id));
  const gapIds = new Set(gaps.map((x) => x.id));
  const cells = new Set<string>();
  for (const node of nodes) {
    if (!laneIds.has(node.lane)) errors.push(`node ${node.id}: 없는 lane '${node.lane}'`);
    if (node.gap && !gapIds.has(node.gap)) errors.push(`node ${node.id}: 없는 gap '${node.gap}'`);
    const cell = `${node.lane}/${node.row}`;
    if (cells.has(cell)) errors.push(`node ${node.id}: lane '${node.lane}' 의 row ${node.row} 에 이미 노드가 있습니다`);
    cells.add(cell);
  }
  for (const edge of edges) {
    if (!nodeIds.has(edge.from)) errors.push(`edge: 없는 from '${edge.from}'`);
    if (!nodeIds.has(edge.to)) errors.push(`edge: 없는 to '${edge.to}'`);
  }
  for (const group of groups)
    for (const id of group.nodes)
      if (!nodeIds.has(id)) errors.push(`group ${group.id}: 없는 node '${id}'`);
  for (const node of nodes)
    if (node.tags && node.tags.length > 3) errors.push(`node ${node.id}: tags 는 3개까지입니다`);
  const tiers = metas[0]?.layout === "tiers";
  lanes.forEach((lane, index) => {
    if (!lane.toNext) return;
    if (!tiers) errors.push(`lane ${lane.id}: toNext 는 meta.layout 이 tiers 일 때만 씁니다`);
    else if (index === lanes.length - 1) errors.push(`lane ${lane.id}: 마지막 띠에는 toNext 를 쓰지 않습니다`);
  });
  if (tiers) {
    // 띠 모드는 화살표를 그리지 않는다. 적힌 관계가 화면에서 조용히 사라지지 않게 오류로 막는다.
    if (edges.length) errors.push(`tiers 에서는 edge 를 쓸 수 없습니다(${edges.length}개) — 띠 사이 연결은 lane.toNext 로 적습니다`);
    for (const group of groups) {
      const members = nodes.filter((n) => group.nodes.includes(n.id));
      const laneSet = new Set(members.map((n) => n.lane));
      if (laneSet.size > 1) {
        errors.push(`group ${group.id}: tiers 에서는 한 띠 안의 노드만 묶습니다`);
        continue;
      }
      const order = nodes.filter((n) => laneSet.has(n.lane)).sort((x, y) => x.row - y.row).map((n) => n.id);
      const at = members.map((n) => order.indexOf(n.id)).sort((x, y) => x - y);
      if (at.length && at[at.length - 1] - at[0] + 1 !== at.length)
        errors.push(`group ${group.id}: tiers 에서는 이웃한 노드만 묶습니다(사이에 다른 노드가 있습니다)`);
    }
  }
  if (errors.length) return { blueprint: null, errors };
  return {
    errors,
    blueprint: {
      meta: metas[0],
      lanes,
      nodes,
      edges,
      groups,
      flow: of<Step>("flow"),
      features: of<Feature>("feature"),
      gaps,
      docs,
    },
  };
}

// 근거 코드 경로 검사용: 어느 항목이 어떤 경로를 주장하는지.
export function claimedPaths(bp: Blueprint): { owner: string; path: string }[] {
  return [
    ...bp.nodes.flatMap((n) => (n.paths || []).map((path) => ({ owner: `node ${n.id}`, path }))),
    ...bp.gaps.flatMap((g) => (g.paths || []).map((path) => ({ owner: `gap ${g.id}`, path }))),
  ];
}

// 맨 위 요약 타일용 집계. 남은 작업은 완료(done)가 아닌 것만 센다.
export function summarize(bp: Blueprint) {
  const states = { done: 0, partial: 0, missing: 0 } as Record<State, number>;
  for (const node of bp.nodes) states[node.state] += 1;
  const open = { P0: 0, P1: 0, P2: 0 } as Record<Priority, number>;
  for (const gap of bp.gaps) if (gap.state !== "done") open[gap.priority] += 1;
  return { states, open };
}

// 문장 길이 점검용: 사람이 읽는 긴 글 칸. 도면 줄(lines)·제목은 상자 폭 검사가 따로 본다.
export function proseFields(bp: Blueprint): { owner: string; text: string }[] {
  const out: { owner: string; text: string }[] = [];
  const add = (owner: string, text?: string) => text && out.push({ owner, text });
  add("meta.summary", bp.meta.summary);
  add("meta.basis", bp.meta.basis);
  for (const n of bp.nodes) {
    add(`node ${n.id}.summary`, n.summary);
    add(`node ${n.id}.next`, n.next);
  }
  bp.flow.forEach((step, index) => add(`flow[${index}].body`, step.body));
  for (const f of bp.features) {
    add(`feature ${f.name}.now`, f.now);
    add(`feature ${f.name}.remaining`, f.remaining);
  }
  for (const g of bp.gaps) for (const key of ["now", "todo", "done"] as const) add(`gap ${g.id}.${key}`, g[key]);
  for (const d of bp.docs) d.paragraphs.forEach((text, index) => add(`doc ${d.id}[${index}]`, text));
  return out;
}
