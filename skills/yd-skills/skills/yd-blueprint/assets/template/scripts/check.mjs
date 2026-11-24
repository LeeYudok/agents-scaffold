// 청사진 JSONL 검사: 스키마·참조 + 근거 코드 경로가 실제로 있는지 + 기준일이 낡았는지.
//   sh scripts/check.sh [--no-paths] [--repo-root <dir>] [--stale-days 60]
// bun 이든 node 든 같은 파일이 돈다(package.json 의 check 가 sh scripts/check.sh 를 부른다).
// 경로는 저장소 루트 기준이다. 오류가 있으면 exit 1, 경고만 있으면 exit 0.
import { execSync, spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// src/blueprint.ts 를 그대로 읽는다. bun 은 바로 읽고, node 는 22.18/23.6 부터 기본이며
// 22.6~22.17 은 --experimental-strip-types 가 필요하다. 그보다 낮은 node 는 쓸 수 없다.
const self = fileURLToPath(import.meta.url);
const canStrip = Boolean(process.versions.bun) || Boolean(process.features?.typescript);
if (!canStrip && !process.execArgv.includes("--experimental-strip-types")) {
  const again = spawnSync(
    process.execPath,
    ["--experimental-strip-types", "--no-warnings", self, ...process.argv.slice(2)],
    { stdio: "inherit" },
  );
  if (again.status === 9) console.error("[FAIL] node 22.6 이상 또는 bun 이 필요합니다");
  process.exit(again.status ?? 1);
}
const { claimedPaths, parseBlueprint, proseFields } = await import("../src/blueprint.ts");


const here = resolve(dirname(self), "..");
const args = process.argv.slice(2);
const option = (name, fallback) => {
  const at = args.indexOf(name);
  return at >= 0 && args[at + 1] ? args[at + 1] : fallback;
};
const dataDir = join(here, "data");
const sources = readdirSync(dataDir)
  .filter((name) => name.endsWith(".jsonl"))
  .map((name) => ({ name: `data/${name}`, text: readFileSync(join(dataDir, name), "utf8") }));
if (!sources.length) {
  console.error("[FAIL] data/*.jsonl 이 없습니다");
  process.exit(1);
}
const { blueprint, errors } = parseBlueprint(sources);
const warnings = [];
if (blueprint) {
  if (!args.includes("--no-paths")) {
    let root = option("--repo-root", "");
    if (!root) {
      try {
        root = execSync("git rev-parse --show-toplevel", { cwd: here, stdio: ["ignore", "pipe", "ignore"] })
          .toString()
          .trim();
      } catch {
        errors.push("저장소 루트를 찾지 못했습니다 — --repo-root <dir> 또는 --no-paths");
      }
    }
    if (root)
      for (const { owner, path } of claimedPaths(blueprint))
        if (!existsSync(join(root, path))) errors.push(`${owner}: 없는 경로 '${path}' (저장소 루트 ${root} 기준)`);
  }
  const days = Math.floor((Date.now() - Date.parse(blueprint.meta.asOf)) / 86_400_000);
  const stale = Number(option("--stale-days", "60"));
  if (days > stale) warnings.push(`기준일 ${blueprint.meta.asOf} 이 ${days}일 지났습니다 — 코드와 다시 맞춰 보세요`);
  // 상자 폭 추정: 한글·CJK 는 1em, 그 밖은 0.55em. 상자 안쪽 폭은 248px.
  const width = (text, size) =>
    [...text].reduce((sum, ch) => sum + (/[ᄀ-ᇿ㄰-㆏가-힯一-鿿]/.test(ch) ? size : size * 0.55), 0);
  for (const node of blueprint.nodes) {
    if (width(node.title, 15) > 248) warnings.push(`node ${node.id}: title 이 상자 폭을 넘을 수 있습니다`);
    (node.lines || []).forEach((line, index) => {
      if (width(line, 13) > 248) warnings.push(`node ${node.id}: lines[${index}] 가 상자 폭을 넘을 수 있습니다`);
    });
  }
  // 상자를 붐비게 하지 않는다: 기술 태그는 짧게, 줄은 태그까지 3줄 안에서.
  for (const node of blueprint.nodes) {
    for (const tag of node.tags || [])
      if (tag.length > 18) warnings.push(`node ${node.id}: tag '${tag}' 가 18자를 넘습니다`);
    const shown = (node.lines || []).length + (node.tags?.length ? 1 : 0);
    if (shown > 3) warnings.push(`node ${node.id}: lines 와 tags 를 합쳐 ${shown}줄입니다 — 3줄 안으로 줄이세요`);
  }
  if (blueprint.meta.layout === "tiers")
    for (const lane of blueprint.lanes) {
      const count = blueprint.nodes.filter((n) => n.lane === lane.id).length;
      if (count > 6) warnings.push(`lane ${lane.id}: 띠 하나에 노드 ${count}개 — 6개를 넘으면 띠를 나누세요`);
      if (lane.toNext && lane.toNext.length > 30) warnings.push(`lane ${lane.id}: toNext 가 30자를 넘습니다`);
    }
  // 한눈에 읽히게: 문장은 60자, 한 칸은 120자를 넘기면 경고한다. 긴 설명은 문서로 보내고 링크한다.
  const sentenceMax = Number(option("--sentence-max", "60"));
  const fieldMax = Number(option("--field-max", "120"));
  for (const { owner, text } of proseFields(blueprint)) {
    if (text.length > fieldMax) warnings.push(`${owner}: ${text.length}자 — ${fieldMax}자 안으로 줄이세요`);
    for (const sentence of text.split(/(?<=[.!?])\s+/)) {
      const body = sentence.replace(/[.!?]+$/, "");
      if (body.length > sentenceMax)
        warnings.push(`${owner}: 문장 ${body.length}자 — ${sentenceMax}자 안으로 나누세요 「${body.slice(0, 24)}…」`);
    }
  }
}
for (const warning of warnings) console.warn(`[WARN] ${warning}`);
if (errors.length) {
  for (const error of errors) console.error(`[FAIL] ${error}`);
  process.exit(1);
}
console.log(
  `[OK] 청사진 ${blueprint.nodes.length}노드 · ${blueprint.edges.length}엣지 · ${blueprint.features.length}현황 · ${blueprint.gaps.length}작업 (기준 ${blueprint.meta.asOf})`,
);
